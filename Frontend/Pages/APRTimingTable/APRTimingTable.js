var APR_TIMING_TABLE_PAGE = window.APR_TIMING_TABLE_PAGE || {
    dbPath: '',
    job: '',
    milestone: '',
    block: '',
    stage: '',
    table: null,
    tableName: '',
    title: ''
};

window.APR_TIMING_TABLE_PAGE = APR_TIMING_TABLE_PAGE;

/*
Function Name: getAPRTimingTableElement
Purpose: Read one APR timing viewer element by its HTML id.
Input Params: elementId (str)
Output: element (HTMLElement | null)
*/
function getAPRTimingTableElement(elementId) {
    return document.getElementById(elementId);
}

/*
Function Name: getAPRTimingTableParam
Purpose: Read one query-string value from the timing viewer URL.
Input Params: paramName (str)
Output: param_value (str)
*/
function getAPRTimingTableParam(paramName) {
    return new URLSearchParams(window.location.search).get(paramName) || '';
}

/*
Function Name: readAPRTimingTableConfig
Purpose: Read the popup configuration from the current URL and store it in page state.
Input Params: None
Output: outputs (None)
*/
function readAPRTimingTableConfig() {
    APR_TIMING_TABLE_PAGE.dbPath = String(getAPRTimingTableParam('db_path')).trim();
    APR_TIMING_TABLE_PAGE.tableName = String(getAPRTimingTableParam('table_name')).trim();
    APR_TIMING_TABLE_PAGE.title = String(getAPRTimingTableParam('title')).trim() || 'APR Timing Table';
    APR_TIMING_TABLE_PAGE.job = String(getAPRTimingTableParam('job')).trim();
    APR_TIMING_TABLE_PAGE.milestone = String(getAPRTimingTableParam('milestone')).trim();
    APR_TIMING_TABLE_PAGE.block = String(getAPRTimingTableParam('block')).trim();
    APR_TIMING_TABLE_PAGE.stage = String(getAPRTimingTableParam('stage')).trim();

    if (!APR_TIMING_TABLE_PAGE.dbPath || !APR_TIMING_TABLE_PAGE.tableName) {
        throw new Error('db_path and table_name are required to open the APR timing table viewer.');
    }
}

/*
Function Name: renderAPRTimingTableHeader
Purpose: Show the popup title, selected row context, and source database path.
Input Params: None
Output: outputs (None)
*/
function renderAPRTimingTableHeader() {
    var metaParts = [];
    var metaText;

    if (APR_TIMING_TABLE_PAGE.block) {
        metaParts.push('Block: ' + APR_TIMING_TABLE_PAGE.block);
    }
    if (APR_TIMING_TABLE_PAGE.milestone) {
        metaParts.push('Milestone: ' + APR_TIMING_TABLE_PAGE.milestone);
    }
    if (APR_TIMING_TABLE_PAGE.job) {
        metaParts.push('Run: ' + APR_TIMING_TABLE_PAGE.job);
    }
    if (APR_TIMING_TABLE_PAGE.stage) {
        metaParts.push('Stage: ' + APR_TIMING_TABLE_PAGE.stage);
    }

    metaText = metaParts.join(' | ');

    getAPRTimingTableElement('timingTableTitle').textContent = APR_TIMING_TABLE_PAGE.title;
    getAPRTimingTableElement('timingTableMeta').textContent = metaText;
    getAPRTimingTableElement('timingTableSource').textContent = APR_TIMING_TABLE_PAGE.dbPath;
}

/*
Function Name: getAPRLegacyTimingDbPath
Purpose: Build the legacy timing DB path that was used before the *_timing.db naming change.
Input Params: dbPath (str)
Output: legacy_db_path (str)
*/
function getAPRLegacyTimingDbPath(dbPath) {
    var text = String(dbPath || '').trim();

    if (text.slice(-10) === '_timing.db') {
        return text.slice(0, -10) + '.db';
    }

    return '';
}

/*
Function Name: buildAPRTimingDropdownConfig
Purpose: Build the small DataTables dropdown config used by one filter type.
Input Params: searchType (str)
Output: dropdown_config (dict)
*/
function buildAPRTimingDropdownConfig(searchType) {
    return {
        extend: 'dropdown',
        content: [
            searchType,
            'spacer',
            'orderAsc',
            'orderDesc',
            'orderClear'
        ]
    };
}

