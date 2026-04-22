window.APR_BUTTONS = window.APR_BUTTONS || [];

function handleAPRExportAction(row) {
    console.log('Export row', row);
    alert('Export row: ' + window.getAPRTrackerRowLabel(row));
}

function registerAPRExportButton() {
    window.APR_BUTTONS.push({
        id: 'export',
        label: 'Export',
        className: 'ui mini button',
        handler: handleAPRExportAction
    });
}

registerAPRExportButton();
