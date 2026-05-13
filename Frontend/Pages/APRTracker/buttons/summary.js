var APR_TIMING_VIEWER_WINDOW_FEATURES = 'popup=yes,width=1320,height=860,resizable=yes,scrollbars=yes';
var APR_TIMING_VIEWER_PAGE_URL = '/static/Pages/APRTimingTable/APRTimingTable.html';
var APR_TIMING_SUMMARY_TABLE_NAME = 'APR_TIMING_SUMMARY';

/*
Function Name: buildAPRTimingDbPath
Purpose: Build the absolute timing database path for one APR tracker row.
Input Params: projectCode (str), row (dict)
Output: db_path (str)
*/
function buildAPRTimingDbPath(projectCode, row) {
    return '/proj/' +
        String(projectCode || '').trim() +
        '/DashAI/APR_RUNS/' +
        String((row && row.Block) || '').trim() +
        '/' +
        String((row && row.Milestone) || '').trim() +
        '/' +
        String((row && row.Job) || '').trim() +
        '/' +
        String((row && row.Stage) || '').trim() +
        '_timing.db';
}

/*
Function Name: getAPRTimingViewerProjectCode
Purpose: Read the current APR tracker project code before opening a timing popup.
Input Params: None
Output: project_code (str)
*/
function getAPRTimingViewerProjectCode() {
    if (window.APR_TRACKER_PAGE && window.APR_TRACKER_PAGE.projectCode) {
        return String(window.APR_TRACKER_PAGE.projectCode).trim();
    }

    return '';
}

/*
Function Name: canOpenAPRTimingViewer
Purpose: Check whether one APR tracker row has enough information to build the timing database path.
Input Params: row (dict)
Output: can_open (bool)
*/
function canOpenAPRTimingViewer(row) {
    var projectCode = getAPRTimingViewerProjectCode();

    return Boolean(
        projectCode &&
        row &&
        String(row.Block || '').trim() &&
        String(row.Milestone || '').trim() &&
        String(row.Job || '').trim() &&
        String(row.Stage || '').trim()
    );
}

/*
Function Name: buildAPRTimingViewerUrl
Purpose: Build the popup URL for the APR timing table viewer page.
Input Params: projectCode (str), row (dict), tableName (str), titleText (str)
Output: popup_url (str)
*/
function buildAPRTimingViewerUrl(projectCode, row, tableName, titleText) {
    var url = new URL(APR_TIMING_VIEWER_PAGE_URL, window.location.origin);

    url.searchParams.set('db_path', buildAPRTimingDbPath(projectCode, row));
    url.searchParams.set('table_name', tableName);
    url.searchParams.set('title', titleText);
    url.searchParams.set('job', String((row && row.Job) || '').trim());
    url.searchParams.set('milestone', String((row && row.Milestone) || '').trim());
    url.searchParams.set('block', String((row && row.Block) || '').trim());
    url.searchParams.set('stage', String((row && row.Stage) || '').trim());
    return url.toString();
}

/*
Function Name: openAPRTimingTableViewer
Purpose: Open the timing table popup for one APR tracker row and chosen timing table.
Input Params: row (dict), tableName (str), titleText (str)
Output: popup_window (Window | null)
*/
function openAPRTimingTableViewer(row, tableName, titleText) {
    var projectCode = getAPRTimingViewerProjectCode();
    var popupUrl;
    var popupWindow;

    if (!canOpenAPRTimingViewer(row)) {
        window.alert('Project code, block, milestone, job, and stage are required before the timing table can open.');
        return null;
    }

    popupUrl = buildAPRTimingViewerUrl(projectCode, row, tableName, titleText);
    popupWindow = window.open(popupUrl, tableName.toLowerCase(), APR_TIMING_VIEWER_WINDOW_FEATURES);

    if (!popupWindow) {
        window.alert('Unable to open the APR timing table window. Please allow pop-ups for this site.');
        return null;
    }

    popupWindow.focus();
    return popupWindow;
}

/*
Function Name: handleAPRSummaryAction
Purpose: Open the APR_TIMING_SUMMARY table for one APR tracker row.
Input Params: row (dict)
Output: outputs (None)
*/
function handleAPRSummaryAction(row) {
    openAPRTimingTableViewer(row, APR_TIMING_SUMMARY_TABLE_NAME, 'APR Timing Summary');
}

/*
Function Name: isAPRSummaryButtonDisabled
Purpose: Disable the Summary button when the APR row does not have enough timing DB path information.
Input Params: row (dict)
Output: is_disabled (bool)
*/
function isAPRSummaryButtonDisabled(row) {
    return !canOpenAPRTimingViewer(row);
}

/*
Function Name: registerAPRSummaryButton
Purpose: Register the Summary action button on the APR tracker page.
Input Params: None
Output: outputs (None)
*/
function registerAPRSummaryButton() {
    window.registerAPRButton({
        id: 'summary',
        label: 'Summary',
        icon: 'table',
        className: 'ui mini button',
        disabled: isAPRSummaryButtonDisabled,
        handler: handleAPRSummaryAction
    });
}

window.openAPRTimingTableViewer = openAPRTimingTableViewer;
window.canOpenAPRTimingViewer = canOpenAPRTimingViewer;

registerAPRSummaryButton();
