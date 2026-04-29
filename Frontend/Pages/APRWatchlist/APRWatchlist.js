const GRAPH_STAGE_ORDER = ['PLACE', 'CLOCK', 'ROUTE'];
const GRAPH_SEQUENTIAL_LABEL = 'Timing Setup Seq';
const GRAPH_COLORS = [
  '#1f6feb',
  '#0f766e',
  '#84a000',
  '#dc6803',
  '#d92d20',
  '#2563eb',
  '#1d4ed8',
  '#15803d',
];

const watchlistUserId = document.getElementById('watchlistUserId');
const watchlistList = document.getElementById('watchlistList');
const watchlistMessage = document.getElementById('watchlistMessage');
const activeWatchlistName = document.getElementById('activeWatchlistName');
const activeWatchlistMeta = document.getElementById('activeWatchlistMeta');
const activeWatchlistLimits = document.getElementById('activeWatchlistLimits');
const activeWatchlistBlocks = document.getElementById('activeWatchlistBlocks');
const watchlistItemsBody = document.getElementById('watchlistItemsBody');
const watchlistEmptyState = document.getElementById('watchlistEmptyState');
const graphWatchlistSelect = document.getElementById('graphWatchlistSelect');
const graphBlockSelect = document.getElementById('graphBlockSelect');
const graphModeSelect = document.getElementById('graphModeSelect');
const graphTcheckSelect = document.getElementById('graphTcheckSelect');
const graphTcornerSelect = document.getElementById('graphTcornerSelect');
const graphVoltageSelect = document.getElementById('graphVoltageSelect');
const applyGraphFiltersButton = document.getElementById('applyGraphFiltersButton');
const reloadGraphDataButton = document.getElementById('reloadGraphDataButton');
const pathgroupCheckboxes = document.getElementById('pathgroupCheckboxes');
const watchlistSummaryChip = document.getElementById('watchlistSummaryChip');
const watchlistSourceChip = document.getElementById('watchlistSourceChip');
const watchlistNoticeArea = document.getElementById('watchlistNoticeArea');
const watchlistCardsContainer = document.getElementById('watchlistCardsContainer');

const watchlistState = {
  userId: '',
  defaultWatchlist: 'APR Weekly',
  selectedWatchlistName: '',
  watchlists: [],
  timingRuns: [],
  timingBlocks: [],
  timingFilters: {
    modes: [],
    tchecks: [],
    tcorners: [],
    voltages: [],
  },
  selectedBlock: '',
  selectedMode: '',
  selectedTcheck: '',
  selectedTcorner: '',
  selectedVoltage: '',
  selectedPathgroups: [],
  timingSource: 'unknown',
  timingNotice: '',
  timingNoticeIsError: false,
  activeCharts: [],
};

window.addEventListener('DOMContentLoaded', initializeAprWatchlistPage);

async function initializeAprWatchlistPage() {
  document.body.dataset.page = 'apr-watchlist';
  bindAprWatchlistEvents();

  try {
    await reloadAprWatchlistPageData();
  } catch (error) {
    showWatchlistMessage(error.message, false);
  }
}

