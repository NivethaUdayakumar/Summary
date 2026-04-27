var APR_TRACKER_DB_LOCATION = 'AppData/App.db';
var APR_TRACKER_TABLE_NAME = 'APR_TRACKER';
var APR_TRACKER_PAGE_STATE = window.APR_TRACKER_PAGE_STATE || {
    table: null
};

window.APR_TRACKER_PAGE_STATE = APR_TRACKER_PAGE_STATE;

function createAPRTrackerDropdownConfig(searchType) {
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

function getAPRTrackerListDropdownConfig() {
    return createAPRTrackerDropdownConfig('searchList');
}

function getAPRTrackerDateDropdownConfig() {
    return createAPRTrackerDropdownConfig('searchDateTime');
}

function getAPRTrackerFloatDropdownConfig() {
    return createAPRTrackerDropdownConfig('searchNumber');
}

async function fetchAPRTrackerRows() {
    var response = await fetch('/api/read-table', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            db_location: APR_TRACKER_DB_LOCATION,
            table_name: APR_TRACKER_TABLE_NAME
        })
    });
    var result;

    if (!response.ok) {
        throw new Error('HTTP error ' + response.status);
    }

    result = await response.json();
    if (!result.success) {
        throw new Error(result.error || 'Failed to load table data');
    }

    return result.rows || [];
}

function getAPRTrackerTableBuilder() {
    return APR_TRACKER_PAGE_STATE.table;
}

function getAPRTrackerDataTable() {
    var tableBuilder = getAPRTrackerTableBuilder();

    if (!tableBuilder || !tableBuilder.getInstance()) {
        return null;
    }

    return tableBuilder.getInstance();
}

function getAPRTrackerPresetSelect() {
    return document.getElementById('presetSelect');
}

function getAPRTrackerSelectedPresetName() {
    var presetSelect = getAPRTrackerPresetSelect();
    return presetSelect ? presetSelect.value : 'default';
}

function applyAPRTrackerCurrentPreset() {
    var tableBuilder = getAPRTrackerTableBuilder();

    if (!tableBuilder) {
        return;
    }

    window.applyAPRTrackerPreset(tableBuilder, getAPRTrackerSelectedPresetName());
}

function clearAPRTrackerColumnControlSearches(dt) {
    if (
        dt.columns &&
        dt.columns().columnControl &&
        typeof dt.columns().columnControl.searchClear === 'function'
    ) {
        dt.columns().columnControl.searchClear();
        return;
    }

    if (
        dt.columns &&
        typeof dt.columns().ccSearchClear === 'function'
    ) {
        dt.columns().ccSearchClear();
    }
}

function clearAPRTrackerFilterInputs(wrapper) {
    var inputs;
    var index;
    var input;

    if (!wrapper) {
        return;
    }

    inputs = wrapper.querySelectorAll('input');
    for (index = 0; index < inputs.length; index += 1) {
        input = inputs[index];
        if (
            input.type === 'search' ||
            input.type === 'text' ||
            input.type === 'number' ||
            input.type === 'date'
        ) {
            input.value = '';
        }
    }
}

function clearAPRTrackerFilterSelects(wrapper) {
    var selects;
    var index;

    if (!wrapper) {
        return;
    }

    selects = wrapper.querySelectorAll('select');
    for (index = 0; index < selects.length; index += 1) {
        selects[index].selectedIndex = 0;
    }
}

function clearAllAPRTrackerAppliedFilters() {
    var dt = getAPRTrackerDataTable();
    var wrapper;

    if (!dt) {
        return;
    }

    dt.search('');
    dt.columns().search('');
    clearAPRTrackerColumnControlSearches(dt);

    if (dt.state && typeof dt.state.clear === 'function') {
        dt.state.clear();
    }

    wrapper = dt.table().container();
    clearAPRTrackerFilterInputs(wrapper);
    clearAPRTrackerFilterSelects(wrapper);

    dt.draw();
    applyAPRTrackerCurrentPreset();
}

function handleAPRTrackerPresetChange() {
    applyAPRTrackerCurrentPreset();
}

function handleAPRTrackerClearFiltersClick() {
    clearAllAPRTrackerAppliedFilters();
}

async function reloadAPRTrackerTableRows() {
    var rows = await fetchAPRTrackerRows();
    var tableBuilder = getAPRTrackerTableBuilder();

    if (!tableBuilder) {
        return;
    }

    await tableBuilder.reload(rows);
    applyAPRTrackerCurrentPreset();
}

function handleAPRTrackerPageError(error) {
    console.error(error);
    alert(error.message);
}

function handleAPRTrackerReloadClick() {
    reloadAPRTrackerTableRows().catch(handleAPRTrackerPageError);
}

function bindAPRTrackerToolbar() {
    var presetSelect = getAPRTrackerPresetSelect();
    var clearFiltersButton = document.getElementById('clearFiltersBtn');
    var reloadButton = document.getElementById('reloadTableBtn');

    if (presetSelect && !presetSelect._aprBound) {
        presetSelect.addEventListener('change', handleAPRTrackerPresetChange);
        presetSelect._aprBound = true;
    }

    if (clearFiltersButton && !clearFiltersButton._aprBound) {
        clearFiltersButton.addEventListener('click', handleAPRTrackerClearFiltersClick);
        clearFiltersButton._aprBound = true;
    }

    if (reloadButton && !reloadButton._aprBound) {
        reloadButton.addEventListener('click', handleAPRTrackerReloadClick);
        reloadButton._aprBound = true;
    }
}

function handleAPRTrackerTableAfterInit(dt, builder) {
    window.bindAPRActionEvents(builder);
}

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
                getAPRTrackerListDropdownConfig(),
                getAPRTrackerDateDropdownConfig(),
                getAPRTrackerFloatDropdownConfig()
            )
        },
        extensions: {
            afterInit: handleAPRTrackerTableAfterInit
        }
    });
}

async function initAPRTracker() {
    var rows = await fetchAPRTrackerRows();

    APR_TRACKER_PAGE_STATE.table = createAPRTrackerTable(rows);
    await APR_TRACKER_PAGE_STATE.table.render();
    bindAPRTrackerToolbar();
    window.applyAPRTrackerPreset(APR_TRACKER_PAGE_STATE.table, 'default');
}

function handleAPRTrackerDOMContentLoaded() {
    initAPRTracker().catch(handleAPRTrackerPageError);
}

document.addEventListener('DOMContentLoaded', handleAPRTrackerDOMContentLoaded);
