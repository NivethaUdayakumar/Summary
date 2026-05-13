var APR_TRACKER_TABLE_NAME = 'APR_TRACKER';
var APR_TRACKER_PAGE = window.APR_TRACKER_PAGE || {
    dbPath: '',
    projectCode: '',
    table: null
};

window.APR_TRACKER_PAGE = APR_TRACKER_PAGE;

/*
Function Name: getAPRTrackerElement
Purpose: Read one APR Tracker page element by its HTML id.
Input Params: elementId (str)
Output: element (HTMLElement | null)
*/
function getAPRTrackerElement(elementId) {
    return document.getElementById(elementId);
}

/*
Function Name: buildAPRTrackerDropdownConfig
Purpose: Build the small DataTables dropdown config used by one filter type.
Input Params: searchType (str)
Output: dropdown_config (dict)
*/
function buildAPRTrackerDropdownConfig(searchType) {
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
Function Name: getAPRTrackerSelectedPresetName
Purpose: Return the preset that is currently selected in the toolbar.
Input Params: None
Output: preset_name (str)
*/
function getAPRTrackerSelectedPresetName() {
    var presetSelect = getAPRTrackerElement('presetSelect');

    return presetSelect && presetSelect.value ? presetSelect.value : 'default';
}

/*
Function Name: loadAPRTrackerProjectCode
Purpose: Read the active project code from the current browser session.
Input Params: None
Output: project_code (Promise[str])
*/
async function loadAPRTrackerProjectCode() {
    var response = await fetch('/api/session');
    var result;
    var projectCode;

    if (!response.ok) {
        throw new Error('Unable to load session information.');
    }

    result = await response.json();
    if (!result.success) {
        throw new Error(result.error || 'Unable to load session information.');
    }

    projectCode = String(result.project_code || '').trim();
    if (!projectCode || projectCode.toLowerCase() === 'unknown') {
        throw new Error('project_code is missing from the current session.');
    }

    return projectCode;
}

/*
Function Name: buildAPRTrackerDbPath
Purpose: Build the APR tracker database path from the current project code.
Input Params: projectCode (str)
Output: db_path (str)
*/
function buildAPRTrackerDbPath(projectCode) {
    return 'AppData/App.db';
    //return '/proj/' + String(projectCode || '').trim() + '/DashAI/DashAI_APR.db';
}

/*
Function Name: fetchAPRTrackerRows
Purpose: Load every APR tracker row from the project-specific DashAI APR database.
Input Params: None
Output: rows (Promise[list[dict]])
*/
async function fetchAPRTrackerRows() {
    var response;
    var result;

    if (!APR_TRACKER_PAGE.dbPath) {
        throw new Error('APR tracker database path is not ready.');
    }

    response = await fetch('/api/read-table', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            db_location: APR_TRACKER_PAGE.dbPath,
            table_name: APR_TRACKER_TABLE_NAME
        })
    });

    if (!response.ok) {
        throw new Error('HTTP error ' + response.status);
    }

    result = await response.json();
    if (!result.success) {
        throw new Error(result.error || 'Failed to load APR tracker rows.');
    }

    return Array.isArray(result.rows) ? result.rows : [];
}

/*
Function Name: getAPRTrackerDataTable
Purpose: Return the current DataTables instance for the APR tracker page.
Input Params: None
Output: data_table (DataTable | null)
*/
function getAPRTrackerDataTable() {
    if (!APR_TRACKER_PAGE.table || !APR_TRACKER_PAGE.table.getInstance) {
        return null;
    }

    return APR_TRACKER_PAGE.table.getInstance();
}

/*
Function Name: applyAPRTrackerSelectedPreset
Purpose: Re-apply the selected preset to the current APR tracker table.
Input Params: None
Output: outputs (None)
*/
function applyAPRTrackerSelectedPreset() {
    if (!APR_TRACKER_PAGE.table) {
        return;
    }

    window.applyAPRTrackerPreset(APR_TRACKER_PAGE.table, getAPRTrackerSelectedPresetName());
}

/*
Function Name: clearAPRTrackerColumnControlSearches
Purpose: Clear DataTables column-control searches no matter which plugin method is available.
Input Params: dataTable (DataTable)
Output: outputs (None)
*/
function clearAPRTrackerColumnControlSearches(dataTable) {
    if (
        dataTable.columns &&
        dataTable.columns().columnControl &&
        typeof dataTable.columns().columnControl.searchClear === 'function'
    ) {
        dataTable.columns().columnControl.searchClear();
        return;
    }

    if (
        dataTable.columns &&
        typeof dataTable.columns().ccSearchClear === 'function'
    ) {
        dataTable.columns().ccSearchClear();
    }
}