function bindAprWatchlistEvents() {
  watchlistList.addEventListener('click', handleWatchlistSelection);
  graphWatchlistSelect.addEventListener('change', handleGraphWatchlistChange);
  graphBlockSelect.addEventListener('change', handleGraphBlockChange);
  graphModeSelect.addEventListener('change', handleGraphModeChange);
  graphTcheckSelect.addEventListener('change', handleGraphTcheckChange);
  graphTcornerSelect.addEventListener('change', handleGraphTcornerChange);
  graphVoltageSelect.addEventListener('change', handleGraphVoltageChange);
  applyGraphFiltersButton.addEventListener('click', handleApplyGraphFilters);
  reloadGraphDataButton.addEventListener('click', handleReloadGraphData);
  pathgroupCheckboxes.addEventListener('change', handlePathgroupSelectionChange);
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

async function reloadAprWatchlistPageData() {
  showWatchlistMessage('', true);
  const payload = await fetchJson('/api/apr-watchlist');
  applyWatchlistPayload(payload);
  await loadTimingDataForSelectedWatchlist();
  renderAprWatchlistPage();
}

function applyWatchlistPayload(payload) {
  watchlistState.userId = String(payload.user_id || '');
  watchlistState.defaultWatchlist = String(payload.default_watchlist || 'APR Weekly');
  watchlistState.watchlists = Array.isArray(payload.watchlists) ? payload.watchlists : [];

  if (!watchlistState.watchlists.length) {
    watchlistState.selectedWatchlistName = '';
    return;
  }

  if (findSelectedWatchlist()) {
    return;
  }

  const defaultWatchlist = watchlistState.watchlists.find((watchlist) => watchlist.is_default);
  watchlistState.selectedWatchlistName = defaultWatchlist
    ? defaultWatchlist.name
    : watchlistState.watchlists[0].name;
}

async function loadTimingDataForSelectedWatchlist() {
  const selectedWatchlist = findSelectedWatchlist();

  if (!selectedWatchlist) {
    applyTimingPayload({
      watchlist_name: '',
      source: 'unknown',
      blocks: [],
      filters: {
        modes: [],
        tchecks: [],
        tcorners: [],
        voltages: [],
      },
      runs: [],
      default_block: '',
    });
    return;
  }

  setTimingNotice('Loading timing data for the selected watchlist...', false);
  renderTimingViewer();

  try {
    const payload = await fetchJson(`/api/apr-watchlist/timing-data?watchlist_name=${encodeURIComponent(selectedWatchlist.name)}`);
    applyTimingPayload(payload);
  } catch (error) {
    applyTimingPayload({
      watchlist_name: selectedWatchlist.name,
      source: 'unknown',
      blocks: [],
      filters: {
        modes: [],
        tchecks: [],
        tcorners: [],
        voltages: [],
      },
      runs: [],
      default_block: '',
    });
    setTimingNotice(error.message, true);
  }
}

function applyTimingPayload(payload) {
  const nextRuns = Array.isArray(payload.runs) ? payload.runs : [];
  const nextBlocks = Array.isArray(payload.blocks) ? payload.blocks : [];
  const nextFilters = normalizeTimingFilters(payload.filters);

  watchlistState.timingRuns = nextRuns;
  watchlistState.timingBlocks = nextBlocks;
  watchlistState.timingFilters = nextFilters;
  watchlistState.timingSource = String(payload.source || 'unknown');

  if (!nextBlocks.includes(watchlistState.selectedBlock)) {
    watchlistState.selectedBlock = String(payload.default_block || nextBlocks[0] || '');
  }

  syncTimingFilterSelections();
  syncSelectedPathgroups();

  if (!watchlistState.timingRuns.length) {
    setTimingNotice('No timing summary rows are available for this watchlist yet.', false);
  } else if (!watchlistState.timingNoticeIsError) {
    setTimingNotice('Pathgroup charts use per-stage APR_TIMING_SUMMARY rows filtered by mode, tcheck, tcorner, and voltage. Timing Setup Seq remains tied to APR_TRACKER setup sequence fields.', false);
  }
}

function renderAprWatchlistPage() {
  watchlistUserId.textContent = watchlistState.userId || '-';
  renderWatchlistList();
  renderTimingControls();
  renderTimingViewer();
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
      const watchlistType = watchlist.is_default
        ? `Weekly default${watchlist.week_label ? ` · ${watchlist.week_label}` : ''}`
        : 'Custom watchlist';

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
            ${watchlistType} &middot; ${limitLabel}
          </span>
        </button>
      `;
    })
    .join('');
}

function renderTimingControls() {
  const selectedWatchlist = findSelectedWatchlist();
  const watchlistNames = watchlistState.watchlists.map((watchlist) => watchlist.name);
  const currentFilterOptions = getCurrentTimingFilterOptions();

  setSelectOptions(
    graphWatchlistSelect,
    watchlistNames,
    watchlistState.selectedWatchlistName,
    'No watchlists'
  );

  setSelectOptions(
    graphBlockSelect,
    watchlistState.timingBlocks,
    watchlistState.selectedBlock,
    'No blocks'
  );

  setSelectOptions(
    graphModeSelect,
    currentFilterOptions.modes,
    watchlistState.selectedMode,
    'No modes'
  );

  setSelectOptions(
    graphTcheckSelect,
    currentFilterOptions.tchecks,
    watchlistState.selectedTcheck,
    'No tchecks'
  );

  setSelectOptions(
    graphTcornerSelect,
    currentFilterOptions.tcorners,
    watchlistState.selectedTcorner,
    'No tcorners'
  );

  setSelectOptions(
    graphVoltageSelect,
    currentFilterOptions.voltages,
    watchlistState.selectedVoltage,
    'No voltages'
  );

  renderPathgroupCheckboxes();

  graphWatchlistSelect.disabled = !watchlistNames.length;
  graphBlockSelect.disabled = !watchlistState.timingBlocks.length;
  graphModeSelect.disabled = !currentFilterOptions.modes.length;
  graphTcheckSelect.disabled = !currentFilterOptions.tchecks.length;
  graphTcornerSelect.disabled = !currentFilterOptions.tcorners.length;
  graphVoltageSelect.disabled = !currentFilterOptions.voltages.length;
  applyGraphFiltersButton.disabled = !selectedWatchlist;
  reloadGraphDataButton.disabled = !selectedWatchlist;
}

function renderPathgroupCheckboxes() {
  const selectablePathgroups = getSelectablePathgroups();

  if (!selectablePathgroups.length) {
    pathgroupCheckboxes.innerHTML = '<div class="watchlist-small">No graph options available for the selected watchlist.</div>';
    return;
  }

  pathgroupCheckboxes.innerHTML = selectablePathgroups
    .map((pathgroup) => `
      <label class="watchlist-checkbox-item">
        <input
          type="checkbox"
          class="watchlist-pathgroup-checkbox"
          value="${escapeHtml(pathgroup)}"
          ${watchlistState.selectedPathgroups.includes(pathgroup) ? 'checked' : ''}
        />
        <span>${escapeHtml(pathgroup)}</span>
      </label>
    `)
    .join('');
}

function renderTimingViewer() {
  const filteredRuns = getTimingRunsForSelectedBlock();
  const filteredSummaryRows = getFilteredTimingSummaryRows(filteredRuns);
  const selectedPathgroups = getSelectedPathgroups();
  let renderedCards = 0;

  destroyTimingCharts();
  renderTimingNotice();

  watchlistSummaryChip.textContent = watchlistState.timingRuns.length
    ? `${filteredRuns.length} runs loaded · ${filteredSummaryRows.length} timing rows matched`
    : 'No timing data loaded';
  watchlistSourceChip.textContent = `Source: ${watchlistState.timingSource || 'unknown'}`;

  if (!filteredRuns.length) {
    watchlistCardsContainer.innerHTML = `
      <div class="watchlist-empty-state is-graph-empty">
        No timing runs match the selected watchlist and block.
      </div>
    `;
    return;
  }

  if (!filteredSummaryRows.length && !shouldShowSequentialGraph()) {
    watchlistCardsContainer.innerHTML = `
      <div class="watchlist-empty-state is-graph-empty">
        No timing summary rows match the selected mode, tcheck, tcorner, and voltage for this block.
      </div>
    `;
    return;
  }

  if (!selectedPathgroups.length) {
    watchlistCardsContainer.innerHTML = `
      <div class="watchlist-empty-state is-graph-empty">
        Select at least one graph to render.
      </div>
    `;
    return;
  }

  watchlistCardsContainer.innerHTML = '';

  selectedPathgroups.forEach((pathgroup) => {
    const series = buildGraphSeries(filteredRuns, pathgroup);

    if (!series.length) {
      return;
    }

    createTimingGraphCard(pathgroup, series);
    renderedCards += 1;
  });

  if (!renderedCards) {
    watchlistCardsContainer.innerHTML = `
      <div class="watchlist-empty-state is-graph-empty">
        The selected pathgroups do not have plottable data for this block.
      </div>
    `;
  }
}

function renderTimingNotice() {
  if (!watchlistState.timingNotice) {
    watchlistNoticeArea.innerHTML = '';
    return;
  }

  watchlistNoticeArea.innerHTML = `
    <div class="watchlist-notice${watchlistState.timingNoticeIsError ? ' is-error' : ''}">
      ${escapeHtml(watchlistState.timingNotice)}
    </div>
  `;
}

function renderActiveWatchlist() {
  const selectedWatchlist = findSelectedWatchlist();

  if (!selectedWatchlist) {
    activeWatchlistName.textContent = 'No watchlist selected';
    activeWatchlistMeta.textContent = '';
    activeWatchlistLimits.textContent = '';
    activeWatchlistBlocks.innerHTML = '';
    watchlistItemsBody.innerHTML = '';
    watchlistEmptyState.classList.remove('is-hidden');
    return;
  }

  activeWatchlistName.textContent = selectedWatchlist.name;
  activeWatchlistMeta.textContent = selectedWatchlist.is_default
    ? `${selectedWatchlist.item_count} saved runs in the current APR Weekly bucket${selectedWatchlist.week_label ? ` (${selectedWatchlist.week_label})` : ''}`
    : `${selectedWatchlist.item_count} saved runs in this user-defined watchlist`;
  activeWatchlistLimits.textContent = selectedWatchlist.is_default
    ? `APR Weekly resets automatically every ISO week and allows up to ${selectedWatchlist.per_block_limit} runs per unique block entry${selectedWatchlist.week_label ? `. Current week: ${selectedWatchlist.week_label}` : '.'}`
    : `This watchlist allows up to ${selectedWatchlist.per_block_limit} runs per unique block entry.`;
  renderBlockChips(selectedWatchlist);
  renderWatchlistItems(selectedWatchlist);
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
    .map((blockName) => `
      <span class="watchlist-block-chip">
        ${escapeHtml(blockName)}: ${blockCounts[blockName]}/${watchlist.per_block_limit}
      </span>
    `)
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
        <td>${buildStatusPillMarkup(item.Status)}</td>
        <td>${buildPromotePillMarkup(item.Promote)}</td>
        <td>${escapeHtml(formatTimestamp(item.created_at))}</td>
      </tr>
    `)
    .join('');
}

