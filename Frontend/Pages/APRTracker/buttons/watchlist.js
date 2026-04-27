window.APR_BUTTONS = window.APR_BUTTONS || [];

const APR_WATCHLIST_POPUP_NAME = 'apr-watchlist-manager';
const APR_WATCHLIST_POPUP_FEATURES = 'popup=yes,width=1180,height=820,resizable=yes,scrollbars=yes';
const APR_WATCHLIST_POPUP_URL = '/static/Pages/APRTracker/watchlistPopup.html';
const APR_WATCHLIST_ALLOWED_STAGES = ['place', 'route', 'clock'];

const aprWatchlistBridgeState = {
  activeRow: null,
  popupWindow: null,
};

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

function getAprWatchlistRowLabel(row) {
  if (typeof window.getAPRTrackerRowLabel === 'function') {
    return window.getAPRTrackerRowLabel(row || {});
  }

  return [row && row.Job, row && row.Milestone, row && row.Block, row && row.Stage]
    .filter((value) => value)
    .join(' / ');
}

function syncAprWatchlistPopupRow() {
  const popupWindow = aprWatchlistBridgeState.popupWindow;

  if (
    !popupWindow ||
    popupWindow.closed ||
    typeof popupWindow.setAprWatchlistPopupActiveRow !== 'function'
  ) {
    return false;
  }

  popupWindow.setAprWatchlistPopupActiveRow(cloneAprWatchlistRow(aprWatchlistBridgeState.activeRow));
  return true;
}

function ensureAprWatchlistPopupWindow() {
  if (aprWatchlistBridgeState.popupWindow && !aprWatchlistBridgeState.popupWindow.closed) {
    return aprWatchlistBridgeState.popupWindow;
  }

  aprWatchlistBridgeState.popupWindow = window.open(
    APR_WATCHLIST_POPUP_URL,
    APR_WATCHLIST_POPUP_NAME,
    APR_WATCHLIST_POPUP_FEATURES
  );

  if (!aprWatchlistBridgeState.popupWindow) {
    window.alert('Unable to open the APR Watchlist window. Please allow pop-ups for this site.');
    return null;
  }

  return aprWatchlistBridgeState.popupWindow;
}

window.APR_WATCHLIST_POPUP_BRIDGE = {
  connect(popupWindow) {
    if (popupWindow && !popupWindow.closed) {
      aprWatchlistBridgeState.popupWindow = popupWindow;
    }
  },
  disconnect(popupWindow) {
    if (aprWatchlistBridgeState.popupWindow === popupWindow) {
      aprWatchlistBridgeState.popupWindow = null;
    }
  },
  getActiveRow() {
    return cloneAprWatchlistRow(aprWatchlistBridgeState.activeRow);
  },
  getTrackerRowLabel(row) {
    return getAprWatchlistRowLabel(row || {});
  },
};

function openAprWatchlistPopup(row) {
  let popupWindow;

  if (!isAprWatchlistEligibleRow(row)) {
    return;
  }

  aprWatchlistBridgeState.activeRow = cloneAprWatchlistRow(row);
  popupWindow = ensureAprWatchlistPopupWindow();
  if (!popupWindow) {
    return;
  }

  syncAprWatchlistPopupRow();
  popupWindow.focus();
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
    handler: openAprWatchlistPopup,
  });
}

registerAprWatchlistButton();
