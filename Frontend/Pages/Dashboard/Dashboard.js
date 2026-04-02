const logoutButton = document.getElementById('logoutBtn');
const userItem = document.getElementById('userItem');
const roleItem = document.getElementById('roleItem');
const projectNameItem = document.getElementById('projectNameItem');
const projectCodeItem = document.getElementById('projectCodeItem');
const dashboardFrame = document.getElementById('dashboardFrame');
const dashboardNav = document.getElementById('dashboardNav');

const dashboardState = {
  allowedTabs: [],
};

window.addEventListener('DOMContentLoaded', () => {
  initializeDashboard();
});

logoutButton.addEventListener('click', async () => {
  await fetch('/api/validate-session');
  window.location.href = '/';
});

async function initializeDashboard() {
  const sessionInfo = await loadSessionInfo();
  if (!sessionInfo) {
    return;
  }

  dashboardState.allowedTabs = Array.isArray(sessionInfo.allowed_tabs) ? sessionInfo.allowed_tabs : [];
  renderDashboardMenu(dashboardState.allowedTabs);
  bindDashboardNavigation();
  openDashboardTab(getInitialTabName(sessionInfo.default_tab));
}

async function loadSessionInfo() {
  const response = await fetch('/api/session');
  if (!response.ok) {
    window.location.href = '/';
    return null;
  }

  const result = await response.json();
  if (!result.success) {
    window.location.href = '/';
    return null;
  }

  userItem.textContent = 'User: ' + result.user_id;
  roleItem.textContent = 'Role: ' + result.role;
  projectCodeItem.textContent = 'Project Code: ' + (result.project_code || 'Unknown');
  await loadProjectName(result.project_code);
  return result;
}

async function loadProjectName(projectCode) {
  if (!projectCode) {
    projectNameItem.textContent = 'Project Name: Unknown';
    return;
  }

  try {
    const response = await fetch(`/api/project-name?project_code=${encodeURIComponent(projectCode)}`);
    if (!response.ok) {
      projectNameItem.textContent = 'Project Name: unknown';
      return;
    }

    const result = await response.json();
    projectNameItem.textContent = result.success
      ? 'Project Name: ' + result.project_name
      : 'Project Name: unknown';
  } catch (error) {
    projectNameItem.textContent = 'Project Name: unknown';
  }
}

function renderDashboardMenu(tabs) {
  const aprTabs = tabs.filter((tab) => tab.group === 'apr');
  const parts = [];
  let aprInserted = false;

  tabs.forEach((tab) => {
    if (tab.group === 'apr') {
      if (!aprInserted && aprTabs.length) {
        parts.push(buildAprDropdownMarkup(aprTabs));
        aprInserted = true;
      }
      return;
    }

    parts.push(buildPrimaryTabMarkup(tab));
  });

  dashboardNav.innerHTML = parts.join('');
}

function buildPrimaryTabMarkup(tab) {
  return `<a class="item dashboard-nav-item" data-tab-target="${tab.key}">${tab.label}</a>`;
}

function buildAprDropdownMarkup(aprTabs) {
  const items = aprTabs
    .map((tab) => `<a class="item dashboard-subitem" data-tab-target="${tab.key}">${tab.label}</a>`)
    .join('');

  return `
    <div class="item dashboard-dropdown" id="aprDropdown">
      <button class="dashboard-dropdown-toggle" id="aprToggle" type="button">
        <span>APR</span>
        <i class="dropdown icon"></i>
      </button>
      <div class="menu dashboard-dropdown-menu">
        ${items}
      </div>
    </div>
  `;
}

function bindDashboardNavigation() {
  dashboardNav.addEventListener('click', handleNavigationClick);
  document.addEventListener('click', handleOutsideClick);
  window.addEventListener('hashchange', () => {
    openDashboardTab(getInitialTabName(''));
  });
}

function handleNavigationClick(event) {
  const targetItem = event.target.closest('[data-tab-target]');
  const dropdownToggle = event.target.closest('#aprToggle');

  if (dropdownToggle) {
    event.preventDefault();
    event.stopPropagation();
    getAprDropdown()?.classList.toggle('is-open');
    return;
  }

  if (!targetItem) {
    return;
  }

  event.preventDefault();
  closeAprDropdown();
  openDashboardTab(targetItem.dataset.tabTarget);
}

function handleOutsideClick(event) {
  const aprDropdown = getAprDropdown();
  if (aprDropdown && !aprDropdown.contains(event.target)) {
    closeAprDropdown();
  }
}

function getAprDropdown() {
  return document.getElementById('aprDropdown');
}

function closeAprDropdown() {
  getAprDropdown()?.classList.remove('is-open');
}

function getInitialTabName(defaultTab) {
  const hashValue = window.location.hash.replace('#', '');
  if (tabIsAllowed(hashValue)) {
    return hashValue;
  }
  if (tabIsAllowed(defaultTab)) {
    return defaultTab;
  }
  return dashboardState.allowedTabs[0]?.key || '';
}

function tabIsAllowed(tabName) {
  return dashboardState.allowedTabs.some((tab) => tab.key === tabName);
}

function openDashboardTab(tabName) {
  if (!tabIsAllowed(tabName)) {
    return;
  }

  dashboardFrame.src = '/api/dashboard?tab=' + encodeURIComponent(tabName);
  updateActiveMenuState(tabName);
  history.replaceState(null, '', window.location.pathname + window.location.search + '#' + tabName);
}

function updateActiveMenuState(tabName) {
  document.querySelectorAll('[data-tab-target]').forEach((item) => {
    item.classList.toggle('active', item.dataset.tabTarget === tabName);
  });

  const activeTab = dashboardState.allowedTabs.find((tab) => tab.key === tabName);
  getAprDropdown()?.classList.toggle('is-active', activeTab?.group === 'apr');
}
