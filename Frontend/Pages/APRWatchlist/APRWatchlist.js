const createWatchlistForm = document.getElementById('createWatchlistForm');
const newWatchlistNameInput = document.getElementById('newWatchlistName');
const watchlistUserId = document.getElementById('watchlistUserId');
const watchlistList = document.getElementById('watchlistList');
const watchlistMessage = document.getElementById('watchlistMessage');
const selectedRunPanel = document.getElementById('selectedRunPanel');
const selectedRunSummary = document.getElementById('selectedRunSummary');
const addSelectedRunButton = document.getElementById('addSelectedRunButton');
const activeWatchlistName = document.getElementById('activeWatchlistName');
const activeWatchlistMeta = document.getElementById('activeWatchlistMeta');
const activeWatchlistLimits = document.getElementById('activeWatchlistLimits');
const activeWatchlistBlocks = document.getElementById('activeWatchlistBlocks');
const deleteWatchlistButton = document.getElementById('deleteWatchlistButton');
const watchlistItemsBody = document.getElementById('watchlistItemsBody');
const watchlistEmptyState = document.getElementById('watchlistEmptyState');

const watchlistState = {
  userId: '',
  defaultWatchlist: 'APR Weekly',
  selectedWatchlistName: '',
  selectedRun: null,
  watchlists: [],
};

window.addEventListener('DOMContentLoaded', initializeAprWatchlistPage);

async function initializeAprWatchlistPage() {
  document.body.dataset.page = 'apr-watchlist';
  watchlistState.selectedRun = getSelectedRunFromQuery();
  bindWatchlistEvents();

  try {
    await loadWatchlists();
  } catch (error) {
    showWatchlistMessage(error.message, false);
  }
}

function bindWatchlistEvents() {
  createWatchlistForm.addEventListener('submit', handleCreateWatchlist);
  watchlistList.addEventListener('click', handleWatchlistSelection);
  addSelectedRunButton.addEventListener('click', handleAddSelectedRun);
  deleteWatchlistButton.addEventListener('click', handleDeleteWatchlist);
  watchlistItemsBody.addEventListener('click', handleWatchlistTableClick);
}

