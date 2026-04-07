(function () {
    var APR_TRACKER_DB_LOCATION = 'AppData/App.db';
    var APR_TRACKER_TABLE_NAME = 'apr-tracker';

    var table = null;

    var listDropdown = {
        extend: 'dropdown',
        content: [
            'searchList',
            'spacer',
            'orderAsc',
            'orderDesc',
            'orderClear'
        ]
    };

    var dateDropdown = {
        extend: 'dropdown',
        content: [
            'searchDateTime',
            'spacer',
            'orderAsc',
            'orderDesc',
            'orderClear'
        ]
    };

    var floatDropdown = {
        extend: 'dropdown',
        content: [
            'searchNumber',
            'spacer',
            'orderAsc',
            'orderDesc',
            'orderClear'
        ]
    };

    function ensureSemanticDropdown() {
        if (window.jQuery && window.jQuery.fn && typeof window.jQuery.fn.dropdown === 'function') {
            window.jQuery('.ui.dropdown').dropdown();
        }
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

        if (!response.ok) {
            throw new Error('HTTP error ' + response.status);
        }

        var result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to load table data');
        }

        return result.rows || [];
    }

    function clearAllAppliedFilters() {
        if (!table || !table.getInstance()) return;

        var dt = table.getInstance();

        // Clear global search
        dt.search('');

        // Clear normal per-column searches
        dt.columns().search('');

        // Clear ColumnControl searches such as searchList, searchText, date, float, etc
        if (
            dt.columns &&
            dt.columns().columnControl &&
            typeof dt.columns().columnControl.searchClear === 'function'
        ) {
            dt.columns().columnControl.searchClear();
        }
        // Fallback for older/alias API
        else if (
            dt.columns &&
            typeof dt.columns().ccSearchClear === 'function'
        ) {
            dt.columns().ccSearchClear();
        }

        // Optional: reset ordering too
        // dt.order([]);

        // Clear saved state so filters do not come back after reload
        if (dt.state && typeof dt.state.clear === 'function') {
            dt.state.clear();
        }

        // Clear visible search inputs/selects in the wrapper
        var wrapper = dt.table().container();

        wrapper.querySelectorAll('input').forEach(function (input) {
            if (
                input.type === 'search' ||
                input.type === 'text' ||
                input.type === 'number' ||
                input.type === 'date'
            ) {
                input.value = '';
            }
        });

        wrapper.querySelectorAll('select').forEach(function (select) {
            select.selectedIndex = 0;
        });

        // Redraw once at the end
        dt.draw();
        window.applyAPRTrackerPreset(table, document.getElementById('presetSelect').value);
        ensureSemanticDropdown();
        window.initAPRActionDropdowns();
    }

    function bindToolbar() {
        var presetSelect = document.getElementById('presetSelect');
        var clearFiltersBtn = document.getElementById('clearFiltersBtn');
        var reloadTableBtn = document.getElementById('reloadTableBtn');

        if (presetSelect) {
            presetSelect.addEventListener('change', function () {
                window.applyAPRTrackerPreset(table, this.value);
            });
        }

        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', function () {
                clearAllAppliedFilters();
            });
        }

        if (reloadTableBtn) {
            reloadTableBtn.addEventListener('click', async function () {
                try {
                    var rows = await fetchAPRTrackerRows();
                    await table.reload(rows);
                    window.applyAPRTrackerPreset(table, document.getElementById('presetSelect').value);
                    ensureSemanticDropdown();
                    window.initAPRActionDropdowns();
                } catch (error) {
                    console.error(error);
                    alert(error.message);
                }
            });
        }
    }

    async function initAPRTracker() {
        ensureSemanticDropdown();

        var rows = await fetchAPRTrackerRows();

        table = new TableBuilder({
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
                order: [[0, 'asc']],
                autoWidth: true,
                responsive: false,
                stateSave: true,
                scrollX: true,
                fixedColumns: {
                    left: 1
                },
                columnDefs: window.getAPRTrackerColumnDefs(listDropdown, dateDropdown, floatDropdown)
            },
            extensions: {
                afterInit: function (dt, builder) {
                    window.bindAPRActionEvents(builder);
                    ensureSemanticDropdown();
                    window.initAPRActionDropdowns();
                }
            }
        });

        await table.render();
        bindToolbar();
        window.applyAPRTrackerPreset(table, 'default');
        ensureSemanticDropdown();
        window.initAPRActionDropdowns();
    }

    document.addEventListener('DOMContentLoaded', function () {
        initAPRTracker().catch(function (error) {
            console.error(error);
            alert(error.message);
        });
    });
})();