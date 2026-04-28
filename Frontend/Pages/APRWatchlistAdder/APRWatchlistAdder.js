const APR_WATCHLIST_ADDER_TRACKER_FIELDS = [
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
const APR_WATCHLIST_ADDER_ALLOWED_STAGES = ['place', 'route', 'clock'];
const APR_WATCHLIST_ADDER_STORAGE_PREFIX = 'apr-watchlist-row:';
const APR_WATCHLIST_MANAGER_URL = '/static/Pages/APRWatchlistManager/APRWatchlistManager.html';
const APR_WATCHLIST_WINDOW_FEATURES = 'popup=yes,width=1180,height=820,resizable=yes,scrollbars=yes';

const aprWatchlistAdderRoot = document.getElementById('aprWatchlistAdderRoot');
const aprWatchlistAdderState = {
  userId: '',
  defaultWatchlist: 'APR Weekly',
  activeRow: null,
  watchlists: [],
  draftWatchlistName: '',
  isLoading: false,
  statusMessage: '',
  statusIsError: false,
};

window.addEventListener('DOMContentLoaded', initializeAprWatchlistAdderPage);

function initializeAprWatchlistAdderPage() {
  aprWatchlistAdderState.activeRow = readAprWatchlistRowFromStorage();
  renderAprWatchlistAdderPage();
  loadAprWatchlistAdderState(
    aprWatchlistAdderState.activeRow
      ? 'Selected run loaded. Click a watchlist to add it.'
      : 'No tracker run was provided for this window.'
  );
}

async function fetchAprWatchlistAdderJson(url, options = {}) {
  const response = await fetch(url, options);
  const result = await response.json().catch(() => ({}));

  if (response.status === 401) {
    window.location.href = '/';
    throw new Error(result.error || 'session inactive');
  }

  if (!response.ok) {
    throw new Error(result.error || 'Request failed');
  }

  return result;
}

function readAprWatchlistRowFromStorage() {
  const url = new URL(window.location.href);
  const runToken = String(url.searchParams.get('run_token') || '').trim();
  let payloadText = '';

  if (!runToken) {
    return null;
  }

  try {
    payloadText = window.localStorage.getItem(APR_WATCHLIST_ADDER_STORAGE_PREFIX + runToken) || '';
    window.localStorage.removeItem(APR_WATCHLIST_ADDER_STORAGE_PREFIX + runToken);
  } catch (error) {
    return null;
  }

  if (!payloadText) {
    return null;
  }

  try {
    return JSON.parse(payloadText);
  } catch (error) {
    return null;
  }
}

function setAprWatchlistAdderStatus(message, isError) {
  aprWatchlistAdderState.statusMessage = message || '';
  aprWatchlistAdderState.statusIsError = Boolean(isError);
}

function applyAprWatchlistAdderPayload(payload) {
  aprWatchlistAdderState.userId = String(payload.user_id || '');
  aprWatchlistAdderState.defaultWatchlist = String(payload.default_watchlist || 'APR Weekly');
  aprWatchlistAdderState.watchlists = Array.isArray(payload.watchlists) ? payload.watchlists : [];
}

async function loadAprWatchlistAdderState(message) {
  aprWatchlistAdderState.isLoading = true;
  setAprWatchlistAdderStatus(message || 'Loading watchlists...', false);
  renderAprWatchlistAdderPage();

  try {
    const payload = await fetchAprWatchlistAdderJson('/api/apr-watchlist');
    applyAprWatchlistAdderPayload(payload);
    aprWatchlistAdderState.isLoading = false;
    setAprWatchlistAdderStatus(message || '', false);
    renderAprWatchlistAdderPage();
  } catch (error) {
    aprWatchlistAdderState.isLoading = false;
    setAprWatchlistAdderStatus(error.message, true);
    renderAprWatchlistAdderPage();
  }
}

function isAprWatchlistAdderEligibleRow(row) {
  const normalizedStatus = String((row && row.Status) || '').trim().toLowerCase();
  const normalizedStage = String((row && row.Stage) || '').trim().toLowerCase();

  return normalizedStatus === 'completed' && APR_WATCHLIST_ADDER_ALLOWED_STAGES.includes(normalizedStage);
}

function normalizeAprWatchlistAdderRun(row) {
  const sourceRow = row && typeof row === 'object' ? row : {};
  const normalizedRun = {};

  APR_WATCHLIST_ADDER_TRACKER_FIELDS.forEach((fieldName) => {
    const fieldValue = sourceRow[fieldName];
    normalizedRun[fieldName] = fieldValue == null ? '' : String(fieldValue).trim();
  });

  if (!normalizedRun.Job || !normalizedRun.Milestone || !normalizedRun.Block || !normalizedRun.Stage) {
    throw new Error('Run must include Job, Milestone, Block, and Stage.');
  }

  return normalizedRun;
}

function canAddAprWatchlistAdderRun(row) {
  if (!isAprWatchlistAdderEligibleRow(row)) {
    return false;
  }

  try {
    normalizeAprWatchlistAdderRun(row);
    return true;
  } catch (error) {
    return false;
  }
}

function getAprWatchlistAdderRowLabel(row) {
  return [row && row.Job, row && row.Milestone, row && row.Block, row && row.Stage]
    .filter((value) => value)
    .join(' / ');
}

function buildAprWatchlistAdderSelectedRunMarkup() {
  let normalizedRun;

  if (!aprWatchlistAdderState.activeRow) {
    return '<div class="watchlist-adder-empty">Open this page from APR Tracker to load a selected run.</div>';
  }

  if (!canAddAprWatchlistAdderRun(aprWatchlistAdderState.activeRow)) {
    return '<div class="watchlist-adder-empty">Only Completed PLACE, ROUTE, or CLOCK runs can be added to a watchlist.</div>';
  }

  try {
    normalizedRun = normalizeAprWatchlistAdderRun(aprWatchlistAdderState.activeRow);
  } catch (error) {
    return '<div class="watchlist-adder-empty">' + escapeAprWatchlistAdderHtml(error.message) + '</div>';
  }

  return [
    ['Run', getAprWatchlistAdderRowLabel(normalizedRun)],
    ['Status', normalizedRun.Status || '-'],
    ['Stage', normalizedRun.Stage || '-'],
    ['Promote', normalizedRun.Promote || '-'],
    ['Owner', normalizedRun.User || '-'],
    ['DFT Release', normalizedRun.Dft_release || '-'],
    ['Comments', normalizedRun.Comments || '-'],
  ]
    .map(([key, value]) => (
      '<div class="watchlist-adder-summary-item">' +
      '<span class="watchlist-adder-summary-key">' + escapeAprWatchlistAdderHtml(key) + '</span>' +
      '<span class="watchlist-adder-summary-value">' + escapeAprWatchlistAdderHtml(value) + '</span>' +
      '</div>'
    ))
    .join('');
}

function buildAprWatchlistAdderOptionsMarkup() {
  const isDisabled = aprWatchlistAdderState.isLoading || !canAddAprWatchlistAdderRun(aprWatchlistAdderState.activeRow);

  if (!aprWatchlistAdderState.watchlists.length) {
    return '<div class="watchlist-adder-empty">No watchlists are available yet.</div>';
  }

  return aprWatchlistAdderState.watchlists
    .map((watchlist) => {
      const watchlistMeta = watchlist.is_default
        ? 'APR Weekly' + (watchlist.week_label ? ' | ' + escapeAprWatchlistAdderHtml(watchlist.week_label) : '')
        : 'Custom watchlist';

      return (
        '<button type="button" class="watchlist-adder-option' +
        (watchlist.is_default ? ' is-default' : '') +
        '" data-watchlist-name="' + escapeAprWatchlistAdderHtml(watchlist.name) + '"' +
        (isDisabled ? ' disabled' : '') +
        '>' +
        '<span class="watchlist-adder-watchlist-title">' +
        '<span>' + escapeAprWatchlistAdderHtml(watchlist.name) + '</span>' +
        '<span class="watchlist-adder-badge">' + escapeAprWatchlistAdderHtml(watchlist.item_count || 0) + '</span>' +
        '</span>' +
        '<span class="watchlist-adder-meta">' +
        watchlistMeta + ' | ' + escapeAprWatchlistAdderHtml(watchlist.per_block_limit || 0) + ' / block' +
        '</span>' +
        '</button>'
      );
    })
    .join('');
}

function renderAprWatchlistAdderPage() {
  const statusClassName = aprWatchlistAdderState.statusIsError
    ? 'watchlist-adder-status is-error'
    : 'watchlist-adder-status';
  const createDisabled = aprWatchlistAdderState.isLoading || !canAddAprWatchlistAdderRun(aprWatchlistAdderState.activeRow);

  if (!aprWatchlistAdderRoot) {
    return;
  }

  aprWatchlistAdderRoot.innerHTML =
    '<div class="watchlist-adder-card">' +
    '<div class="watchlist-adder-header">' +
    '<div>' +
    '<h1 class="watchlist-adder-title">Add APR Run To Watchlist</h1>' +
    '<p class="watchlist-adder-copy">Choose an existing watchlist for this tracker run, or create a new watchlist and add it in one step. APR Weekly behavior stays the same.</p>' +
    '</div>' +
    '</div>' +
    '<div class="watchlist-adder-toolbar">' +
    '<div class="watchlist-adder-toolbar-note">Signed in as <strong>' + escapeAprWatchlistAdderHtml(aprWatchlistAdderState.userId || '-') + '</strong></div>' +
    '<div class="watchlist-adder-toolbar-actions">' +
    '<button type="button" class="watchlist-adder-button is-secondary" id="aprWatchlistAdderRefreshBtn"' + (aprWatchlistAdderState.isLoading ? ' disabled' : '') + '>Refresh</button>' +
    '<button type="button" class="watchlist-adder-button is-secondary" id="aprWatchlistAdderManagerBtn">Open Manager</button>' +
    '</div>' +
    '</div>' +
    '<div class="' + statusClassName + '">' +
    escapeAprWatchlistAdderHtml(
      aprWatchlistAdderState.statusMessage ||
      (aprWatchlistAdderState.isLoading ? 'Loading watchlists...' : 'Click a watchlist to add this run.')
    ) +
    '</div>' +
    '<div class="watchlist-adder-layout">' +
    '<div class="watchlist-adder-section">' +
    '<h2 class="watchlist-adder-section-title">Selected Run</h2>' +
    '<div class="watchlist-adder-summary-grid">' + buildAprWatchlistAdderSelectedRunMarkup() + '</div>' +
    '</div>' +
    '<div class="watchlist-adder-section">' +
    '<h2 class="watchlist-adder-section-title">Available Watchlists</h2>' +
    '<div class="watchlist-adder-options">' + buildAprWatchlistAdderOptionsMarkup() + '</div>' +
    '<div style="height: 14px;"></div>' +
    '<form id="aprWatchlistAdderCreateForm">' +
    '<label class="watchlist-adder-label" for="aprWatchlistAdderInput">Create New Watchlist</label>' +
    '<div class="watchlist-adder-create-row">' +
    '<input id="aprWatchlistAdderInput" class="watchlist-adder-input" type="text" maxlength="80" placeholder="Tapeout Focus" value="' +
    escapeAprWatchlistAdderHtml(aprWatchlistAdderState.draftWatchlistName) + '"' +
    (aprWatchlistAdderState.isLoading ? ' disabled' : '') +
    ' />' +
    '<button type="submit" class="watchlist-adder-button"' + (createDisabled ? ' disabled' : '') + '>Create & Add</button>' +
    '</div>' +
    '</form>' +
    '</div>' +
    '</div>' +
    '</div>';

  attachAprWatchlistAdderEvents();
}

function attachAprWatchlistAdderEvents() {
  const refreshButton = document.getElementById('aprWatchlistAdderRefreshBtn');
  const managerButton = document.getElementById('aprWatchlistAdderManagerBtn');
  const createForm = document.getElementById('aprWatchlistAdderCreateForm');

  if (refreshButton) {
    refreshButton.addEventListener('click', handleAprWatchlistAdderRefresh);
  }

  if (managerButton) {
    managerButton.addEventListener('click', handleAprWatchlistAdderOpenManager);
  }

  if (createForm) {
    createForm.addEventListener('submit', handleAprWatchlistAdderCreateSubmit);
  }

  Array.from(document.querySelectorAll('[data-watchlist-name]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistAdderWatchlistClick);
  });
}

function handleAprWatchlistAdderRefresh() {
  loadAprWatchlistAdderState(
    aprWatchlistAdderState.activeRow
      ? 'Selected run loaded. Click a watchlist to add it.'
      : 'No tracker run was provided for this window.'
  );
}

function handleAprWatchlistAdderOpenManager() {
  const popupWindow = window.open(
    APR_WATCHLIST_MANAGER_URL,
    'apr-watchlist-manager',
    APR_WATCHLIST_WINDOW_FEATURES
  );

  if (!popupWindow) {
    window.alert('Unable to open the APR Watchlist window. Please allow pop-ups for this site.');
    return;
  }

  popupWindow.focus();
}

async function addAprWatchlistAdderRunToWatchlist(watchlistName) {
  let normalizedRun;

  if (!watchlistName) {
    setAprWatchlistAdderStatus('Select a watchlist first.', true);
    renderAprWatchlistAdderPage();
    return;
  }

  if (!canAddAprWatchlistAdderRun(aprWatchlistAdderState.activeRow)) {
    setAprWatchlistAdderStatus('Only Completed PLACE, ROUTE, or CLOCK runs can be added to a watchlist.', true);
    renderAprWatchlistAdderPage();
    return;
  }

  try {
    normalizedRun = normalizeAprWatchlistAdderRun(aprWatchlistAdderState.activeRow);
  } catch (error) {
    setAprWatchlistAdderStatus(error.message, true);
    renderAprWatchlistAdderPage();
    return;
  }

  aprWatchlistAdderState.isLoading = true;
  setAprWatchlistAdderStatus('Adding selected run...', false);
  renderAprWatchlistAdderPage();

  try {
    const payload = await fetchAprWatchlistAdderJson('/api/apr-watchlist/add-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watchlist_name: watchlistName,
        run: normalizedRun,
      }),
    });

    applyAprWatchlistAdderPayload(payload);
    aprWatchlistAdderState.isLoading = false;
    setAprWatchlistAdderStatus(payload.message || ('run added to ' + watchlistName), false);
    renderAprWatchlistAdderPage();
  } catch (error) {
    aprWatchlistAdderState.isLoading = false;
    setAprWatchlistAdderStatus(error.message, true);
    renderAprWatchlistAdderPage();
  }
}