function getSelectedRunFromQuery() {
  const query = new URLSearchParams(window.location.search);
  const runParam = query.get('run');

  if (!runParam) {
    return null;
  }

  try {
    const parsed = JSON.parse(runParam);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch (error) {
    console.error(error);
    return null;
  }
}

async function fetchJson(url, options = {}) {
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

async function loadWatchlists() {
  const payload = await fetchJson('/api/apr-watchlist');
  applyWatchlistPayload(payload);
}

function applyWatchlistPayload(payload) {
  watchlistState.userId = String(payload.user_id || '');
  watchlistState.defaultWatchlist = String(payload.default_watchlist || 'APR Weekly');
  watchlistState.watchlists = Array.isArray(payload.watchlists) ? payload.watchlists : [];

  if (!watchlistState.watchlists.length) {
    watchlistState.selectedWatchlistName = '';
  } else if (!findSelectedWatchlist()) {
    const defaultWatchlist = watchlistState.watchlists.find((watchlist) => watchlist.is_default);
    watchlistState.selectedWatchlistName = defaultWatchlist
      ? defaultWatchlist.name
      : watchlistState.watchlists[0].name;
  }

  renderWatchlistPage();
}

function renderWatchlistPage() {
  watchlistUserId.textContent = watchlistState.userId || '-';
  renderWatchlistList();
  renderSelectedRunPanel();
  renderActiveWatchlist();
}

function renderWatchlistList() {
  if (!watchlistState.watchlists.length) {
    watchlistList.innerHTML = '<div class="watchlist-empty-state">No watchlists available.</div>';
    return;
  }

  watchlistList.innerHTML = watchlistState.watchlists
    .map((watchlist) => {
      const isActive = watchlist.name === watchlistState.selectedWatchlistName;
      const limitLabel = `${watchlist.per_block_limit} / block`;
      return `
        <button
          type="button"
          class="watchlist-list-button${isActive ? ' is-active' : ''}"
          data-watchlist-name="${escapeHtml(watchlist.name)}"
        >
          <span class="watchlist-list-title">
            <span>${escapeHtml(watchlist.name)}</span>
            <span class="watchlist-badge">${watchlist.item_count}</span>
          </span>
          <span class="watchlist-list-meta">
            ${watchlist.is_default ? 'Permanent default' : 'Custom watchlist'} &middot; ${limitLabel}
          </span>
        </button>
      `;
    })
    .join('');
}

function renderSelectedRunPanel() {
  const selectedRun = watchlistState.selectedRun;
  if (!selectedRun) {
    selectedRunPanel.classList.add('is-hidden');
    return;
  }

  selectedRunPanel.classList.remove('is-hidden');
  selectedRunSummary.innerHTML = buildRunSummaryMarkup(selectedRun);
  addSelectedRunButton.disabled = !findSelectedWatchlist();
}

function renderActiveWatchlist() {
  const watchlist = findSelectedWatchlist();

  if (!watchlist) {
    activeWatchlistName.textContent = 'No watchlist selected';
    activeWatchlistMeta.textContent = '';
    activeWatchlistLimits.textContent = '';
    activeWatchlistBlocks.innerHTML = '';
    deleteWatchlistButton.style.display = 'none';
    watchlistItemsBody.innerHTML = '';
    watchlistEmptyState.classList.remove('is-hidden');
    return;
  }

  activeWatchlistName.textContent = watchlist.name;
  activeWatchlistMeta.textContent = watchlist.is_default
    ? `${watchlist.item_count} saved runs in the permanent default watchlist`
    : `${watchlist.item_count} saved runs in this user-defined watchlist`;
  activeWatchlistLimits.textContent = `This watchlist allows up to ${watchlist.per_block_limit} runs per unique block entry.`;
  deleteWatchlistButton.style.display = watchlist.is_default ? 'none' : '';
  renderBlockChips(watchlist);
  renderWatchlistItems(watchlist);
}

function renderBlockChips(watchlist) {
  const blockCounts = {};

  watchlist.items.forEach((item) => {
    const blockName = String(item.Block || '').trim() || 'Unknown Block';
    blockCounts[blockName] = (blockCounts[blockName] || 0) + 1;
  });

  const blockNames = Object.keys(blockCounts).sort((leftName, rightName) => leftName.localeCompare(rightName));
  if (!blockNames.length) {
    activeWatchlistBlocks.innerHTML = '';
    return;
  }

  activeWatchlistBlocks.innerHTML = blockNames
    .map((blockName) => {
      const count = blockCounts[blockName];
      return `<span class="watchlist-block-chip">${escapeHtml(blockName)}: ${count}/${watchlist.per_block_limit}</span>`;
    })
    .join('');
}

function renderWatchlistItems(watchlist) {
  if (!watchlist.items.length) {
    watchlistItemsBody.innerHTML = '';
    watchlistEmptyState.classList.remove('is-hidden');
    return;
  }

  watchlistEmptyState.classList.add('is-hidden');
  watchlistItemsBody.innerHTML = watchlist.items
    .map((item) => `
      <tr>
        <td>${escapeHtml(item.Job || '-')}</td>
        <td>${escapeHtml(item.Milestone || '-')}</td>
        <td>${escapeHtml(item.Block || '-')}</td>
        <td>${escapeHtml(item.Stage || '-')}</td>
        <td>${escapeHtml(item.Status || '-')}</td>
        <td>${escapeHtml(item.Promote || '-')}</td>
        <td>${escapeHtml(formatTimestamp(item.created_at))}</td>
        <td>
          <button type="button" class="ui mini button negative" data-item-id="${item.id}">
            Remove
          </button>
        </td>
      </tr>
    `)
    .join('');
}

function buildRunSummaryMarkup(run) {
  const summaryFields = [
    ['Job', run.Job],
    ['Milestone', run.Milestone],
    ['Block', run.Block],
    ['Stage', run.Stage],
    ['Status', run.Status],
    ['Promote', run.Promote],
    ['Owner', run.User],
    ['DFT Release', run.Dft_release],
  ];

  return summaryFields
    .map(([label, value]) => `
      <div class="watchlist-summary-card">
        <span class="watchlist-summary-card-label">${escapeHtml(label)}</span>
        <span class="watchlist-summary-card-value">${escapeHtml(String(value || '-'))}</span>
      </div>
    `)
    .join('');
}

async function handleCreateWatchlist(event) {
  event.preventDefault();

  const watchlistName = newWatchlistNameInput.value.trim();
  if (!watchlistName) {
    showWatchlistMessage('Enter a watchlist name first.', false);
    return;
  }

  try {
    const payload = await fetchJson('/api/apr-watchlist/create-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: watchlistName }),
    });

    watchlistState.selectedWatchlistName = watchlistName;
    applyWatchlistPayload(payload);
    newWatchlistNameInput.value = '';
    showWatchlistMessage(payload.message || 'watchlist created', true);
  } catch (error) {
    showWatchlistMessage(error.message, false);
  }
}

function handleWatchlistSelection(event) {
  const button = event.target.closest('[data-watchlist-name]');
  if (!button) {
    return;
  }

  watchlistState.selectedWatchlistName = button.dataset.watchlistName;
  renderWatchlistPage();
}

async function handleAddSelectedRun() {
  const watchlist = findSelectedWatchlist();
  if (!watchlist) {
    showWatchlistMessage('Select a watchlist first.', false);
    return;
  }

  if (!watchlistState.selectedRun) {
    showWatchlistMessage('No APR run was passed into this window.', false);
    return;
  }

  try {
    const payload = await fetchJson('/api/apr-watchlist/add-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watchlist_name: watchlist.name,
        run: watchlistState.selectedRun,
      }),
    });

    applyWatchlistPayload(payload);
    showWatchlistMessage(payload.message || 'run added to watchlist', true);
  } catch (error) {
    showWatchlistMessage(error.message, false);
  }
}

