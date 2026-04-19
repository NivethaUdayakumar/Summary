(function () {
    var TRACKER_COLUMN_NAMES = [
        'Job',
        'Milestone',
        'Block',
        'Stage',
        'Dft_release',
        'User',
        'Created',
        'Modified',
        'Rerun',
        'Status',
        'Comments',
        'Promote'
    ];

    var KPI_COLUMN_NAMES = [
        'Setup_WNS_seq',
        'Setup_TNS_seq',
        'Setup_NVP_seq',
        'Hold_WNS_seq',
        'Hold_TNS_seq',
        'Hold_NVP_seq',
        'Clock_trans',
        'Max_trans',
        'Max_hotspot',
        'Total_hotspot',
        'Fp',
        'Macro',
        'Hard',
        'Soft',
        'Area_fp',
        'Area_macro',
        'Psh',
        'Phys',
        'Logic',
        'Hrow',
        'Srow',
        'Dynamic',
        'Leakage',
        'SVT',
        'LVTL',
        'LVT',
        'ULVTL',
        'ULVT',
        'ELVT',
        'Conversion_rate',
        'Bits_per_cell'
    ];

    var LIST_COLUMN_NAMES = [
        'Job',
        'Milestone',
        'Block',
        'Stage',
        'Dft_release',
        'User',
        'Status',
        'Comments',
        'Promote'
    ];

    var DATE_COLUMN_NAMES = ['Created', 'Modified'];
    var FLOAT_COLUMN_NAMES = ['Rerun'].concat(KPI_COLUMN_NAMES);

    function buildColumn(name) {
        return {
            data: name,
            title: name,
            name: name
        };
    }

    function namesToTargets(names) {
        return names.map(function (name) {
            return name + ':name';
        });
    }

    window.APR_TRACKER_BASE_COLUMNS = TRACKER_COLUMN_NAMES.slice();
    window.APR_TRACKER_KPI_COLUMNS = KPI_COLUMN_NAMES.slice();

    window.getAPRTrackerColumns = function () {
        var dataColumns = TRACKER_COLUMN_NAMES.concat(KPI_COLUMN_NAMES).map(buildColumn);
        return [window.buildAPRActionColumn()].concat(dataColumns);
    };

    window.getAPRTrackerColumnDefs = function (listDropdown, dateDropdown, floatDropdown) {
        return [
            {
                targets: '_all',
                defaultContent: ''
            },
            {
                targets: namesToTargets(LIST_COLUMN_NAMES),
                columnControl: ['order', listDropdown]
            },
            {
                targets: namesToTargets(DATE_COLUMN_NAMES),
                columnControl: ['order', dateDropdown]
            },
            {
                targets: namesToTargets(FLOAT_COLUMN_NAMES),
                columnControl: ['order', floatDropdown]
            }
        ];
    };
})();
