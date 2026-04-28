const aprWatchlistManagerRoot = document.getElementById('aprWatchlistManagerRoot');
const aprWatchlistManagerState = {
  userId: '',
  defaultWatchlist: 'APR Weekly',
  selectedWatchlistName: '',
  watchlists: [],
  draftWatchlistName: '',
  isLoading: false,
  statusMessage: '',
  statusIsError: false,
};

window.addEventListener('DOMContentLoaded', initializeAprWatchlistManagerPage);

function initializeAprWatchlistManagerPage() {
  renderAprWatchlistManagerPage();
  loadAprWatchlistManagerState('Loading watchlists...');
}

async function fetchAprWatchlistManagerJson(url, options = {}) {
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

function setAprWatchlistManagerStatus(message, isError) {
  aprWatchlistManagerState.statusMessage = message || '';
  aprWatchlistManagerState.statusIsError = Boolean(isError);
}

function applyAprWatchlistManagerPayload(payload) {
  const defaultWatchlist = Array.isArray(payload.watchlists)
    ? payload.watchlists.find((watchlist) => watchlist.is_default)
    : null;

  aprWatchlistManagerState.userId = String(payload.user_id || '');
  aprWatchlistManagerState.defaultWatchlist = String(payload.default_watchlist || 'APR Weekly');
  aprWatchlistManagerState.watchlists = Array.isArray(payload.watchlists) ? payload.watchlists : [];

  if (!aprWatchlistManagerState.watchlists.length) {
    aprWatchlistManagerState.selectedWatchlistName = '';
    return;
  }

  if (findSelectedAprWatchlistManagerWatchlist()) {
    return;
  }

  aprWatchlistManagerState.selectedWatchlistName = defaultWatchlist
    ? defaultWatchlist.name
    : aprWatchlistManagerState.watchlists[0].name;
}

async function loadAprWatchlistManagerState(message) {
  aprWatchlistManagerState.isLoading = true;
  setAprWatchlistManagerStatus(message || 'Loading watchlists...', false);
  renderAprWatchlistManagerPage();

  try {
    const payload = await fetchAprWatchlistManagerJson('/api/apr-watchlist');
    applyAprWatchlistManagerPayload(payload);
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(message ? '' : aprWatchlistManagerState.statusMessage, false);
    renderAprWatchlistManagerPage();
  } catch (error) {
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(error.message, true);
    renderAprWatchlistManagerPage();
  }
}

function findSelectedAprWatchlistManagerWatchlist() {
  return aprWatchlistManagerState.watchlists.find(
    (watchlist) => watchlist.name === aprWatchlistManagerState.selectedWatchlistName
  ) || null;
}

function buildAprWatchlistManagerWatchlistsMarkup() {
  if (!aprWatchlistManagerState.watchlists.length) {
    return '<div class="watchlist-manager-empty">No watchlists are available yet.</div>';
  }

  return aprWatchlistManagerState.watchlists
    .map((watchlist) => (
      '<button type="button" class="watchlist-manager-watchlist-button' +
      (watchlist.name === aprWatchlistManagerState.selectedWatchlistName ? ' is-active' : '') +
      '" data-watchlist-name="' + escapeAprWatchlistManagerHtml(watchlist.name) + '">' +
      '<span class="watchlist-manager-list-title">' +
      '<span>' + escapeAprWatchlistManagerHtml(watchlist.name) + '</span>' +
      '<span class="watchlist-manager-badge">' + escapeAprWatchlistManagerHtml(watchlist.item_count || 0) + '</span>' +
      '</span>' +
      '<span class="watchlist-manager-meta">' +
      (watchlist.is_default
        ? 'APR Weekly' + (watchlist.week_label ? ' | ' + escapeAprWatchlistManagerHtml(watchlist.week_label) : '')
        : 'Custom watchlist') +
      ' | ' + escapeAprWatchlistManagerHtml(watchlist.per_block_limit || 0) + ' / block' +
      '</span>' +
      '</button>'
    ))
    .join('');
}

function buildAprWatchlistManagerBlockChipsMarkup(watchlist) {
  const blockCounts = {};

  if (!watchlist || !Array.isArray(watchlist.items)) {
    return '';
  }

  watchlist.items.forEach((item) => {
    const blockName = String(item.Block || '').trim() || 'Unknown Block';
    blockCounts[blockName] = (blockCounts[blockName] || 0) + 1;
  });

  return Object.keys(blockCounts)
    .sort((leftName, rightName) => leftName.localeCompare(rightName))
    .map((blockName) => (
      '<span class="watchlist-manager-chip">' +
      escapeAprWatchlistManagerHtml(blockName) + ': ' + blockCounts[blockName] + '/' + (watchlist.per_block_limit || 0) +
      '</span>'
    ))
    .join('');
}

function buildAprWatchlistManagerRowsMarkup(watchlist) {
  if (!watchlist || !Array.isArray(watchlist.items) || !watchlist.items.length) {
    return '<div class="watchlist-manager-empty">No runs are saved in this watchlist yet.</div>';
  }

  return (
    '<div class="watchlist-manager-table-wrap">' +
    '<table class="watchlist-manager-table">' +
    '<thead><tr>' +
    '<th>Job</th>' +
    '<th>Milestone</th>' +
    '<th>Block</th>' +
    '<th>Stage</th>' +
    '<th>Status</th>' +
    '<th>Promote</th>' +
    '<th>Added</th>' +
    '<th>Action</th>' +
    '</tr></thead>' +
    '<tbody>' +
    watchlist.items.map((item) => (
      '<tr>' +
      '<td>' + escapeAprWatchlistManagerHtml(item.Job || '-') + '</td>' +
      '<td>' + escapeAprWatchlistManagerHtml(item.Milestone || '-') + '</td>' +
      '<td>' + escapeAprWatchlistManagerHtml(item.Block || '-') + '</td>' +
      '<td>' + escapeAprWatchlistManagerHtml(item.Stage || '-') + '</td>' +
      '<td>' + buildAprWatchlistManagerStatusPillMarkup(item.Status) + '</td>' +
      '<td>' + buildAprWatchlistManagerPromotePillMarkup(item.Promote) + '</td>' +
      '<td>' + escapeAprWatchlistManagerHtml(formatAprWatchlistManagerTimestamp(item.created_at)) + '</td>' +
      '<td><button type="button" class="watchlist-manager-button is-danger" data-item-id="' + item.id + '"' +
      (aprWatchlistManagerState.isLoading ? ' disabled' : '') + '>Remove</button></td>' +
      '</tr>'
    )).join('') +
    '</tbody></table></div>'
  );
}

function renderAprWatchlistManagerPage() {
  const selectedWatchlist = findSelectedAprWatchlistManagerWatchlist();
  const deleteDisabled = aprWatchlistManagerState.isLoading || !selectedWatchlist || selectedWatchlist.is_default;
  const statusClassName = aprWatchlistManagerState.statusIsError
    ? 'watchlist-manager-status is-error'
    : 'watchlist-manager-status';
  const activeWatchlistName = selectedWatchlist ? selectedWatchlist.name : 'No watchlist selected';
  const activeWatchlistMeta = selectedWatchlist
    ? (selectedWatchlist.is_default
      ? selectedWatchlist.item_count + ' runs in the current APR Weekly bucket' +
        (selectedWatchlist.week_label ? ' (' + selectedWatchlist.week_label + ')' : '')
      : selectedWatchlist.item_count + ' runs in this user-defined watchlist')
    : 'Create or select a watchlist to manage it here.';
  const activeWatchlistLimits = selectedWatchlist
    ? (selectedWatchlist.is_default
      ? 'APR Weekly resets automatically every ISO week and allows up to ' +
        selectedWatchlist.per_block_limit + ' runs per block' +
        (selectedWatchlist.week_label ? '. Current week: ' + selectedWatchlist.week_label : '.')
      : 'This watchlist allows up to ' + selectedWatchlist.per_block_limit + ' runs per block.')
    : 'Select a watchlist to view its limits.';

  if (!aprWatchlistManagerRoot) {
    return;
  }

  aprWatchlistManagerRoot.innerHTML =
    '<div class="watchlist-manager-card">' +
    '<div class="watchlist-manager-header">' +
    '<div>' +
    '<h1 class="watchlist-manager-title">APR Watchlist Manager</h1>' +
    '<p class="watchlist-manager-copy">Browse watchlists, create new ones, remove saved runs, and clean up custom watchlists without leaving the tracker flow.</p>' +
    '</div>' +
    '</div>' +
    '<div class="watchlist-manager-toolbar">' +
    '<div class="watchlist-manager-copy">Signed in as <strong>' + escapeAprWatchlistManagerHtml(aprWatchlistManagerState.userId || '-') + '</strong></div>' +
    '<div class="watchlist-manager-toolbar-actions">' +
    '<button type="button" class="watchlist-manager-button is-secondary" id="aprWatchlistManagerRefreshBtn"' + (aprWatchlistManagerState.isLoading ? ' disabled' : '') + '>Refresh</button>' +
    '</div>' +
    '</div>' +
    '<div class="' + statusClassName + '">' +
    escapeAprWatchlistManagerHtml(
      aprWatchlistManagerState.statusMessage || (aprWatchlistManagerState.isLoading ? 'Loading watchlists...' : '')
    ) +
    '</div>' +
    '<div class="watchlist-manager-layout">' +
    '<div class="watchlist-manager-stack">' +
    '<section class="watchlist-manager-section">' +
    '<h2 class="watchlist-manager-section-title">Create Watchlist</h2>' +
    '<form id="aprWatchlistManagerCreateForm">' +
    '<label class="watchlist-manager-label" for="aprWatchlistManagerInput">Watchlist name</label>' +
    '<div class="watchlist-manager-create-row">' +
    '<input id="aprWatchlistManagerInput" class="watchlist-manager-input" type="text" maxlength="80" placeholder="Tapeout Focus" value="' +
    escapeAprWatchlistManagerHtml(aprWatchlistManagerState.draftWatchlistName) + '"' +
    (aprWatchlistManagerState.isLoading ? ' disabled' : '') +
    ' />' +
    '<button type="submit" class="watchlist-manager-button"' + (aprWatchlistManagerState.isLoading ? ' disabled' : '') + '>Create</button>' +
    '</div>' +
    '</form>' +
    '</section>' +
    '<section class="watchlist-manager-section">' +
    '<h2 class="watchlist-manager-section-title">Available Watchlists</h2>' +
    '<div class="watchlist-manager-watchlists">' + buildAprWatchlistManagerWatchlistsMarkup() + '</div>' +
    '</section>' +
    '</div>' +
    '<section class="watchlist-manager-section">' +
    '<div class="watchlist-manager-header">' +
    '<div>' +
    '<h2 class="watchlist-manager-section-title" style="margin: 0;">' + escapeAprWatchlistManagerHtml(activeWatchlistName) + '</h2>' +
    '<p class="watchlist-manager-copy">' + escapeAprWatchlistManagerHtml(activeWatchlistMeta) + '</p>' +
    '</div>' +
    '<button type="button" class="watchlist-manager-button is-danger" id="aprWatchlistManagerDeleteBtn"' +
    (deleteDisabled ? ' disabled' : '') + '>Delete Watchlist</button>' +
    '</div>' +
    '<p class="watchlist-manager-copy" style="margin-bottom: 12px;">' + escapeAprWatchlistManagerHtml(activeWatchlistLimits) + '</p>' +
    '<div class="watchlist-manager-chip-row">' + buildAprWatchlistManagerBlockChipsMarkup(selectedWatchlist) + '</div>' +
    buildAprWatchlistManagerRowsMarkup(selectedWatchlist) +
    '</section>' +
    '</div>' +
    '</div>';

  attachAprWatchlistManagerEvents();
}

function attachAprWatchlistManagerEvents() {
  const refreshButton = document.getElementById('aprWatchlistManagerRefreshBtn');
  const createForm = document.getElementById('aprWatchlistManagerCreateForm');
  const deleteButton = document.getElementById('aprWatchlistManagerDeleteBtn');

  if (refreshButton) {
    refreshButton.addEventListener('click', handleAprWatchlistManagerRefresh);
  }

  if (createForm) {
    createForm.addEventListener('submit', handleAprWatchlistManagerCreateSubmit);
  }

  if (deleteButton) {
    deleteButton.addEventListener('click', handleAprWatchlistManagerDeleteWatchlist);
  }

  Array.from(document.querySelectorAll('[data-watchlist-name]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistManagerSelectWatchlist);
  });

  Array.from(document.querySelectorAll('[data-item-id]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistManagerRemoveRun);
  });
}

function handleAprWatchlistManagerRefresh() {
  loadAprWatchlistManagerState('Refreshing watchlists...');
}

async function handleAprWatchlistManagerCreateSubmit(event) {
  const nameInput = document.getElementById('aprWatchlistManagerInput');
  const watchlistName = nameInput ? String(nameInput.value || '').trim() : '';

  event.preventDefault();
  aprWatchlistManagerState.draftWatchlistName = watchlistName;

  if (!watchlistName) {
    setAprWatchlistManagerStatus('Enter a watchlist name first.', true);
    renderAprWatchlistManagerPage();
    return;
  }

  aprWatchlistManagerState.isLoading = true;
  setAprWatchlistManagerStatus('Creating watchlist...', false);
  renderAprWatchlistManagerPage();

  try {
    const payload = await fetchAprWatchlistManagerJson('/api/apr-watchlist/create-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: watchlistName }),
    });

    aprWatchlistManagerState.selectedWatchlistName = watchlistName;
    applyAprWatchlistManagerPayload(payload);
    aprWatchlistManagerState.draftWatchlistName = '';
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(payload.message || 'watchlist created', false);
    renderAprWatchlistManagerPage();
  } catch (error) {
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(error.message, true);
    renderAprWatchlistManagerPage();
  }
}