/*
Function Name: clearAPRTrackerFilterFields
Purpose: Clear the text, number, date, and select fields inside the filter area.
Input Params: container (HTMLElement | null)
Output: outputs (None)
*/
function clearAPRTrackerFilterFields(container) {
    var fields;
    var index;
    var field;

    if (!container) {
        return;
    }

    fields = container.querySelectorAll('input, select');
    for (index = 0; index < fields.length; index += 1) {
        field = fields[index];

        if (field.tagName === 'SELECT') {
            field.selectedIndex = 0;
            continue;
        }

        if (
            field.type === 'search' ||
            field.type === 'text' ||
            field.type === 'number' ||
            field.type === 'date'
        ) {
            field.value = '';
        }
    }
}

/*
Function Name: clearAPRTrackerFilters
Purpose: Clear every search box, state save, and preset filter applied to the table.
Input Params: None
Output: outputs (None)
*/
function clearAPRTrackerFilters() {
    var dataTable = getAPRTrackerDataTable();

    if (!dataTable) {
        return;
    }

    dataTable.search('');
    dataTable.columns().search('');
    clearAPRTrackerColumnControlSearches(dataTable);

    if (dataTable.state && typeof dataTable.state.clear === 'function') {
        dataTable.state.clear();
    }

    clearAPRTrackerFilterFields(dataTable.table().container());
    dataTable.draw();
    applyAPRTrackerSelectedPreset();
}

/*
Function Name: reloadAPRTrackerTable
Purpose: Fetch fresh tracker rows from the database and rebuild the table.
Input Params: None
Output: outputs (Promise[None])
*/
async function reloadAPRTrackerTable() {
    var rows = await fetchAPRTrackerRows();

    if (!APR_TRACKER_PAGE.table) {
        return;
    }

    await APR_TRACKER_PAGE.table.reload(rows);
    applyAPRTrackerSelectedPreset();
}

/*
Function Name: showAPRTrackerPageError
Purpose: Display one tracker-page error in both the console and a browser alert.
Input Params: error (Error | any)
Output: outputs (None)
*/
function showAPRTrackerPageError(error) {
    console.error(error);
    alert(error && error.message ? error.message : 'Unexpected APR Tracker error.');
}

/*
Function Name: openAPRTrackerWatchlistManager
Purpose: Open the APR Watchlist Manager if that helper was registered on the page.
Input Params: None
Output: outputs (None)
*/
function openAPRTrackerWatchlistManager() {
    if (typeof window.openAprWatchlistManager === 'function') {
        window.openAprWatchlistManager();
    }
}

/*
Function Name: bindAPRTrackerToolbar
Purpose: Connect the toolbar controls to the preset, clear, watchlist, and reload actions.
Input Params: None
Output: outputs (None)
*/
function bindAPRTrackerToolbar() {
    var presetSelect = getAPRTrackerElement('presetSelect');
    var clearFiltersButton = getAPRTrackerElement('clearFiltersBtn');
    var watchlistManagerButton = getAPRTrackerElement('watchlistManagerBtn');
    var reloadButton = getAPRTrackerElement('reloadTableBtn');

    if (presetSelect) {
        presetSelect.onchange = applyAPRTrackerSelectedPreset;
    }

    if (clearFiltersButton) {
        clearFiltersButton.onclick = clearAPRTrackerFilters;
    }

    if (watchlistManagerButton) {
        watchlistManagerButton.onclick = openAPRTrackerWatchlistManager;
    }

    if (reloadButton) {
        reloadButton.onclick = handleAPRTrackerReloadClick;
    }
}

/*
Function Name: handleAPRTrackerReloadClick
Purpose: Reload the APR tracker rows when the toolbar Reload button is pressed.
Input Params: None
Output: outputs (None)
*/
function handleAPRTrackerReloadClick() {
    reloadAPRTrackerTable().catch(showAPRTrackerPageError);
}

/*
Function Name: showAPRTrackerCellValue
Purpose: Show the full value for one truncated tracker cell.
Input Params: trigger (HTMLElement | null)
Output: outputs (None)
*/
function showAPRTrackerCellValue(trigger) {
    var value = trigger ? trigger.getAttribute('data-apr-full-value') || '' : '';

    if (value) {
        alert(value);
    }
}

