/*
Function Name: buildAPRTrackerPresets
Purpose: Build the small preset list that decides which columns stay visible.
Input Params: None
Output: presets (dict)
*/
function buildAPRTrackerPresets() {
    var kpiColumns = (window.APR_TRACKER_KPI_COLUMNS || []).slice();

    return {
        default: {
            hiddenColumns: []
        },
        trackerOnly: {
            hiddenColumns: kpiColumns
        },
        kpiFocus: {
            hiddenColumns: ['Dft_release', 'User', 'Created', 'Modified', 'Comments', 'Promote']
        }
    };
}

/*
Function Name: applyAPRTrackerPreset
Purpose: Show or hide APR tracker columns based on the selected preset.
Input Params: tableBuilder (TableBuilder), presetName (str)
Output: outputs (None)
*/
function applyAPRTrackerPreset(tableBuilder, presetName) {
    var dataTable = tableBuilder ? tableBuilder.getInstance() : null;
    var preset = window.APR_TRACKER_PRESETS[presetName] || window.APR_TRACKER_PRESETS.default;
    var hiddenColumns = preset.hiddenColumns || [];
    var tableSettings;
    var columnCount;
    var index;
    var columnName;

    if (!dataTable) {
        return;
    }

    tableSettings = dataTable.settings()[0];
    columnCount = tableSettings.aoColumns.length;

    for (index = 0; index < columnCount; index += 1) {
        columnName = tableSettings.aoColumns[index].name;
        dataTable.column(index).visible(hiddenColumns.indexOf(columnName) === -1, false);
    }

    dataTable.columns.adjust().draw(false);
}

window.APR_TRACKER_PRESETS = buildAPRTrackerPresets();
window.applyAPRTrackerPreset = applyAPRTrackerPreset;