async function handleWatchlistSelection(event) {
  const button = event.target.closest('[data-watchlist-name]');
  if (!button) {
    return;
  }

  await selectWatchlist(button.dataset.watchlistName);
}

async function handleGraphWatchlistChange(event) {
  await selectWatchlist(event.target.value);
}

async function selectWatchlist(watchlistName) {
  if (!watchlistName || watchlistName === watchlistState.selectedWatchlistName) {
    renderAprWatchlistPage();
    return;
  }

  watchlistState.selectedWatchlistName = watchlistName;
  renderAprWatchlistPage();
  await loadTimingDataForSelectedWatchlist();
  renderAprWatchlistPage();
}

function handleGraphBlockChange(event) {
  watchlistState.selectedBlock = event.target.value;
  syncTimingFilterSelections();
  syncSelectedPathgroups();
  renderTimingControls();
  renderTimingViewer();
}

function handleGraphModeChange(event) {
  watchlistState.selectedMode = event.target.value;
  syncTimingFilterSelections();
  syncSelectedPathgroups();
  renderTimingControls();
  renderTimingViewer();
}

function handleGraphTcheckChange(event) {
  watchlistState.selectedTcheck = event.target.value;
  syncTimingFilterSelections();
  syncSelectedPathgroups();
  renderTimingControls();
  renderTimingViewer();
}

