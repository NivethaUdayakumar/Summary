(function () {
    window.getAPRTrackerColumns = function () {
        return [
            { data: 'item_code', title: 'item_code', name: 'item_code' },
            window.buildAPRActionColumn(),
            { data: 'workstream', title: 'workstream', name: 'workstream' },
            { data: 'milestone', title: 'milestone', name: 'milestone' },
            { data: 'owner', title: 'owner', name: 'owner' },
            { data: 'status', title: 'status', name: 'status' },
            { data: 'due_date', title: 'due_date', name: 'due_date' },
            { data: 'score', title: 'score', name: 'score' }
        ];
    };

    window.getAPRTrackerColumnDefs = function (listDropdown, dateDropdown, floatDropdown) {
        return [
            {
                targets: '_all',
                defaultContent: ''
            },
            {
                targets: ['item_code:name', 'workstream:name', 'owner:name', 'status:name'],
                columnControl: ['order', listDropdown]
            },
            {
                targets: ['due_date:name'],
                columnControl: ['order', dateDropdown]
            },
            {
                targets: ['score:name'],
                columnControl: ['order', floatDropdown]
            }
        ];
    };
})();