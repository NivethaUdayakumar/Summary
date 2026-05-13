window.APR_BUTTONS = window.APR_BUTTONS || [];

/*
Function Name: escapeAPRActionHtml
Purpose: Safely escape button text before it is placed inside HTML strings.
Input Params: value (any)
Output: escaped_value (str)
*/
function escapeAPRActionHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/*
Function Name: getAPRActionButtons
Purpose: Return the shared APR action-button list and create it if needed.
Input Params: None
Output: buttons (list[dict])
*/
function getAPRActionButtons() {
    if (!Array.isArray(window.APR_BUTTONS)) {
        window.APR_BUTTONS = [];
    }

    return window.APR_BUTTONS;
}

/*
Function Name: registerAPRButton
Purpose: Add one APR action-button config only once so button files can stay very small.
Input Params: buttonConfig (dict)
Output: outputs (None)
*/
function registerAPRButton(buttonConfig) {
    var buttons = getAPRActionButtons();
    var index;

    if (!buttonConfig || !buttonConfig.id) {
        return;
    }

    for (index = 0; index < buttons.length; index += 1) {
        if (buttons[index] && buttons[index].id === buttonConfig.id) {
            return;
        }
    }

    buttons.push(buttonConfig);
}

/*
Function Name: isAPRActionDisabled
Purpose: Decide whether one APR action button should be disabled for the current row.
Input Params: button (dict), row (dict)
Output: is_disabled (bool)
*/
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

/*
Function Name: buildAPRActionIconHtml
Purpose: Build the optional Semantic UI icon HTML for one APR action button.
Input Params: button (dict)
Output: icon_html (str)
*/
function buildAPRActionIconHtml(button) {
    var iconName;

    if (!button || !button.icon) {
        return '';
    }

    iconName = String(button.icon).trim();
    if (!iconName) {
        return '';
    }

    return '<i class="' + escapeAPRActionHtml(iconName + ' icon') + '"></i>';
}

/*
Function Name: buildAPRActionButtonHtml
Purpose: Build the button HTML for one APR tracker action with optional icon support.
Input Params: button (dict), row (dict), extraClassName (str)
Output: button_html (str)
*/
function buildAPRActionButtonHtml(button, row, extraClassName) {
    var className = button.className || 'ui mini button';
    var disabled = isAPRActionDisabled(button, row);
    var titleText = String(button.title || button.label || button.id || 'Action');
    var content = buildAPRActionIconHtml(button);

    if (extraClassName) {
        className += ' ' + extraClassName;
    }

    if (button.icon && !button.label && className.indexOf(' icon') === -1) {
        className += ' icon';
    }

    if (button.label) {
        content += '<span>' + escapeAPRActionHtml(button.label) + '</span>';
    }

    if (!content) {
        content = escapeAPRActionHtml(titleText);
    }

    return '' +
        '<button type="button" class="' + escapeAPRActionHtml(className) + '" ' +
        'data-apr-action="' + escapeAPRActionHtml(button.id) + '" ' +
        'title="' + escapeAPRActionHtml(titleText) + '" ' +
        'aria-label="' + escapeAPRActionHtml(titleText) + '"' +
        (disabled ? ' disabled aria-disabled="true"' : '') +
        '>' +
        content +
        '</button>';
}

/*
Function Name: splitAPRActionButtons
Purpose: Keep the first two APR actions visible and move the rest behind the More button.
Input Params: buttons (list[dict])
Output: grouped_buttons (dict)
*/
function splitAPRActionButtons(buttons) {
    return {
        visibleButtons: buttons.slice(0, 2),
        hiddenButtons: buttons.slice(2)
    };
}

/*
Function Name: buildAPRActionButtonsHtml
Purpose: Build a flat string of APR action buttons for one row.
Input Params: buttons (list[dict]), row (dict), extraClassName (str)
Output: buttons_html (str)
*/
function buildAPRActionButtonsHtml(buttons, row, extraClassName) {
    var html = '';
    var index;

    for (index = 0; index < buttons.length; index += 1) {
        html += buildAPRActionButtonHtml(buttons[index], row, extraClassName);
    }

    return html;
}

