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

const APR_WATCHLIST_ALLOWED_STAGES = ['place', 'route', 'clock'];

const aprWatchlistPopupState = {
  userId: '',
  defaultWatchlist: 'APR Weekly',
  activeRow: null,
  selectedWatchlistName: '',
  watchlists: [],
  draftWatchlistName: '',
  isLoading: false,
  statusMessage: '',
  statusIsError: false,
};

const aprWatchlistPopupRoot = document.getElementById('apr-watchlist-root');

window.addEventListener('DOMContentLoaded', handleAprWatchlistPopupDOMContentLoaded);
window.addEventListener('beforeunload', disconnectAprWatchlistPopupBridge);

function cloneAprWatchlistRow(row) {
  if (!row || typeof row !== 'object') {
    return null;
  }

  return Object.assign({}, row);
}

function getAprWatchlistPopupBridge() {
  if (!window.opener || window.opener.closed) {
    return null;
  }

  return window.opener.APR_WATCHLIST_POPUP_BRIDGE || null;
}

function connectAprWatchlistPopupBridge() {
  const bridge = getAprWatchlistPopupBridge();

  if (bridge && typeof bridge.connect === 'function') {
    bridge.connect(window);
  }
}

function disconnectAprWatchlistPopupBridge() {
  const bridge = getAprWatchlistPopupBridge();

  if (bridge && typeof bridge.disconnect === 'function') {
    bridge.disconnect(window);
  }
}

function syncAprWatchlistPopupActiveRowFromBridge() {
  const bridge = getAprWatchlistPopupBridge();

  if (bridge && typeof bridge.getActiveRow === 'function') {
    aprWatchlistPopupState.activeRow = cloneAprWatchlistRow(bridge.getActiveRow());
  }
}

function setAprWatchlistPopupStatus(message, isError) {
  aprWatchlistPopupState.statusMessage = message || '';
  aprWatchlistPopupState.statusIsError = Boolean(isError);
}

function setAprWatchlistPopupActiveRow(row) {
  aprWatchlistPopupState.activeRow = cloneAprWatchlistRow(row);

  if (!aprWatchlistPopupState.isLoading) {
    setAprWatchlistPopupStatus(
      aprWatchlistPopupState.activeRow
        ? 'Selected run updated. Choose a watchlist to add it.'
        : '',
      false
    );
  }

  renderAprWatchlistPopup();
}

window.setAprWatchlistPopupActiveRow = setAprWatchlistPopupActiveRow;

function isAprWatchlistEligibleRow(row) {
  const normalizedStatus = String((row && row.Status) || '').trim().toLowerCase();
  const normalizedStage = String((row && row.Stage) || '').trim().toLowerCase();

  return normalizedStatus === 'completed' && APR_WATCHLIST_ALLOWED_STAGES.includes(normalizedStage);
}

