window.APR_BUTTONS = window.APR_BUTTONS || [];

window.APR_BUTTONS.push({
    id: 'view',
    label: 'View',
    className: 'ui mini button',
    handler: function (row) {
        alert('View row: ' + JSON.stringify(row, null, 2));
    }
});