function handleGraphTcornerChange(event) {
  watchlistState.selectedTcorner = event.target.value;
  syncTimingFilterSelections();
  syncSelectedPathgroups();
  renderTimingControls();
  renderTimingViewer();
}

function handleGraphVoltageChange(event) {
  watchlistState.selectedVoltage = event.target.value;
  syncTimingFilterSelections();
  syncSelectedPathgroups();
  renderTimingControls();
  renderTimingViewer();
}

function handleApplyGraphFilters() {
  updateSelectedPathgroupsFromInputs();
  renderTimingViewer();
}

async function handleReloadGraphData() {
  await loadTimingDataForSelectedWatchlist();
  renderAprWatchlistPage();
}

function handlePathgroupSelectionChange() {
  updateSelectedPathgroupsFromInputs();
  renderTimingViewer();
}

function updateSelectedPathgroupsFromInputs() {
  const checkboxes = pathgroupCheckboxes.querySelectorAll('.watchlist-pathgroup-checkbox:checked');
  watchlistState.selectedPathgroups = Array.from(checkboxes).map((checkbox) => checkbox.value);
}

function setSelectOptions(selectElement, values, selectedValue, emptyLabel) {
  if (!values.length) {
    selectElement.innerHTML = `<option value="">${escapeHtml(emptyLabel)}</option>`;
    return;
  }

  selectElement.innerHTML = values
    .map((value) => `
      <option value="${escapeHtml(value)}"${value === selectedValue ? ' selected' : ''}>
        ${escapeHtml(value)}
      </option>
    `)
    .join('');
}

