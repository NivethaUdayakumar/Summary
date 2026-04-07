window.APR_BUTTONS = window.APR_BUTTONS || [];

window.APR_BUTTONS.push({
    id: 'edit',
    label: 'Edit',
    className: 'ui mini button',
    handler: function (row) {
        alert('Edit row item_code: ' + row.item_code);
    }
});