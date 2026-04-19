window.APR_BUTTONS = window.APR_BUTTONS || [];

window.APR_BUTTONS.push({
    id: 'export',
    label: 'Export',
    className: 'ui mini button',
    handler: function (row) {
        console.log('Export row', row);
        alert('Export row: ' + window.getAPRTrackerRowLabel(row));
    }
});