function handleAprWatchlistManagerSelectWatchlist(event) {
  const watchlistName = String(event.currentTarget.getAttribute('data-watchlist-name') || '').trim();

  if (!watchlistName) {
    return;
  }

  aprWatchlistManagerState.selectedWatchlistName = watchlistName;
  setAprWatchlistManagerStatus('', false);
  renderAprWatchlistManagerPage();
}

async function handleAprWatchlistManagerDeleteWatchlist() {
  const selectedWatchlist = findSelectedAprWatchlistManagerWatchlist();

  if (!selectedWatchlist || selectedWatchlist.is_default) {
    return;
  }

  if (!window.confirm('Delete watchlist "' + selectedWatchlist.name + '" and all of its saved runs?')) {
    return;
  }

  aprWatchlistManagerState.isLoading = true;
  setAprWatchlistManagerStatus('Deleting watchlist...', false);
  renderAprWatchlistManagerPage();

  try {
    const payload = await fetchAprWatchlistManagerJson('/api/apr-watchlist/delete-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: selectedWatchlist.name }),
    });

    aprWatchlistManagerState.selectedWatchlistName = aprWatchlistManagerState.defaultWatchlist;
    applyAprWatchlistManagerPayload(payload);
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(payload.message || 'watchlist deleted', false);
    renderAprWatchlistManagerPage();
  } catch (error) {
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(error.message, true);
    renderAprWatchlistManagerPage();
  }
}

