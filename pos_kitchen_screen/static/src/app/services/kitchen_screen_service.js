import { patch } from "@web/core/utils/patch";
import { reactive } from "@odoo/owl";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { PrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import {
    KitchenSelectDialog,
    KitchenChefDialog,
    KitchenInfoDialog,
} from "@pos_kitchen_screen/app/components/kitchen_dialogs";

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };

patch(PrepDisplay.prototype, {
    async setup() {
        this.kitchen = reactive({
            chef: null,
            workload: [],
            chefFilter: "all",
            stationFilter: [],
            focusedStateId: null,
            lastActivity: Date.now(),
            now: Date.now(),
        });
        await super.setup(...arguments);
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
    kitchenOption(name) {
        return this.kitchenAdvanced && Boolean(this.kitchenDisplay?.[name]);
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
    openChefLogin() {
        if (!this.kitchenAdvanced) {
            return;
        }
        this.dialog.add(KitchenChefDialog, {
            chefs: this.chefs.map((c) => ({
                id: c.id,
                name: c.name,
            })),
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
        this.kitchen.lastActivity = Date.now();
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
        const touch = () => {
            this.kitchen.lastActivity = Date.now();
        };
        document.addEventListener("pointerdown", touch, true);
        document.addEventListener("keydown", touch, true);
        setInterval(() => {
            this.kitchen.now = Date.now();
            const idle = this.kitchenDisplay?.chef_idle_minutes;
            if (
                this.kitchenAdvanced &&
                idle > 0 &&
                this.kitchen.chef &&
                Date.now() - this.kitchen.lastActivity > idle * 60000
            ) {
                this.logoutChef();
            }
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
        this.onNotified("KITCHEN_READINESS_CHANGED", (data) => {
            const order = models["pos.order"].get(data.order_id);
            if (order) {
                order.kitchen_readiness = data.readiness;
                order.kitchen_station_status = data.status;
            }
        });
        this.onNotified("KITCHEN_ORDER_READY", (data) => {
            if (this.kitchenOption("show_readiness")) {
                this.notification.add(_t("%s: all stations are ready", data.name || ""), {
                    type: "success",
                });
                this.ringTheBell();
            }
        });
        this.onNotified("ITEM_CHANGED", (data) => {
            this.notification.add(`${data.order}: ${data.product} - ${data.text}`, {
                type: "warning",
                sticky: true,
            });
            this.ringTheBell();
        });
        this.onNotified("OVERLOAD_UNRESOLVED", (data) => {
            this.notification.add(
                _t("%(station)s is over by %(min)s min and no station can take the work. Inform the supervisor.", {
                    station: data.station,
                    min: data.excess,
                }),
                { type: "danger", sticky: true }
            );
        });
        this.onNotified("WORKLOAD_CHANGED", () => this.refreshWorkload());
        this.onNotified("LOAD_ORDERS", () => this.refreshWorkload());
    },

    async kitchenCall(model, method, args) {
        try {
            return await this.orm.call(model, method, args, {});
        } catch (error) {
            const message = error?.data?.message || error?.message || _t("Action failed");
            this.notification.add(message, { type: "danger" });
            return null;
        }
    },

    async loadWorkload() {
        if (!this.kitchenOption("show_workload")) {
            return;
        }
        const result = await this.kitchenCall("pos.kitchen.station", "get_station_workload", [
            this.id,
        ]);
        if (result) {
            this.alertNewOverflow(this.kitchen.workload, result);
            this.kitchen.workload = result;
        }
    },
    alertNewOverflow(previous, current) {
        const ownIds = this.ownStations.map((s) => s.id);
        for (const entry of current) {
            if (!ownIds.includes(entry.id) || !entry.overflow_orders) {
                continue;
            }
            const before = previous.find((w) => w.id === entry.id);
            if (!before || entry.overflow_orders > before.overflow_orders) {
                this.notification.add(
                    _t("%(station)s is overloaded: %(count)s order(s) are waiting. Use the Move button.", {
                        station: entry.name,
                        count: entry.overflow_orders,
                    }),
                    { type: "danger", sticky: true }
                );
                this.ringTheBell();
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
        if (!this.kitchenOption("show_workload") || !posOrderId) {
            return false;
        }
        const ownIds = this.ownStations.map((s) => s.id);
        return this.kitchen.workload.some(
            (w) => ownIds.includes(w.id) && w.overflow_order_ids.includes(posOrderId)
        );
    },
    openOverflowMenu(entry) {
        if (entry.metric === "time") {
            return this.openTimePlan(entry);
        }
        const targets = this.workloadView.filter(
            (w) => !w.isOwn && entry.alternatives.includes(w.id)
        );
        if (!targets.length) {
            this.notification.add(_t("No alternative station is configured for %s.", entry.name), {
                type: "warning",
            });
            return;
        }
        this.dialog.add(KitchenSelectDialog, {
            title: _t("%(station)s is full: %(count)s order(s) waiting", {
                station: entry.name,
                count: entry.overflow_orders,
            }),
            options: targets.map((t) => ({
                id: t.id,
                label: t.name,
                sub: t.limit
                    ? _t("%(value)s / %(limit)s %(unit)s, %(free)s free", {
                          value: t.value,
                          limit: t.limit,
                          unit: t.unit,
                          free: t.free,
                      })
                    : _t("%(value)s %(unit)s, no limit", { value: t.value, unit: t.unit }),
                disabled: t.limit && !t.free,
            })),
            withReason: true,
            confirm: (stationId, reason) => this.moveOverflow(entry.id, stationId, reason),
        });
    },
    async openTimePlan(entry) {
        const plan = await this.kitchenCall("pos.kitchen.station", "plan_overload", [[entry.id]]);
        if (!plan) {
            return;
        }
        if (!plan.destination) {
            this.notification.add(
                _t("%(station)s is over by %(min)s min. %(reason)s Please inform the supervisor.", {
                    station: entry.name,
                    min: plan.excess,
                    reason: plan.reason || "",
                }),
                { type: "danger", sticky: true }
            );
            return;
        }
        this.dialog.add(KitchenInfoDialog, {
            title: _t("%(station)s is over by %(min)s min", { station: entry.name, min: plan.excess }),
            intro: _t("These items move to %(dest)s (%(free)s):", {
                dest: plan.destination.name,
                free:
                    plan.destination.free === null
                        ? _t("no limit")
                        : _t("%s min free", plan.destination.free),
            }),
            rows: plan.lines.map((l) => ({
                label: `${l.qty}x ${l.product}`,
                sub: `${l.minutes} min, ${l.order}`,
            })),
            summary: plan.exact
                ? _t("Exact match: %s min moved.", plan.moved_minutes)
                : _t("%(moved)s of %(excess)s min can be moved.", {
                      moved: plan.moved_minutes,
                      excess: plan.excess,
                  }),
            confirmLabel: _t("Move these items"),
            confirm: async () => {
                const result = await this.kitchenCall("pos.kitchen.station", "resolve_overload", [
                    [entry.id],
                    plan.destination.id,
                    plan.lines.map((l) => l.line_id),
                    false,
                    this.actorChefId,
                ]);
                if (result) {
                    this.notification.add(_t("%s item(s) moved.", result.moved.length), {
                        type: "success",
                    });
                }
                this.refreshWorkload();
            },
        });
    },
    async moveOverflow(stationId, targetId, reason) {
        const result = await this.kitchenCall("pos.kitchen.station", "move_overflow", [
            [stationId],
            targetId,
            reason || false,
            this.actorChefId,
        ]);
        if (result) {
            const msg = [_t("%s order line(s) moved.", result.moved.length)];
            if (result.skipped.length) {
                msg.push(_t("%s already started, kept here.", result.skipped.length));
            }
            if (result.remaining) {
                msg.push(_t("%s order(s) still waiting.", result.remaining));
            }
            this.notification.add(msg.join(" "), { type: result.moved.length ? "success" : "warning" });
        }
        this.refreshWorkload();
    },

    //  reassign one item
    openReassignMenu(states) {
        const targets = this.reassignTargets;
        if (!targets.length) {
            this.notification.add(_t("No alternative station is configured."), { type: "warning" });
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
                _t("%s item(s) were already started and could not be moved.", result.skipped.length),
                { type: "warning" }
            );
        }
        this.refreshWorkload();
    },
    chefOptions(states) {
        const categories = new Set(
            states.flatMap((s) => s.prep_line_id.product_id.pos_categ_ids.map((c) => c.id))
        );
        const cooks = this.chefs.filter((chef) => {
            const allowed = chef.allowed_category_ids || [];
            return !allowed.length || allowed.some((id) => categories.has(id));
        });
        return [
            { id: 0, label: _t("Unassigned") },
            ...cooks.map((c) => ({ id: c.id, label: c.name })),
        ];
    },
    openAssignMenu(states) {
        const lineIds = [...new Set(states.map((s) => s.prep_line_id.id))];
        this.dialog.add(KitchenSelectDialog, {
            title: _t("Assign chef"),
            options: this.chefOptions(states),
            current: this.kitchen.chef?.id ?? null,
            confirm: (chefId) => this.assignChef(lineIds, chefId),
        });
    },
    async assignChef(lineIds, chefId, reason) {
        await this.kitchenCall("pos.prep.line", "assign_chef", [
            lineIds,
            chefId || false,
            this.actorChefId,
            reason || false,
        ]);
    },
    takeStates(states) {
        if (!this.kitchen.chef) {
            this.openChefLogin();
            return;
        }
        const lineIds = [...new Set(states.map((s) => s.prep_line_id.id))];
        return this.assignChef(lineIds, this.kitchen.chef.id);
    },

    //  re-prepare
    async openChangeDialog(line) {
        const events = await this.orm.searchRead(
            "pos.kitchen.item.history",
            [["prep_line_id", "=", line.id]],
            ["event_type", "old_quantity", "new_quantity", "changed_at"],
            { order: "id desc", limit: 5 }
        );
        const label = (e) =>
            ({
                qty_increased: _t("Quantity %(old)s to %(new)s", { old: e.old_quantity, new: e.new_quantity }),
                qty_decreased: _t("Quantity %(old)s to %(new)s", { old: e.old_quantity, new: e.new_quantity }),
                cancelled: _t("Cancelled"),
                note_changed: _t("Note changed"),
                new_item: _t("New item"),
                reprep: _t("Re-prepared"),
            })[e.event_type] || e.event_type;
        this.dialog.add(KitchenInfoDialog, {
            title: _t("Order changed: %s", line.product_id.display_name),
            intro: line.change_text || "",
            rows: events.map((e) => ({ label: label(e), sub: (e.changed_at || "").slice(11, 16) })),
            confirmLabel: _t("Re-prepare"),
            confirmClass: "btn-danger",
            confirm: () => this.reprepareLines([line.id]),
        });
    },
    async reprepareLines(lineIds) {
        await this.kitchenCall("pos.prep.line", "reprepare", [lineIds, false, this.actorChefId]);
    },

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
        if (k.stationFilter.length && !k.stationFilter.includes(line.station_id?.id)) {
            return false;
        }
        return true;
    },
    get filteredOrders() {
        const orders = super.filteredOrders;
        if (!this.kitchenOption("show_priority")) {
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

    moveFocus(delta) {
        const orders = this.filteredOrders;
        if (!orders.length) {
            this.kitchen.focusedStateId = null;
            return;
        }
        const current = orders.findIndex((o) => o.states[0].id === this.kitchen.focusedStateId);
        const next = Math.min(Math.max(current + delta, 0), orders.length - 1);
        this.kitchen.focusedStateId = orders[next].states[0].id;
    },
    get focusedOrder() {
        return this.filteredOrders.find((o) => o.states[0].id === this.kitchen.focusedStateId);
    },
    bumpFocused() {
        const order = this.focusedOrder;
        if (!order) {
            return;
        }
        if (order.stage.id === this.lastStage.id) {
            this.doneOrders(order.states);
        } else {
            this.changeStateStage(order.states);
        }
        this.moveFocus(0);
    },
});