function handleAprWatchlistAdderWatchlistClick(event) {
  addAprWatchlistAdderRunToWatchlist(event.currentTarget.getAttribute('data-watchlist-name'));
}

async function handleAprWatchlistAdderCreateSubmit(event) {
  const nameInput = document.getElementById('aprWatchlistAdderInput');
  const watchlistName = nameInput ? String(nameInput.value || '').trim() : '';

  event.preventDefault();
  aprWatchlistAdderState.draftWatchlistName = watchlistName;

  if (!watchlistName) {
    setAprWatchlistAdderStatus('Enter a watchlist name first.', true);
    renderAprWatchlistAdderPage();
    return;
  }

  if (!canAddAprWatchlistAdderRun(aprWatchlistAdderState.activeRow)) {
    setAprWatchlistAdderStatus('Only Completed PLACE, ROUTE, or CLOCK runs can be added to a watchlist.', true);
    renderAprWatchlistAdderPage();
    return;
  }

  aprWatchlistAdderState.isLoading = true;
  setAprWatchlistAdderStatus('Creating watchlist...', false);
  renderAprWatchlistAdderPage();

  try {
    const payload = await fetchAprWatchlistAdderJson('/api/apr-watchlist/create-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: watchlistName }),
    });

    applyAprWatchlistAdderPayload(payload);
    await addAprWatchlistAdderRunToWatchlist(watchlistName);
    aprWatchlistAdderState.draftWatchlistName = '';
    renderAprWatchlistAdderPage();
  } catch (error) {
    aprWatchlistAdderState.isLoading = false;
    setAprWatchlistAdderStatus(error.message, true);
    renderAprWatchlistAdderPage();
  }
}

function escapeAprWatchlistAdderHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