async function fetchAprWatchlistJson(url, options = {}) {
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

function applyAprWatchlistPayload(payload) {
  aprWatchlistPopupState.userId = String(payload.user_id || '');
  aprWatchlistPopupState.defaultWatchlist = String(payload.default_watchlist || 'APR Weekly');
  aprWatchlistPopupState.watchlists = Array.isArray(payload.watchlists) ? payload.watchlists : [];

  if (!aprWatchlistPopupState.watchlists.length) {
    aprWatchlistPopupState.selectedWatchlistName = '';
    return;
  }

  if (findSelectedAprWatchlist()) {
    return;
  }

  const defaultWatchlist = aprWatchlistPopupState.watchlists.find((watchlist) => watchlist.is_default);
  aprWatchlistPopupState.selectedWatchlistName = defaultWatchlist
    ? defaultWatchlist.name
    : aprWatchlistPopupState.watchlists[0].name;
}

async function loadAprWatchlistPopupState(message) {
  aprWatchlistPopupState.isLoading = true;
  setAprWatchlistPopupStatus(message || 'Loading watchlists...', false);
  renderAprWatchlistPopup();

  try {
    const payload = await fetchAprWatchlistJson('/api/apr-watchlist');
    applyAprWatchlistPayload(payload);
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(message || '', false);
    renderAprWatchlistPopup();
  } catch (error) {
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(error.message, true);
    renderAprWatchlistPopup();
  }
}

function findSelectedAprWatchlist() {
  return aprWatchlistPopupState.watchlists.find(
    (watchlist) => watchlist.name === aprWatchlistPopupState.selectedWatchlistName
  ) || null;
}

function getPopupRowLabel(row) {
  const bridge = getAprWatchlistPopupBridge();

  if (bridge && typeof bridge.getTrackerRowLabel === 'function') {
    return bridge.getTrackerRowLabel(row || {});
  }

  return [row.Job, row.Milestone, row.Block, row.Stage]
    .filter((value) => value)
    .join(' / ');
}

function buildPopupSelectedRunMarkup() {
  if (!aprWatchlistPopupState.activeRow) {
    return '<div class="popup-empty">Select a tracker row to add it into a watchlist.</div>';
  }

  if (!canAddAprWatchlistRun(aprWatchlistPopupState.activeRow)) {
    return '<div class="popup-empty">Only Completed PLACE, ROUTE, or CLOCK runs can be added to a watchlist.</div>';
  }

  let normalizedRun;

  try {
    normalizedRun = normalizeAprWatchlistRun(aprWatchlistPopupState.activeRow);
  } catch (error) {
    return `<div class="popup-empty">${escapeAprWatchlistHtml(error.message)}</div>`;
  }

  return [
    ['Run', getPopupRowLabel(normalizedRun)],
    ['Status', normalizedRun.Status || '-'],
    ['Stage', normalizedRun.Stage || '-'],
    ['Promote', normalizedRun.Promote || '-'],
    ['Owner', normalizedRun.User || '-'],
    ['DFT Release', normalizedRun.Dft_release || '-'],
    ['Comments', normalizedRun.Comments || '-'],
  ]
    .map(([key, value]) => `
      <div class="popup-summary-item">
        <span class="popup-summary-key">${escapeAprWatchlistHtml(key)}</span>
        <span class="popup-summary-value">${escapeAprWatchlistHtml(value)}</span>
      </div>
    `)
    .join('');
}

function buildPopupWatchlistButtonsMarkup() {
  if (!aprWatchlistPopupState.watchlists.length) {
    return '<div class="popup-empty">No watchlists available.</div>';
  }

  return aprWatchlistPopupState.watchlists
    .map((watchlist) => {
      const isActive = watchlist.name === aprWatchlistPopupState.selectedWatchlistName;
      const watchlistType = watchlist.is_default
        ? `Weekly default${watchlist.week_label ? ` &middot; ${escapeAprWatchlistHtml(watchlist.week_label)}` : ''}`
        : 'Custom watchlist';

      return `
        <button
          type="button"
          class="popup-watchlist-button${isActive ? ' active' : ''}"
          data-watchlist-name="${escapeAprWatchlistHtml(watchlist.name)}"
        >
          <span class="popup-watchlist-title">
            <span>${escapeAprWatchlistHtml(watchlist.name)}</span>
            <span class="popup-badge">${watchlist.item_count}</span>
          </span>
          <span class="popup-watchlist-meta">
            ${watchlistType} &middot; ${watchlist.per_block_limit} / block
          </span>
        </button>
      `;
    })
    .join('');
}

function buildPopupBlockChipsMarkup(watchlist) {
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
    .map((blockName) => `
      <span class="popup-chip">
        ${escapeAprWatchlistHtml(blockName)}: ${blockCounts[blockName]}/${watchlist.per_block_limit}
      </span>
    `)
    .join('');
}

function buildPopupWatchlistRowsMarkup(watchlist) {
  if (!watchlist || !Array.isArray(watchlist.items) || !watchlist.items.length) {
    return '<div class="popup-empty">No runs are saved in this watchlist yet.</div>';
  }

  const rowsHtml = watchlist.items
    .map((item) => `
      <tr>
        <td>${escapeAprWatchlistHtml(item.Job || '-')}</td>
        <td>${escapeAprWatchlistHtml(item.Milestone || '-')}</td>
        <td>${escapeAprWatchlistHtml(item.Block || '-')}</td>
        <td>${escapeAprWatchlistHtml(item.Stage || '-')}</td>
        <td>${buildPopupStatusPillMarkup(item.Status)}</td>
        <td>${buildPopupPromotePillMarkup(item.Promote)}</td>
        <td>${escapeAprWatchlistHtml(formatAprWatchlistTimestamp(item.created_at))}</td>
        <td>
          <button
            type="button"
            class="popup-button danger"
            data-item-id="${item.id}"
            ${aprWatchlistPopupState.isLoading ? 'disabled' : ''}
          >
            Remove
          </button>
        </td>
      </tr>
    `)
    .join('');

  return (
    '<div class="popup-table-wrap">' +
    '<table class="popup-table">' +
    '<thead>' +
    '<tr>' +
    '<th>Job</th>' +
    '<th>Milestone</th>' +
    '<th>Block</th>' +
    '<th>Stage</th>' +
    '<th>Status</th>' +
    '<th>Promote</th>' +
    '<th>Added</th>' +
    '<th>Action</th>' +
    '</tr>' +
    '</thead>' +
    `<tbody>${rowsHtml}</tbody>` +
    '</table>' +
    '</div>'
  );
}

function buildPopupStatusPillMarkup(statusValue) {
  const toneClass = getPopupStatusToneClass(statusValue);
  return `<span class="popup-status-pill${toneClass ? ` ${toneClass}` : ''}">${escapeAprWatchlistHtml(statusValue || '-')}</span>`;
}

function buildPopupPromotePillMarkup(promoteValue) {
  const normalizedValue = String(promoteValue || '').trim().toLowerCase();
  const toneClass = normalizedValue === 'yes' ? 'is-positive' : normalizedValue === 'no' ? 'is-negative' : '';
  return `<span class="popup-promote-pill${toneClass ? ` ${toneClass}` : ''}">${escapeAprWatchlistHtml(promoteValue || '-')}</span>`;
}

function getPopupStatusToneClass(statusValue) {
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

function formatAprWatchlistTimestamp(timestamp) {
  if (!timestamp) {
    return '-';
  }

  return String(timestamp).replace('T', ' ').replace('Z', '');
}

function escapeAprWatchlistHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderAprWatchlistPopup() {
  const selectedWatchlist = findSelectedAprWatchlist();
  const addDisabled = aprWatchlistPopupState.isLoading || !selectedWatchlist || !canAddAprWatchlistRun(aprWatchlistPopupState.activeRow);
  const deleteDisabled = aprWatchlistPopupState.isLoading || !selectedWatchlist || selectedWatchlist.is_default;
  const statusClassName = aprWatchlistPopupState.statusIsError ? 'popup-status error' : 'popup-status';
  const activeWatchlistName = selectedWatchlist ? selectedWatchlist.name : 'No watchlist selected';
  const activeWatchlistMeta = selectedWatchlist
    ? (selectedWatchlist.is_default
      ? `${selectedWatchlist.item_count} runs in the current APR Weekly bucket${selectedWatchlist.week_label ? ` (${selectedWatchlist.week_label})` : ''}`
      : `${selectedWatchlist.item_count} runs in this user-defined watchlist`)
    : 'Create or select a watchlist to manage it here.';
  const activeWatchlistLimits = selectedWatchlist
    ? (selectedWatchlist.is_default
      ? `APR Weekly resets automatically every ISO week and allows up to ${selectedWatchlist.per_block_limit} runs per block${selectedWatchlist.week_label ? `. Current week: ${selectedWatchlist.week_label}` : '.'}`
      : `This watchlist allows up to ${selectedWatchlist.per_block_limit} runs per block.`)
    : 'Select a watchlist to view its limits.';
  const blockChipMarkup = buildPopupBlockChipsMarkup(selectedWatchlist);

  if (!aprWatchlistPopupRoot) {
    return;
  }

  aprWatchlistPopupRoot.innerHTML =
    '<div class="popup-card">' +
    '<div class="popup-header">' +
    '<div>' +
    '<h1 class="popup-title">APR Watchlist Manager</h1>' +
    '<p class="popup-subtitle">Use this popup to create or delete watchlists, then add or remove APR runs without leaving the tracker. APR Weekly resets automatically each ISO week.</p>' +
    '</div>' +
    '<div class="popup-toolbar">' +
    `<button type="button" class="popup-button secondary" id="popup-refresh"${aprWatchlistPopupState.isLoading ? ' disabled' : ''}>Refresh</button>` +
    '</div>' +
    '</div>' +
    `<div class="${statusClassName}">${escapeAprWatchlistHtml(aprWatchlistPopupState.statusMessage || (aprWatchlistPopupState.isLoading ? 'Loading watchlists...' : ''))}</div>` +
    '<div class="popup-layout">' +
    '<div class="popup-stack">' +
    '<section class="popup-section">' +
    '<div class="popup-header" style="margin-bottom: 12px;">' +
    '<div>' +
    '<h2 class="popup-section-title" style="margin: 0;">Selected APR Run</h2>' +
    '<p class="popup-copy">Signed in as ' + escapeAprWatchlistHtml(aprWatchlistPopupState.userId || '-') + '</p>' +
    '</div>' +
    `<button type="button" class="popup-button" id="popup-add-run"${addDisabled ? ' disabled' : ''}>Add To Selected Watchlist</button>` +
    '</div>' +
    `<div class="popup-summary-grid">${buildPopupSelectedRunMarkup()}</div>` +
    '</section>' +
    '<section class="popup-section">' +
    '<h2 class="popup-section-title">Create Watchlist</h2>' +
    '<form id="popup-create-form">' +
    '<label class="popup-label" for="popup-watchlist-name">Watchlist name</label>' +
    '<div class="popup-inline-form">' +
    `<input id="popup-watchlist-name" class="popup-input" type="text" maxlength="80" placeholder="Tapeout Focus" value="${escapeAprWatchlistHtml(aprWatchlistPopupState.draftWatchlistName)}"${aprWatchlistPopupState.isLoading ? ' disabled' : ''} />` +
    `<button type="submit" class="popup-button"${aprWatchlistPopupState.isLoading ? ' disabled' : ''}>Create</button>` +
    '</div>' +
    '</form>' +
    '</section>' +
    '<section class="popup-section">' +
    '<h2 class="popup-section-title">Available Watchlists</h2>' +
    `<div class="popup-watchlists">${buildPopupWatchlistButtonsMarkup()}</div>` +
    '</section>' +
    '</div>' +
    '<section class="popup-section">' +
    '<div class="popup-header">' +
    '<div>' +
    `<h2 class="popup-section-title" style="margin: 0;">${escapeAprWatchlistHtml(activeWatchlistName)}</h2>` +
    `<p class="popup-copy">${escapeAprWatchlistHtml(activeWatchlistMeta)}</p>` +
    '</div>' +
    `<button type="button" class="popup-button danger" id="popup-delete-watchlist"${deleteDisabled ? ' disabled' : ''}>Delete Watchlist</button>` +
    '</div>' +
    `<p class="popup-copy" style="margin-bottom: 12px;">${escapeAprWatchlistHtml(activeWatchlistLimits)}</p>` +
    `<div class="popup-chip-row">${blockChipMarkup}</div>` +
    buildPopupWatchlistRowsMarkup(selectedWatchlist) +
    '</section>' +
    '</div>' +
    '</div>';

  attachAprWatchlistPopupEvents();
}

function attachAprWatchlistPopupEvents() {
  const refreshButton = document.getElementById('popup-refresh');
  const createForm = document.getElementById('popup-create-form');
  const addButton = document.getElementById('popup-add-run');
  const deleteButton = document.getElementById('popup-delete-watchlist');

  if (refreshButton) {
    refreshButton.addEventListener('click', handleAprWatchlistPopupRefresh);
  }

  if (createForm) {
    createForm.addEventListener('submit', handleAprWatchlistPopupCreateSubmit);
  }

  if (addButton) {
    addButton.addEventListener('click', handleAprWatchlistPopupAddRun);
  }

  if (deleteButton) {
    deleteButton.addEventListener('click', handleAprWatchlistPopupDeleteWatchlist);
  }

  Array.from(document.querySelectorAll('[data-watchlist-name]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistPopupSelectWatchlist);
  });

  Array.from(document.querySelectorAll('[data-item-id]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistPopupRemoveRun);
  });
}

function handleAprWatchlistPopupRefresh() {
  loadAprWatchlistPopupState('Refreshing watchlists...');
}

async function handleAprWatchlistPopupCreateSubmit(event) {
  const nameInput = document.getElementById('popup-watchlist-name');
  const watchlistName = nameInput ? String(nameInput.value || '').trim() : '';

  event.preventDefault();
  aprWatchlistPopupState.draftWatchlistName = watchlistName;

  if (!watchlistName) {
    setAprWatchlistPopupStatus('Enter a watchlist name first.', true);
    renderAprWatchlistPopup();
    return;
  }

  aprWatchlistPopupState.isLoading = true;
  setAprWatchlistPopupStatus('Creating watchlist...', false);
  renderAprWatchlistPopup();

  try {
    const payload = await fetchAprWatchlistJson('/api/apr-watchlist/create-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: watchlistName }),
    });

    aprWatchlistPopupState.selectedWatchlistName = watchlistName;
    applyAprWatchlistPayload(payload);
    aprWatchlistPopupState.draftWatchlistName = '';
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(payload.message || 'watchlist created', false);
    renderAprWatchlistPopup();
  } catch (error) {
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(error.message, true);
    renderAprWatchlistPopup();
  }
}

function handleAprWatchlistPopupSelectWatchlist(event) {
  const watchlistName = event.currentTarget.getAttribute('data-watchlist-name');
  if (!watchlistName) {
    return;
  }

  aprWatchlistPopupState.selectedWatchlistName = watchlistName;
  setAprWatchlistPopupStatus('', false);
  renderAprWatchlistPopup();
}

async function handleAprWatchlistPopupAddRun() {
  const selectedWatchlist = findSelectedAprWatchlist();
  let normalizedRun;

  if (!selectedWatchlist) {
    setAprWatchlistPopupStatus('Select a watchlist first.', true);
    renderAprWatchlistPopup();
    return;
  }

  if (!canAddAprWatchlistRun(aprWatchlistPopupState.activeRow)) {
    setAprWatchlistPopupStatus('Only Completed PLACE, ROUTE, or CLOCK runs can be added to a watchlist.', true);
    renderAprWatchlistPopup();
    return;
  }

  try {
    normalizedRun = normalizeAprWatchlistRun(aprWatchlistPopupState.activeRow);
  } catch (error) {
    setAprWatchlistPopupStatus(error.message, true);
    renderAprWatchlistPopup();
    return;
  }

  aprWatchlistPopupState.isLoading = true;
  setAprWatchlistPopupStatus('Adding selected run...', false);
  renderAprWatchlistPopup();

  try {
    const payload = await fetchAprWatchlistJson('/api/apr-watchlist/add-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watchlist_name: selectedWatchlist.name,
        run: normalizedRun,
      }),
    });

    applyAprWatchlistPayload(payload);
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(payload.message || 'run added to watchlist', false);
    renderAprWatchlistPopup();
  } catch (error) {
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(error.message, true);
    renderAprWatchlistPopup();
  }
}