function normalizeTimingFilters(filters) {
  return {
    modes: Array.isArray(filters && filters.modes) ? filters.modes : [],
    tchecks: Array.isArray(filters && filters.tchecks) ? filters.tchecks : [],
    tcorners: Array.isArray(filters && filters.tcorners) ? filters.tcorners : [],
    voltages: Array.isArray(filters && filters.voltages) ? filters.voltages : [],
  };
}

function getCurrentTimingFilterOptions() {
  return {
    modes: watchlistState.timingFilters.modes.slice(),
    tchecks: watchlistState.timingFilters.tchecks.slice(),
    tcorners: watchlistState.timingFilters.tcorners.slice(),
    voltages: watchlistState.timingFilters.voltages.slice(),
  };
}

function getSelectablePathgroups() {
  const filteredRows = getFilteredTimingSummaryRows(getTimingRunsForSelectedBlock());
  const pathgroups = getUniqueTimingValues(filteredRows, 'Pathgroup');

  return shouldShowSequentialGraph()
    ? [GRAPH_SEQUENTIAL_LABEL].concat(pathgroups)
    : pathgroups;
}

function syncTimingFilterSelections() {
  const runs = getTimingRunsForSelectedBlock();
  const summaryRows = collectTimingSummaryRows(runs);

  const modeOptions = getUniqueTimingValues(summaryRows, 'Mode');
  watchlistState.selectedMode = coerceSelectedValue(watchlistState.selectedMode, modeOptions);

  const modeRows = filterTimingRowsByField(summaryRows, 'Mode', watchlistState.selectedMode);
  const tcheckOptions = getUniqueTimingValues(modeRows, 'TCheck');
  watchlistState.selectedTcheck = coerceSelectedValue(watchlistState.selectedTcheck, tcheckOptions);

  const tcheckRows = filterTimingRowsByField(modeRows, 'TCheck', watchlistState.selectedTcheck);
  const tcornerOptions = getUniqueTimingValues(tcheckRows, 'TCorner');
  watchlistState.selectedTcorner = coerceSelectedValue(watchlistState.selectedTcorner, tcornerOptions);

  const tcornerRows = filterTimingRowsByField(tcheckRows, 'TCorner', watchlistState.selectedTcorner);
  const voltageOptions = getUniqueTimingValues(tcornerRows, 'Voltage');
  watchlistState.selectedVoltage = coerceSelectedValue(watchlistState.selectedVoltage, voltageOptions);

  watchlistState.timingFilters = {
    modes: modeOptions,
    tchecks: tcheckOptions,
    tcorners: tcornerOptions,
    voltages: voltageOptions,
  };
}

function syncSelectedPathgroups() {
  const selectablePathgroups = getSelectablePathgroups();
  watchlistState.selectedPathgroups = watchlistState.selectedPathgroups.filter((pathgroup) =>
    selectablePathgroups.includes(pathgroup)
  );

  if (!watchlistState.selectedPathgroups.length) {
    watchlistState.selectedPathgroups = selectablePathgroups.slice();
  }
}

function collectTimingSummaryRows(runs) {
  return (Array.isArray(runs) ? runs : []).flatMap((run) =>
    Array.isArray(run.timing_summary_rows) ? run.timing_summary_rows : []
  );
}

