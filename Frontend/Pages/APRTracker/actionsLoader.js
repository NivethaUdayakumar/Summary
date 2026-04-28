window.APR_BUTTONS = window.APR_BUTTONS || [];
window.APR_ACTION_MENU_STATE = window.APR_ACTION_MENU_STATE || {
    globalEventsBound: false
};

function escapeAPRActionHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function getAPRActionCell(element) {
    return element ? element.closest('td.dt-actions, th.dt-actions') : null;
}

function setAPRActionCellOpenState(cell, isOpen) {
    if (!cell) {
        return;
    }

    cell.classList.toggle('is-menu-open', Boolean(isOpen));
}

function getAPRActionMenuList(menu) {
    return menu ? menu.querySelector('.apr-action-menu-list') : null;
}

function clearAPRActionMenuPosition(menu) {
    var menuList = getAPRActionMenuList(menu);

    if (!menuList) {
        return;
    }

    menuList.style.left = '';
    menuList.style.top = '';
    menuList.style.right = '';
}

function positionAPRActionMenu(menu) {
    var summaryEl;
    var menuList;
    var summaryRect;
    var menuRect;
    var left;
    var top;
    var margin = 8;

    if (!menu || !menu.open) {
        return;
    }

    summaryEl = menu.querySelector('summary');
    menuList = getAPRActionMenuList(menu);
    if (!summaryEl || !menuList) {
        return;
    }

    summaryRect = summaryEl.getBoundingClientRect();
    menuRect = menuList.getBoundingClientRect();

    left = summaryRect.right - menuRect.width;
    top = summaryRect.bottom + 4;

    if (left + menuRect.width > window.innerWidth - margin) {
        left = window.innerWidth - menuRect.width - margin;
    }
    if (left < margin) {
        left = margin;
    }

    if (top + menuRect.height > window.innerHeight - margin) {
        top = summaryRect.top - menuRect.height - 4;
    }
    if (top < margin) {
        top = margin;
    }

    menuList.style.left = Math.round(left) + 'px';
    menuList.style.top = Math.round(top) + 'px';
}

function scheduleAPRActionMenuPosition(menu) {
    window.requestAnimationFrame(function positionAPRActionMenuFrame() {
        positionAPRActionMenu(menu);
    });
}

function closeAPRActionMenu(menu) {
    if (!menu) {
        return;
    }

    menu.open = false;
    setAPRActionCellOpenState(getAPRActionCell(menu), false);
    clearAPRActionMenuPosition(menu);
}

function closeAPRSiblingMenus(tableEl, currentMenu) {
    var menus;
    var index;
    var menu;

    if (!tableEl) {
        return;
    }

    menus = tableEl.querySelectorAll('details.apr-action-menu[open]');
    for (index = 0; index < menus.length; index += 1) {
        menu = menus[index];
        if (menu === currentMenu) {
            continue;
        }

        closeAPRActionMenu(menu);
    }
}

function syncAPRActionMenuState(tableEl, menu) {
    if (!menu) {
        return;
    }

    if (menu.open) {
        closeAPRSiblingMenus(tableEl, menu);
        scheduleAPRActionMenuPosition(menu);
    } else {
        clearAPRActionMenuPosition(menu);
    }

    setAPRActionCellOpenState(getAPRActionCell(menu), menu.open);
}

function closeAPRActionMenusOutside(targetElement) {
    var menus;
    var index;
    var menu;

    menus = document.querySelectorAll('details.apr-action-menu[open]');
    for (index = 0; index < menus.length; index += 1) {
        menu = menus[index];
        if (targetElement && menu.contains(targetElement)) {
            continue;
        }

        closeAPRActionMenu(menu);
    }
}

function handleAPRActionDocumentMouseDown(event) {
    if (event.target.closest('.apr-action-menu')) {
        return;
    }

    closeAPRActionMenusOutside(event.target);
}

function handleAPRActionViewportChange() {
    var menus;
    var index;

    menus = document.querySelectorAll('details.apr-action-menu[open]');
    for (index = 0; index < menus.length; index += 1) {
        scheduleAPRActionMenuPosition(menus[index]);
    }
}

function bindAPRActionGlobalEvents() {
    if (window.APR_ACTION_MENU_STATE.globalEventsBound) {
        return;
    }

    document.addEventListener('mousedown', handleAPRActionDocumentMouseDown, true);
    window.addEventListener('resize', handleAPRActionViewportChange);
    window.addEventListener('scroll', handleAPRActionViewportChange, true);
    window.APR_ACTION_MENU_STATE.globalEventsBound = true;
}

function isAPRActionDisabled(button, row) {
    if (!button) {
        return false;
    }

    if (typeof button.disabled === 'function') {
        try {
            return Boolean(button.disabled(row));
        } catch (error) {
            console.error('APR action disabled check failed for', button.id, error);
            return false;
        }
    }

    return Boolean(button.disabled);
}

