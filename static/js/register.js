document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('error-message');
    
    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password }),
            credentials: 'include' // Include cookies for session
        });
        
        const data = await response.json();
        
        if (data.success) {
            window.location.href = '/api/login';
        } else {
            errorMessage.textContent = data.error || 'Error registering user';
            errorMessage.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Registration error:', error);
        errorMessage.textContent = 'Error registering. Please try again.';
        errorMessage.classList.remove('hidden');
    }
});