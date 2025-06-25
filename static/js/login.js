document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('error-message');
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password }),
            credentials: 'include' // Include cookies for session
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.role === 'admin') {
                window.location.href = '/admin';
            } else {
                window.location.href = '/';
            }
        } else {
            errorMessage.textContent = data.error || 'Invalid username or password';
            errorMessage.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Login error:', error);
        errorMessage.textContent = 'Error logging in. Please try again.';
        errorMessage.classList.remove('hidden');
    }
});