function filterTimingRowsByField(rows, fieldName, expectedValue) {
  const normalizedExpectedValue = normalizeTimingValue(expectedValue);
  if (!normalizedExpectedValue) {
    return rows.slice();
  }

  return rows.filter((row) => normalizeTimingValue(row[fieldName]) === normalizedExpectedValue);
}

function getFilteredTimingSummaryRows(runs) {
  let rows = collectTimingSummaryRows(runs);
  rows = filterTimingRowsByField(rows, 'Mode', watchlistState.selectedMode);
  rows = filterTimingRowsByField(rows, 'TCheck', watchlistState.selectedTcheck);
  rows = filterTimingRowsByField(rows, 'TCorner', watchlistState.selectedTcorner);
  rows = filterTimingRowsByField(rows, 'Voltage', watchlistState.selectedVoltage);
  return rows;
}

function getUniqueTimingValues(rows, fieldName) {
  const uniqueValues = new Map();

  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const rawValue = String((row && row[fieldName]) || '').trim();
    const normalizedValue = normalizeTimingValue(rawValue);
    if (!normalizedValue || uniqueValues.has(normalizedValue)) {
      return;
    }

    uniqueValues.set(normalizedValue, rawValue);
  });

  return Array.from(uniqueValues.values()).sort((leftValue, rightValue) =>
    leftValue.localeCompare(rightValue, undefined, { sensitivity: 'base' })
  );
}

function coerceSelectedValue(currentValue, availableValues) {
  const normalizedCurrentValue = normalizeTimingValue(currentValue);
  const nextValue = (Array.isArray(availableValues) ? availableValues : []).find(
    (value) => normalizeTimingValue(value) === normalizedCurrentValue
  );
  return nextValue || (availableValues[0] || '');
}

function normalizeTimingValue(value) {
  return String(value == null ? '' : value).trim().toLowerCase();
}

function shouldShowSequentialGraph() {
  return normalizeTimingValue(watchlistState.selectedTcheck) === 'setup';
}

function getTimingRunsForSelectedBlock() {
  if (!watchlistState.selectedBlock) {
    return watchlistState.timingRuns.slice();
  }

  return watchlistState.timingRuns.filter((run) => run.Block === watchlistState.selectedBlock);
}

function getSelectedPathgroups() {
  return watchlistState.selectedPathgroups.slice();
}

function setTimingNotice(message, isError) {
  watchlistState.timingNotice = message || '';
  watchlistState.timingNoticeIsError = Boolean(isError);
}

function destroyTimingCharts() {
  watchlistState.activeCharts.forEach((chartInstance) => chartInstance.destroy());
  watchlistState.activeCharts = [];
}

function buildGraphSeries(runs, pathgroup) {
  return runs
    .map((run, index) => buildRunSeries(run, index, pathgroup))
    .filter((seriesItem) => hasSeriesData(seriesItem.rawWns, seriesItem.rawTns, seriesItem.rawNvp));
}

function buildRunSeries(run, index, pathgroup) {
  let rawWns;
  let rawTns;
  let rawNvp;

  if (pathgroup === GRAPH_SEQUENTIAL_LABEL) {
    rawWns = getSequentialMetricSeries(run, 'WNS');
    rawTns = getSequentialMetricSeries(run, 'TNS');
    rawNvp = getSequentialMetricSeries(run, 'NVP');
  } else {
    rawWns = GRAPH_STAGE_ORDER.map((stageName) => getStageMetricValue(run, stageName, pathgroup, 'WNS'));
    rawTns = GRAPH_STAGE_ORDER.map((stageName) => getStageMetricValue(run, stageName, pathgroup, 'TNS'));
    rawNvp = GRAPH_STAGE_ORDER.map((stageName) => getStageMetricValue(run, stageName, pathgroup, 'NVP'));
  }

  return {
    label: buildTimingRunLabel(run),
    color: getGraphColor(index),
    rawWns,
    rawTns,
    rawNvp,
    plotWns: rawWns.map(absOrNull),
    plotTns: rawTns.map(absOrNull),
    meta: run,
  };
}

function getStageMetricValue(run, stageName, pathgroup, metricName) {
  const metricPayload = getTimingSummaryMetricPayload(run, stageName, pathgroup);
  return metricPayload[metricName] == null ? null : Number(metricPayload[metricName]);
}