function buildAPRActionButtonHtml(button, row, extraClassName) {
    var className = button.className || 'ui mini button';
    var disabled = isAPRActionDisabled(button, row);

    if (extraClassName) {
        className += ' ' + extraClassName;
    }

    return '' +
        '<button type="button" class="' + escapeAPRActionHtml(className) + '" ' +
        'data-apr-action="' + escapeAPRActionHtml(button.id) + '"' +
        (disabled ? ' disabled aria-disabled="true"' : '') +
        '>' +
        escapeAPRActionHtml(button.label) +
        '</button>';
}

function splitAPRActionButtons(buttons) {
    var visibleButtons = [];
    var hiddenButtons = [];
    var index;

    for (index = 0; index < buttons.length; index += 1) {
        if (index < 2) {
            visibleButtons.push(buttons[index]);
            continue;
        }

        hiddenButtons.push(buttons[index]);
    }

    return {
        visibleButtons: visibleButtons,
        hiddenButtons: hiddenButtons
    };
}

function buildAPRVisibleActionButtonsHtml(buttons, row) {
    var html = '';
    var index;

    for (index = 0; index < buttons.length; index += 1) {
        html += buildAPRActionButtonHtml(buttons[index], row, 'apr-action-button');
    }

    return html;
}

function buildAPRHiddenActionButtonsHtml(buttons, row) {
    var html = '';
    var index;

    if (!buttons.length) {
        return html;
    }

    html += '<details class="apr-action-menu">';
    html += '<summary class="ui mini button apr-action-summary">More</summary>';
    html += '<div class="apr-action-menu-list">';

    for (index = 0; index < buttons.length; index += 1) {
        html += buildAPRActionButtonHtml(buttons[index], row, 'apr-action-menu-item');
    }

    html += '</div>';
    html += '</details>';
    return html;
}

function renderAPRActionColumn(data, type, row) {
    var buttons = window.APR_BUTTONS || [];
    var groupedButtons = splitAPRActionButtons(buttons);

    return '' +
        '<div class="apr-action-group">' +
        buildAPRVisibleActionButtonsHtml(groupedButtons.visibleButtons, row) +
        buildAPRHiddenActionButtonsHtml(groupedButtons.hiddenButtons, row) +
        '</div>';
}

function buildAPRActionColumn() {
    return {
        data: null,
        title: 'actions',
        name: 'actions',
        orderable: false,
        searchable: false,
        className: 'dt-actions',
        render: renderAPRActionColumn
    };
}

function getAPRTrackerRowLabel(row) {
    var parts = [];
    var index;
    var fields = [row.Job, row.Milestone, row.Block, row.Stage];

    for (index = 0; index < fields.length; index += 1) {
        if (fields[index]) {
            parts.push(fields[index]);
        }
    }

    return parts.join(' / ');
}

function findAPRActionButton(actionId) {
    var buttons = window.APR_BUTTONS || [];
    var index;

    for (index = 0; index < buttons.length; index += 1) {
        if (buttons[index].id === actionId) {
            return buttons[index];
        }
    }

    return null;
}

function closeAPRActionMenuForElement(actionElement) {
    var menu = actionElement ? actionElement.closest('details') : null;

    closeAPRActionMenu(menu);
}

function handleAPRActionTableClick(event) {
    var tableEl = event.currentTarget;
    var summaryEl = event.target.closest('.apr-action-menu > summary');
    var menuEl;
    var actionEl;
    var actionId;
    var tr;
    var tableBuilder;
    var dt;
    var rowData;
    var button;

    if (summaryEl) {
        event.preventDefault();
        menuEl = summaryEl.parentElement;
        menuEl.open = !menuEl.open;
        syncAPRActionMenuState(tableEl, menuEl);
        return;
    }

    actionEl = event.target.closest('[data-apr-action]');
    if (!actionEl || actionEl.disabled) {
        return;
    }

    actionId = actionEl.getAttribute('data-apr-action');
    tr = actionEl.closest('tr');
    if (!tr) {
        return;
    }

    tableBuilder = tableEl._aprActionTableBuilder;
    if (!tableBuilder) {
        return;
    }

    dt = tableBuilder.getInstance();
    if (!dt) {
        return;
    }

    rowData = dt.row(tr).data();
    if (!rowData) {
        return;
    }

    button = findAPRActionButton(actionId);
    if (isAPRActionDisabled(button, rowData)) {
        return;
    }

    if (button && typeof button.handler === 'function') {
        button.handler(rowData, dt, tr, tableBuilder, actionEl);
    }

    closeAPRActionMenuForElement(actionEl);
}

function bindAPRActionEvents(tableBuilder) {
    var tableEl = document.querySelector(tableBuilder.selector);

    if (!tableEl) {
        return;
    }

    tableEl._aprActionTableBuilder = tableBuilder;

    if (tableEl._aprActionEventsBound) {
        return;
    }

    bindAPRActionGlobalEvents();
    tableEl.addEventListener('click', handleAPRActionTableClick);
    tableEl._aprActionEventsBound = true;
}

window.buildAPRActionColumn = buildAPRActionColumn;
window.getAPRTrackerRowLabel = getAPRTrackerRowLabel;
window.bindAPRActionEvents = bindAPRActionEvents;
