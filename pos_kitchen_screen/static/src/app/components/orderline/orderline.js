import { patch } from "@web/core/utils/patch";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";
import { inPreparation, viewingPreparation } from "@pos_kitchen_screen/app/utils/kitchen_utils";

patch(Orderline.prototype, {
    get kitchenState() {
        return this.props.orderline.stage_id ? this.props.orderline : null;
    },
    get kitchenChangeText() {
        const line = this.preparation_line;
        if (
            !this.prepDisplay.kitchenAdvanced ||
            !line.change_text ||
            !viewingPreparation(this.prepDisplay)
        ) {
            return null;
        }
        if (line.last_change_type === "reprep") {
            return line.change_pending && inPreparation(this.kitchenState)
                ? { text: line.change_text, cls: "o_kitchen_change_reprep" }
                : null;
        }
        return line.change_pending ? { text: line.change_text, cls: "o_kitchen_change_pending" } : null;
    },
    get kitchenStationName() {
        if (!this.prepDisplay.kitchenAdvanced || this.prepDisplay.ownStations.length < 2) {
            return "";
        }
        return this.preparation_line.station_id?.name || "";
    },
    get kitchenChef() {
        return this.prepDisplay.kitchenAdvanced ? this.preparation_line.assigned_chef_id || null : null;
    },
    get kitchenChefAuto() {
        return Boolean(this.kitchenChef && this.preparation_line.chef_assignment === "auto");
    },
    get kitchenCanAssign() {
        const state = this.kitchenState;
        return Boolean(
            state && this.prepDisplay.kitchenAdvanced && state.stage_id.stage_type !== "done"
        );
    },
    get kitchenMovedFrom() {
        return this.prepDisplay.kitchenAdvanced ? this.preparation_line.moved_from || "" : "";
    },
    get kitchenCanMove() {
        const state = this.kitchenState;
        return Boolean(
            state &&
                this.prepDisplay.kitchenAdvanced &&
                this.prepDisplay.kitchenIsAdmin &&
                state.stage_id.stage_type === "todo" &&
                state.todo &&
                this.prepDisplay.moveTargetsFor([this.preparation_line]).length
        );
    },
    get kitchenIsAdmin() {
        return this.prepDisplay.kitchenIsAdmin;
    },
    get kitchenShowTake() {
        return !(this.kitchenIsAdmin && this.prepDisplay.kitchenAutoMode !== "auto");
    },
    get kitchenCanReprepare() {
        const state = this.kitchenState;
        const line = this.preparation_line;
        return Boolean(
            state &&
                line &&
                this.prepDisplay.kitchenAdvanced &&
                state.stage_id.stage_type === "ready" &&
                line.quantity - (line.cancelled || 0) > 0
        );
    },
    get kitchenMetaVisible() {
        return Boolean(
            this.prepDisplay.kitchenAdvanced &&
                (this.kitchenMovedFrom ||
                    this.kitchenStationName ||
                    this.kitchenCanAssign ||
                    this.kitchenCanReprepare)
        );
    },
    kitchenReprepareClick() {
        this.prepDisplay.openReprepareDialog([this.kitchenState]);
    },
    kitchenAssign() {
        this.prepDisplay.openAssignMenu([this.kitchenState]);
    },
    kitchenMove() {
        this.prepDisplay.openReassignMenu([this.kitchenState]);
    },
    kitchenTake() {
        this.prepDisplay.takeStates([this.kitchenState]);
    },
});
