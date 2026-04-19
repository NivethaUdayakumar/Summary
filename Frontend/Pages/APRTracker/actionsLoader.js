(function () {
    window.APR_BUTTONS = window.APR_BUTTONS || [];

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function getActionCell(element) {
        return element ? element.closest('td.dt-actions, th.dt-actions') : null;
    }

    function setActionCellOpenState(cell, isOpen) {
        if (!cell) return;
        cell.classList.toggle('is-menu-open', Boolean(isOpen));
    }

    function closeSiblingMenus(tableEl, currentMenu) {
        tableEl.querySelectorAll('details.apr-action-menu[open]').forEach(function (menu) {
            if (menu === currentMenu) return;
            menu.open = false;
            setActionCellOpenState(getActionCell(menu), false);
        });
    }

    function syncActionMenuState(tableEl, menu) {
        if (!menu) return;

        if (menu.open) {
            closeSiblingMenus(tableEl, menu);
        }

        setActionCellOpenState(getActionCell(menu), menu.open);
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
                    html += '<details class="apr-action-menu">';
                    html += '<summary class="ui mini button">More</summary>';
                    html += '<div class="apr-action-menu-list">';

                    hiddenButtons.forEach(function (btn) {
                        html +=
                            '<button type="button" class="ui mini button apr-action-menu-item" data-apr-action="' + escapeHtml(btn.id) + '">' +
                            escapeHtml(btn.label) +
                            '</button>';
                    });

                    html += '</div>';
                    html += '</details>';
                }

                return html;
            }
        };
    };

    window.getAPRTrackerRowLabel = function (row) {
        return [row.Job, row.Milestone, row.Block, row.Stage]
            .filter(function (value) {
                return value;
            })
            .join(' / ');
    };

    window.bindAPRActionEvents = function (tableBuilder) {
        var tableEl = document.querySelector(tableBuilder.selector);
        if (!tableEl) return;

        tableEl.addEventListener('click', function (event) {
            var summaryEl = event.target.closest('.apr-action-menu > summary');
            if (summaryEl) {
                var summaryMenu = summaryEl.parentElement;
                window.requestAnimationFrame(function () {
                    syncActionMenuState(tableEl, summaryMenu);
                });
                return;
            }

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

            var menu = actionEl.closest('details');
            if (menu) {
                menu.open = false;
                setActionCellOpenState(getActionCell(menu), false);
            }
        });
    };
})();