/*
Function Name: buildAPRMoreButtonHtml
Purpose: Build the simple More button that will show hidden action names in an alert.
Input Params: buttons (list[dict])
Output: button_html (str)
*/
function buildAPRMoreButtonHtml(buttons) {
    if (!buttons.length) {
        return '';
    }

    return '' +
        '<button type="button" class="ui mini button apr-action-more-button" ' +
        'data-apr-more-actions="true" title="More actions" aria-label="More actions">' +
        '<i class="ellipsis horizontal icon"></i>More' +
        '</button>';
}

/*
Function Name: renderAPRActionColumn
Purpose: Render the APR tracker action column for one table row.
Input Params: data (any), type (str), row (dict)
Output: column_html (str)
*/
function renderAPRActionColumn(data, type, row) {
    var groupedButtons = splitAPRActionButtons(getAPRActionButtons());

    return '' +
        '<div class="apr-action-group">' +
        buildAPRActionButtonsHtml(groupedButtons.visibleButtons, row, 'apr-action-button') +
        buildAPRMoreButtonHtml(groupedButtons.hiddenButtons) +
        '</div>';
}

/*
Function Name: buildAPRActionColumn
Purpose: Build the DataTables column config for the APR action column.
Input Params: None
Output: column_config (dict)
*/
function buildAPRActionColumn() {
    return {
        data: null,
        title: 'Actions',
        name: 'actions',
        orderable: false,
        searchable: false,
        className: 'dt-actions',
        render: renderAPRActionColumn
    };
}

/*
Function Name: getAPRTrackerRowLabel
Purpose: Build a short human-readable label for one APR tracker row.
Input Params: row (dict)
Output: label (str)
*/
function getAPRTrackerRowLabel(row) {
    var fields = [row.Job, row.Milestone, row.Block, row.Stage];
    var parts = [];
    var index;

    for (index = 0; index < fields.length; index += 1) {
        if (fields[index]) {
            parts.push(fields[index]);
        }
    }

    return parts.join(' / ');
}

/*
Function Name: findAPRActionButton
Purpose: Find one APR button config by its action id.
Input Params: actionId (str)
Output: button (dict | null)
*/
function findAPRActionButton(actionId) {
    var buttons = getAPRActionButtons();
    var index;

    for (index = 0; index < buttons.length; index += 1) {
        if (buttons[index] && buttons[index].id === actionId) {
            return buttons[index];
        }
    }

    return null;
}

/*
Function Name: getAPRActionRowContext
Purpose: Read the current DataTable row information that belongs to a clicked APR action button.
Input Params: tableElement (HTMLElement), actionElement (HTMLElement)
Output: row_context (dict | null)
*/
function getAPRActionRowContext(tableElement, actionElement) {
    var tableBuilder = tableElement ? tableElement._aprActionTableBuilder : null;
    var dataTable = tableBuilder && tableBuilder.getInstance ? tableBuilder.getInstance() : null;
    var rowElement = actionElement ? actionElement.closest('tr') : null;
    var rowData;

    if (!dataTable || !rowElement) {
        return null;
    }

    rowData = dataTable.row(rowElement).data();
    if (!rowData) {
        return null;
    }

    return {
        dataTable: dataTable,
        rowData: rowData,
        rowElement: rowElement,
        tableBuilder: tableBuilder
    };
}

/*
Function Name: getAPRHiddenActionButtons
Purpose: Return the action buttons that should appear after the More button is clicked.
Input Params: None
Output: hidden_buttons (list[dict])
*/
function getAPRHiddenActionButtons() {
    return splitAPRActionButtons(getAPRActionButtons()).hiddenButtons;
}

/*
Function Name: buildAPRMoreActionsAlertText
Purpose: Build the alert text that lists the hidden action buttons for one APR row.
Input Params: rowData (dict), hiddenButtons (list[dict])
Output: alert_text (str)
*/
function buildAPRMoreActionsAlertText(rowData, hiddenButtons) {
    var lines = ['More actions for: ' + getAPRTrackerRowLabel(rowData)];
    var index;
    var button;
    var label;

    lines.push('');
    for (index = 0; index < hiddenButtons.length; index += 1) {
        button = hiddenButtons[index];
        label = String(button.label || button.id || ('Action ' + (index + 1)));

        if (isAPRActionDisabled(button, rowData)) {
            label += ' (disabled)';
        }

        lines.push((index + 1) + '. ' + label);
    }

    lines.push('');
    lines.push('Enter the action number in the next prompt.');
    return lines.join('\n');
}

