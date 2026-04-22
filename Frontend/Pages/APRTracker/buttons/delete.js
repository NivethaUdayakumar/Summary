window.APR_BUTTONS = window.APR_BUTTONS || [];

function handleAPRDeleteAction(row) {
    alert('Delete row: ' + window.getAPRTrackerRowLabel(row));
}

function registerAPRDeleteButton() {
    window.APR_BUTTONS.push({
        id: 'delete',
        label: 'Delete',
        className: 'ui red mini button',
        handler: handleAPRDeleteAction
    });
}

registerAPRDeleteButton();
