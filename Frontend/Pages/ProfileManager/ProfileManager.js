const createUserForm = document.getElementById('createUserForm');
const tableSearchInput = document.getElementById('tableSearchInput');
const tableBody = document.getElementById('profileUserTableBody');
const selectedUserIdInput = document.getElementById('selectedUserId');
const selectedUserRoleInput = document.getElementById('selectedUserRole');
const selectedUserPasswordInput = document.getElementById('selectedUserPassword');
const selectionStatus = document.getElementById('profileSelectionStatus');
const profileManagerMessage = document.getElementById('profileManagerMessage');
const updateRoleButton = document.getElementById('updateRoleButton');
const updatePasswordButton = document.getElementById('updatePasswordButton');
const deleteUserButton = document.getElementById('deleteUserButton');

const USERS_DB_LOCATION = 'AppData/App.db';
const USERS_TABLE_NAME = 'users';
const USER_ID_PATTERN = /^mtk\d+$/;

const profileState = {
  currentRole: '',
  currentUserId: '',
  searchTerm: '',
  selectedUserId: '',
  sortDirection: 'asc',
  sortKey: 'user_id',
  users: [],
};

window.addEventListener('DOMContentLoaded', () => {
  initializeProfileManager();
});

async function initializeProfileManager() {
  try {
    await loadSessionInfo();
    bindProfileManagerEvents();
    await loadUsers();
  } catch (error) {
    showProfileMessage(error.message, false);
  }
}

function bindProfileManagerEvents() {
  createUserForm.addEventListener('submit', handleCreateUser);
  tableSearchInput.addEventListener('input', handleSearchInput);
  tableBody.addEventListener('click', handleTableClick);
  updateRoleButton.addEventListener('click', handleUpdateRole);
  updatePasswordButton.addEventListener('click', handleUpdatePassword);
  deleteUserButton.addEventListener('click', handleDeleteUser);

  document.querySelectorAll('[data-sort-key]').forEach((button) => {
    button.addEventListener('click', handleSortClick);
  });
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const result = await response.json().catch(() => ({}));

  if (response.status === 401) {
    window.top.location.href = '/';
    throw new Error(result.error || 'session inactive');
  }

  if (!response.ok) {
    throw new Error(result.error || 'Request failed');
  }

  return result;
}

async function loadSessionInfo() {
  const result = await fetchJson('/api/session');
  profileState.currentRole = String(result.role || '');
  profileState.currentUserId = String(result.user_id || '').toLowerCase();

  if (profileState.currentRole !== 'admin') {
    throw new Error('admin access required');
  }
}

async function loadUsers() {
  const result = await fetchJson('/api/query-table', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      db_location: USERS_DB_LOCATION,
      query: 'SELECT user_id, role FROM users ORDER BY user_id',
    }),
  });

  profileState.users = Array.isArray(result.rows) ? result.rows : [];
  const selectedUser = profileState.users.find((user) => user.user_id === profileState.selectedUserId);

  if (selectedUser) {
    setSelectedUser(selectedUser.user_id, selectedUser.role);
  } else {
    setSelectedUser('');
  }

  renderUserTable();
}

function renderUserTable() {
  const users = getVisibleUsers();
  if (!users.length) {
    tableBody.innerHTML = '<tr class="empty-row"><td colspan="2">No users found.</td></tr>';
    return;
  }

  tableBody.innerHTML = users
    .map((user) => `
      <tr data-user-id="${user.user_id}" data-user-role="${user.role}" class="${user.user_id === profileState.selectedUserId ? 'is-selected' : ''}">
        <td>${escapeHtml(user.user_id)}</td>
        <td>${escapeHtml(user.role)}</td>
      </tr>
    `)
    .join('');
}

function getVisibleUsers() {
  const filteredUsers = profileState.users.filter(matchesSearchTerm);
  return filteredUsers.sort(compareUsers);
}

function matchesSearchTerm(user) {
  if (!profileState.searchTerm) {
    return true;
  }

  const needle = profileState.searchTerm.toLowerCase();
  return user.user_id.toLowerCase().includes(needle) || user.role.toLowerCase().includes(needle);
}

function compareUsers(leftUser, rightUser) {
  const leftValue = String(leftUser[profileState.sortKey] || '').toLowerCase();
  const rightValue = String(rightUser[profileState.sortKey] || '').toLowerCase();
  const comparison = leftValue.localeCompare(rightValue);
  return profileState.sortDirection === 'asc' ? comparison : comparison * -1;
}

