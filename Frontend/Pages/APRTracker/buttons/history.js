window.APR_BUTTONS = window.APR_BUTTONS || [];

window.APR_BUTTONS.push({
    id: 'history',
    label: 'History',
    className: 'ui mini button',
    handler: function (row) {
        console.log('History row', row);
        alert('History row: ' + window.getAPRTrackerRowLabel(row));
    }
});