async function handleAprWatchlistManagerRemoveRun(event) {
  const itemId = Number(event.currentTarget.getAttribute('data-item-id'));

  if (!itemId) {
    return;
  }

  if (!window.confirm('Remove this run from the selected watchlist?')) {
    return;
  }

  aprWatchlistManagerState.isLoading = true;
  setAprWatchlistManagerStatus('Removing run...', false);
  renderAprWatchlistManagerPage();

  try {
    const payload = await fetchAprWatchlistManagerJson('/api/apr-watchlist/delete-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_id: itemId }),
    });

    applyAprWatchlistManagerPayload(payload);
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(payload.message || 'run removed from watchlist', false);
    renderAprWatchlistManagerPage();
  } catch (error) {
    aprWatchlistManagerState.isLoading = false;
    setAprWatchlistManagerStatus(error.message, true);
    renderAprWatchlistManagerPage();
  }
}

function buildAprWatchlistManagerStatusPillMarkup(statusValue) {
  const toneClass = getAprWatchlistManagerStatusToneClass(statusValue);
  return '<span class="watchlist-manager-status-pill' + (toneClass ? ' ' + toneClass : '') + '">' +
    escapeAprWatchlistManagerHtml(statusValue || '-') +
    '</span>';
}

function buildAprWatchlistManagerPromotePillMarkup(promoteValue) {
  const normalizedValue = String(promoteValue || '').trim().toLowerCase();
  const toneClass = normalizedValue === 'yes' ? 'is-positive' : normalizedValue === 'no' ? 'is-negative' : '';
  return '<span class="watchlist-manager-promote-pill' + (toneClass ? ' ' + toneClass : '') + '">' +
    escapeAprWatchlistManagerHtml(promoteValue || '-') +
    '</span>';
}

function getAprWatchlistManagerStatusToneClass(statusValue) {
  const normalizedStatus = String(statusValue || '').trim().toLowerCase();

  if (normalizedStatus === 'completed') {
    return 'is-positive';
  }

  if (normalizedStatus === 'await extraction') {
    return 'is-warning';
  }

  if (normalizedStatus === 'job running' || normalizedStatus === 'extracting') {
    return 'is-info';
  }

  if (normalizedStatus === 'job failed' || normalizedStatus === 'extraction failed') {
    return 'is-negative';
  }

  return '';
}

function formatAprWatchlistManagerTimestamp(timestamp) {
  if (!timestamp) {
    return '-';
  }

  return String(timestamp).replace('T', ' ').replace('Z', '');
}

function escapeAprWatchlistManagerHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