function getTimingSummaryMetricPayload(run, stageName, pathgroup) {
  const matchingRow = (Array.isArray(run.timing_summary_rows) ? run.timing_summary_rows : []).find((row) =>
    normalizeTimingValue(row.Stage) === normalizeTimingValue(stageName) &&
    normalizeTimingValue(row.Pathgroup) === normalizeTimingValue(pathgroup) &&
    normalizeTimingValue(row.Mode) === normalizeTimingValue(watchlistState.selectedMode) &&
    normalizeTimingValue(row.TCheck) === normalizeTimingValue(watchlistState.selectedTcheck) &&
    normalizeTimingValue(row.TCorner) === normalizeTimingValue(watchlistState.selectedTcorner) &&
    normalizeTimingValue(row.Voltage) === normalizeTimingValue(watchlistState.selectedVoltage)
  );

  return matchingRow || {};
}

function getSequentialMetricSeries(run, metricName) {
  const sequentialSetup = run.sequential_setup || {};
  const series = sequentialSetup[metricName];
  return Array.isArray(series) ? series.map((value) => (value == null ? null : Number(value))) : [null, null, null];
}

function hasSeriesData(rawWns, rawTns, rawNvp) {
  return hasMetricValue(rawWns) || hasMetricValue(rawTns) || hasMetricValue(rawNvp);
}

function hasMetricValue(metricValues) {
  return Array.isArray(metricValues) && metricValues.some((value) => value != null && value !== '');
}

function buildTimingRunLabel(run) {
  if (run.Job && run.Milestone) {
    return `${run.Job} / ${run.Milestone}`;
  }

  return run.Job || run.Block || run.series_key || 'APR Run';
}

function getGraphColor(index) {
  return GRAPH_COLORS[index % GRAPH_COLORS.length];
}

function absOrNull(value) {
  if (value == null || value === '') {
    return null;
  }

  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? Math.abs(numericValue) : null;
}

function createTimingGraphCard(pathgroup, series) {
  const chartLibrary = window.Chart;

  if (!chartLibrary) {
    setTimingNotice('Chart.js could not be loaded for the timing viewer.', true);
    renderTimingNotice();
    return;
  }

  const card = document.createElement('div');
  const chartId = `watchlist-chart-${Math.random().toString(36).slice(2)}`;
  const legendId = `watchlist-legend-${Math.random().toString(36).slice(2)}`;
  const detailId = `watchlist-detail-${Math.random().toString(36).slice(2)}`;

  card.className = 'watchlist-graph-card';
  card.innerHTML = `
    <div class="watchlist-graph-layout">
      <div class="watchlist-chart-wrap">
        <canvas id="${chartId}"></canvas>
      </div>
      <div class="watchlist-graph-side-panel">
        <div id="${legendId}" class="watchlist-legend-boxes"></div>
        <div id="${detailId}"></div>
      </div>
    </div>
  `;
  watchlistCardsContainer.appendChild(card);

  renderGraphLegend(card.querySelector(`#${legendId}`), card.querySelector(`#${detailId}`), series);
  renderGraphChart(card.querySelector(`#${chartId}`), pathgroup, series);
}

function renderGraphLegend(legendContainer, detailContainer, series) {
  legendContainer.innerHTML = '';

  series.forEach((seriesItem, index) => {
    const legendItem = document.createElement('div');
    legendItem.className = `watchlist-legend-item${index === 0 ? ' is-active' : ''}`;
    legendItem.style.background = seriesItem.color;
    legendItem.title = seriesItem.label;
    legendItem.addEventListener('click', function handleLegendClick() {
      legendContainer.querySelectorAll('.watchlist-legend-item').forEach((element) => {
        element.classList.remove('is-active');
      });
      legendItem.classList.add('is-active');
      renderRunDetails(detailContainer, seriesItem);
    });
    legendContainer.appendChild(legendItem);
  });

  if (series[0]) {
    renderRunDetails(detailContainer, series[0]);
  }
}

