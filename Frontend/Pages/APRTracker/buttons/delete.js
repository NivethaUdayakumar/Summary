window.APR_BUTTONS = window.APR_BUTTONS || [];

window.APR_BUTTONS.push({
    id: 'delete',
    label: 'Delete',
    className: 'ui red mini button',
    handler: function (row) {
        alert('Delete row item_code: ' + row.item_code);
    }
});