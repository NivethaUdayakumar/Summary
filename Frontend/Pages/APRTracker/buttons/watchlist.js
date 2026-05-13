var APR_WATCHLIST_ADDER_WINDOW_NAME = 'apr-watchlist-adder';
var APR_WATCHLIST_MANAGER_WINDOW_NAME = 'apr-watchlist-manager';
var APR_WATCHLIST_WINDOW_FEATURES = 'popup=yes,width=1180,height=820,resizable=yes,scrollbars=yes';
var APR_WATCHLIST_ADDER_URL = '/static/Pages/APRWatchlistAdder/APRWatchlistAdder.html';
var APR_WATCHLIST_MANAGER_URL = '/static/Pages/APRWatchlistManager/APRWatchlistManager.html';
var APR_WATCHLIST_ALLOWED_STAGES = ['place', 'route', 'clock'];
var APR_WATCHLIST_STORAGE_PREFIX = 'apr-watchlist-row:';
var APR_WATCHLIST_TRACKER_FIELDS = [
    'Job',
    'Milestone',
    'Block',
    'Stage',
    'Dft_release',
    'User',
    'Status',
    'Comments',
    'Promote'
];

/*
Function Name: cloneAprWatchlistRow
Purpose: Make a safe copy of one APR tracker row before it is saved in local storage.
Input Params: row (dict)
Output: cloned_row (dict | null)
*/
function cloneAprWatchlistRow(row) {
    if (!row || typeof row !== 'object') {
        return null;
    }

    return Object.assign({}, row);
}

/*
Function Name: isAprWatchlistEligibleRow
Purpose: Check whether one APR row is allowed to be added into the watchlist flow.
Input Params: row (dict)
Output: is_eligible (bool)
*/
function isAprWatchlistEligibleRow(row) {
    var normalizedStatus = String((row && row.Status) || '').trim().toLowerCase();
    var normalizedStage = String((row && row.Stage) || '').trim().toLowerCase();

    return normalizedStatus === 'completed' &&
        APR_WATCHLIST_ALLOWED_STAGES.indexOf(normalizedStage) !== -1;
}

/*
Function Name: normalizeAprWatchlistRun
Purpose: Keep only the tracker fields that the watchlist popup needs and normalize them into strings.
Input Params: row (dict)
Output: normalized_run (dict)
*/
function normalizeAprWatchlistRun(row) {
    var sourceRow = row && typeof row === 'object' ? row : {};
    var normalizedRun = {};
    var index;
    var fieldName;
    var fieldValue;

    for (index = 0; index < APR_WATCHLIST_TRACKER_FIELDS.length; index += 1) {
        fieldName = APR_WATCHLIST_TRACKER_FIELDS[index];
        fieldValue = sourceRow[fieldName];
        normalizedRun[fieldName] = fieldValue == null ? '' : String(fieldValue).trim();
    }

    if (!normalizedRun.Job || !normalizedRun.Milestone || !normalizedRun.Block || !normalizedRun.Stage) {
        throw new Error('Run must include Job, Milestone, Block, and Stage.');
    }

    return normalizedRun;
}

/*
Function Name: canAddAprWatchlistRun
Purpose: Decide whether the Watchlist button should be enabled for one APR row.
Input Params: row (dict)
Output: can_add (bool)
*/
function canAddAprWatchlistRun(row) {
    if (!isAprWatchlistEligibleRow(row)) {
        return false;
    }

    try {
        normalizeAprWatchlistRun(row);
        return true;
    } catch (error) {
        return false;
    }
}

/*
Function Name: buildAprWatchlistWindowUrl
Purpose: Add query-string values to one watchlist popup URL.
Input Params: baseUrl (str), queryParams (dict)
Output: full_url (str)
*/
function buildAprWatchlistWindowUrl(baseUrl, queryParams) {
    var url = new URL(baseUrl, window.location.origin);
    var key;

    for (key in queryParams || {}) {
        if (Object.prototype.hasOwnProperty.call(queryParams, key) && queryParams[key]) {
            url.searchParams.set(key, queryParams[key]);
        }
    }

    return url.toString();
}

/*
Function Name: openAprWatchlistWindow
Purpose: Open one watchlist popup window and show an alert if the browser blocks it.
Input Params: url (str), windowName (str)
Output: popup_window (Window | null)
*/
function openAprWatchlistWindow(url, windowName) {
    var popupWindow = window.open(url, windowName, APR_WATCHLIST_WINDOW_FEATURES);

    if (!popupWindow) {
        window.alert('Unable to open the APR Watchlist window. Please allow pop-ups for this site.');
        return null;
    }

    popupWindow.focus();
    return popupWindow;
}

/*
Function Name: storeAprWatchlistRun
Purpose: Save one APR row in local storage and return the token that the popup will read.
Input Params: row (dict)
Output: run_token (str)
*/
function storeAprWatchlistRun(row) {
    var runToken = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    var storageKey = APR_WATCHLIST_STORAGE_PREFIX + runToken;

    window.localStorage.setItem(storageKey, JSON.stringify(cloneAprWatchlistRow(row)));
    return runToken;
}

/*
Function Name: openAprWatchlistAdder
Purpose: Open the quick-add watchlist popup for one eligible APR row.
Input Params: row (dict)
Output: popup_window (Window | null)
*/
function openAprWatchlistAdder(row) {
    var runToken;
    var url;

    if (!canAddAprWatchlistRun(row)) {
        window.alert('Only Completed PLACE, ROUTE, or CLOCK runs can be added to a watchlist.');
        return null;
    }

    try {
        runToken = storeAprWatchlistRun(row);
    } catch (error) {
        window.alert('Unable to prepare the selected run for watchlist add.');
        return null;
    }

    url = buildAprWatchlistWindowUrl(APR_WATCHLIST_ADDER_URL, { run_token: runToken });
    return openAprWatchlistWindow(url, APR_WATCHLIST_ADDER_WINDOW_NAME);
}

/*
Function Name: openAprWatchlistManager
Purpose: Open the APR Watchlist Manager popup window.
Input Params: None
Output: popup_window (Window | null)
*/
function openAprWatchlistManager() {
    return openAprWatchlistWindow(APR_WATCHLIST_MANAGER_URL, APR_WATCHLIST_MANAGER_WINDOW_NAME);
}

/*
Function Name: openAprWatchlistQuickAddAction
Purpose: Run the Watchlist action from the APR tracker row button.
Input Params: row (dict)
Output: outputs (None)
*/
function openAprWatchlistQuickAddAction(row) {
    openAprWatchlistAdder(row);
}

/*
Function Name: isAprWatchlistButtonDisabled
Purpose: Disable the Watchlist action when the APR row is not eligible.
Input Params: row (dict)
Output: is_disabled (bool)
*/
function isAprWatchlistButtonDisabled(row) {
    return !isAprWatchlistEligibleRow(row);
}

/*
Function Name: registerAprWatchlistButton
Purpose: Register the Watchlist action button on the APR tracker page.
Input Params: None
Output: outputs (None)
*/
function registerAprWatchlistButton() {
    window.registerAPRButton({
        id: 'watchlist',
        label: 'Watchlist',
        icon: 'bookmark',
        className: 'ui mini button',
        disabled: isAprWatchlistButtonDisabled,
        handler: openAprWatchlistQuickAddAction
    });
}

window.openAprWatchlistManager = openAprWatchlistManager;
window.openAprWatchlistAdder = openAprWatchlistAdder;

registerAprWatchlistButton();
