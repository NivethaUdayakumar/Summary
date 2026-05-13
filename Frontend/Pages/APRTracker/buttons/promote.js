var APR_PROMOTE_ALLOWED_STAGES = ['place', 'route', 'clock'];

/*
Function Name: isAPRPromoteEligibleRow
Purpose: Check whether one APR row is allowed to use the Promote action.
Input Params: row (dict)
Output: is_eligible (bool)
*/
function isAPRPromoteEligibleRow(row) {
    var normalizedStatus = String((row && row.Status) || '').trim().toLowerCase();
    var normalizedStage = String((row && row.Stage) || '').trim().toLowerCase();
    var normalizedPromote = String((row && row.Promote) || '').trim().toLowerCase();

    return normalizedStatus === 'completed' &&
        APR_PROMOTE_ALLOWED_STAGES.indexOf(normalizedStage) !== -1 &&
        normalizedPromote === 'yes';
}

/*
Function Name: isAPRPromoteButtonDisabled
Purpose: Disable the Promote button when the selected APR row is not eligible.
Input Params: row (dict)
Output: is_disabled (bool)
*/
function isAPRPromoteButtonDisabled(row) {
    return !isAPRPromoteEligibleRow(row);
}

/*
Function Name: handleAPRPromoteAction
Purpose: Run the Promote action for one APR row.
Input Params: row (dict)
Output: outputs (None)
*/
function handleAPRPromoteAction(row) {
    alert('Promote row: ' + JSON.stringify(row, null, 2));
}

/*
Function Name: registerAPRPromoteButton
Purpose: Register the Promote action button on the APR tracker page.
Input Params: None
Output: outputs (None)
*/
function registerAPRPromoteButton() {
    window.registerAPRButton({
        id: 'promote',
        label: 'Promote',
        icon: 'upload',
        className: 'ui mini button',
        disabled: isAPRPromoteButtonDisabled,
        handler: handleAPRPromoteAction
    });
}

registerAPRPromoteButton();