function renderRunDetails(container, seriesItem) {
  const stageRows = GRAPH_STAGE_ORDER.map((stageName, index) => `
    <tr>
      <td>${escapeHtml(stageName)}</td>
      <td>${formatMetricValue(seriesItem.rawWns[index])}</td>
      <td>${formatMetricValue(seriesItem.rawTns[index])}</td>
      <td>${formatMetricValue(seriesItem.rawNvp[index])}</td>
    </tr>
  `).join('');

  container.innerHTML = `
    <div class="watchlist-run-title">${escapeHtml(seriesItem.label)}</div>
    <div class="watchlist-run-subtitle">
      Block: ${escapeHtml(seriesItem.meta.Block || '-')} &middot;
      DFT Release: ${escapeHtml(seriesItem.meta.Dft_release || '-')}
    </div>
    <table class="watchlist-detail-table">
      <thead>
        <tr>
          <th>Stage</th>
          <th>WNS</th>
          <th>TNS</th>
          <th>NVP</th>
        </tr>
      </thead>
      <tbody>
        ${stageRows}
      </tbody>
    </table>
  `;
}

function renderGraphChart(canvas, pathgroup, series) {
  const chartDataSets = [];

  series.forEach((seriesItem) => {
    chartDataSets.push({
      type: 'bar',
      label: `${seriesItem.label} TNS`,
      data: seriesItem.plotTns,
      backgroundColor: seriesItem.color,
      borderColor: seriesItem.color,
      yAxisID: 'y1',
      order: 2,
      barPercentage: 0.72,
      categoryPercentage: 0.72,
    });

    chartDataSets.push({
      type: 'line',
      label: `${seriesItem.label} WNS`,
      data: seriesItem.plotWns,
      borderColor: seriesItem.color,
      backgroundColor: seriesItem.color,
      yAxisID: 'y',
      order: 1,
      tension: 0.2,
      fill: false,
      pointRadius: 4,
      pointHoverRadius: 5,
    });
  });

  const chartInstance = new window.Chart(canvas.getContext('2d'), {
    data: {
      labels: GRAPH_STAGE_ORDER,
      datasets: chartDataSets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        title: {
          display: true,
          text: pathgroup === GRAPH_SEQUENTIAL_LABEL ? GRAPH_SEQUENTIAL_LABEL : `Pathgroup: ${pathgroup}`,
        },
        legend: {
          display: false,
        },
      },
      scales: {
        y: {
          type: 'linear',
          position: 'left',
          beginAtZero: true,
          title: {
            display: true,
            text: 'WNS',
          },
        },
        y1: {
          type: 'linear',
          position: 'right',
          beginAtZero: true,
          grid: {
            drawOnChartArea: false,
          },
          title: {
            display: true,
            text: 'TNS',
          },
        },
      },
    },
  });

  watchlistState.activeCharts.push(chartInstance);
}

function buildStatusPillMarkup(statusValue) {
  const toneClass = getStatusToneClass(statusValue);
  return `<span class="watchlist-status-pill${toneClass ? ` ${toneClass}` : ''}">${escapeHtml(statusValue || '-')}</span>`;
}

function buildPromotePillMarkup(promoteValue) {
  const normalizedValue = String(promoteValue || '').trim().toLowerCase();
  const toneClass = normalizedValue === 'yes' ? 'is-positive' : normalizedValue === 'no' ? 'is-negative' : '';
  return `<span class="watchlist-promote-pill${toneClass ? ` ${toneClass}` : ''}">${escapeHtml(promoteValue || '-')}</span>`;
}

function getStatusToneClass(statusValue) {
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

function findSelectedWatchlist() {
  return watchlistState.watchlists.find((watchlist) => watchlist.name === watchlistState.selectedWatchlistName) || null;
}

function showWatchlistMessage(message, isSuccess) {
  if (!message) {
    watchlistMessage.textContent = '';
    watchlistMessage.className = 'watchlist-message is-hidden';
    return;
  }

  watchlistMessage.textContent = message;
  watchlistMessage.className = `watchlist-message ${isSuccess ? 'is-success' : 'is-error'}`;
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '-';
  }

  return String(timestamp).replace('T', ' ').replace('Z', '');
}

function formatMetricValue(value) {
  return value == null || value === '' ? '-' : escapeHtml(String(value));
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
