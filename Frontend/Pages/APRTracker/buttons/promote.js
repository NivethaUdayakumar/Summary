window.APR_BUTTONS = window.APR_BUTTONS || [];

window.APR_BUTTONS.push({
    id: 'promote',
    label: 'Promote',
    className: 'ui mini button',
    handler: function (row) {
        alert('Promote row: ' + JSON.stringify(row, null, 2));
    }
});