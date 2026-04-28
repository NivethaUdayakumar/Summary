window.APR_BUTTONS = window.APR_BUTTONS || [];

const APR_WATCHLIST_ADDER_WINDOW_NAME = 'apr-watchlist-adder';
const APR_WATCHLIST_MANAGER_WINDOW_NAME = 'apr-watchlist-manager';
const APR_WATCHLIST_WINDOW_FEATURES = 'popup=yes,width=1180,height=820,resizable=yes,scrollbars=yes';
const APR_WATCHLIST_ADDER_URL = '/static/Pages/APRWatchlistAdder/APRWatchlistAdder.html';
const APR_WATCHLIST_MANAGER_URL = '/static/Pages/APRWatchlistManager/APRWatchlistManager.html';
const APR_WATCHLIST_ALLOWED_STAGES = ['place', 'route', 'clock'];
const APR_WATCHLIST_STORAGE_PREFIX = 'apr-watchlist-row:';
const APR_WATCHLIST_TRACKER_FIELDS = [
  'Job',
  'Milestone',
  'Block',
  'Stage',
  'Dft_release',
  'User',
  'Status',
  'Comments',
  'Promote',
];

function cloneAprWatchlistRow(row) {
  if (!row || typeof row !== 'object') {
    return null;
  }

  return Object.assign({}, row);
}

function isAprWatchlistEligibleRow(row) {
  const normalizedStatus = String((row && row.Status) || '').trim().toLowerCase();
  const normalizedStage = String((row && row.Stage) || '').trim().toLowerCase();

  return normalizedStatus === 'completed' && APR_WATCHLIST_ALLOWED_STAGES.includes(normalizedStage);
}

function normalizeAprWatchlistRun(row) {
  const sourceRow = row && typeof row === 'object' ? row : {};
  const normalizedRun = {};

  APR_WATCHLIST_TRACKER_FIELDS.forEach((fieldName) => {
    const fieldValue = sourceRow[fieldName];
    normalizedRun[fieldName] = fieldValue == null ? '' : String(fieldValue).trim();
  });

  if (!normalizedRun.Job || !normalizedRun.Milestone || !normalizedRun.Block || !normalizedRun.Stage) {
    throw new Error('Run must include Job, Milestone, Block, and Stage.');
  }

  return normalizedRun;
}

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

function buildAprWatchlistWindowUrl(baseUrl, queryParams) {
  const url = new URL(baseUrl, window.location.origin);

  Object.keys(queryParams || {}).forEach((key) => {
    if (queryParams[key]) {
      url.searchParams.set(key, queryParams[key]);
    }
  });

  return url.toString();
}

function openAprWatchlistWindow(url, windowName) {
  const popupWindow = window.open(url, windowName, APR_WATCHLIST_WINDOW_FEATURES);

  if (!popupWindow) {
    window.alert('Unable to open the APR Watchlist window. Please allow pop-ups for this site.');
    return null;
  }

  popupWindow.focus();
  return popupWindow;
}

function storeAprWatchlistRun(row) {
  const runToken = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  const storageKey = APR_WATCHLIST_STORAGE_PREFIX + runToken;

  window.localStorage.setItem(storageKey, JSON.stringify(cloneAprWatchlistRow(row)));
  return runToken;
}

function openAprWatchlistAdder(row) {
  let runToken;
  let url;

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

function openAprWatchlistManager() {
  return openAprWatchlistWindow(APR_WATCHLIST_MANAGER_URL, APR_WATCHLIST_MANAGER_WINDOW_NAME);
}

function openAprWatchlistQuickAddAction(row) {
  openAprWatchlistAdder(row);
}

function isAprWatchlistButtonDisabled(row) {
  return !isAprWatchlistEligibleRow(row);
}

function registerAprWatchlistButton() {
  const hasExistingButton = window.APR_BUTTONS.some((buttonConfig) => buttonConfig && buttonConfig.id === 'watchlist');
  if (hasExistingButton) {
    return;
  }

  window.APR_BUTTONS.push({
    id: 'watchlist',
    label: 'Watchlist',
    className: 'ui mini button',
    disabled: isAprWatchlistButtonDisabled,
    handler: openAprWatchlistQuickAddAction,
  });
}

window.openAprWatchlistManager = openAprWatchlistManager;
window.openAprWatchlistAdder = openAprWatchlistAdder;

registerAprWatchlistButton();
