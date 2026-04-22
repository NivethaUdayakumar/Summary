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

function applyAPRTrackerPreset(tableBuilder, presetName) {
    var dt = tableBuilder.getInstance();
    var preset;
    var hiddenColumns;
    var settings;
    var columnCount;
    var index;
    var columnName;

    if (!dt) {
        return;
    }

    preset = window.APR_TRACKER_PRESETS[presetName] || window.APR_TRACKER_PRESETS.default;
    hiddenColumns = preset.hiddenColumns || [];
    settings = dt.settings()[0];
    columnCount = settings.aoColumns.length;

    for (index = 0; index < columnCount; index += 1) {
        columnName = settings.aoColumns[index].name;
        dt.column(index).visible(hiddenColumns.indexOf(columnName) === -1, false);
    }

    dt.columns.adjust().draw(false);
}

window.APR_TRACKER_PRESETS = buildAPRTrackerPresets();
window.applyAPRTrackerPreset = applyAPRTrackerPreset;
