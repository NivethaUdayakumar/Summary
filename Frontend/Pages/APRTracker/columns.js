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
var APR_TRACKER_ALERT_COLUMN_NAMES = ['Job'];
var APR_TRACKER_VALUE_COLUMN_WIDTH = '180px';
var APR_TRACKER_TONE_CLASS_NAMES = [
    'apr-tracker-cell-tone',
    'apr-tracker-cell-tone-success',
    'apr-tracker-cell-tone-warning',
    'apr-tracker-cell-tone-danger',
    'apr-tracker-cell-tone-info'
];

/*
Function Name: escapeAPRTrackerHtml
Purpose: Safely escape tracker cell text before it is inserted into HTML.
Input Params: value (any)
Output: escaped_value (str)
*/
function escapeAPRTrackerHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/*
Function Name: isAPRTrackerAlertColumn
Purpose: Check whether one APR tracker column should open the full-value alert on click.
Input Params: columnName (str)
Output: is_alert_column (bool)
*/
function isAPRTrackerAlertColumn(columnName) {
    return APR_TRACKER_ALERT_COLUMN_NAMES.indexOf(columnName) !== -1;
}

/*
Function Name: renderAPRTrackerCellValue
Purpose: Render one tracker cell and only make the chosen columns clickable for the full-value alert.
Input Params: columnName (str), cellData (any), type (str)
Output: rendered_value (str)
*/
function renderAPRTrackerCellValue(columnName, cellData, type) {
    var value = String(cellData == null ? '' : cellData);

    if (type !== 'display') {
        return value;
    }

    if (!value) {
        return '';
    }

    if (!isAPRTrackerAlertColumn(columnName)) {
        return '' +
            '<span class="apr-tracker-cell-text" title="' + escapeAPRTrackerHtml(value) + '">' +
            escapeAPRTrackerHtml(value) +
            '</span>';
    }

    return '' +
        '<button type="button" class="apr-tracker-cell-trigger" ' +
        'data-apr-full-value="' + escapeAPRTrackerHtml(value) + '" ' +
        'title="' + escapeAPRTrackerHtml(value) + '">' +
        escapeAPRTrackerHtml(value) +
        '</button>';
}

/*
Function Name: buildAPRTrackerDataColumn
Purpose: Build one standard DataTables column config for a tracker or KPI field.
Input Params: name (str)
Output: column_config (dict)
*/
function buildAPRTrackerDataColumn(name) {
    return {
        data: name,
        title: name,
        name: name,
        width: APR_TRACKER_VALUE_COLUMN_WIDTH,
        className: 'apr-tracker-value-cell',
        render: function renderAPRTrackerColumnValue(cellData, type) {
            return renderAPRTrackerCellValue(name, cellData, type);
        }
    };
}

/*
Function Name: makeAPRTrackerTargets
Purpose: Convert a list of column names into DataTables name-target selectors.
Input Params: names (list[str])
Output: targets (list[str])
*/
function makeAPRTrackerTargets(names) {
    var targets = [];
    var index;

    for (index = 0; index < names.length; index += 1) {
        targets.push(names[index] + ':name');
    }

    return targets;
}

/*
Function Name: normalizeAPRTrackerValue
Purpose: Normalize tracker text values before tone rules compare them.
Input Params: value (any)
Output: normalized_value (str)
*/
function normalizeAPRTrackerValue(value) {
    return String(value == null ? '' : value).trim().toLowerCase();
}

/*
Function Name: setAPRTrackerCellTone
Purpose: Reset the cell tone classes and apply the requested tone.
Input Params: cell (HTMLElement), tone (str)
Output: outputs (None)
*/
function setAPRTrackerCellTone(cell, tone) {
    var index;

    for (index = 0; index < APR_TRACKER_TONE_CLASS_NAMES.length; index += 1) {
        cell.classList.remove(APR_TRACKER_TONE_CLASS_NAMES[index]);
    }

    if (!tone) {
        return;
    }

    cell.classList.add('apr-tracker-cell-tone');
    cell.classList.add('apr-tracker-cell-tone-' + tone);
}

/*
Function Name: getAPRTrackerStatusTone
Purpose: Choose the background tone for the Status column.
Input Params: statusValue (any)
Output: tone (str)
*/
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

/*
Function Name: getAPRTrackerCommentTone
Purpose: Choose the background tone for the Comments column.
Input Params: commentValue (any), rowData (dict)
Output: tone (str)
*/
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

/*
Function Name: styleAPRTrackerStatusCell
Purpose: Apply the tracker status tone to a DataTables cell after it is created.
Input Params: cell (HTMLElement), cellData (any), rowData (dict)
Output: outputs (None)
*/
function styleAPRTrackerStatusCell(cell, cellData, rowData) {
    setAPRTrackerCellTone(cell, getAPRTrackerStatusTone(cellData || (rowData && rowData.Status)));
}

/*
Function Name: styleAPRTrackerCommentsCell
Purpose: Apply the tracker comment tone to a DataTables cell after it is created.
Input Params: cell (HTMLElement), cellData (any), rowData (dict)
Output: outputs (None)
*/
function styleAPRTrackerCommentsCell(cell, cellData, rowData) {
    setAPRTrackerCellTone(cell, getAPRTrackerCommentTone(cellData || (rowData && rowData.Comments), rowData));
}

/*
Function Name: buildAPRTrackerColumns
Purpose: Build the full APR tracker column list with the action column in front.
Input Params: None
Output: columns (list[dict])
*/
function buildAPRTrackerColumns() {
    var columns = [window.buildAPRActionColumn()];
    var allColumnNames = TRACKER_COLUMN_NAMES.concat(KPI_COLUMN_NAMES);
    var index;

    for (index = 0; index < allColumnNames.length; index += 1) {
        columns.push(buildAPRTrackerDataColumn(allColumnNames[index]));
    }

    return columns;
}

/*
Function Name: getAPRTrackerColumnDefs
Purpose: Build the DataTables column definitions used for filters and cell tone styling.
Input Params: listDropdown (dict), dateDropdown (dict), floatDropdown (dict)
Output: column_defs (list[dict])
*/
function getAPRTrackerColumnDefs(listDropdown, dateDropdown, floatDropdown) {
    return [
        {
            targets: '_all',
            defaultContent: ''
        },
        {
            targets: makeAPRTrackerTargets(LIST_COLUMN_NAMES),
            columnControl: ['order', listDropdown]
        },
        {
            targets: makeAPRTrackerTargets(DATE_COLUMN_NAMES),
            columnControl: ['order', dateDropdown]
        },
        {
            targets: makeAPRTrackerTargets(FLOAT_COLUMN_NAMES),
            columnControl: ['order', floatDropdown]
        },
        {
            targets: makeAPRTrackerTargets(['Status']),
            createdCell: styleAPRTrackerStatusCell
        },
        {
            targets: makeAPRTrackerTargets(['Comments']),
            createdCell: styleAPRTrackerCommentsCell
        }
    ];
}

window.APR_TRACKER_BASE_COLUMNS = TRACKER_COLUMN_NAMES.slice();
window.APR_TRACKER_KPI_COLUMNS = KPI_COLUMN_NAMES.slice();
window.getAPRTrackerColumns = buildAPRTrackerColumns;
window.getAPRTrackerColumnDefs = getAPRTrackerColumnDefs;