/*
Function Name: pickAPRMoreActionButton
Purpose: Ask the user which hidden APR action button should run.
Input Params: rowData (dict), hiddenButtons (list[dict])
Output: selected_button (dict | null)
*/
function pickAPRMoreActionButton(rowData, hiddenButtons) {
    var answer;
    var selectedIndex;

    window.alert(buildAPRMoreActionsAlertText(rowData, hiddenButtons));
    answer = window.prompt('Choose a More action number:', '');

    if (answer == null || String(answer).trim() === '') {
        return null;
    }

    selectedIndex = Number(String(answer).trim()) - 1;
    if (String(selectedIndex) === 'NaN' || selectedIndex < 0 || selectedIndex >= hiddenButtons.length) {
        window.alert('Invalid More action number.');
        return null;
    }

    return hiddenButtons[selectedIndex];
}

/*
Function Name: runAPRActionButton
Purpose: Run one APR action button handler after disabled checks are complete.
Input Params: button (dict), rowContext (dict), actionElement (HTMLElement | null)
Output: outputs (None)
*/
function runAPRActionButton(button, rowContext, actionElement) {
    if (!button || !rowContext) {
        return;
    }

    if (isAPRActionDisabled(button, rowContext.rowData)) {
        window.alert((button.label || button.id || 'This action') + ' is disabled for this row.');
        return;
    }

    if (typeof button.handler === 'function') {
        button.handler(
            rowContext.rowData,
            rowContext.dataTable,
            rowContext.rowElement,
            rowContext.tableBuilder,
            actionElement
        );
    }
}

/*
Function Name: handleAPRMoreActionsClick
Purpose: Show the hidden APR action buttons in an alert and let the user choose one.
Input Params: rowContext (dict), actionElement (HTMLElement)
Output: outputs (None)
*/
function handleAPRMoreActionsClick(rowContext, actionElement) {
    var hiddenButtons = getAPRHiddenActionButtons();
    var selectedButton;

    if (!hiddenButtons.length) {
        return;
    }

    selectedButton = pickAPRMoreActionButton(rowContext.rowData, hiddenButtons);
    runAPRActionButton(selectedButton, rowContext, actionElement);
}

/*
Function Name: handleAPRActionTableClick
Purpose: Handle APR row action clicks, including the simple More alert flow.
Input Params: event (MouseEvent)
Output: outputs (None)
*/
function handleAPRActionTableClick(event) {
    var tableElement = event.currentTarget;
    var actionElement = event.target.closest('[data-apr-action], [data-apr-more-actions]');
    var rowContext;
    var button;

    if (!actionElement || actionElement.disabled) {
        return;
    }

    rowContext = getAPRActionRowContext(tableElement, actionElement);
    if (!rowContext) {
        return;
    }

    if (actionElement.hasAttribute('data-apr-more-actions')) {
        handleAPRMoreActionsClick(rowContext, actionElement);
        return;
    }

    button = findAPRActionButton(actionElement.getAttribute('data-apr-action'));
    runAPRActionButton(button, rowContext, actionElement);
}

/*
Function Name: bindAPRActionEvents
Purpose: Attach the APR action click handler to the tracker table once.
Input Params: tableBuilder (TableBuilder)
Output: outputs (None)
*/
function bindAPRActionEvents(tableBuilder) {
    var tableElement = document.querySelector(tableBuilder.selector);

    if (!tableElement) {
        return;
    }

    tableElement._aprActionTableBuilder = tableBuilder;

    if (tableElement._aprActionEventsBound) {
        return;
    }

    tableElement.addEventListener('click', handleAPRActionTableClick);
    tableElement._aprActionEventsBound = true;
}

window.buildAPRActionColumn = buildAPRActionColumn;
window.getAPRTrackerRowLabel = getAPRTrackerRowLabel;
window.bindAPRActionEvents = bindAPRActionEvents;
window.registerAPRButton = registerAPRButton;
