window.APR_BUTTONS = window.APR_BUTTONS || [];

const APR_WATCHLIST_POPUP_NAME = 'apr-watchlist-manager';
const APR_WATCHLIST_POPUP_FEATURES = 'popup=yes,width=1180,height=820,resizable=yes,scrollbars=yes';
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

const aprWatchlistPopupState = {
  popupWindow: null,
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

function buildAprWatchlistPopupShell(doc) {
  doc.open();
  doc.write(
    '<!DOCTYPE html>' +
    '<html lang="en">' +
    '<head>' +
    '<meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1">' +
    '<title>APR Watchlist Manager</title>' +
    '<style>' +
    ':root { color-scheme: light; }' +
    '* { box-sizing: border-box; }' +
    'body { margin: 0; font-family: Arial, sans-serif; background: #f5f7fa; color: #1b1c1d; }' +
    '.popup-shell { padding: 18px; }' +
    '.popup-card { background: #ffffff; border: 1px solid rgba(20, 33, 50, 0.08); border-radius: 16px; box-shadow: 0 16px 36px rgba(30, 54, 80, 0.08); padding: 16px; }' +
    '.popup-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }' +
    '.popup-title { margin: 0; font-size: 24px; font-weight: 700; }' +
    '.popup-subtitle { margin: 6px 0 0; color: rgba(20, 33, 50, 0.7); font-size: 13px; line-height: 1.5; }' +
    '.popup-toolbar { display: flex; flex-wrap: wrap; gap: 8px; }' +
    '.popup-layout { display: grid; grid-template-columns: minmax(280px, 340px) minmax(0, 1fr); gap: 16px; }' +
    '.popup-stack { display: grid; gap: 16px; }' +
    '.popup-section { border: 1px solid rgba(20, 33, 50, 0.08); background: #ffffff; border-radius: 14px; padding: 14px; }' +
    '.popup-section-title { margin: 0 0 12px; font-size: 16px; font-weight: 700; }' +
    '.popup-status { min-height: 20px; margin-bottom: 12px; font-size: 13px; color: #315f2b; }' +
    '.popup-status.error { color: #b42318; }' +
    '.popup-button { border: 0; border-radius: 10px; padding: 9px 14px; font-size: 13px; font-weight: 700; cursor: pointer; background: #1f6feb; color: #ffffff; }' +
    '.popup-button.secondary { background: #eef2f7; color: #1b1c1d; }' +
    '.popup-button.danger { background: #d92d20; }' +
    '.popup-button:disabled { opacity: 0.55; cursor: not-allowed; }' +
    '.popup-label { display: block; margin-bottom: 6px; font-size: 12px; font-weight: 700; color: #4c6280; text-transform: uppercase; letter-spacing: 0.05em; }' +
    '.popup-inline-form { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }' +
    '.popup-input { width: 100%; min-height: 40px; border: 1px solid rgba(20, 33, 50, 0.14); border-radius: 10px; padding: 8px 10px; font-size: 14px; background: #ffffff; color: #1b1c1d; }' +
    '.popup-summary-grid { display: grid; gap: 8px; }' +
    '.popup-summary-item { border: 1px solid rgba(20, 33, 50, 0.08); background: #f9fbfd; border-radius: 12px; padding: 10px 12px; }' +
    '.popup-summary-key { display: block; margin-bottom: 4px; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: rgba(20, 33, 50, 0.58); }' +
    '.popup-summary-value { font-size: 13px; font-weight: 700; word-break: break-word; }' +
    '.popup-watchlists { display: grid; gap: 8px; }' +
    '.popup-watchlist-button { width: 100%; border: 1px solid rgba(20, 33, 50, 0.08); border-radius: 12px; background: #f9fbfd; padding: 11px 12px; text-align: left; cursor: pointer; transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease; }' +
    '.popup-watchlist-button:hover { transform: translateY(-1px); border-color: rgba(15, 108, 189, 0.35); }' +
    '.popup-watchlist-button.active { background: #eef5fd; border-color: #9fc3ea; box-shadow: 0 12px 24px rgba(15, 108, 189, 0.12); }' +
    '.popup-watchlist-title { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-weight: 700; }' +
    '.popup-watchlist-meta { display: block; margin-top: 6px; font-size: 12px; color: rgba(20, 33, 50, 0.72); }' +
    '.popup-badge, .popup-chip { display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; font-weight: 700; }' +
    '.popup-badge { min-width: 1.65rem; padding: 0.2rem 0.5rem; background: rgba(15, 108, 189, 0.12); color: #18548d; font-size: 0.75rem; }' +
    '.popup-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }' +
    '.popup-chip { padding: 0.38rem 0.74rem; background: #ecf3fb; color: #214d80; font-size: 0.78rem; }' +
    '.popup-copy { margin: 0; color: rgba(20, 33, 50, 0.7); font-size: 13px; line-height: 1.5; }' +
    '.popup-table-wrap { overflow: auto; border: 1px solid rgba(20, 33, 50, 0.08); border-radius: 12px; background: #ffffff; }' +
    '.popup-table { width: 100%; border-collapse: collapse; font-size: 13px; }' +
    '.popup-table th, .popup-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid rgba(20, 33, 50, 0.08); vertical-align: middle; }' +
    '.popup-table th { background: #eef2f7; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: #4c6280; position: sticky; top: 0; }' +
    '.popup-table tr:last-child td { border-bottom: 0; }' +
    '.popup-empty { padding: 24px 16px; text-align: center; color: rgba(20, 33, 50, 0.66); font-size: 13px; }' +
    '.popup-status-pill, .popup-promote-pill { display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; padding: 0.35rem 0.68rem; font-size: 0.78rem; font-weight: 700; background: #eef2f7; color: #44566d; }' +
    '.is-positive { background: #e9f8ec; color: #1f5e31; }' +
    '.is-negative { background: #fde8e7; color: #9b2c2c; }' +
    '.is-warning { background: #fff4dc; color: #8a5a00; }' +
    '.is-info { background: #e7f1fb; color: #1f4f8c; }' +
    '@media (max-width: 920px) { .popup-layout { grid-template-columns: 1fr; } .popup-shell { padding: 12px; } }' +
    '</style>' +
    '</head>' +
    '<body>' +
    '<div id="apr-watchlist-root" class="popup-shell"></div>' +
    '</body>' +
    '</html>'
  );
  doc.close();
}

function ensureAprWatchlistPopupWindow() {
  if (aprWatchlistPopupState.popupWindow && !aprWatchlistPopupState.popupWindow.closed) {
    if (!aprWatchlistPopupState.popupWindow.document.getElementById('apr-watchlist-root')) {
      buildAprWatchlistPopupShell(aprWatchlistPopupState.popupWindow.document);
    }
    return aprWatchlistPopupState.popupWindow;
  }

  aprWatchlistPopupState.popupWindow = window.open('', APR_WATCHLIST_POPUP_NAME, APR_WATCHLIST_POPUP_FEATURES);

  if (!aprWatchlistPopupState.popupWindow) {
    window.alert('Unable to open the APR Watchlist window. Please allow pop-ups for this site.');
    return null;
  }

  buildAprWatchlistPopupShell(aprWatchlistPopupState.popupWindow.document);
  return aprWatchlistPopupState.popupWindow;
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

function setAprWatchlistPopupStatus(message, isError) {
  aprWatchlistPopupState.statusMessage = message || '';
  aprWatchlistPopupState.statusIsError = Boolean(isError);
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
  if (typeof window.getAPRTrackerRowLabel === 'function') {
    return window.getAPRTrackerRowLabel(row || {});
  }

  return [row.Job, row.Milestone, row.Block, row.Stage]
    .filter((value) => value)
    .join(' / ');
}

function buildPopupSelectedRunMarkup() {
  if (!aprWatchlistPopupState.activeRow) {
    return '<div class="popup-empty">Select a tracker row to add it into a watchlist.</div>';
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
        ? `Weekly default${watchlist.week_label ? ` · ${watchlist.week_label}` : ''}`
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
  const popupWindow = ensureAprWatchlistPopupWindow();
  if (!popupWindow) {
    return;
  }

  const doc = popupWindow.document;
  const root = doc.getElementById('apr-watchlist-root');
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

  root.innerHTML =
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

  attachAprWatchlistPopupEvents(doc);
}

function attachAprWatchlistPopupEvents(doc) {
  const refreshButton = doc.getElementById('popup-refresh');
  const createForm = doc.getElementById('popup-create-form');
  const addButton = doc.getElementById('popup-add-run');
  const deleteButton = doc.getElementById('popup-delete-watchlist');

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

  Array.from(doc.querySelectorAll('[data-watchlist-name]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistPopupSelectWatchlist);
  });

  Array.from(doc.querySelectorAll('[data-item-id]')).forEach((button) => {
    button.addEventListener('click', handleAprWatchlistPopupRemoveRun);
  });
}

function handleAprWatchlistPopupRefresh() {
  loadAprWatchlistPopupState('Refreshing watchlists...');
}

async function handleAprWatchlistPopupCreateSubmit(event) {
  event.preventDefault();

  const popupWindow = ensureAprWatchlistPopupWindow();
  const nameInput = popupWindow && popupWindow.document.getElementById('popup-watchlist-name');
  const watchlistName = nameInput ? String(nameInput.value || '').trim() : '';
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
  const popupWindow = ensureAprWatchlistPopupWindow();
  const selectedWatchlist = findSelectedAprWatchlist();

  if (!selectedWatchlist || selectedWatchlist.is_default) {
    return;
  }

  if (!popupWindow.confirm(`Delete watchlist "${selectedWatchlist.name}" and all of its saved runs?`)) {
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
  const popupWindow = ensureAprWatchlistPopupWindow();
  const itemId = Number(event.currentTarget.getAttribute('data-item-id'));

  if (!itemId) {
    return;
  }

  if (!popupWindow.confirm('Remove this run from the selected watchlist?')) {
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

function openAprWatchlistPopup(row) {
  aprWatchlistPopupState.activeRow = row || null;

  if (!ensureAprWatchlistPopupWindow()) {
    return;
  }

  setAprWatchlistPopupStatus(
    aprWatchlistPopupState.activeRow
      ? 'Selected run updated. Choose a watchlist to add it.'
      : aprWatchlistPopupState.statusMessage,
    false
  );
  renderAprWatchlistPopup();
  loadAprWatchlistPopupState(aprWatchlistPopupState.statusMessage);

  if (aprWatchlistPopupState.popupWindow && !aprWatchlistPopupState.popupWindow.closed) {
    aprWatchlistPopupState.popupWindow.focus();
  }
}

function isAprWatchlistButtonDisabled(row) {
  return String((row && row.Status) || '').trim().toLowerCase() !== 'completed';
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
