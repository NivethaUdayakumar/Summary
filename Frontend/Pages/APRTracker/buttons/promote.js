window.APR_BUTTONS = window.APR_BUTTONS || [];

function isAPRPromoteButtonDisabled(row) {
    return String((row && row.Promote) || '').trim().toLowerCase() !== 'yes';
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
