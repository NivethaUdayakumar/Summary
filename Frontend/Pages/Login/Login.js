const loginForm = document.getElementById('loginForm');
const loginMessage = document.getElementById('loginMessage');
const registerLink = document.getElementById('registerLink');

registerLink.addEventListener('click', (event) => {
  event.preventDefault();
  window.location.href = '/static/Pages/Register/Register.html';
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const userId = document.getElementById('userId').value.trim();
  const password = document.getElementById('password').value;

  if (!userId || !password) {
    showMessage('Please enter user ID and password.', false);
    return;
  }

  const response = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, password }),
  });

  const result = await response.json();
  if (result.success) {
    window.location.href = '/api/dashboard';
  } else {
    showMessage(result.error || 'Login failed.', false);
  }
});

function showMessage(message, isSuccess) {
  loginMessage.textContent = message;
  loginMessage.className = isSuccess ? 'ui positive message' : 'ui negative message';
}
