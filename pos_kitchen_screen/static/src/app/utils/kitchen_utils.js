export function inPreparation(state) {
    return Boolean(
        state?.stage_id && ["todo", "in_progress"].includes(state.stage_id.stage_type) && state.todo
    );
}

export function viewingPreparation(prepDisplay) {
    const id = prepDisplay.selectedStageId;
    if (!id) {
        return true;
    }
    const stage = prepDisplay.data.models["pos.prep.stage"].get(id);
    return ["todo", "in_progress"].includes(stage?.stage_type);
}
