(function () {
    window.APR_TRACKER_PRESETS = {
        default: {
            hiddenColumns: []
        },
        hideOwner: {
            hiddenColumns: ['owner']
        },
        hideName: {
            hiddenColumns: ['workstream']
        }
    };

    window.applyAPRTrackerPreset = function (tableBuilder, presetName) {
        var dt = tableBuilder.getInstance();
        if (!dt) return;

        var preset = window.APR_TRACKER_PRESETS[presetName] || window.APR_TRACKER_PRESETS.default;
        var hiddenColumns = preset.hiddenColumns || [];

        dt.columns().every(function (index) {
            var columnName = this.settings()[0].aoColumns[index].name;
            this.visible(hiddenColumns.indexOf(columnName) === -1, false);
        });

        dt.columns.adjust().draw(false);
    };
})();