/*
Function Name: handleAPRTrackerTableClick
Purpose: Show the full tracker value when a truncated table cell is clicked.
Input Params: event (MouseEvent)
Output: outputs (None)
*/
function handleAPRTrackerTableClick(event) {
    var trigger = event.target.closest('.apr-tracker-cell-trigger');

    if (trigger) {
        showAPRTrackerCellValue(trigger);
    }
}

/*
Function Name: handleAPRTrackerTableKeyDown
Purpose: Show the full tracker value when a truncated table cell is opened with the keyboard.
Input Params: event (KeyboardEvent)
Output: outputs (None)
*/
function handleAPRTrackerTableKeyDown(event) {
    var trigger;

    if (event.key !== 'Enter' && event.key !== ' ') {
        return;
    }

    trigger = event.target.closest('.apr-tracker-cell-trigger');
    if (!trigger) {
        return;
    }

    event.preventDefault();
    showAPRTrackerCellValue(trigger);
}

/*
Function Name: bindAPRTrackerTableExtras
Purpose: Attach the action-button handler and full-cell-value handler to the APR tracker table.
Input Params: tableBuilder (TableBuilder)
Output: outputs (None)
*/
function bindAPRTrackerTableExtras(tableBuilder) {
    var tableElement = document.querySelector(tableBuilder.selector);

    if (!tableElement) {
        return;
    }

    window.bindAPRActionEvents(tableBuilder);

    if (tableElement._aprTrackerExtrasBound) {
        return;
    }

    tableElement.addEventListener('click', handleAPRTrackerTableClick);
    tableElement.addEventListener('keydown', handleAPRTrackerTableKeyDown);
    tableElement._aprTrackerExtrasBound = true;
}

/*
Function Name: handleAPRTrackerTableAfterInit
Purpose: Run the last setup steps after DataTables finishes creating the APR tracker table.
Input Params: dataTable (DataTable), tableBuilder (TableBuilder)
Output: outputs (None)
*/
function handleAPRTrackerTableAfterInit(dataTable, tableBuilder) {
    bindAPRTrackerTableExtras(tableBuilder);
}

/*
Function Name: createAPRTrackerTable
Purpose: Build the TableBuilder config for the APR tracker page.
Input Params: rows (list[dict])
Output: table_builder (TableBuilder)
*/
function createAPRTrackerTable(rows) {
    return new TableBuilder({
        selector: '#aprTrackerTable',
        data: rows,
        columns: window.getAPRTrackerColumns(),
        options: {
            paging: true,
            searching: true,
            ordering: {
                indicators: false,
                handler: false
            },
            orderMulti: true,
            info: true,
            pageLength: 10,
            lengthChange: true,
            order: [[8, 'desc']],
            autoWidth: true,
            responsive: false,
            stateSave: true,
            scrollX: true,
            fixedColumns: {
                left: 2
            },
            columnDefs: window.getAPRTrackerColumnDefs(
                buildAPRTrackerDropdownConfig('searchList'),
                buildAPRTrackerDropdownConfig('searchDateTime'),
                buildAPRTrackerDropdownConfig('searchNumber')
            )
        },
        extensions: {
            afterInit: handleAPRTrackerTableAfterInit
        }
    });
}

/*
Function Name: initAPRTracker
Purpose: Load the session project code, read the APR database, render the table, and bind the toolbar.
Input Params: None
Output: outputs (Promise[None])
*/
async function initAPRTracker() {
    var rows;

    APR_TRACKER_PAGE.projectCode = await loadAPRTrackerProjectCode();
    APR_TRACKER_PAGE.dbPath = buildAPRTrackerDbPath(APR_TRACKER_PAGE.projectCode);
    rows = await fetchAPRTrackerRows();

    APR_TRACKER_PAGE.table = createAPRTrackerTable(rows);
    await APR_TRACKER_PAGE.table.render();
    bindAPRTrackerToolbar();
    applyAPRTrackerSelectedPreset();
}

/*
Function Name: startAPRTrackerPage
Purpose: Start the APR tracker page when the browser finishes loading the HTML.
Input Params: None
Output: outputs (None)
*/
function startAPRTrackerPage() {
    initAPRTracker().catch(showAPRTrackerPageError);
}

document.addEventListener('DOMContentLoaded', startAPRTrackerPage);
