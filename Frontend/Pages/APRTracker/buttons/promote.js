window.APR_BUTTONS = window.APR_BUTTONS || [];

const APR_PROMOTE_ALLOWED_STAGES = ['place', 'route', 'clock'];

function isAPRPromoteEligibleRow(row) {
    var normalizedStatus = String((row && row.Status) || '').trim().toLowerCase();
    var normalizedStage = String((row && row.Stage) || '').trim().toLowerCase();
    var normalizedPromote = String((row && row.Promote) || '').trim().toLowerCase();

    return normalizedStatus === 'completed' &&
        APR_PROMOTE_ALLOWED_STAGES.indexOf(normalizedStage) !== -1 &&
        normalizedPromote === 'yes';
}

function isAPRPromoteButtonDisabled(row) {
    return !isAPRPromoteEligibleRow(row);
}

function handleAPRPromoteAction(row) {
    alert('Promote row: ' + JSON.stringify(row, null, 2));
}

function registerAPRPromoteButton() {
    window.APR_BUTTONS.push({
        id: 'promote',
        label: 'Promote',
        className: 'ui mini button',
        disabled: isAPRPromoteButtonDisabled,
        handler: handleAPRPromoteAction
    });
}

registerAPRPromoteButton();
