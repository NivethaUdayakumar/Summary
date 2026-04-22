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
var APR_TRACKER_TONE_CLASS_NAMES = [
    'apr-tracker-cell-tone',
    'apr-tracker-cell-tone-success',
    'apr-tracker-cell-tone-warning',
    'apr-tracker-cell-tone-danger',
    'apr-tracker-cell-tone-info'
];

function buildAPRTrackerDataColumn(name) {
    return {
        data: name,
        title: name,
        name: name
    };
}

function mapAPRTrackerColumnTargets(names) {
    var targets = [];
    var index;

    for (index = 0; index < names.length; index += 1) {
        targets.push(names[index] + ':name');
    }

    return targets;
}

function normalizeAPRTrackerValue(value) {
    return String(value == null ? '' : value).trim().toLowerCase();
}

function clearAPRTrackerToneClasses(cell) {
    var index;

    for (index = 0; index < APR_TRACKER_TONE_CLASS_NAMES.length; index += 1) {
        cell.classList.remove(APR_TRACKER_TONE_CLASS_NAMES[index]);
    }
}

function applyAPRTrackerTone(cell, tone) {
    clearAPRTrackerToneClasses(cell);

    if (!tone) {
        return;
    }

    cell.classList.add('apr-tracker-cell-tone');
    cell.classList.add('apr-tracker-cell-tone-' + tone);
}

function getAPRTrackerStatusTone(statusValue) {
    var normalizedStatus = normalizeAPRTrackerValue(statusValue);

    if (normalizedStatus === 'completed') {
        return 'success';
    }

    if (normalizedStatus === 'job failed' || normalizedStatus === 'extraction failed') {
        return 'danger';
    }

    if (normalizedStatus === 'await extraction') {
        return 'warning';
    }

    if (normalizedStatus === 'job running' || normalizedStatus === 'extracting') {
        return 'info';
    }

    return '';
}

function getAPRTrackerCommentTone(commentValue, rowData) {
    var normalizedComment = normalizeAPRTrackerValue(commentValue);

    if (normalizedComment === 'qc pass') {
        return 'success';
    }

    if (normalizedComment === 'err001' || normalizedComment === 'err002') {
        return 'danger';
    }

    return getAPRTrackerStatusTone(rowData ? rowData.Status : '');
}

function styleAPRTrackerStatusCell(cell, cellData, rowData) {
    applyAPRTrackerTone(cell, getAPRTrackerStatusTone(cellData || (rowData && rowData.Status)));
}

function styleAPRTrackerCommentsCell(cell, cellData, rowData) {
    applyAPRTrackerTone(cell, getAPRTrackerCommentTone(cellData || (rowData && rowData.Comments), rowData));
}

function buildAPRTrackerColumns() {
    var dataColumns = [];
    var columnNames = TRACKER_COLUMN_NAMES.concat(KPI_COLUMN_NAMES);
    var index;

    for (index = 0; index < columnNames.length; index += 1) {
        dataColumns.push(buildAPRTrackerDataColumn(columnNames[index]));
    }

    return [window.buildAPRActionColumn()].concat(dataColumns);
}

function getAPRTrackerColumnDefs(listDropdown, dateDropdown, floatDropdown) {
    return [
        {
            targets: '_all',
            defaultContent: ''
        },
        {
            targets: mapAPRTrackerColumnTargets(LIST_COLUMN_NAMES),
            columnControl: ['order', listDropdown]
        },
        {
            targets: mapAPRTrackerColumnTargets(DATE_COLUMN_NAMES),
            columnControl: ['order', dateDropdown]
        },
        {
            targets: mapAPRTrackerColumnTargets(FLOAT_COLUMN_NAMES),
            columnControl: ['order', floatDropdown]
        },
        {
            targets: mapAPRTrackerColumnTargets(['Status']),
            createdCell: styleAPRTrackerStatusCell
        },
        {
            targets: mapAPRTrackerColumnTargets(['Comments']),
            createdCell: styleAPRTrackerCommentsCell
        }
    ];
}

window.APR_TRACKER_BASE_COLUMNS = TRACKER_COLUMN_NAMES.slice();
window.APR_TRACKER_KPI_COLUMNS = KPI_COLUMN_NAMES.slice();
window.getAPRTrackerColumns = buildAPRTrackerColumns;
window.getAPRTrackerColumnDefs = getAPRTrackerColumnDefs;