async function handleAprWatchlistPopupDeleteWatchlist() {
  const selectedWatchlist = findSelectedAprWatchlist();

  if (!selectedWatchlist || selectedWatchlist.is_default) {
    return;
  }

  if (!window.confirm(`Delete watchlist "${selectedWatchlist.name}" and all of its saved runs?`)) {
    return;
  }

  aprWatchlistPopupState.isLoading = true;
  setAprWatchlistPopupStatus('Deleting watchlist...', false);
  renderAprWatchlistPopup();

  try {
    const payload = await fetchAprWatchlistJson('/api/apr-watchlist/delete-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: selectedWatchlist.name }),
    });

    aprWatchlistPopupState.selectedWatchlistName = aprWatchlistPopupState.defaultWatchlist;
    applyAprWatchlistPayload(payload);
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(payload.message || 'watchlist deleted', false);
    renderAprWatchlistPopup();
  } catch (error) {
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(error.message, true);
    renderAprWatchlistPopup();
  }
}

async function handleAprWatchlistPopupRemoveRun(event) {
  const itemId = Number(event.currentTarget.getAttribute('data-item-id'));

  if (!itemId) {
    return;
  }

  if (!window.confirm('Remove this run from the selected watchlist?')) {
    return;
  }

  aprWatchlistPopupState.isLoading = true;
  setAprWatchlistPopupStatus('Removing run...', false);
  renderAprWatchlistPopup();

  try {
    const payload = await fetchAprWatchlistJson('/api/apr-watchlist/delete-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_id: itemId }),
    });

    applyAprWatchlistPayload(payload);
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(payload.message || 'run removed from watchlist', false);
    renderAprWatchlistPopup();
  } catch (error) {
    aprWatchlistPopupState.isLoading = false;
    setAprWatchlistPopupStatus(error.message, true);
    renderAprWatchlistPopup();
  }
}

function handleAprWatchlistPopupDOMContentLoaded() {
  connectAprWatchlistPopupBridge();
  syncAprWatchlistPopupActiveRowFromBridge();
  renderAprWatchlistPopup();
  loadAprWatchlistPopupState(
    aprWatchlistPopupState.activeRow
      ? 'Selected run updated. Choose a watchlist to add it.'
      : 'Loading watchlists...'
  );
}
