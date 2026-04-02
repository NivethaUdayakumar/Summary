const registerForm = document.getElementById('registerForm');
const registerMessage = document.getElementById('registerMessage');
const loginLink = document.getElementById('loginLink');

loginLink.addEventListener('click', (event) => {
  event.preventDefault();
  window.location.href = '/';
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const userId = document.getElementById('userId').value.trim();
  const role = document.getElementById('role').value;
  const password = document.getElementById('password').value;

  if (!userId || !role || !password) {
    showMessage('Please complete all fields.', false);
    return;
  }
  if (!/^mtk\d+$/.test(userId)) {
    showMessage('User ID must begin with mtk followed by digits.', false);
    return;
  }

  const response = await fetch('/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, role, password }),
  });

  const result = await response.json();
  if (result.success) {
    showMessage('Registration complete. Redirecting to login...', true);
    setTimeout(() => {
      window.location.href = '/';
    }, 900);
  } else {
    showMessage(result.error || 'Registration failed.', false);
  }
});

function showMessage(message, isSuccess) {
  registerMessage.textContent = message;
  registerMessage.className = isSuccess ? 'ui positive message' : 'ui negative message';
}
