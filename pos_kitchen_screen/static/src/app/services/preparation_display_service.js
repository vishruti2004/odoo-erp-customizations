import { patch } from "@web/core/utils/patch";
import { reactive } from "@odoo/owl";
import { debounce } from "@web/core/utils/timing";
import { _t } from "@web/core/l10n/translation";
import { PrepDisplay } from "@pos_enterprise/app/services/preparation_display_service";
import {
    KitchenSelectDialog,
    KitchenInfoDialog,
    KitchenReprepareDialog,
} from "@pos_kitchen_screen/app/components/kitchen_dialogs/kitchen_dialogs";

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
            chefWorkload: [],

            access: null,
            chefFilter: "all",
            priorityFilter: "all",
            stationFilter: [],
        });
        await super.setup(...arguments);
        this.overloadAlerts = new Map();
        this.refreshWorkload = debounce(() => this.loadWorkload(), 800);
        this.registerKitchenHandlers();
        await this.loadKitchenAccess();
        this.loadWorkload();
    },

    async loadKitchenAccess() {
        if (!this.kitchenAdvanced) {
            this.kitchen.access = { admin: true, chef: false };
            return;
        }
        const access = await this.kitchenCall("pos.kitchen.chef", "get_kitchen_access", [this.id]);
        this.kitchen.access = access || { admin: false, chef: false };
        if (!this.kitchen.access.admin) {
            const chef = this.kitchen.access.chef;
            if (chef) {
                this.kitchen.chef = { id: chef.id, name: chef.name };
            } else {
                this.notification.add(_t("Your user is not linked to any chef. Please ask an administrator."), {
                    type: "warning",
                });
            }
            this.kitchen.chefFilter = "all";
        }
        this.computeOrderCounts?.();
    },
    get kitchenIsAdmin() {
        return !this.kitchenAdvanced || Boolean(this.kitchen.access?.admin);
    },
    get kitchenRestricted() {
        return this.kitchenAdvanced && !this.kitchen.access?.admin;
    },

    get myStationIds() {
        return this.kitchen.access?.chef?.station_ids || [];
    },

    get visibleStations() {
        const own = this.ownStations;
        return this.kitchenRestricted ? own.filter((station) => this.myStationIds.includes(station.id)) : own;
    },

    get kitchenDisplay() {
        return this.data.models["pos.prep.display"].getFirst();
    },
    get kitchenAdvanced() {
        return Boolean(this.kitchenDisplay?.kitchen_advanced);
    },
    get kitchenAutoMode() {
        return (this.kitchenAdvanced && this.kitchenDisplay?.kitchen_auto_assign) || "manual";
    },
    get ownStations() {
        return this.data.models["pos.kitchen.station"].filter(
            (station) => station.display_id_int === this.id
        );
    },
    get chefs() {
        const ownIds = this.ownStations.map((station) => station.id);
        return this.data.models["pos.kitchen.chef"].filter((chef) => {
            const allowed = chef.allowed_station_ids || [];
            return !allowed.length || allowed.some((id) => ownIds.includes(id));
        });
    },
    get actorChefId() {
        return this.kitchen.chef?.id || false;
    },

    async loadChefsOnShift(chefs) {
        const ids = await this.kitchenCall("pos.kitchen.chef", "get_chefs_on_shift", [
            chefs.map((chef) => chef.id),
        ]);
        return new Set(ids || []);
    },
    loginChef(chefId) {
        const chef = this.data.models["pos.kitchen.chef"].get(chefId);
        if (!chef || this.kitchenRestricted) {
            return;
        }

        this.kitchen.chef = { id: chef.id, name: chef.name };
        this.kitchen.chefFilter = "mine";
    },
    logoutChef() {
        if (this.kitchenRestricted) {
            return;
        }
        this.kitchen.chef = null;
        this.kitchen.chefFilter = "all";
    },

    get chefMenu() {
        const shift = new Map(this.kitchen.chefWorkload.map((load) => [load.id, load.on_shift]));
        return this.chefs.map((chef) => ({
            id: chef.id,
            name: chef.name,
            offShift: shift.has(chef.id) && !shift.get(chef.id),
            selected: this.kitchen.chef?.id === chef.id,
        }));
    },

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
                    if (data.modes && lineId in data.modes) {
                        line.chef_assignment = data.modes[lineId];
                    }
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
                this.notification.add(_t("Order %s is ready.", data.name || ""), {
                    type: "success",
                });
                this.ringTheBell();
            }
        });
        this.onNotified("ITEM_CHANGED", (data) => {
            this.notification.add(_t("Order %(order)s updated: %(product)s (%(text)s)", {
                order: data.order,
                product: data.product,
                text: data.text,
            }), {
                type: "warning",
            });
            this.ringTheBell();
        });
        this.onNotified("OVERLOAD_UNRESOLVED", (data) => {
            if (!this.visibleStations.some((station) => station.id === data.id)) {
                return;
            }
            this.showOverloadAlert(`u${data.id}`,
                _t("%(station)s is over capacity by %(excess)s %(unit)s. No other station is available.", {
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
                error?.data?.message || error?.message || _t("The action could not be completed. Please try again.");
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
        const [result, chefs] = await Promise.all([
            this.kitchenCall("pos.kitchen.station", "get_station_workload", [this.id]),
            this.kitchenCall("pos.kitchen.chef", "get_chef_workload", [this.id]),
        ]);
        if (result) {
            this.alertOverflow(result);
            this.kitchen.workload = result;
        }
        if (chefs) {
            this.kitchen.chefWorkload = chefs;
        }
    },
    chefLoadLabel(chefLoad) {
        const qty = Number.isInteger(chefLoad.items)
            ? chefLoad.items
            : Math.round(chefLoad.items * 10) / 10;
        return chefLoad.metric === "time"
            ? _t("%(minutes)s min · Qty %(qty)s", { minutes: chefLoad.minutes, qty })
            : _t("Qty %(qty)s", { qty });
    },
    get chefWorkloadView() {
        const myChefId = this.kitchen.access?.chef?.id;
        return this.kitchen.chefWorkload
            .filter(
                (chefLoad) =>
                    chefLoad.on_shift && (!this.kitchenRestricted || chefLoad.id === myChefId)
            )
            .map((chefLoad) => {
                const label = this.chefLoadLabel(chefLoad);
                return {
                    ...chefLoad,
                    label,
                    title: _t("%(name)s · Pending: %(load)s", { name: chefLoad.name, load: label }),
                    isMe: this.kitchen.chef?.id === chefLoad.id,
                };
            });
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
        const ownIds = this.visibleStations.map((station) => station.id);
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
                    _t("%(station)s is over capacity by %(excess)s %(unit)s.", {
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
        const ownIds = this.ownStations.map((station) => station.id);
        const visibleIds = this.visibleStations.map((station) => station.id);
        const own = this.kitchen.workload.filter((load) => visibleIds.includes(load.id));
        const altIds = new Set(own.flatMap((load) => load.alternatives));

        const alt = this.kitchenRestricted
            ? []
            : this.kitchen.workload.filter((load) => altIds.has(load.id) && !ownIds.includes(load.id));
        return [...own, ...alt].map((load) => ({
            ...load,
            percent: load.limit ? Math.min(100, Math.round((load.value / load.limit) * 100)) : 0,
            isOwn: ownIds.includes(load.id),
            unit: load.metric === "time" ? _t("min") : _t("items"),
        }));
    },

    moveTargetsFor(lines) {
        if (!this.kitchenIsAdmin || !lines.length) {
            return [];
        }
        const stations = this.data.models["pos.kitchen.station"];
        const current = new Set(lines.map((line) => line.station_id?.id).filter(Boolean));
        return this.kitchen.workload
            .filter((load) => !current.has(load.id))
            .filter((load) => {
                const categories = stations.get(load.id)?.category_ids_int || [];
                return lines.every((line) =>
                    line.product_id.pos_categ_ids.some((category) => categories.includes(category.id))
                );
            })
            .map((load) => ({ ...load, unit: load.metric === "time" ? _t("min") : _t("items") }));
    },
    isOverflowOrder(posOrderId) {
        if (!this.kitchenAdvanced || !posOrderId) {
            return false;
        }
        const ownIds = this.ownStations.map((station) => station.id);
        return this.kitchen.workload.some(
            (load) => ownIds.includes(load.id) && load.overflow_order_ids.includes(posOrderId)
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
                _t("%(station)s is over capacity by %(excess)s %(unit)s. %(reason)s", {
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
            intro: _t("These items will move to %(dest)s (%(free)s):", {
                dest: plan.destination.name,
                free:
                    plan.destination.free === null
                        ? _t("no limit")
                        : _t("%(free)s %(unit)s available", { free: plan.destination.free, unit }),
            }),
            rows: plan.lines.map((line) => ({
                label: `${line.qty} x ${line.product}`,
                sub: `${line.load} ${unit}, ${_t("order")} ${line.order}`,
            })),
            summary: plan.exact
                ? _t("This moves the full excess (%(moved)s %(unit)s).", { moved: plan.moved, unit })
                : _t("This moves %(moved)s of the %(excess)s %(unit)s excess.", {
                      moved: plan.moved,
                      excess: plan.excess,
                      unit,
                  }),
            confirmLabel: _t("Move items"),
            confirm: async () => {
                const result = await this.kitchenCall("pos.kitchen.station", "resolve_overload", [
                    [entry.id],
                    plan.destination.id,
                    plan.lines.map((line) => line.line_id),
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
        const lines = [...new Set(states.map((state) => state.prep_line_id))];
        const targets = this.moveTargetsFor(lines);
        if (!targets.length) {
            this.notification.add(_t("No other station handles this category."), { type: "warning" });
            return;
        }
        const lineIds = [...new Set(states.map((state) => state.prep_line_id.id))];
        this.dialog.add(KitchenSelectDialog, {
            title: _t("Move to another station"),
            options: targets.map((target) => ({
                id: target.id,
                label: target.name,
                sub: target.limit
                    ? `${target.value} / ${target.limit} ${target.unit}`
                    : `${target.value} ${target.unit}`,
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
                _t("%s item(s) were not moved because they are already in progress.", result.skipped.length),
                { type: "warning" }
            );
        }
        this.refreshWorkload();
    },
    async chefOptions(states) {
        const categories = new Set(
            states.flatMap((state) => state.prep_line_id.product_id.pos_categ_ids.map((category) => category.id))
        );
        const cooks = this.chefs.filter((chef) => {
            const allowed = chef.allowed_category_ids || [];
            return !allowed.length || allowed.some((id) => categories.has(id));
        });
        const onShift = await this.loadChefsOnShift(cooks);
        const load = new Map(this.kitchen.chefWorkload.map((chefLoad) => [chefLoad.id, chefLoad]));
        return [
            ...(this.kitchenAutoMode === "auto"
                ? [{ id: "auto", label: _t("Automatic"), sub: _t("Least loaded chef") }]
                : []),
            { id: 0, label: _t("Unassigned") },
            ...cooks
                .filter((chef) => onShift.has(chef.id))
                .map((chef) => ({
                    id: chef.id,
                    label: chef.name,
                    sub: load.has(chef.id)
                        ? _t("Pending: %s", this.chefLoadLabel(load.get(chef.id)))
                        : undefined,
                })),
        ];
    },
    async openAssignMenu(states) {
        if (this.kitchenRestricted) {

            const free = states.filter((state) => !state.prep_line_id.assigned_chef_id);
            return free.length ? this.takeStates(free) : undefined;
        }
        const lineIds = [...new Set(states.map((state) => state.prep_line_id.id))];
        const options = await this.chefOptions(states);
        if (!options.some((option) => typeof option.id === "number" && option.id)) {
            this.notification.add(_t("No chef on shift for this station."), {
                type: "warning",
            });
        }
        const current = this.kitchen.chef?.id;
        this.dialog.add(KitchenSelectDialog, {
            title: _t("Assign chef"),
            options,
            current: options.some((option) => option.id === current) ? current : null,
            confirm: (chefId) => this.assignChef(lineIds, chefId),
        });
    },
    async autoAssignLines(lineIds) {
        const result = await this.kitchenCall("pos.prep.line", "kitchen_auto_assign", [
            lineIds,
            this.actorChefId,
        ]);
        if (result) {
            const assigned = Object.keys(result.assigned || {}).length;
            if (assigned) {
                this.notification.add(_t("%s item(s) assigned automatically.", assigned), {
                    type: "success",
                });
            } else if (!result.unassigned?.length) {
                this.notification.add(_t("The current assignment is already the best one."), {
                    type: "info",
                });
            }
        }
        this.refreshWorkload();
        return result;
    },
    async assignChef(lineIds, chefId, reason) {
        if (chefId === "auto") {
            return this.autoAssignLines(lineIds);
        }
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
                    line.chef_assignment = chef ? "manual" : false;
                }
            }
        }
        return result;
    },
    chefCooks(chef, line) {
        const allowed = chef.allowed_category_ids || [];
        return !allowed.length || line.product_id.pos_categ_ids.some((category) => allowed.includes(category.id));
    },
    takeStates(states) {
        if (!this.kitchen.chef) {
            this.notification.add(_t("Select a chef first."), { type: "warning" });
            return;
        }
        const lineIds = [...new Set(states.map((state) => state.prep_line_id.id))];
        return this.assignChef(lineIds, this.kitchen.chef.id);
    },

    openReprepareDialog(states) {
        const lineIds = [...new Set(states.map((state) => state.prep_line_id.id))];
        const names = [...new Set(states.map((state) => state.prep_line_id.product_id.display_name))];
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
            this.notification.add(_t("Item sent back for re-preparation."), {
                type: "success",
            });
        } else if (result?.skipped?.length) {
            this.notification.add(_t("Only ready items can be re-prepared."), {
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
            const missing = counted.filter((state) => !state.prep_line_id.assigned_chef_id);
            if (missing.length) {
                const names = [...new Set(missing.map((state) => state.prep_line_id.product_id.display_name))];
                return _t("Assign a chef before marking these items ready: %s", names.join(", "));
            }
        }
        if (nextStage.stage_type === "done") {
            const moving = new Set(states.map((state) => state.id));
            const posOrderIds = new Set(
                states.map((state) => state.prep_line_id.prep_order_id.pos_order_id?.id)
            );
            const waiting = this.data.models["pos.prep.state"].filter(
                (state) =>
                    !moving.has(state.id) &&
                    posOrderIds.has(state.prep_line_id.prep_order_id.pos_order_id?.id) &&
                    countsForKitchen(state) &&
                    !FORWARD_STAGES.includes(state.stage_id.stage_type)
            );
            if (waiting.length) {
                const names = [...new Set(waiting.map((state) => state.prep_line_id.product_id.display_name))];
                return _t(
                    "This order cannot be completed yet. Still in preparation: %s",
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
        if (blocked.some((state) => state.todo === false)) {
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

    checkStateVisibility(state) {
        if (!super.checkStateVisibility(...arguments)) {
            return false;
        }
        if (!this.kitchenAdvanced) {
            return true;
        }
        const line = state.prep_line_id;
        const kitchen = this.kitchen;
        if (this.kitchenRestricted) {

            const myChef = kitchen.access?.chef;
            if (!myChef) {
                return false;
            }
            const chefId = line.assigned_chef_id?.id;
            if (chefId ? chefId !== myChef.id : !this.myStationIds.includes(line.station_id?.id)) {
                return false;
            }
        }
        if (kitchen.chefFilter === "mine" && kitchen.chef && line.assigned_chef_id?.id !== kitchen.chef.id) {
            return false;
        }
        if (kitchen.chefFilter === "unassigned" && line.assigned_chef_id) {
            return false;
        }
        if (kitchen.priorityFilter !== "all" && line.prep_order_id.priority !== kitchen.priorityFilter) {
            return false;
        }
        if (kitchen.stationFilter.length && !kitchen.stationFilter.includes(line.station_id?.id)) {
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
        const rank = (order) => PRIORITY_RANK[order.prepOrder.priority] ?? 1;
        return orders
            .map((order, index) => ({ order, index }))
            .sort((first, second) => {
                const firstStage = first.order.stage;
                const secondStage = second.order.stage;
                const stageDiff = firstStage.sequence - secondStage.sequence || firstStage.id - secondStage.id;
                if (stageDiff) {
                    return stageDiff;
                }
                if (firstStage.id === lastId) {
                    return first.index - second.index;
                }
                return rank(first.order) - rank(second.order) || first.index - second.index;
            })
            .map(({ order }) => order);
    },
});
