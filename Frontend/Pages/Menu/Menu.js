const logoutButton = document.getElementById('logoutBtn');
const userInfo = document.getElementById('userInfo');

window.addEventListener('DOMContentLoaded', () => {
  loadUserInfo();
});

logoutButton.addEventListener('click', async () => {
  await fetch('/api/validate-session');
  window.location.href = '/';
});

async function loadUserInfo() {
  const response = await fetch('/api/session');
  if (!response.ok) {
    window.location.href = '/';
    return;
  }
  const result = await response.json();
  if (!result.success) {
    window.location.href = '/';
    return;
  }
  const userItem = document.getElementById('userItem');
  const roleItem = document.getElementById('roleItem');
  const projectItem = document.getElementById('projectItem');
  userItem.textContent = result.user_id;
  roleItem.textContent = result.role;
  projectItem.textContent = result.project_code;
}

async function openDashboard(projectCode) {
  // Update session project code
  const response = await fetch('/api/session-pcode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_code: projectCode }),
  });
  const result = await response.json();
  if (result.success) {
    // Open Dashboard page
    window.location.href = '/api/dashboard?tab=Dashboard';
  } else {
    alert('Failed to update project code: ' + (result.error || 'Unknown error'));
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