/*
Function Name: fetchAPRTimingTableData
Purpose: Read the selected timing table from the chosen SQLite database path.
Input Params: None
Output: payload (Promise[dict])
*/
async function fetchAPRTimingTableData() {
    return await fetchAPRTimingTableDataFromPath(APR_TIMING_TABLE_PAGE.dbPath);
}

/*
Function Name: fetchAPRTimingTableDataFromPath
Purpose: Read the selected timing table from one specific SQLite database path.
Input Params: dbPath (str)
Output: payload (Promise[dict])
*/
async function fetchAPRTimingTableDataFromPath(dbPath) {
    var response = await fetch('/api/read-table', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            db_location: dbPath,
            table_name: APR_TIMING_TABLE_PAGE.tableName
        })
    });
    var result;

    if (!response.ok) {
        throw new Error('HTTP error ' + response.status);
    }

    result = await response.json();
    if (!result.success) {
        throw new Error(result.error || 'Failed to load the APR timing table.');
    }

    return result;
}

/*
Function Name: normalizeAPRTimingColumnType
Purpose: Normalize one SQLite type name before filter rules inspect it.
Input Params: typeName (str)
Output: normalized_type (str)
*/
function normalizeAPRTimingColumnType(typeName) {
    return String(typeName || '').trim().toUpperCase();
}

/*
Function Name: isAPRTimingNumberColumn
Purpose: Check whether one SQLite column type should use the numeric filter.
Input Params: columnInfo (dict)
Output: is_number_column (bool)
*/
function isAPRTimingNumberColumn(columnInfo) {
    var typeName = normalizeAPRTimingColumnType(columnInfo.type);

    return typeName.indexOf('INT') !== -1 ||
        typeName.indexOf('REAL') !== -1 ||
        typeName.indexOf('NUM') !== -1 ||
        typeName.indexOf('DEC') !== -1 ||
        typeName.indexOf('FLOA') !== -1 ||
        typeName.indexOf('DOUB') !== -1;
}

/*
Function Name: isAPRTimingDateColumn
Purpose: Check whether one SQLite column type should use the date filter.
Input Params: columnInfo (dict)
Output: is_date_column (bool)
*/
function isAPRTimingDateColumn(columnInfo) {
    var typeName = normalizeAPRTimingColumnType(columnInfo.type);

    return typeName.indexOf('DATE') !== -1 || typeName.indexOf('TIME') !== -1;
}

/*
Function Name: isAPRTimingTextColumn
Purpose: Check whether one SQLite column type should use the text/list filter.
Input Params: columnInfo (dict)
Output: is_text_column (bool)
*/
function isAPRTimingTextColumn(columnInfo) {
    return !isAPRTimingNumberColumn(columnInfo) && !isAPRTimingDateColumn(columnInfo);
}

/*
Function Name: buildAPRTimingColumns
Purpose: Convert the SQLite schema into DataTables column configs.
Input Params: columnInfos (list[dict])
Output: columns (list[dict])
*/
function buildAPRTimingColumns(columnInfos) {
    var columns = [];
    var index;
    var columnInfo;

    for (index = 0; index < columnInfos.length; index += 1) {
        columnInfo = columnInfos[index];
        columns.push({
            data: columnInfo.name,
            title: columnInfo.name,
            name: columnInfo.name
        });
    }

    return columns;
}

/*
Function Name: buildAPRTimingColumnTargets
Purpose: Convert selected timing columns into DataTables name-target selectors.
Input Params: columnInfos (list[dict]), ruleFn (function)
Output: targets (list[str])
*/
function buildAPRTimingColumnTargets(columnInfos, ruleFn) {
    var targets = [];
    var index;
    var columnInfo;

    for (index = 0; index < columnInfos.length; index += 1) {
        columnInfo = columnInfos[index];
        if (ruleFn(columnInfo)) {
            targets.push(columnInfo.name + ':name');
        }
    }

    return targets;
}

