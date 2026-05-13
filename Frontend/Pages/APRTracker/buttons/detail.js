var APR_TIMING_DETAIL_TABLE_NAME = 'APR_TIMING_DETAIL';

/*
Function Name: handleAPRDetailAction
Purpose: Open the APR_TIMING_DETAIL table for one APR tracker row.
Input Params: row (dict)
Output: outputs (None)
*/
function handleAPRDetailAction(row) {
    window.openAPRTimingTableViewer(row, APR_TIMING_DETAIL_TABLE_NAME, 'APR Timing Detail');
}

/*
Function Name: isAPRDetailButtonDisabled
Purpose: Disable the Detail button when the APR row does not have enough timing DB path information.
Input Params: row (dict)
Output: is_disabled (bool)
*/
function isAPRDetailButtonDisabled(row) {
    return !window.canOpenAPRTimingViewer(row);
}

/*
Function Name: registerAPRDetailButton
Purpose: Register the Detail action button on the APR tracker page.
Input Params: None
Output: outputs (None)
*/
function registerAPRDetailButton() {
    window.registerAPRButton({
        id: 'detail',
        label: 'Detail',
        icon: 'list alternate outline',
        className: 'ui mini button',
        disabled: isAPRDetailButtonDisabled,
        handler: handleAPRDetailAction
    });
}

registerAPRDetailButton();