async function handleDeleteWatchlist() {
  const watchlist = findSelectedWatchlist();
  if (!watchlist || watchlist.is_default) {
    return;
  }

  const shouldDelete = window.confirm(`Delete watchlist "${watchlist.name}" and all of its saved runs?`);
  if (!shouldDelete) {
    return;
  }

  try {
    const payload = await fetchJson('/api/apr-watchlist/delete-watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist_name: watchlist.name }),
    });

    watchlistState.selectedWatchlistName = watchlistState.defaultWatchlist;
    applyWatchlistPayload(payload);
    showWatchlistMessage(payload.message || 'watchlist deleted', true);
  } catch (error) {
    showWatchlistMessage(error.message, false);
  }
}

async function handleWatchlistTableClick(event) {
  const removeButton = event.target.closest('[data-item-id]');
  if (!removeButton) {
    return;
  }

  try {
    const payload = await fetchJson('/api/apr-watchlist/delete-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        item_id: Number(removeButton.dataset.itemId),
      }),
    });

    applyWatchlistPayload(payload);
    showWatchlistMessage(payload.message || 'run removed from watchlist', true);
  } catch (error) {
    showWatchlistMessage(error.message, false);
  }
}

function findSelectedWatchlist() {
  return watchlistState.watchlists.find((watchlist) => watchlist.name === watchlistState.selectedWatchlistName) || null;
}

function showWatchlistMessage(message, isSuccess) {
  watchlistMessage.textContent = message;
  watchlistMessage.className = `watchlist-message ${isSuccess ? 'is-success' : 'is-error'}`;
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '-';
  }

  return String(timestamp).replace('T', ' ').replace('Z', '');
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