function handleSearchInput(event) {
  profileState.searchTerm = event.target.value.trim();
  renderUserTable();
}

function handleTableClick(event) {
  const row = event.target.closest('tr[data-user-id]');
  if (!row) {
    return;
  }

  setSelectedUser(row.dataset.userId, row.dataset.userRole);
  renderUserTable();
}

function handleSortClick(event) {
  const nextKey = event.currentTarget.dataset.sortKey;
  if (profileState.sortKey === nextKey) {
    profileState.sortDirection = profileState.sortDirection === 'asc' ? 'desc' : 'asc';
  } else {
    profileState.sortKey = nextKey;
    profileState.sortDirection = 'asc';
  }

  renderUserTable();
}

async function handleCreateUser(event) {
  event.preventDefault();
  const userId = document.getElementById('newUserId').value.trim().toLowerCase();
  const role = document.getElementById('newUserRole').value;
  const password = document.getElementById('newUserPassword').value;

  if (!userId || !role || !password) {
    showProfileMessage('User ID, role, and password are required.', false);
    return;
  }

  if (!USER_ID_PATTERN.test(userId)) {
    showProfileMessage('User ID must begin with mtk followed by digits.', false);
    return;
  }

  if (profileState.users.some((user) => user.user_id === userId)) {
    showProfileMessage('user already exists', false);
    return;
  }

  try {
    await fetchJson('/api/insert-record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        db_location: USERS_DB_LOCATION,
        table_name: USERS_TABLE_NAME,
        record: {
          user_id: userId,
          role,
          password,
        },
      }),
    });

    createUserForm.reset();
    showProfileMessage('user created', true);
    await loadUsers();
  } catch (error) {
    showProfileMessage(error.message, false);
  }
}

async function handleUpdateRole() {
  if (!profileState.selectedUserId) {
    showProfileMessage('Select a user first.', false);
    return;
  }

  try {
    const result = await fetchJson('/api/update_record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        db_location: USERS_DB_LOCATION,
        table_name: USERS_TABLE_NAME,
        updates: { role: selectedUserRoleInput.value },
        criteria: { user_id: profileState.selectedUserId },
      }),
    });

    showProfileMessage(result.updated_count ? 'role updated' : 'user not found', Boolean(result.updated_count));
    await loadUsers();
  } catch (error) {
    showProfileMessage(error.message, false);
  }
}

async function handleUpdatePassword() {
  if (!profileState.selectedUserId) {
    showProfileMessage('Select a user first.', false);
    return;
  }

  if (!selectedUserPasswordInput.value) {
    showProfileMessage('Enter a new password first.', false);
    return;
  }

  try {
    const result = await fetchJson('/api/update_record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        db_location: USERS_DB_LOCATION,
        table_name: USERS_TABLE_NAME,
        updates: { password: selectedUserPasswordInput.value },
        criteria: { user_id: profileState.selectedUserId },
      }),
    });

    selectedUserPasswordInput.value = '';
    showProfileMessage(result.updated_count ? 'password updated' : 'user not found', Boolean(result.updated_count));
  } catch (error) {
    showProfileMessage(error.message, false);
  }
}

async function handleDeleteUser() {
  if (!profileState.selectedUserId) {
    showProfileMessage('Select a user first.', false);
    return;
  }

  if (profileState.selectedUserId === profileState.currentUserId) {
    showProfileMessage('cannot delete the active admin user', false);
    return;
  }

  try {
    await fetchJson('/api/delete-record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        db_location: USERS_DB_LOCATION,
        table_name: USERS_TABLE_NAME,
        criteria: { user_id: profileState.selectedUserId },
      }),
    });

    showProfileMessage('user deleted', true);
    setSelectedUser('');
    await loadUsers();
  } catch (error) {
    showProfileMessage(error.message, false);
  }
}

function setSelectedUser(userId, role = 'user') {
  profileState.selectedUserId = userId;
  selectedUserIdInput.value = userId;
  selectedUserRoleInput.value = role;
  selectedUserPasswordInput.value = '';
  selectionStatus.textContent = userId ? `Selected: ${userId}` : 'No user selected';
}

function showProfileMessage(message, isSuccess) {
  profileManagerMessage.textContent = message;
  profileManagerMessage.className = isSuccess ? 'ui positive message' : 'ui negative message';
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
