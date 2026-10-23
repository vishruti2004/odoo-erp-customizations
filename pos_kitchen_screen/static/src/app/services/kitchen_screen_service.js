import { patch } from "@web/core/utils/patch";
import { reactive } from "@odoo/owl";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { PrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import {
    KitchenSelectDialog,
    KitchenChefDialog,
    KitchenInfoDialog,
    KitchenReprepareDialog,
} from "@pos_kitchen_screen/app/components/kitchen_dialogs";

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const FORWARD_STAGES = ["ready", "done"];
const WORKING_STAGES = ["todo", "in_progress"];

function isKitchenRuleError(error) {
    return Boolean(error?.data?.name?.endsWith(".KitchenRuleError"));
}
function countsForKitchen(state) {
    const line = state.prep_line_id;
    return line.quantity - (line.cancelled || 0) > 0 && !line.combo_line_ids?.length;
}

patch(PrepDisplay.prototype, {
    async setup() {
        this.kitchen = reactive({
            chef: null,
            workload: [],
            chefFilter: "all",
            priorityFilter: "all",
            stationFilter: [],
            now: Date.now(),
        });
        await super.setup(...arguments);
        this.overloadAlerts = new Map();
        this.refreshWorkload = debounce(() => this.loadWorkload(), 800);
        this.restoreChef();
        this.registerKitchenHandlers();
        this.startKitchenTimers();
        this.loadWorkload();
    },

    get kitchenDisplay() {
        return this.data.models["pos.prep.display"].getFirst();
    },
    get kitchenAdvanced() {
        return Boolean(this.kitchenDisplay?.kitchen_advanced);
    },
    get ownStations() {
        return this.data.models["pos.kitchen.station"].filter(
            (station) => station.display_id_int === this.id
        );
    },
    get chefs() {
        const ownIds = this.ownStations.map((s) => s.id);
        return this.data.models["pos.kitchen.chef"].filter((chef) => {
            const allowed = chef.allowed_station_ids || [];
            return !allowed.length || allowed.some((id) => ownIds.includes(id));
        });
    },
    get actorChefId() {
        return this.kitchen.chef?.id || false;
    },

    restoreChef() {
        try {
            const id = parseInt(localStorage.getItem(`kitchen_chef_${this.id}`));
            const chef = id && this.data.models["pos.kitchen.chef"].get(id);
            if (chef) {
                this.kitchen.chef = this.chefSnapshot(chef);
            }
        } catch {
        }
    },
    chefSnapshot(chef) {
        return {
            id: chef.id,
            name: chef.name,
        };
    },
    async loadChefsOnShift(chefs) {
        const ids = await this.kitchenCall("pos.kitchen.chef", "get_chefs_on_shift", [
            chefs.map((c) => c.id),
        ]);
        return new Set(ids || []);
    },
    async openChefLogin() {
        if (!this.kitchenAdvanced) {
            return;
        }
        const onShift = await this.loadChefsOnShift(this.chefs);
        this.dialog.add(KitchenChefDialog, {
            chefs: this.chefs
                .filter((c) => onShift.has(c.id))
                .map((c) => ({ id: c.id, name: c.name })),
            current: this.kitchen.chef,
            login: (chefId) => this.loginChef(chefId),
            logout: () => this.logoutChef(),
        });
    },
    loginChef(chefId) {
        const chef = this.data.models["pos.kitchen.chef"].get(chefId);
        if (!chef) {
            return;
        }
        this.kitchen.chef = this.chefSnapshot(chef);
        try {
            localStorage.setItem(`kitchen_chef_${this.id}`, chef.id);
        } catch {
        }
    },
    logoutChef() {
        this.kitchen.chef = null;
        try {
            localStorage.removeItem(`kitchen_chef_${this.id}`);
        } catch {
        }
        if (this.kitchen.chefFilter === "mine") {
            this.kitchen.chefFilter = "all";
        }
    },
    startKitchenTimers() {
        setInterval(() => {
            this.kitchen.now = Date.now();
        }, 15000);
    },

    //  bus
    registerKitchenHandlers() {
        const models = this.data.models;
        this.onNotified("PRIORITY_CHANGED", (data) => {
            for (const id of data.prep_order_ids) {
                const order = models["pos.prep.order"].get(id);
                if (order) {
                    order.priority = data.priority;
                    order.priority_updated_at = data.updated_at;
                }
            }
        });
        this.onNotified("CHEF_ASSIGNED", (data) => {
            for (const [lineId, chefId] of Object.entries(data.assignments)) {
                const line = models["pos.prep.line"].get(parseInt(lineId));
                if (line) {
                    line.assigned_chef_id = chefId ? models["pos.kitchen.chef"].get(chefId) : false;
                }
            }
        });
        this.onNotified("STATION_REASSIGNED", (data) => {
            for (const id of data.state_ids) {
                const state = models["pos.prep.state"].get(id);
                if (state) {
                    state.delete();
                }
            }
            this.computeOrderCounts();
        });
        this.onNotified("KITCHEN_LINE_CHANGES", (lines) => {
            for (const values of lines) {
                const line = models["pos.prep.line"].get(values.id);
                if (line) {
                    line.change_pending = values.change_pending;
                    line.last_change_type = values.last_change_type;
                    line.change_text = values.change_text;
                }
            }
        });
        this.onNotified("KITCHEN_READINESS_CHANGED", (data) => {
            const order = models["pos.order"].get(data.order_id);
            if (order) {
                order.kitchen_readiness = data.readiness;
                order.kitchen_station_status = data.status;
            }
        });
        this.onNotified("KITCHEN_ORDER_READY", (data) => {
            if (this.kitchenAdvanced) {
                this.notification.add(_t("Order %s is ready at all stations.", data.name || ""), {
                    type: "success",
                });
                this.ringTheBell();
            }
        });
        this.onNotified("ITEM_CHANGED", (data) => {
            this.notification.add(_t("Order %(order)s updated: %(product)s. %(text)s.", {
                order: data.order,
                product: data.product,
                text: data.text,
            }), {
                type: "warning",
            });
            this.ringTheBell();
        });
        this.onNotified("OVERLOAD_UNRESOLVED", (data) => {
            this.showOverloadAlert(`u${data.id}`, 
                _t("%(station)s is over capacity by %(excess)s %(unit)s and no other station can take the work. Please inform your supervisor.", {
                    station: data.station,
                    excess: data.excess,
                    unit: data.unit === "min" ? _t("min") : _t("items"),
                })
            );
        });
        this.onNotified("KITCHEN_WARNING", (data) => {
            this.notification.add(data.message, { type: "warning" });
        });
        this.onNotified("WORKLOAD_CHANGED", () => this.refreshWorkload());
        this.onNotified("LOAD_ORDERS", () => this.refreshWorkload());
    },

    async kitchenCall(model, method, args) {
        try {
            return await this.orm.call(model, method, args, {});
        } catch (error) {
            const message =
                error?.data?.message || error?.message || _t("The action could not be completed.");
            this.notification.add(message, {
                type: isKitchenRuleError(error) ? "warning" : "danger",
            });
            return null;
        }
    },

    async loadWorkload() {
        if (!this.kitchenAdvanced) {
            return;
        }
        const result = await this.kitchenCall("pos.kitchen.station", "get_station_workload", [
            this.id,
        ]);
        if (result) {
            this.alertOverflow(result);
            this.kitchen.workload = result;
        }
    },
    showOverloadAlert(key, message) {
        this.overloadAlerts.get(key)?.close();
        const close = this.notification.add(message, { type: "danger", sticky: true });
        this.overloadAlerts.set(key, { close });
        this.ringTheBell();
    },
    closeOverloadAlerts(stationId) {
        for (const key of [stationId, `u${stationId}`]) {
            this.overloadAlerts.get(key)?.close();
            this.overloadAlerts.delete(key);
        }
    },
    alertOverflow(current) {
        const ownIds = this.ownStations.map((s) => s.id);
        for (const entry of current) {
            if (!ownIds.includes(entry.id)) {
                continue;
            }
            const shown = this.overloadAlerts.get(entry.id);
            if (!entry.overloaded) {
                this.closeOverloadAlerts(entry.id);
                continue;
            }
            const signature = `${entry.overflow_orders}/${entry.excess}`;
            if (shown?.signature !== signature) {
                this.showOverloadAlert(
                    entry.id,
                    _t("%(station)s is over capacity by %(excess)s %(unit)s. Please move items to another station.", {
                        station: entry.name,
                        excess: entry.excess,
                        unit: entry.metric === "time" ? _t("min") : _t("items"),
                    })
                );
                this.overloadAlerts.get(entry.id).signature = signature;
            }
        }
    },
    get workloadView() {
        const ownIds = this.ownStations.map((s) => s.id);
        const own = this.kitchen.workload.filter((w) => ownIds.includes(w.id));
        const altIds = new Set(own.flatMap((w) => w.alternatives));
        const alt = this.kitchen.workload.filter((w) => altIds.has(w.id) && !ownIds.includes(w.id));
        return [...own, ...alt].map((w) => ({
            ...w,
            percent: w.limit ? Math.min(100, Math.round((w.value / w.limit) * 100)) : 0,
            isOwn: ownIds.includes(w.id),
            unit: w.metric === "time" ? _t("min") : _t("items"),
        }));
    },
    get reassignTargets() {
        return this.workloadView.filter((w) => !w.isOwn);
    },
    isOverflowOrder(posOrderId) {
        if (!this.kitchenAdvanced || !posOrderId) {
            return false;
        }
        const ownIds = this.ownStations.map((s) => s.id);
        return this.kitchen.workload.some(
            (w) => ownIds.includes(w.id) && w.overflow_order_ids.includes(posOrderId)
        );
    },
    async openOverflowMenu(entry) {
        const plan = await this.kitchenCall("pos.kitchen.station", "plan_overload", [[entry.id]]);
        if (!plan) {
            return;
        }
        const unit = plan.unit === "min" ? _t("min") : _t("items");
        if (!plan.destination) {
            this.showOverloadAlert(
                `u${entry.id}`,
                _t("%(station)s is over capacity by %(excess)s %(unit)s. %(reason)s Please inform your supervisor.", {
                    station: entry.name,
                    excess: plan.excess,
                    unit,
                    reason: plan.reason || "",
                })
            );
            return;
        }
        this.dialog.add(KitchenInfoDialog, {
            title: _t("%(station)s is over capacity by %(excess)s %(unit)s", {
                station: entry.name,
                excess: plan.excess,
                unit,
            }),
            intro: _t("The following items will move to %(dest)s (%(free)s):", {
                dest: plan.destination.name,
                free:
                    plan.destination.free === null
                        ? _t("no limit")
                        : _t("%(free)s %(unit)s available", { free: plan.destination.free, unit }),
            }),
            rows: plan.lines.map((l) => ({
                label: `${l.qty} x ${l.product}`,
                sub: `${l.load} ${unit}, ${_t("order")} ${l.order}`,
            })),
            summary: plan.exact
                ? _t("This removes the excess exactly (%(moved)s %(unit)s).", { moved: plan.moved, unit })
                : _t("This moves %(moved)s of the %(excess)s %(unit)s.", {
                      moved: plan.moved,
                      excess: plan.excess,
                      unit,
                  }),
            confirmLabel: _t("Move items"),
            confirm: async () => {
                const result = await this.kitchenCall("pos.kitchen.station", "resolve_overload", [
                    [entry.id],
                    plan.destination.id,
                    plan.lines.map((l) => l.line_id),
                    false,
                    this.actorChefId,
                ]);
                if (result) {
                    this.closeOverloadAlerts(entry.id);
                    this.notification.add(
                        _t("%(count)s item(s) moved to %(dest)s.", {
                            count: result.moved.length,
                            dest: plan.destination.name,
                        }),
                        { type: "success" }
                    );
                }
                this.refreshWorkload();
            },
        });
    },

    openReassignMenu(states) {
        const targets = this.reassignTargets;
        if (!targets.length) {
            this.notification.add(_t("No other station prepares these products."), { type: "warning" });
            return;
        }
        const lineIds = [...new Set(states.map((s) => s.prep_line_id.id))];
        this.dialog.add(KitchenSelectDialog, {
            title: _t("Move to another station"),
            options: targets.map((t) => ({
                id: t.id,
                label: t.name,
                sub: t.limit ? `${t.value} / ${t.limit} ${t.unit}` : `${t.value} ${t.unit}`,
            })),
            withReason: true,
            confirm: (stationId, reason) => this.reassignLines(lineIds, stationId, reason),
        });
    },
    async reassignLines(lineIds, stationId, reason) {
        const result = await this.kitchenCall("pos.prep.line", "reassign", [
            lineIds,
            stationId,
            reason || false,
            this.actorChefId,
        ]);
        if (result?.skipped?.length) {
            this.notification.add(
                _t("%s item(s) could not be moved because they are already started.", result.skipped.length),
                { type: "warning" }
            );
        }
        this.refreshWorkload();
    },
    async chefOptions(states) {
        const categories = new Set(
            states.flatMap((s) => s.prep_line_id.product_id.pos_categ_ids.map((c) => c.id))
        );
        const cooks = this.chefs.filter((chef) => {
            const allowed = chef.allowed_category_ids || [];
            return !allowed.length || allowed.some((id) => categories.has(id));
        });
        const onShift = await this.loadChefsOnShift(cooks);
        return [
            { id: 0, label: _t("Unassigned") },
            ...cooks.filter((c) => onShift.has(c.id)).map((c) => ({ id: c.id, label: c.name })),
        ];
    },
    async openAssignMenu(states) {
        const lineIds = [...new Set(states.map((s) => s.prep_line_id.id))];
        const options = await this.chefOptions(states);
        if (options.length === 1) {
            this.notification.add(_t("No chef of this station is on shift now."), {
                type: "warning",
            });
        }
        const current = this.kitchen.chef?.id;
        this.dialog.add(KitchenSelectDialog, {
            title: _t("Assign chef"),
            options,
            current: options.some((o) => o.id === current) ? current : null,
            confirm: (chefId) => this.assignChef(lineIds, chefId),
        });
    },
    async assignChef(lineIds, chefId, reason) {
        const result = await this.kitchenCall("pos.prep.line", "assign_chef", [
            lineIds,
            chefId || false,
            this.actorChefId,
            reason || false,
        ]);
        if (result) {
            const chef = chefId ? this.data.models["pos.kitchen.chef"].get(chefId) : false;
            for (const id of lineIds) {
                const line = this.data.models["pos.prep.line"].get(id);
                if (line && (!chef || this.chefCooks(chef, line))) {
                    line.assigned_chef_id = chef;
                }
            }
        }
        return result;
    },
    chefCooks(chef, line) {
        const allowed = chef.allowed_category_ids || [];
        return !allowed.length || line.product_id.pos_categ_ids.some((c) => allowed.includes(c.id));
    },
    takeStates(states) {
        if (!this.kitchen.chef) {
            this.openChefLogin();
            return;
        }
        const lineIds = [...new Set(states.map((s) => s.prep_line_id.id))];
        return this.assignChef(lineIds, this.kitchen.chef.id);
    },

    openReprepareDialog(states) {
        const lineIds = [...new Set(states.map((s) => s.prep_line_id.id))];
        const names = [...new Set(states.map((s) => s.prep_line_id.product_id.display_name))];
        this.dialog.add(KitchenReprepareDialog, {
            title: _t("Re-prepare: %s", names.join(", ")),
            confirm: (reasonType, reason) => this.reprepareLines(lineIds, reasonType, reason),
        });
    },
    async reprepareLines(lineIds, reasonType, reason) {
        const result = await this.kitchenCall("pos.prep.line", "kitchen_reprepare", [
            lineIds,
            reasonType,
            reason || false,
            this.actorChefId,
        ]);
        if (result?.moved?.length) {
            this.notification.add(_t("Sent back to the kitchen to be prepared again."), {
                type: "success",
            });
        } else if (result?.skipped?.length) {
            this.notification.add(_t("This item is no longer ready and cannot be re-prepared."), {
                type: "warning",
            });
        }
        this.refreshWorkload();
    },

    kitchenStageBlock(states, nextStage) {
        const current = states[0].stage_id;
        const counted = states.filter(countsForKitchen);
        if (
            FORWARD_STAGES.includes(nextStage.stage_type) &&
            WORKING_STAGES.includes(current.stage_type)
        ) {
            const missing = counted.filter((s) => !s.prep_line_id.assigned_chef_id);
            if (missing.length) {
                const names = [...new Set(missing.map((s) => s.product.display_name))];
                return _t("Assign a chef before marking these items ready: %s", names.join(", "));
            }
        }
        if (nextStage.stage_type === "done") {
            const moving = new Set(states.map((s) => s.id));
            const posOrderIds = new Set(
                states.map((s) => s.prep_line_id.prep_order_id.pos_order_id?.id)
            );
            const waiting = this.data.models["pos.prep.state"].filter(
                (s) =>
                    !moving.has(s.id) &&
                    posOrderIds.has(s.prep_line_id.prep_order_id.pos_order_id?.id) &&
                    countsForKitchen(s) &&
                    !FORWARD_STAGES.includes(s.stage_id.stage_type)
            );
            if (waiting.length) {
                const names = [...new Set(waiting.map((s) => s.product.display_name))];
                return _t(
                    "The order cannot be completed yet, these items are still being prepared: %s",
                    names.join(", ")
                );
            }
        }
        return false;
    },
    async changeStateStage(states, direction = 1) {
        if (!this.kitchenAdvanced || !states.length || direction !== 1) {
            return super.changeStateStage(...arguments);
        }
        const nextStage = this.orderNextStage(states[0].stage_id.id, direction);
        const tickets = new Map();
        for (const state of states) {
            const key = state.prep_line_id.prep_order_id.id;
            tickets.set(key, [...(tickets.get(key) || []), state]);
        }
        const allowed = [];
        const blocked = [];
        const messages = new Set();
        for (const ticketStates of tickets.values()) {
            const message = nextStage && this.kitchenStageBlock(ticketStates, nextStage);
            if (message) {
                messages.add(message);
                blocked.push(...ticketStates);
            } else {
                allowed.push(...ticketStates);
            }
        }
        for (const message of messages) {
            this.notification.add(message, { type: "warning" });
        }
        if (blocked.some((s) => s.todo === false)) {
            this.syncStateStatus(blocked);
        }
        if (!allowed.length) {
            return;
        }
        try {
            return await super.changeStateStage(allowed, direction);
        } catch (error) {
            if (!isKitchenRuleError(error)) {
                throw error;
            }
            this.notification.add(error.data.message, { type: "warning" });
        }
    },

    //  filtering & sorting
    checkStateVisibility(state) {
        if (!super.checkStateVisibility(...arguments)) {
            return false;
        }
        if (!this.kitchenAdvanced) {
            return true;
        }
        const line = state.prep_line_id;
        const k = this.kitchen;
        if (k.chefFilter === "mine" && k.chef && line.assigned_chef_id?.id !== k.chef.id) {
            return false;
        }
        if (k.chefFilter === "unassigned" && line.assigned_chef_id) {
            return false;
        }
        if (k.priorityFilter !== "all" && line.prep_order_id.priority !== k.priorityFilter) {
            return false;
        }
        if (k.stationFilter.length && !k.stationFilter.includes(line.station_id?.id)) {
            return false;
        }
        return true;
    },
    get filteredOrders() {
        const orders = super.filteredOrders;
        if (!this.kitchenAdvanced) {
            return orders;
        }
        const lastId = this.lastStage.id;
        const rank = (o) => PRIORITY_RANK[o.prepOrder.priority] ?? 1;
        return orders
            .map((order, index) => ({ order, index }))
            .sort((a, b) => {
                const sa = a.order.stage;
                const sb = b.order.stage;
                const stageDiff = sa.sequence - sb.sequence || sa.id - sb.id;
                if (stageDiff) {
                    return stageDiff;
                }
                if (sa.id === lastId) {
                    return a.index - b.index;
                }
                return rank(a.order) - rank(b.order) || a.index - b.index;
            })
            .map(({ order }) => order);
    },

});