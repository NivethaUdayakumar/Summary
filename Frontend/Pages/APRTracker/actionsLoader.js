(function () {
    window.APR_BUTTONS = window.APR_BUTTONS || [];

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    window.buildAPRActionColumn = function () {
        return {
            data: null,
            title: 'actions',
            name: 'actions',
            orderable: false,
            searchable: false,
            className: 'dt-actions',
            render: function (data, type, row) {
                var buttons = window.APR_BUTTONS || [];
                var visibleButtons = buttons.slice(0, 2);
                var hiddenButtons = buttons.slice(2);

                var html = '';

                visibleButtons.forEach(function (btn) {
                    html +=
                        '<button class="' + escapeHtml(btn.className || 'ui mini button') + '" ' +
                        'data-apr-action="' + escapeHtml(btn.id) + '">' +
                        escapeHtml(btn.label) +
                        '</button>';
                });

                if (hiddenButtons.length > 0) {
                    html += '<div class="ui floating dropdown mini button">';
                    html += 'More';
                    html += '<div class="menu">';

                    hiddenButtons.forEach(function (btn) {
                        html +=
                            '<div class="item" data-apr-action="' + escapeHtml(btn.id) + '">' +
                            escapeHtml(btn.label) +
                            '</div>';
                    });

                    html += '</div>';
                    html += '</div>';
                }

                return html;
            }
        };
    };

    window.bindAPRActionEvents = function (tableBuilder) {
        var tableEl = document.querySelector(tableBuilder.selector);
        if (!tableEl) return;

        tableEl.addEventListener('click', function (event) {
            var actionEl = event.target.closest('[data-apr-action]');
            if (!actionEl) return;

            var actionId = actionEl.getAttribute('data-apr-action');
            var tr = actionEl.closest('tr');
            if (!tr) return;

            var dt = tableBuilder.getInstance();
            if (!dt) return;

            var rowData = dt.row(tr).data();
            if (!rowData) return;

            var button = (window.APR_BUTTONS || []).find(function (b) {
                return b.id === actionId;
            });

            if (button && typeof button.handler === 'function') {
                button.handler(rowData, dt, tr, tableBuilder);
            }
        });
    };

    window.initAPRActionDropdowns = function () {
        if (window.jQuery && window.jQuery.fn && typeof window.jQuery.fn.dropdown === 'function') {
            window.jQuery('.dt-actions .ui.dropdown').dropdown();
        }
    };
})();