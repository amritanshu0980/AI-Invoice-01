// AI Invoice Assistant - Enhanced with Database Integration

class InvoiceAssistant {
    constructor() {
        this.API_BASE_URL = '/api';
        this.sessionId = this.generateSessionId();
        this.isProcessing = false;
        this.isConnected = false;
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.currentChatId = null;
        
        console.log('Constructor initialized with Session-ID:', this.sessionId);

        // DOM elements cache
        this.elements = {};
        
        this.init();
        this.deleteChatDebounced = this.debounce(this.deleteChat.bind(this), 500);
    }

    debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    init() {
        console.log('Initializing InvoiceAssistant');
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                console.log('DOM loaded, running setup');
                this.setup();
            });
        } else {
            console.log('DOM already loaded, running setup');
            this.setup();
        }
    }

    setup() {
        this.cacheElements();
        this.setupEventListeners();
        this.setupDragAndDrop();
        this.initTheme();
        this.checkConnection();
        this.loadClientDetails();
        this.setupAutoResize();
        
        // Load user info for settings dropdown
        this.loadUserInfo();
        
        // Focus input
        setTimeout(() => {
            if (this.elements.messageInput) {
                this.elements.messageInput.focus();
            }
        }, 100);

        // Load chats after setup
        console.log('Calling updateChatList in setup');
        this.updateChatList().catch(error => {
            console.error('Setup updateChatList failed:', error);
        });

        console.log('🚀 AI Invoice Assistant initialized');
        console.log('📱 Session ID:', this.sessionId);
    }

    

    cacheElements() {
        // ... existing elements
        const elementIds = [
            'sidebar', 'sidebarToggle', 'mobileOverlay', 'newChatBtn',
            'chatList', 'sidebarProductCount', 'sidebarCartCount',
            'connectionStatus', 'statusDot', 'statusText', 'headerCartCount',
            'downloadChatBtn', 'themeIcon', 'chatMessages', 'typingIndicator',
            'messageInput', 'sendBtn', 'sendIcon', 'loadingSpinner',
            'uploadModal', 'clientModal', 'uploadArea', 'fileInput',
            'uploadProgress', 'progressFill', 'fileName', 'uploadPercent',
            'clientForm', 'clientName', 'clientEmail', 'clientPhone',
            'clientAddress', 'clientGST', 'clientPlace',
            // Add settings dropdown elements
            'settingsDropdown', 'settingsBtn', 'logoutModal',
            'userAvatar', 'userInitials', 'settingsUsername', 'settingsUserRole',
            'settingsThemeIcon', 'themeStatus'
        ];

        elementIds.forEach(id => {
            this.elements[id] = document.getElementById(id);
        });
        this.elements.productsModal = document.getElementById('productsModal');
    this.elements.productsList = document.getElementById('productsList');
    this.elements.productsLoading = document.getElementById('productsLoading');
    this.elements.productsEmpty = document.getElementById('productsEmpty');
    this.elements.productsCount = document.getElementById('productsCount');
    this.elements.productSearchInput = document.getElementById('productSearchInput');

    this.elements.connectionStatus = document.getElementById('connectionStatus');
    this.elements.statusDot = document.getElementById('statusDot');
    this.elements.statusText = document.getElementById('statusText');
    
    // Add these user info elements  
    this.elements.settingsUsername = document.getElementById('settingsUsername');
    this.elements.settingsUserRole = document.getElementById('settingsUserRole');
    this.elements.userInitials = document.getElementById('userInitials');
    this.elements.settingsThemeIcon = document.getElementById('settingsThemeIcon');
    this.elements.themeStatus = document.getElementById('themeStatus');


    this.elements.userGuideModal = document.getElementById('userGuideModal');


     console.log('🔍 Settings elements cached:', {
        settingsUsername: !!this.elements.settingsUsername,
        settingsUserRole: !!this.elements.settingsUserRole,
        userInitials: !!this.elements.userInitials
    });


    }

    setupEventListeners() {
        // Sidebar toggle
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }

        // Mobile overlay
        if (this.elements.mobileOverlay) {
            this.elements.mobileOverlay.addEventListener('click', () => this.closeSidebar());
        }

        // New chat button
        if (this.elements.newChatBtn) {
            this.elements.newChatBtn.addEventListener('click', () => this.startNewChat());
        }

        // Send message
        if (this.elements.sendBtn) {
            this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        }

        document.addEventListener('click', (e) => {
            if (this.elements.settingsDropdown && 
                !this.elements.settingsDropdown.contains(e.target) && 
                !this.elements.settingsBtn.contains(e.target)) {
                this.closeSettingsDropdown();
            }
        });

        // Message input
        if (this.elements.messageInput) {
            this.elements.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }

        // File upload
        if (this.elements.fileInput) {
            this.elements.fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Window resize
        window.addEventListener('resize', () => this.handleResize());

        if (this.elements.productSearchInput) {
        this.elements.productSearchInput.addEventListener('input', () => {
            this.filterProductsList();
        });
    }
    }

    showUserGuide() {
        console.log('📖 Opening user guide modal...');
        
        if (this.elements.userGuideModal) {
            this.elements.userGuideModal.classList.add('active');
        }
        this.closeSidebar();
    }

    closeUserGuideModal() {
        if (this.elements.userGuideModal) {
            this.elements.userGuideModal.classList.remove('active');
        }
    }

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            
            // Show a brief success message
            this.showCopySuccess();
            console.log('✅ Copied to clipboard:', text);
        } catch (err) {
            // Fallback for older browsers
            this.fallbackCopyToClipboard(text);
        }
    }

    fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            this.showCopySuccess();
            console.log('✅ Copied to clipboard (fallback):', text);
        } catch (err) {
            console.error('❌ Copy failed:', err);
        }
        
        document.body.removeChild(textArea);
    }

    showCopySuccess() {
        // Create a temporary success indicator
        const successMsg = document.createElement('div');
        successMsg.className = 'copy-success-toast';
        successMsg.textContent = 'Copied to clipboard!';
        successMsg.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--accent-primary);
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;
        
        document.body.appendChild(successMsg);
        
        // Animate in
        setTimeout(() => {
            successMsg.style.transform = 'translateX(0)';
        }, 10);
        
        // Remove after 2 seconds
        setTimeout(() => {
            successMsg.style.transform = 'translateX(100%)';
            setTimeout(() => {
                document.body.removeChild(successMsg);
            }, 300);
        }, 2000);
    }

    async loadUserInfo() {
        /**
         * Load current user information from the status endpoint
         */
        try {
            const response = await fetch(`${this.API_BASE_URL}/status`, {
                method: 'GET',
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.user_info) {
                    this.updateUserInfo(data.user_info);
                } else {
                    // Fallback if not authenticated
                    this.updateUserInfo();
                }
            } else {
                // Fallback to basic info if endpoint fails
                this.updateUserInfo();
            }
        } catch (error) {
            console.error('Error loading user info:', error);
            // Fallback to basic info
            this.updateUserInfo();
        }
    }


    updateConnectionStatus(isConnected) {
        /**
         * Update the connection status indicator in the UI
         */
        this.isConnected = isConnected;
        
        if (this.elements.connectionStatus) {
            this.elements.connectionStatus.textContent = isConnected ? 'Connected' : 'Disconnected';
        }
        
        if (this.elements.statusDot) {
            this.elements.statusDot.className = isConnected ? 'status-dot online' : 'status-dot offline';
        }
        
        if (this.elements.statusText) {
            this.elements.statusText.textContent = isConnected ? 'Online' : 'Offline';
        }
        
        // Update the overall connection state
        document.documentElement.setAttribute('data-connection', isConnected ? 'online' : 'offline');
    }

    updateUserInfo(userData = null) {
        /**
         * Update user info in the settings dropdown
         */
        let username = 'User';
        let role = 'User';
        let initials = 'U';
        
        if (userData) {
            username = userData.username || 'User';
            role = userData.role || 'User';
            initials = userData.initials || username.charAt(0).toUpperCase();
        }
        
        if (this.elements.settingsUsername) {
            this.elements.settingsUsername.textContent = username;
        }
        
        if (this.elements.settingsUserRole) {
            this.elements.settingsUserRole.textContent = role;
        }
        
        if (this.elements.userInitials) {
            this.elements.userInitials.textContent = initials;
        }
        
        // Update theme status
        this.updateThemeStatus();
    }

    updateThemeStatus() {
        /**
         * Update theme icon and status in settings dropdown
         */
        const isDark = this.currentTheme === 'dark';
        
        if (this.elements.settingsThemeIcon) {
            this.elements.settingsThemeIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        }
        
        if (this.elements.themeStatus) {
            this.elements.themeStatus.textContent = isDark ? 'Dark' : 'Light';
        }
    }

    updateUserInfo(userData = null) {
        /**
         * Update user info in the settings dropdown
         */
        let username = 'User';
        let role = 'User';
        let initials = 'U';
        
        if (userData) {
            username = userData.username || 'User';
            role = userData.role || 'User';
            initials = userData.initials || username.charAt(0).toUpperCase();
        }
        
        if (this.elements.settingsUsername) {
            this.elements.settingsUsername.textContent = username;
        }
        
        if (this.elements.settingsUserRole) {
            this.elements.settingsUserRole.textContent = role;
        }
        
        if (this.elements.userInitials) {
            this.elements.userInitials.textContent = initials;
        }
        
        // Update theme status
        this.updateThemeStatus();
    }

    updateThemeStatus() {
        /**
         * Update theme icon and status in settings dropdown
         */
        const isDark = this.currentTheme === 'dark';
        
        if (this.elements.settingsThemeIcon) {
            this.elements.settingsThemeIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        }
        
        if (this.elements.themeStatus) {
            this.elements.themeStatus.textContent = isDark ? 'Light' : 'Dark';
        }
    }

    toggleSettingsDropdown() {
        /**
         * Toggle the settings dropdown visibility
         */
        if (!this.elements.settingsDropdown) return;
        
        const isVisible = this.elements.settingsDropdown.classList.contains('show');
        
        if (isVisible) {
            this.closeSettingsDropdown();
        } else {
            this.openSettingsDropdown();
        }
    }

    openSettingsDropdown() {
        /**
         * Open the settings dropdown
         */
        if (!this.elements.settingsDropdown) return;
        
        // Update user info before showing
        this.updateUserInfo();
        
        // Show dropdown
        this.elements.settingsDropdown.classList.add('show');
        this.elements.settingsBtn.classList.add('active');
        
        // Close sidebar on mobile when opening settings
        if (window.innerWidth <= 768) {
            // Don't close sidebar, just show dropdown
        }
    }

    closeSettingsDropdown() {
        /**
         * Close the settings dropdown
         */
        if (!this.elements.settingsDropdown) return;
        
        this.elements.settingsDropdown.classList.remove('show');
        this.elements.settingsBtn.classList.remove('active');
    }

    toggleTheme() {
        /**
         * Toggle theme and update all theme indicators
         */
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
        
        // Update main theme icon (top-right)
        this.updateThemeIcon();
        
        // Update settings dropdown theme status
        this.updateThemeStatus();
    }

    handleLogout() {
        /**
         * Handle logout button click - show confirmation modal
         */
        this.closeSettingsDropdown();
        this.openLogoutModal();
    }

    openLogoutModal() {
        /**
         * Open logout confirmation modal
         */
        if (this.elements.logoutModal) {
            this.elements.logoutModal.classList.add('active');
        }
    }

    closeLogoutModal() {
        /**
         * Close logout confirmation modal
         */
        if (this.elements.logoutModal) {
            this.elements.logoutModal.classList.remove('active');
        }
    }

    async confirmLogout() {
        /**
         * Confirm logout and perform logout actions
         */
        try {
            // Clear local data
            this.currentChatId = null;
            this.sessionId = this.generateSessionId();
            
            // Clear session storage
            if (typeof(Storage) !== "undefined") {
                localStorage.removeItem('theme'); // Keep theme preference
                // Clear any other stored data if needed
            }
            
            // Call logout API
            const response = await fetch(`${this.API_BASE_URL}/logout`, {
                method: 'POST',
                credentials: 'include'
            });
            
            if (response.ok) {
                // Redirect to login page
                window.location.href = '/api/login';
            } else {
                // Even if API fails, redirect to login
                console.warn('Logout API failed, but redirecting anyway');
                window.location.href = '/api/login';
            }
            
        } catch (error) {
            console.error('Error during logout:', error);
            // Even if error occurs, redirect to login for security
            window.location.href = '/api/login';
        }
    }

    setupDragAndDrop() {
        if (!this.elements.uploadArea) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.elements.uploadArea.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            this.elements.uploadArea.addEventListener(eventName, () => {
                this.elements.uploadArea.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            this.elements.uploadArea.addEventListener(eventName, () => {
                this.elements.uploadArea.classList.remove('dragover');
            }, false);
        });

        this.elements.uploadArea.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.elements.fileInput.files = files;
                this.handleFileUpload({ target: this.elements.fileInput });
            }
        }, false);

        this.elements.uploadArea.addEventListener('click', () => {
            this.elements.fileInput.click();
        });
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    setupAutoResize() {
        if (this.elements.messageInput) {
            this.elements.messageInput.addEventListener('input', () => {
                this.elements.messageInput.style.height = 'auto';
                this.elements.messageInput.style.height = Math.min(this.elements.messageInput.scrollHeight, 120) + 'px';
            });
        }
    }

    initTheme() {
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        this.updateThemeIcon();
    }

    updateThemeIcon() {
        if (this.elements.themeIcon) {
            this.elements.themeIcon.className = this.currentTheme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
        }
    }

    toggleTheme() {
        this.currentTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        localStorage.setItem('theme', this.currentTheme);
        this.updateThemeIcon();
    }

    toggleSidebar() {
        if (window.innerWidth <= 768) {
            this.elements.sidebar.classList.add('open');
            this.elements.mobileOverlay.classList.add('active');
        }
    }

    closeSidebar() {
        this.elements.sidebar.classList.remove('open');
        this.elements.mobileOverlay.classList.remove('active');
    }

    async checkConnection() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/status`, {
                method: 'GET',
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('📊 Status response:', data); // DEBUG: See what data we get
                
                this.isConnected = data.api_status === 'online';
                
                // Debug element finding
                console.log('🔍 Elements check:', {
                    settingsUsername: !!this.elements.settingsUsername,
                    settingsUserRole: !!this.elements.settingsUserRole,
                    userInitials: !!this.elements.userInitials
                });

                // Update product count from status response
                if (data.default_products_count !== undefined) {
                    this.updateProductCount(data.default_products_count);
                    console.log('✅ Updated product count to:', data.default_products_count);
                }
                
                // Update user info if available
                if (data.user_info) {
                    console.log('👤 User info from status:', data.user_info); // DEBUG: See user info
                    
                    if (this.elements.settingsUsername) {
                        this.elements.settingsUsername.textContent = data.user_info.username || 'User';
                        console.log('✅ Updated username to:', data.user_info.username);
                    }
                    if (this.elements.settingsUserRole) {
                        this.elements.settingsUserRole.textContent = data.user_info.role || 'User';
                        console.log('✅ Updated role to:', data.user_info.role);
                    }
                    if (this.elements.userInitials) {
                        this.elements.userInitials.textContent = data.user_info.initials || 'U';
                        console.log('✅ Updated initials to:', data.user_info.initials);
                    }
                } else {
                    console.log('❌ No user_info in status response');
                }
                
                console.log('✅ Connection check successful');
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.log('Connection error:', error);
            this.isConnected = false;
        }
    }

    setConnectionStatus(connected) {
        this.isConnected = connected;
        
        if (this.elements.statusDot) {
            this.elements.statusDot.className = `status-dot ${connected ? '' : 'offline'}`;
        }
        
        if (this.elements.statusText) {
            this.elements.statusText.textContent = connected ? 'Connected' : 'Offline';
        }
    }

    async loadProductStats() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/get_products`, {
                headers: { 'Session-ID': this.sessionId },
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.updateProductCount(data.count || data.products.length);
            } else if (response.status === 403) {
                console.warn('Access denied, fetching limited product info');
                this.addMessage('⚠️ Access restricted. Please log in as admin or contact support.', 'ai', true);
            } else {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error loading product stats:', error);
            this.addMessage('❌ Failed to load product stats. Please try again later.', 'ai', true);
        }
    }

    updateProductCount(count) {
        if (this.elements.sidebarProductCount) {
            this.elements.sidebarProductCount.textContent = count || 0;
        }
    }

    updateCartCount(count) {
        if (this.elements.sidebarCartCount) {
            this.elements.sidebarCartCount.textContent = count;
        }
        if (this.elements.headerCartCount) {
            this.elements.headerCartCount.textContent = count;
        }
    }

    async startNewChat() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/create_new_chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': this.sessionId
                },
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                this.currentChatId = data.chat_id;
                
                // Clear chat interface
                this.elements.chatMessages.innerHTML = this.getWelcomeMessage();
                
                // Update chat list
                await this.updateChatList();
                
                // Close sidebar on mobile
                this.closeSidebar();
                
                console.log(`✅ New chat created: ${data.title}`);
            } else {
                const errorText = await response.text();
                this.addMessage('❌ Error creating new chat: ' + errorText, 'ai', true);
            }
        } catch (error) {
            console.error('Error starting new chat:', error);
            this.addMessage('❌ Error starting new chat', 'ai', true);
        }
    }

    getWelcomeMessage() {
        return `
            <div class="message-group">
                <div class="message ai-message">
                    <div class="message-avatar">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div class="message-content">
                        <div class="message-text">
                            <h3>Welcome to AI Invoice Assistant! 👋</h3>
                            <p>I'm here to help you manage products, create smart carts, and generate professional invoices. Here's what I can do:</p>
                            <ul class="feature-list">
                                <li><strong>Product Management:</strong> Add, remove, and search products</li>
                                <li><strong>Smart Cart:</strong> Apply discounts and manage quantities</li>
                                <li><strong>Invoice Generation:</strong> Create professional PDF invoices</li>
                                <li><strong>Client Management:</strong> Store and manage customer details</li>
                            </ul>
                            <p class="help-text">Try saying: <code>"add 5 laptops with 10% discount"</code> or <code>"show my cart"</code></p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

// Continue from Part 1...

    async sendMessage() {
        if (!this.elements.messageInput) return;
        
        const message = this.elements.messageInput.value.trim();
        if (!message || this.isProcessing || !this.isConnected) return;

        // Add user message
        this.addMessage(message, 'user');
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';

        this.setProcessing(true);
        this.showTyping();

        try {
            const response = await fetch(`${this.API_BASE_URL}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': this.sessionId
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId
                }),
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                
                // Update current chat ID if not set
                if (data.chat_id && !this.currentChatId) {
                    this.currentChatId = data.chat_id;
                    await this.updateChatList(); // Refresh chat list
                }
                
                // Update cart count if provided
                if (data.cart_count !== undefined) {
                    this.updateCartCount(data.cart_count);
                }
                
                // Handle special actions
                if (data.action_data && data.action_data.action === 'generate_invoice') {
                    await this.generateInvoiceFromCart();
                } else {
                    this.addMessage(data.response, 'ai');
                }
            } else {
                const errorText = await response.text();
                this.addMessage(`❌ Error: ${errorText}`, 'ai', true);
            }
        } catch (error) {
            console.error('Send message error:', error);
            this.addMessage('❌ Connection error. Please try again.', 'ai', true);
        } finally {
            this.hideTyping();
            this.setProcessing(false);
        }
    }

    addMessage(content, type = 'ai', isError = false) {
        if (!this.elements.chatMessages) return;

        const messageGroup = document.createElement('div');
        messageGroup.className = 'message-group';

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        avatarDiv.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        
        if (isError) {
            textDiv.style.color = 'var(--danger)';
        }
        
        // Handle HTML content vs plain text
        if (content.includes('<')) {
            textDiv.innerHTML = content;
        } else {
            textDiv.textContent = content;
        }

        contentDiv.appendChild(textDiv);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        messageGroup.appendChild(messageDiv);

        this.elements.chatMessages.appendChild(messageGroup);
        this.scrollToBottom();
    }

    showTyping() {
        if (this.elements.typingIndicator) {
            this.elements.typingIndicator.style.display = 'flex';
            this.scrollToBottom();
        }
    }

    hideTyping() {
        if (this.elements.typingIndicator) {
            this.elements.typingIndicator.style.display = 'none';
        }
    }

    setProcessing(processing) {
        this.isProcessing = processing;
        
        if (this.elements.sendBtn) {
            this.elements.sendBtn.disabled = processing;
        }
        
        if (processing) {
            this.elements.loadingSpinner.style.display = 'block';
            this.elements.sendIcon.style.display = 'none';
        } else {
            this.elements.loadingSpinner.style.display = 'none';
            this.elements.sendIcon.style.display = 'block';
        }
    }

    scrollToBottom() {
        if (this.elements.chatMessages) {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }
    }

    async updateChatList() {
        if (!this.elements.chatList) {
            console.error('chatList element not found during updateChatList');
            return;
        }
        
        console.log('Fetching chats with Session-ID:', this.sessionId);
        try {
            const response = await fetch(`${this.API_BASE_URL}/get_chats`, {
                headers: { 'Session-ID': this.sessionId },
                credentials: 'include'
            });
            
            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('API Response:', data);
            
            if (data.success) {
                this.elements.chatList.innerHTML = '';
                this.elements.chatList.classList.add('loaded');
                
                if (data.chats.length === 0) {
                    this.elements.chatList.innerHTML = '<div class="chat-item placeholder"><i class="fas fa-comment"></i><span>No chats yet</span></div>';
                } else {
                    data.chats.forEach(chat => {
                        const chatItem = document.createElement('div');
                        chatItem.className = `chat-item ${chat.chat_id === this.currentChatId ? 'active' : ''}`;
                        
                        chatItem.innerHTML = `
                            <i class="fas fa-message"></i>
                            <span class="chat-title" title="${chat.title}">${chat.title}</span>
                            <div class="chat-actions">
                                <button class="chat-rename" onclick="invoiceApp.showRenameDialog('${chat.chat_id}', '${chat.title}')" title="Rename chat">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="chat-delete" onclick="invoiceApp.deleteChatDebounced('${chat.chat_id}')" title="Delete chat">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        `;
                        
                        // Add click listener for loading chat (excluding action buttons)
                        chatItem.addEventListener('click', (e) => {
                            if (!e.target.closest('.chat-actions')) {
                                this.loadChat(chat.chat_id);
                            }
                        });
                        
                        this.elements.chatList.appendChild(chatItem);
                    });
                    console.log(`Rendered ${data.chats.length} chats`);
                }
            } else {
                console.log('API success false:', data);
                this.elements.chatList.innerHTML = '<div class="chat-item placeholder"><i class="fas fa-exclamation-triangle"></i><span>Failed to load chats</span></div>';
            }
        } catch (error) {
            console.error('Error updating chat list:', error);
            this.addMessage('❌ Error loading chat history', 'ai', true);
            this.elements.chatList.innerHTML = '<div class="chat-item placeholder"><i class="fas fa-exclamation-triangle"></i><span>Failed to load chats</span></div>';
        }
    }

    async loadChat(chatId) {
        try {

            const response = await fetch(`${this.API_BASE_URL}/load_chat/${chatId}`, {
                headers: { 'Session-ID': this.sessionId },
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                
                // Update current chat ID
                this.currentChatId = data.chat_id;

                // Clear current messages
                this.elements.chatMessages.innerHTML = '';

                // Add welcome message
                this.elements.chatMessages.innerHTML = this.getWelcomeMessage();

                // Add chat messages
                data.messages.forEach(msg => {
                    this.addMessage(msg.content, msg.role === 'user' ? 'user' : 'ai');
                });

                // Update chat list to highlight active chat
                await this.updateChatList();

                // Close sidebar on mobile
                this.closeSidebar();

                // Scroll to bottom
                this.scrollToBottom();

                console.log(`Loaded chat: ${chatId}`);
            } else {
                const errorText = await response.text();
                this.addMessage(`❌ Error loading chat: ${errorText}`, 'ai', true);
            }
        } catch (error) {
            console.error('Error loading chat:', error);
            this.addMessage('❌ Error loading chat', 'ai', true);
        }
    }

    async deleteChat(chatId) {
        if (!confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
            return;
        }

        console.log('Attempting to delete chat:', chatId, 'with Session-ID:', this.sessionId);
        try {
            const response = await fetch(`${this.API_BASE_URL}/delete_chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': this.sessionId
                },
                body: JSON.stringify({ chat_id: chatId }),
                credentials: 'include'
            });
            
            const data = await response.json();
            console.log('Delete chat response:', data);
            
            if (data.success) {
                // Clear current chat if it was deleted
                if (this.currentChatId === chatId) {
                    this.currentChatId = null;
                    this.elements.chatMessages.innerHTML = this.getWelcomeMessage();
                }
                
                // Refresh chat list
                await this.updateChatList();
                console.log(`Chat ${chatId} deleted successfully`);
            } else {
                console.error('Failed to delete chat:', data.error);
                this.addMessage(`❌ Failed to delete chat: ${data.error}`, 'ai', true);
            }
        } catch (error) {
            console.error('Error deleting chat:', error);
            this.addMessage('❌ Error deleting chat', 'ai', true);
        }
    }

    showRenameDialog(chatId, currentTitle) {
        const newTitle = prompt('Enter new chat name:', currentTitle);
        if (newTitle && newTitle.trim() !== currentTitle) {
            this.renameChat(chatId, newTitle.trim());
        }
    }

    async renameChat(chatId, newTitle) {
        try {
            const response = await fetch(`${this.API_BASE_URL}/rename_chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': this.sessionId
                },
                body: JSON.stringify({ 
                    chat_id: chatId, 
                    title: newTitle 
                }),
                credentials: 'include'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Refresh chat list to show new name
                await this.updateChatList();
                console.log(`Chat renamed successfully: ${newTitle}`);
            } else {
                this.addMessage(`❌ Failed to rename chat: ${data.error}`, 'ai', true);
            }
        } catch (error) {
            console.error('Error renaming chat:', error);
            this.addMessage('❌ Error renaming chat', 'ai', true);
        }
    }

    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Validate file type
        const allowedTypes = ['.csv', '.xlsx', '.xls'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedTypes.includes(fileExtension)) {
            this.addMessage('❌ Please upload only CSV or Excel files', 'ai', true);
            return;
        }

        this.showUploadProgress(file.name);

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${this.API_BASE_URL}/upload_catalog`, {
                method: 'POST',
                headers: { 'Session-ID': this.sessionId },
                body: formData,
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.updateProductCount(data.product_count);
                    this.addMessage(`✅ Successfully uploaded ${data.product_count} products from ${data.filename}`, 'ai');
                    this.closeUploadModal();
                } else {
                    this.addMessage(`❌ ${data.error || 'Upload failed'}`, 'ai', true);
                }
            } else {
                this.addMessage('❌ Upload failed', 'ai', true);
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.addMessage('❌ Network error during upload', 'ai', true);
        } finally {
            this.hideUploadProgress();
        }
    }

    showUploadProgress(fileName) {
        if (this.elements.fileName) {
            this.elements.fileName.textContent = fileName;
        }
        
        if (this.elements.uploadProgress) {
            this.elements.uploadProgress.style.display = 'block';
        }

        // Simulate progress
        let progress = 0;
        const interval = setInterval(() => {
            progress += 10;
            if (this.elements.progressFill) {
                this.elements.progressFill.style.width = progress + '%';
            }
            if (this.elements.uploadPercent) {
                this.elements.uploadPercent.textContent = progress + '%';
            }
            if (progress >= 100) {
                clearInterval(interval);
            }
        }, 100);
    }

    hideUploadProgress() {
        setTimeout(() => {
            if (this.elements.uploadProgress) {
                this.elements.uploadProgress.style.display = 'none';
            }
        }, 1000);
    }

// Continue from Part 2...

    async generateInvoiceFromCart() {
        try {
            this.addMessage('🔄 Generating PDF invoice from cart...', 'ai');
            
            const response = await fetch(`${this.API_BASE_URL}/generate_invoice_from_cart`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': this.sessionId
                },
                body: JSON.stringify({ session_id: this.sessionId }),
                credentials: 'include'
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    const downloadBtn = `<a href="#" class="download-invoice-btn" onclick="invoiceApp.downloadInvoice('${data.pdf_path}')">
                        <i class="fas fa-download"></i> Download PDF Invoice
                    </a>`;
                    
                    this.addMessage(`✅ Invoice generated successfully!<br>Invoice #: ${data.invoice_number}<br>Total: ₹${data.invoice.summary.grand_total.toFixed(2)}<br><br>${downloadBtn}`, 'ai');
                    this.updateCartCount(0);
                } else {
                    this.addMessage(`❌ ${data.error || 'Error generating invoice'}`, 'ai', true);
                }
            }
        } catch (error) {
            console.error('Invoice generation error:', error);
            this.addMessage(`❌ Error generating invoice: ${error.message}`, 'ai', true);
        }
    }

    async downloadInvoice(filename) {
        try {
            const response = await fetch(`${this.API_BASE_URL}/download_invoice/${filename}`, {
                credentials: 'include'
            });
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }
        } catch (error) {
            console.error('Download error:', error);
            this.addMessage('❌ Error downloading invoice', 'ai', true);
        }
    }

    async downloadCurrentChat() {
        // Implementation for downloading current chat as PDF
        this.addMessage('📄 Generating chat PDF...', 'ai');
        // Add your PDF generation logic here
    }

    async loadClientDetails() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/client/get`, {
                headers: { 'Session-ID': this.sessionId },
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.client) {
                    const fields = ['clientName', 'clientEmail', 'clientPhone', 'clientAddress', 'clientGST', 'clientPlace'];
                    const clientData = ['name', 'email', 'phone', 'address', 'gst_number', 'place_of_supply'];
                    
                    fields.forEach((field, index) => {
                        if (this.elements[field] && data.client[clientData[index]]) {
                            this.elements[field].value = data.client[clientData[index]];
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Error loading client details:', error);
        }
    }

    async saveClientDetails() {
        const clientData = {
            name: this.elements.clientName?.value || '',
            email: this.elements.clientEmail?.value || '',
            phone: this.elements.clientPhone?.value || '',
            address: this.elements.clientAddress?.value || '',
            gst_number: this.elements.clientGST?.value || '',
            place_of_supply: this.elements.clientPlace?.value || '',
            session_id: this.sessionId
        };

        try {
            const response = await fetch(`${this.API_BASE_URL}/client/save`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': this.sessionId
                },
                body: JSON.stringify(clientData),
                credentials: 'include'
            });

            if (response.ok) {
                this.addMessage('✅ Client details saved successfully', 'ai');
                this.closeClientModal();
            } else {
               this.addMessage('❌ Error saving client details', 'ai', true);
           }
       } catch (error) {
           console.error('Save client error:', error);
           this.addMessage('❌ Error saving client details', 'ai', true);
       }
   }

   showCartSummary() {
       // Send a message to show cart details
       if (this.elements.messageInput) {
           this.elements.messageInput.value = 'show cart breakdown';
           this.sendMessage();
       }
       this.closeSidebar();
   }

   handleKeyboardShortcuts(e) {
       // Escape key closes modals
       if (e.key === 'Escape') {
            this.closeAllModals();
            this.closeSettingsDropdown();
            this.closeSidebar();
        }

       // Ctrl/Cmd + K for new chat
       if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
           e.preventDefault();
           this.startNewChat();
       }

       // Ctrl/Cmd + U for upload
       if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
           e.preventDefault();
           this.openUploadModal();
       }

       // Ctrl/Cmd + D for download
       if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
           e.preventDefault();
           this.downloadCurrentChat();
       }
   }

   handleResize() {
       // Close sidebar on desktop resize
       if (window.innerWidth > 768) {
           this.closeSidebar();
       }
   }

    closeAllModals() {
        this.closeUploadModal();
        this.closeClientModal();
        this.closeProductsModal(); // ADD THIS LINE
        this.closeLogoutModal();
        this.closeUserGuideModal();
        this.closeSettingsDropdown();
    }

   // Quick action functions that can be called from HTML
   sendQuickMessage(message) {
       if (this.elements.messageInput) {
           this.elements.messageInput.value = message;
           this.sendMessage();
       }
   }


    async showAllProducts() {
        console.log('📦 Opening all products modal...');
        
        if (this.elements.productsModal) {
            this.elements.productsModal.classList.add('active');
            await this.loadProductsForModal();
        }
    }

    closeProductsModal() {
        if (this.elements.productsModal) {
            this.elements.productsModal.classList.remove('active');
        }
        this.closeSidebar();
    }

    async loadProductsForModal() {
        try {
            // Show loading state
            this.elements.productsLoading.style.display = 'block';
            this.elements.productsList.style.display = 'none';
            this.elements.productsEmpty.style.display = 'none';
            
            const response = await fetch(`${this.API_BASE_URL}/products/all`, {
                method: 'GET',
                headers: {
                    'Session-ID': this.sessionId
                },
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.displayProductsInModal(data.products);
            } else {
                throw new Error('Failed to load products');
            }
        } catch (error) {
            console.error('Error loading products:', error);
            this.showProductsError();
        } finally {
            this.elements.productsLoading.style.display = 'none';
        }
    }

    displayProductsInModal(products) {
        if (!products || products.length === 0) {
            this.elements.productsEmpty.style.display = 'block';
            this.elements.productsList.style.display = 'none';
            this.elements.productsCount.textContent = 'No products available';
            return;
        }

        
        this.updateProductCount(products.length);
        
        // Update count
        this.elements.productsCount.textContent = `${products.length} products available`;

        
        // Create products HTML
        const productsHTML = products.map(product => `
            <div class="product-item" data-name="${product.name.toLowerCase()}">
                <div class="product-info">
                    <div class="product-name">${product.name}</div>
                    ${product.name_description ? `<div class="product-description">${product.name_description}</div>` : ''}
                </div>
                <div class="product-details">
                    <div class="product-price">₹${this.formatPrice(product.price)}</div>
                    ${product.stock !== undefined ? `<div class="product-stock">Stock: ${product.stock}</div>` : ''}
                </div>
                <button class="add-to-cart-btn" onclick="window.invoiceApp.addProductToCart('${product.name}')">
                    <i class="fas fa-plus"></i> Add
                </button>
            </div>
        `).join('');
        
        this.elements.productsList.innerHTML = productsHTML;
        this.elements.productsList.style.display = 'block';
        this.elements.productsEmpty.style.display = 'none';
    }

    filterProductsList() {
        const searchTerm = this.elements.productSearchInput.value.toLowerCase();
        const productItems = this.elements.productsList.querySelectorAll('.product-item');
        let visibleCount = 0;
        
        productItems.forEach(item => {
            const productName = item.dataset.name;
            if (productName.includes(searchTerm)) {
                item.style.display = 'block';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });
        
        // Update count
        const totalProducts = productItems.length;
        if (searchTerm) {
            this.elements.productsCount.textContent = `${visibleCount} of ${totalProducts} products`;
        } else {
            this.elements.productsCount.textContent = `${totalProducts} products available`;
        }
    }

    showProductsError() {
        this.elements.productsList.innerHTML = `
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i>
                <h4>Error Loading Products</h4>
                <p>There was an error loading the products. Please try again.</p>
            </div>
        `;
        this.elements.productsList.style.display = 'block';
    }

    addProductToCart(productName) {
        // Send message to add product to cart
        if (this.elements.messageInput) {
            this.elements.messageInput.value = `add 1 ${productName}`;
            this.sendMessage();
        }
        this.closeProductsModal();
    }

    formatPrice(price) {
        return new Intl.NumberFormat('en-IN').format(price);
    }



   // Modal control functions
   openUploadModal() {
       if (this.elements.uploadModal) {
           this.elements.uploadModal.classList.add('active');
       }
   }

   closeUploadModal() {
       if (this.elements.uploadModal) {
           this.elements.uploadModal.classList.remove('active');
       }
       // Reset upload area
       if (this.elements.uploadProgress) {
           this.elements.uploadProgress.style.display = 'none';
       }
       if (this.elements.fileInput) {
           this.elements.fileInput.value = '';
       }
   }

   openClientModal() {
       if (this.elements.clientModal) {
           this.elements.clientModal.classList.add('active');
       }
   }

   closeClientModal() {
       if (this.elements.clientModal) {
           this.elements.clientModal.classList.remove('active');
       }
   }

   // Utility functions
   formatCurrency(amount) {
       return new Intl.NumberFormat('en-IN', {
           style: 'currency',
           currency: 'INR'
       }).format(amount);
   }

   showNotification(message, type = 'info') {
       // Implementation for showing toast notifications
       console.log(`${type.toUpperCase()}: ${message}`);
   }

   // Connection monitoring
   startConnectionMonitoring() {
       setInterval(() => {
           this.checkConnection();
       }, 30000); // Check every 30 seconds
   }

   // Voice input functionality (future enhancement)
   initVoiceInput() {
       if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
           // Implementation for voice input
           console.log('Voice recognition available');
       }
   }

   // Export chat functionality
   exportChat(format = 'json') {
       if (!this.elements.chatMessages) return;

       const messages = Array.from(this.elements.chatMessages.querySelectorAll('.message')).map(msg => {
           const isUser = msg.classList.contains('user-message');
           const content = msg.querySelector('.message-text').textContent.trim();
           return {
               type: isUser ? 'user' : 'assistant',
               content: content,
               timestamp: new Date().toISOString()
           };
       });

       const chatExport = {
           sessionId: this.sessionId,
           chatId: this.currentChatId,
           messages: messages,
           exportDate: new Date().toISOString()
       };

       const blob = new Blob([JSON.stringify(chatExport, null, 2)], { 
           type: 'application/json' 
       });
       
       const url = URL.createObjectURL(blob);
       const a = document.createElement('a');
       a.href = url;
       a.download = `chat-export-${this.currentChatId || this.sessionId}.json`;
       document.body.appendChild(a);
       a.click();
       document.body.removeChild(a);
       URL.revokeObjectURL(url);
   }

   // Cleanup function
   destroy() {
        console.log('🔄 Application shutting down...');

   }
}

// Global functions for HTML onclick handlers
function openUploadModal() {
   window.invoiceApp.openUploadModal();
}

function closeUploadModal() {
   window.invoiceApp.closeUploadModal();
}

function openClientModal() {
   window.invoiceApp.openClientModal();
}

function closeClientModal() {
   window.invoiceApp.closeClientModal();
}

function saveClientDetails() {
   window.invoiceApp.saveClientDetails();
}

function toggleTheme() {
   window.invoiceApp.toggleTheme();
}

function downloadCurrentChat() {
   window.invoiceApp.downloadCurrentChat();
}

function showCartSummary() {
   window.invoiceApp.showCartSummary();
}

function closeSidebar() {
   window.invoiceApp.closeSidebar();
}

// Initialize the application
window.invoiceApp = new InvoiceAssistant();

// Start connection monitoring
window.invoiceApp.startConnectionMonitoring();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.invoiceApp) {
        window.invoiceApp.destroy();
    }
});

// Service Worker registration for PWA capabilities (optional)
if ('serviceWorker' in navigator) {
   window.addEventListener('load', () => {
       navigator.serviceWorker.register('/sw.js')
           .then(registration => {
               console.log('SW registered: ', registration);
           })
           .catch(registrationError => {
               console.log('SW registration failed: ', registrationError);
           });
   });
}

function showAllProducts() {
    window.invoiceApp.showAllProducts();
}

function closeProductsModal() {
    window.invoiceApp.closeProductsModal();
}

function showUserGuide() {
    window.invoiceApp.showUserGuide();
}

function closeUserGuideModal() {
    window.invoiceApp.closeUserGuideModal();
}

function copyToClipboard(text) {
    window.invoiceApp.copyToClipboard(text);
}

console.log('🎉 AI Invoice Assistant loaded successfully!');
console.log('💡 Keyboard shortcuts:');
console.log('  • Ctrl/Cmd + K: New chat');
console.log('  • Ctrl/Cmd + U: Upload catalog');
console.log('  • Ctrl/Cmd + D: Download chat');
console.log('  • Escape: Close modals/sidebar');