/*
Function Name: buildAPRTimingColumnDefs
Purpose: Build DataTables filter definitions based on the SQLite column datatypes.
Input Params: columnInfos (list[dict])
Output: column_defs (list[dict])
*/
function buildAPRTimingColumnDefs(columnInfos) {
    var numberTargets = buildAPRTimingColumnTargets(columnInfos, isAPRTimingNumberColumn);
    var dateTargets = buildAPRTimingColumnTargets(columnInfos, isAPRTimingDateColumn);
    var textTargets = buildAPRTimingColumnTargets(columnInfos, isAPRTimingTextColumn);

    return [
        {
            targets: '_all',
            defaultContent: ''
        },
        {
            targets: textTargets,
            columnControl: ['order', buildAPRTimingDropdownConfig('searchList')]
        },
        {
            targets: dateTargets,
            columnControl: ['order', buildAPRTimingDropdownConfig('searchDateTime')]
        },
        {
            targets: numberTargets,
            columnControl: ['order', buildAPRTimingDropdownConfig('searchNumber')]
        }
    ];
}

/*
Function Name: createAPRTimingTable
Purpose: Build the TableBuilder config for the APR timing popup table.
Input Params: payload (dict)
Output: table_builder (TableBuilder)
*/
function createAPRTimingTable(payload) {
    return new TableBuilder({
        selector: '#aprTimingTable',
        data: payload.rows || [],
        columns: buildAPRTimingColumns(payload.columns || []),
        options: {
            paging: true,
            searching: true,
            ordering: {
                indicators: false,
                handler: false
            },
            orderMulti: true,
            info: true,
            pageLength: 25,
            lengthChange: true,
            autoWidth: true,
            responsive: false,
            stateSave: true,
            scrollX: true,
            columnDefs: buildAPRTimingColumnDefs(payload.columns || [])
        }
    });
}

/*
Function Name: reloadAPRTimingTable
Purpose: Reload the selected timing table from disk and re-render the popup table.
Input Params: None
Output: outputs (Promise[None])
*/
async function reloadAPRTimingTable() {
    var payload;
    var legacyDbPath;

    try {
        payload = await fetchAPRTimingTableData();
    } catch (error) {
        legacyDbPath = getAPRLegacyTimingDbPath(APR_TIMING_TABLE_PAGE.dbPath);
        if (!legacyDbPath) {
            throw error;
        }

        payload = await fetchAPRTimingTableDataFromPath(legacyDbPath);
        APR_TIMING_TABLE_PAGE.dbPath = legacyDbPath;
        renderAPRTimingTableHeader();
    }

    APR_TIMING_TABLE_PAGE.table = createAPRTimingTable(payload);
    await APR_TIMING_TABLE_PAGE.table.render();
}

/*
Function Name: showAPRTimingTableError
Purpose: Display one popup error in both the console and a browser alert.
Input Params: error (Error | any)
Output: outputs (None)
*/
function showAPRTimingTableError(error) {
    console.error(error);
    window.alert(error && error.message ? error.message : 'Unexpected APR timing table error.');
}

/*
Function Name: handleAPRTimingReloadClick
Purpose: Reload the selected APR timing table when the popup Reload button is pressed.
Input Params: None
Output: outputs (None)
*/
function handleAPRTimingReloadClick() {
    reloadAPRTimingTable().catch(showAPRTimingTableError);
}

/*
Function Name: bindAPRTimingTableToolbar
Purpose: Connect the Reload button to the timing table reload action.
Input Params: None
Output: outputs (None)
*/
function bindAPRTimingTableToolbar() {
    var reloadButton = getAPRTimingTableElement('reloadTimingTableBtn');

    if (!reloadButton) {
        return;
    }

    reloadButton.onclick = handleAPRTimingReloadClick;
}

/*
Function Name: initAPRTimingTablePage
Purpose: Read popup parameters, render the header, and load the requested timing table.
Input Params: None
Output: outputs (Promise[None])
*/
async function initAPRTimingTablePage() {
    readAPRTimingTableConfig();
    renderAPRTimingTableHeader();
    bindAPRTimingTableToolbar();
    await reloadAPRTimingTable();
}

/*
Function Name: startAPRTimingTablePage
Purpose: Start the APR timing popup page when the browser finishes loading the HTML.
Input Params: None
Output: outputs (None)
*/
function startAPRTimingTablePage() {
    initAPRTimingTablePage().catch(showAPRTimingTableError);
}

document.addEventListener('DOMContentLoaded', startAPRTimingTablePage);
