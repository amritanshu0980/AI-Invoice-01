// Fixed Enhanced Admin Dashboard JavaScript
class EnhancedAdminDashboard {
    constructor() {
        this.API_BASE_URL = '/api';
        this.currentSection = 'dashboard';
        this.autoRefreshInterval = null;
        this.refreshCountdown = 30;
        this.charts = {};
        this.isLoading = false;
        this.currentEditProduct = null;
        
        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        console.log('🚀 Initializing Enhanced Admin Dashboard');
        
        // Cache DOM elements
        this.cacheElements();

        this.setupLogoutHandler();


        // Setup event listeners
        this.setupEventListeners();
        
        // Initialize components
        this.initializeComponents();
        
        // Start auto-refresh
        this.startAutoRefresh();
        
        // Hide loading screen
        setTimeout(() => this.hideLoadingScreen(), 1500);
        
        console.log('✅ Enhanced Admin Dashboard initialized successfully');
    }

    cacheElements() {
        // Main elements
        this.elements = {
            // Layout elements
            loadingScreen: document.getElementById('loadingScreen'),
            sidebar: document.getElementById('sidebar'),
            sidebarToggle: document.getElementById('sidebarToggle'),
            mobileMenuBtn: document.getElementById('mobileMenuBtn'),
            mobileOverlay: document.getElementById('mobileOverlay'),
            
            // Header elements
            pageTitle: document.getElementById('pageTitle'),
            lastUpdate: document.getElementById('lastUpdate'),
            refreshBtn: document.getElementById('refreshBtn'),
            refreshCountdown: document.getElementById('refreshCountdown'),
            connectionStatus: document.getElementById('connectionStatus'),
            
            // Navigation
            navLinks: document.querySelectorAll('.nav-link'),
            
            // Metrics
            totalRevenue: document.getElementById('totalRevenue'),
            totalOrders: document.getElementById('totalOrders'),
            totalProducts: document.getElementById('totalProducts'),
            totalUsers: document.getElementById('totalUsers'),
            
            // Charts
            revenueChart: document.getElementById('revenueChart'),
            productsChart: document.getElementById('productsChart'),
            revenueSparkline: document.getElementById('revenueSparkline'),
            ordersSparkline: document.getElementById('ordersSparkline'),
            productsSparkline: document.getElementById('productsSparkline'),
            usersSparkline: document.getElementById('usersSparkline'),
            
            // Products
            productSearch: document.getElementById('productSearch'),
            categoryFilter: document.getElementById('categoryFilter'),
            stockFilter: document.getElementById('stockFilter'),
            productsTable: document.getElementById('productsTable'),
            productsTableBody: document.getElementById('productsTableBody'),
            
            // Modals
            uploadModal: document.getElementById('uploadModal'),
            addProductModal: document.getElementById('addProductModal'),
            editProductModal: document.getElementById('editProductModal'),
            uploadZone: document.getElementById('uploadZone'),
            catalogFileInput: document.getElementById('catalogFileInput'),
            
            // Forms
            addProductForm: document.getElementById('addProductForm'),
            editProductForm: document.getElementById('editProductForm'),
            
            // Toast container
            toastContainer: document.getElementById('toastContainer'),
            
            // Badges
            productCount: document.getElementById('productCount'),
            invoiceCount: document.getElementById('invoiceCount'),
            userCount: document.getElementById('userCount')
        };
    }

    setupEventListeners() {
        // Fixed Sidebar toggle - now properly toggles
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }
        
        // Mobile menu
        if (this.elements.mobileMenuBtn) {
            this.elements.mobileMenuBtn.addEventListener('click', () => this.toggleMobileSidebar());
        }
        
        // Mobile overlay
        if (this.elements.mobileOverlay) {
            this.elements.mobileOverlay.addEventListener('click', () => this.closeMobileSidebar());
        }
        
        // Navigation links
        this.elements.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.dataset.section;
                this.switchSection(section);
            });
        });
        
        // Refresh button
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.addEventListener('click', () => this.refreshData());
        }
        
        // Product search
        if (this.elements.productSearch) {
            this.elements.productSearch.addEventListener('input', 
                this.debounce(() => this.filterProducts(), 300)
            );
        }
        
        // Category filter
        if (this.elements.categoryFilter) {
            this.elements.categoryFilter.addEventListener('change', () => this.filterProducts());
        }
        
        // Stock filter
        if (this.elements.stockFilter) {
            this.elements.stockFilter.addEventListener('change', () => this.filterProducts());
        }
        
        // Upload zone
        if (this.elements.uploadZone) {
            this.setupFileUpload();
        }
        
        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => this.closeModals());
        });
        
        // Quick actions
        document.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                this.handleQuickAction(action);
            });
        });
        
        // Add product button
        const addProductBtn = document.getElementById('addProductBtn');
        if (addProductBtn) {
            addProductBtn.addEventListener('click', () => this.openAddProductModal());
        }
        
        // Upload catalog button
        const uploadCatalogBtn = document.getElementById('uploadCatalogBtn');
        if (uploadCatalogBtn) {
            uploadCatalogBtn.addEventListener('click', () => this.openUploadModal());
        }
        
        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.handleLogout());
        }
        
        // Form submissions
        if (this.elements.addProductForm) {
            this.elements.addProductForm.addEventListener('submit', (e) => this.handleAddProduct(e));
        }
        
        if (this.elements.editProductForm) {
            this.elements.editProductForm.addEventListener('submit', (e) => this.handleEditProduct(e));
        }
        
        // Window resize
        window.addEventListener('resize', () => this.handleResize());
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
    }

    // FIXED: Proper sidebar toggle functionality
    toggleSidebar() {
        console.log('🔄 Toggling sidebar');
        this.elements.sidebar.classList.toggle('collapsed');
        
        // Save state to localStorage
        const isCollapsed = this.elements.sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);
        
        // Update toggle button icon rotation
        const toggleIcon = this.elements.sidebarToggle.querySelector('i');
        if (toggleIcon) {
            if (isCollapsed) {
                toggleIcon.style.transform = 'rotate(180deg)';
            } else {
                toggleIcon.style.transform = 'rotate(0deg)';
            }
        }
        
        // Trigger chart resize after transition
        setTimeout(() => {
            Object.values(this.charts).forEach(chart => {
                if (chart && typeof chart.resize === 'function') {
                    chart.resize();
                }
            });
        }, 300);
    }

    // Load saved sidebar state
    loadSidebarState() {
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (isCollapsed) {
            this.elements.sidebar.classList.add('collapsed');
            const toggleIcon = this.elements.sidebarToggle?.querySelector('i');
            if (toggleIcon) {
                toggleIcon.style.transform = 'rotate(180deg)';
            }
        }
    }

    initializeComponents() {
        // Load saved sidebar state
        this.loadSidebarState();
        
        // Initialize charts
        this.initializeCharts();
        
        // Load initial data
        this.loadDashboardData();
        
        // Set initial page title
        this.updatePageTitle('Dashboard Overview');
        
        // Initialize animations
        this.initializeAnimations();
        
        // Create edit product modal if it doesn't exist
        this.createEditProductModal();
    }

    // NEW: Create edit product modal dynamically
    createEditProductModal() {
        // Check if edit modal already exists
        if (document.getElementById('editProductModal')) {
            return;
        }

        const editModalHTML = `
            <div class="modal-overlay" id="editProductModal">
                <div class="modal enhanced-modal large-modal">
                    <div class="modal-header">
                        <h3>Edit Product</h3>
                        <button class="modal-close" type="button">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div class="modal-body">
                        <form id="editProductForm" class="product-form">
                            <div class="form-grid">
                                <div class="form-group">
                                    <label for="editProductName">Product Name *</label>
                                    <input type="text" id="editProductName" name="name" required>
                                    <input type="hidden" id="editProductOriginalName" name="original_name">
                                </div>
                                <div class="form-group">
                                    <label for="editProductPrice">Price (₹) *</label>
                                    <input type="number" id="editProductPrice" name="price" step="0.01" required>
                                </div>
                                <div class="form-group">
                                    <label for="editProductStock">Stock Quantity</label>
                                    <input type="number" id="editProductStock" name="stock" min="0">
                                </div>
                                <div class="form-group">
                                    <label for="editProductGST">GST Rate (%)</label>
                                    <input type="number" id="editProductGST" name="gst_rate" step="0.01" value="18">
                                </div>
                                <div class="form-group">
                                    <label for="editInstallationCharge">Installation Charge (₹)</label>
                                    <input type="number" id="editInstallationCharge" name="installation_charge" step="0.01">
                                </div>
                                <div class="form-group">
                                    <label for="editServiceCharge">Service Charge (₹)</label>
                                    <input type="number" id="editServiceCharge" name="service_charge" step="0.01">
                                </div>
                                <div class="form-group">
                                    <label for="editShippingCharge">Shipping Charge (₹)</label>
                                    <input type="number" id="editShippingCharge" name="shipping_charge" step="0.01">
                                </div>
                                <div class="form-group">
                                    <label for="editHandlingFee">Handling Fee (₹)</label>
                                    <input type="number" id="editHandlingFee" name="handling_fee" step="0.01">
                                </div>
                            </div>
                            <div class="form-actions">
                                <button type="button" class="btn-secondary" onclick="adminDashboard.closeModals()">Cancel</button>
                                <button type="submit" class="btn-primary">
                                    <i class="fas fa-save"></i>
                                    Save Changes
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        `;

        // Add to page
        document.body.insertAdjacentHTML('beforeend', editModalHTML);
        
        // Update cached elements
        this.elements.editProductModal = document.getElementById('editProductModal');
        this.elements.editProductForm = document.getElementById('editProductForm');
        
        // Add event listeners
        const editModalClose = this.elements.editProductModal.querySelector('.modal-close');
        if (editModalClose) {
            editModalClose.addEventListener('click', () => this.closeModals());
        }
        
        if (this.elements.editProductForm) {
            this.elements.editProductForm.addEventListener('submit', (e) => this.handleEditProduct(e));
        }
    }

    // NEW: Open edit product modal with pre-filled data
    async openEditProductModal(productName) {
        try {
            console.log('✏️ Opening edit modal for:', productName);
            
            // Get product data
            const response = await fetch(`${this.API_BASE_URL}/get_products`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                const product = data.products.find(p => p.name === productName);
                
                if (product) {
                    this.currentEditProduct = product;
                    
                    // Fill form with product data
                    document.getElementById('editProductOriginalName').value = product.name;
                    document.getElementById('editProductName').value = product.name;
                    document.getElementById('editProductPrice').value = product.price || 0;
                    document.getElementById('editProductStock').value = product.stock || 0;
                    document.getElementById('editProductGST').value = product.gst_rate || 18;
                    document.getElementById('editInstallationCharge').value = product['Installation Charge'] || 0;
                    document.getElementById('editServiceCharge').value = product['Service Charge'] || 0;
                    document.getElementById('editShippingCharge').value = product['Shipping Charge'] || 0;
                    document.getElementById('editHandlingFee').value = product['Handling Fee'] || 0;
                    
                    // Show modal
                    this.elements.editProductModal.classList.add('active');
                } else {
                    this.showToast('Product not found', 'error');
                }
            } else {
                this.showToast('Failed to load product data', 'error');
            }
        } catch (error) {
            console.error('Error opening edit modal:', error);
            this.showToast('Error loading product data', 'error');
        }
    }

    // NEW: Handle edit product form submission
    async handleEditProduct(e) {
        e.preventDefault();
        
        if (!this.currentEditProduct) {
            this.showToast('No product selected for editing', 'error');
            return;
        }
        
        const formData = new FormData(e.target);
        const productData = {};
        
        // Convert form data to object
        for (let [key, value] of formData.entries()) {
            if (key === 'name' || key === 'original_name') {
                productData[key] = value;
            } else {
                productData[key] = parseFloat(value) || 0;
            }
        }
        
        try {
            // Show loading state
            const submitBtn = e.target.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
            submitBtn.disabled = true;
            
            const response = await fetch(`${this.API_BASE_URL}/update_product`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(productData),
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.showToast('Product updated successfully', 'success');
                    this.closeModals();
                    
                    // Refresh products table
                    if (this.currentSection === 'products') {
                        this.loadProductsData();
                    }
                    
                    // Update badges
                    this.updateBadges();
                    
                    this.currentEditProduct = null;
                } else {
                    this.showToast(data.error || 'Failed to update product', 'error');
                }
            } else {
                this.showToast('Failed to update product', 'error');
            }
        } catch (error) {
            console.error('Edit product error:', error);
            this.showToast('Network error', 'error');
        } finally {
            // Reset button state
            const submitBtn = e.target.querySelector('button[type="submit"]');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    // NEW: Handle add product form submission
    async handleAddProduct(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const productData = {};
        
        // Convert form data to object
        for (let [key, value] of formData.entries()) {
            if (key === 'name') {
                productData[key] = value;
            } else {
                productData[key] = parseFloat(value) || 0;
            }
        }
        
        try {
            // Show loading state
            const submitBtn = e.target.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adding...';
            submitBtn.disabled = true;
            
            const response = await fetch(`${this.API_BASE_URL}/add_product`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(productData),
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.showToast('Product added successfully', 'success');
                    this.closeModals();
                    e.target.reset();
                    
                    // Refresh products table
                    if (this.currentSection === 'products') {
                        this.loadProductsData();
                    }
                    
                    // Update badges
                    this.updateBadges();
                } else {
                    this.showToast(data.error || 'Failed to add product', 'error');
                }
            } else {
                this.showToast('Failed to add product', 'error');
            }
        } catch (error) {
            console.error('Add product error:', error);
            this.showToast('Network error', 'error');
        } finally {
            // Reset button state
            const submitBtn = e.target.querySelector('button[type="submit"]');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }

    // UPDATED: Product table with working edit buttons
    displayProductsTable(products) {
        if (!this.elements.productsTableBody) return;
        
        if (products.length === 0) {
            this.elements.productsTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center" style="padding: 2rem;">
                        <div style="color: #6b7280;">
                            <i class="fas fa-box" style="font-size: 2rem; margin-bottom: 1rem; display: block;"></i>
                            <p>No products found</p>
                            <button class="btn-primary" onclick="adminDashboard.openAddProductModal()" style="margin-top: 1rem;">
                                <i class="fas fa-plus"></i> Add Your First Product
                            </button>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        this.elements.productsTableBody.innerHTML = products.map((product, index) => {
            const stock = product.stock || 0;
            const status = stock > 10 ? 'In Stock' : stock > 0 ? 'Low Stock' : 'Out of Stock';
            const statusClass = stock > 10 ? 'active' : stock > 0 ? 'pending' : 'inactive';
            
            return `
                <tr>
                    <td>
                        <input type="checkbox" value="${index}">
                    </td>
                    <td>
                        <div style="display: flex; align-items: center; gap: 0.75rem;">
                            <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #6366f1, #8b5cf6); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;">
                                ${product.name.charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <div style="font-weight: 500; color: var(--text-primary);">${product.name}</div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">SKU: ${product.name.replace(/\s+/g, '').toUpperCase().substring(0, 8)}</div>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span style="font-weight: 600;">₹${product.price.toLocaleString()}</span>
                    </td>
                    <td>
                        <span style="font-weight: 500;">${stock}</span>
                    </td>
                    <td>
                        <span style="color: var(--text-secondary);">Electronics</span>
                    </td>
                    <td>
                        <span class="status-badge ${statusClass}">${status}</span>
                    </td>
                    <td>
                        <div style="display: flex; gap: 0.5rem;">
                            <button class="btn-icon" onclick="adminDashboard.editProduct('${product.name.replace(/'/g, "\\'")}')" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn-icon danger" onclick="adminDashboard.deleteProduct('${product.name.replace(/'/g, "\\'")}')" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        
        // Add CSS for btn-icon if not exists
        if (!document.querySelector('.btn-icon-styles')) {
            const style = document.createElement('style');
            style.className = 'btn-icon-styles';
            style.textContent = `
                .btn-icon {
                    width: 32px;
                    height: 32px;
                    border: 1px solid var(--border-color);
                    background: var(--bg-primary);
                    color: var(--text-secondary);
                    border-radius: 6px;
                    cursor: pointer;
                    transition: all 0.15s ease;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .btn-icon:hover {
                    border-color: var(--primary-color);
                    color: var(--primary-color);
                    background: rgba(99, 102, 241, 0.05);
                }
                .btn-icon.danger:hover {
                    border-color: var(--danger-color);
                    color: var(--danger-color);
                    background: rgba(239, 68, 68, 0.05);
                }
            `;
            document.head.appendChild(style);
        }
    }

    // UPDATED: Edit product function
    editProduct(productName) {
        console.log('✏️ Editing product:', productName);
        this.openEditProductModal(productName);
    }

    // Keep all other existing methods unchanged...
    // [Previous methods remain the same from hideLoadingScreen to destroy]

    hideLoadingScreen() {
        if (this.elements.loadingScreen) {
            this.elements.loadingScreen.classList.add('hidden');
            setTimeout(() => {
                this.elements.loadingScreen.style.display = 'none';
            }, 500);
        }
    }

    toggleMobileSidebar() {
        this.elements.sidebar.classList.add('mobile-open');
        this.elements.mobileOverlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    closeMobileSidebar() {
        this.elements.sidebar.classList.remove('mobile-open');
        this.elements.mobileOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    switchSection(section) {
        console.log(`Switching to section: ${section}`);
        
        // Update active nav link
        this.elements.navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.dataset.section === section) {
                link.classList.add('active');
            }
        });
        
        // Hide all sections
        document.querySelectorAll('.content-section').forEach(sec => {
            sec.classList.remove('active');
        });
        
        // Show target section
        const targetSection = document.getElementById(`${section}Section`);
        if (targetSection) {
            targetSection.classList.add('active');
        }
        
        // Update page title
        const titles = {
            dashboard: 'Dashboard Overview',
            products: 'Product Management',
            invoices: 'Invoice Management',
            users: 'User Management',
            analytics: 'Analytics & Reports',
            settings: 'Settings'
        };
        
        this.updatePageTitle(titles[section] || 'Dashboard');
        this.currentSection = section;
        
        // Load section-specific data
        this.loadSectionData(section);
        
        // Close mobile sidebar
        if (window.innerWidth <= 768) {
            this.closeMobileSidebar();
        }
    }

    updatePageTitle(title) {
        if (this.elements.pageTitle) {
            this.elements.pageTitle.textContent = title;
        }
        document.title = `${title} - AI Invoice Assistant`;
    }

    startAutoRefresh() {
        this.autoRefreshInterval = setInterval(() => {
            this.refreshCountdown--;
            
            if (this.elements.refreshCountdown) {
                this.elements.refreshCountdown.textContent = this.refreshCountdown;
            }
            
            // Update progress bar
            const progress = ((30 - this.refreshCountdown) / 30) * 100;
            const progressBar = document.querySelector('.refresh-progress');
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
            }
            
            if (this.refreshCountdown <= 0) {
                this.refreshData();
                this.refreshCountdown = 30;
            }
        }, 1000);
    }

    async refreshData() {
        console.log('🔄 Refreshing dashboard data...');
        
        if (this.isLoading) return;
        
        this.isLoading = true;
        
        // Show loading state
        const refreshBtn = this.elements.refreshBtn;
        if (refreshBtn) {
            refreshBtn.disabled = true;
            const icon = refreshBtn.querySelector('i');
            if (icon) {
                icon.style.animation = 'spin 1s linear infinite';
            }
        }
        
        try {
            await this.loadDashboardData();
            this.updateLastUpdate();
            this.showToast('Data refreshed successfully', 'success');
        } catch (error) {
            console.error('Refresh failed:', error);
            this.showToast('Failed to refresh data', 'error');
        } finally {
            this.isLoading = false;
            
            // Reset loading state
            if (refreshBtn) {
                refreshBtn.disabled = false;
                const icon = refreshBtn.querySelector('i');
                if (icon) {
                    icon.style.animation = '';
                }
            }
        }
    }

    updateLastUpdate() {
        if (this.elements.lastUpdate) {
            const now = new Date();
            this.elements.lastUpdate.textContent = 
                `Last updated: ${now.toLocaleTimeString()}`;
        }
    }

    async loadDashboardData() {
        try {
            console.log('📊 Loading dashboard data...');
            
            // Update connection status
            this.updateConnectionStatus(true);
            
            // Load metrics
            await this.loadMetrics();
            
            // Load charts data
            await this.loadChartsData();
            
            // Load recent activity
            await this.loadRecentActivity();
            
            // Update badges
            await this.updateBadges();
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            this.updateConnectionStatus(false);
            throw error;
        }
    }

    async loadMetrics() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/admin_dashboard_data`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update metric values with animation
                this.animateCounter(this.elements.totalRevenue, 0, data.totalRevenue, '₹');
                this.animateCounter(this.elements.totalOrders, 0, data.totalInvoices);
                this.animateCounter(this.elements.totalProducts, 0, await this.getProductCount());
                this.animateCounter(this.elements.totalUsers, 0, data.activeUsers);
                
                return data;
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('Failed to load metrics:', error);
            // Set default values
            if (this.elements.totalRevenue) this.elements.totalRevenue.textContent = '₹0';
            if (this.elements.totalOrders) this.elements.totalOrders.textContent = '0';
            if (this.elements.totalProducts) this.elements.totalProducts.textContent = '0';
            if (this.elements.totalUsers) this.elements.totalUsers.textContent = '0';
        }
    }

    async getProductCount() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/get_products`, {
                credentials: 'include'
            });
            if (response.ok) {
                const data = await response.json();
                return data.count || data.products.length || 0;
            }
        } catch (error) {
            console.error('Failed to get product count:', error);
        }
        return 0;
    }

    animateCounter(element, start, end, prefix = '', duration = 1000) {
        if (!element) return;
        
        const startTime = performance.now();
        const startNum = parseInt(start) || 0;
        const endNum = parseInt(end) || 0;
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            const current = Math.floor(startNum + (endNum - startNum) * easeOutQuart);
            
            element.textContent = prefix + current.toLocaleString();
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }

    async loadChartsData() {
        try {
            // Generate sample data for demonstration
            const revenueData = this.generateSampleRevenueData();
            const productsData = await this.getTopProductsData();
            
            // Update main charts
            this.updateRevenueChart(revenueData);
            this.updateProductsChart(productsData);
            
            // Update sparklines
            this.updateSparklines(revenueData);
            
        } catch (error) {
            console.error('Failed to load charts data:', error);
        }
    }

    generateSampleRevenueData() {
        const data = [];
        const labels = [];
        const now = new Date();
        
        for (let i = 29; i >= 0; i--) {
            const date = new Date(now);
            date.setDate(date.getDate() - i);
            
            labels.push(date.toLocaleDateString());
            // Generate realistic revenue data with some randomness
            const baseRevenue = 50000 + Math.random() * 30000;
            const trend = (30 - i) * 1000; // Upward trend
            data.push(Math.floor(baseRevenue + trend));
        }
        
        return { labels, data };
    }

    async getTopProductsData() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/get_products`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const result = await response.json();
                const products = result.products || [];
                
                // Get top 5 products by price (as a demo metric)
                const topProducts = products
                    .sort((a, b) => b.price - a.price)
                    .slice(0, 5)
                    .map(product => ({
                        name: product.name.length > 20 ? 
                              product.name.substring(0, 20) + '...' : 
                              product.name,
                        value: Math.floor(Math.random() * 100) + 20 // Mock sales data
                    }));
                
                return topProducts;
            }
        } catch (error) {
            console.error('Failed to get products data:', error);
        }
        
        // Return mock data if API fails
        return [
            { name: 'AI Security Camera', value: 85 },
            { name: 'Smart Door Lock', value: 72 },
            { name: 'Thermal Camera', value: 58 },
            { name: 'Smart Thermostat', value: 45 },
            { name: 'Mesh Router', value: 33 }
        ];
    }

    initializeCharts() {
        // Initialize revenue chart
        if (this.elements.revenueChart) {
            const ctx = this.elements.revenueChart.getContext('2d');
            this.charts.revenue = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Revenue',
                        data: [],
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#6366f1',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            borderColor: '#6366f1',
                            borderWidth: 1,
                            cornerRadius: 8,
                            callbacks: {
                                label: function(context) {
                                    return `Revenue: ₹${context.parsed.y.toLocaleString()}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        },
                        y: {
                            display: true,
                            grid: {
                                color: 'rgba(107, 114, 128, 0.1)'
                            },
                            ticks: {
                                color: '#6b7280',
                                callback: function(value) {
                                    return '₹' + value.toLocaleString();
                                }
                            }
                        }
                    },
                    elements: {
                        point: {
                            hoverBackgroundColor: '#6366f1'
                        }
                    }
                }
            });
        }

        // Initialize products chart
        if (this.elements.productsChart) {
            const ctx = this.elements.productsChart.getContext('2d');
            this.charts.products = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Sales',
                        data: [],
                        backgroundColor: [
                            '#6366f1',
                            '#10b981',
                            '#f59e0b',
                            '#ef4444',
                            '#8b5cf6'
                        ],
                        borderRadius: 8,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: '#ffffff',
                            bodyColor: '#ffffff',
                            borderColor: '#6366f1',
                            borderWidth: 1,
                            cornerRadius: 8
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        },
                        y: {
                            display: true,
                            grid: {
                                color: 'rgba(107, 114, 128, 0.1)'
                            },
                            ticks: {
                                color: '#6b7280'
                            }
                        }
                    }
                }
            });
        }

        // Initialize sparklines
        this.initializeSparklines();
    }

    initializeSparklines() {
        const sparklineOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            },
            elements: {
                point: { radius: 0 },
                line: { borderWidth: 2 }
            }
        };

        // Revenue sparkline
        if (this.elements.revenueSparkline) {
            const ctx = this.elements.revenueSparkline.getContext('2d');
            this.charts.revenueSparkline = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(7).fill(''),
                    datasets: [{
                        data: [20, 35, 25, 40, 30, 45, 35],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: sparklineOptions
            });
        }

        // Orders sparkline
        if (this.elements.ordersSparkline) {
            const ctx = this.elements.ordersSparkline.getContext('2d');
            this.charts.ordersSparkline = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(7).fill(''),
                    datasets: [{
                        data: [15, 25, 20, 30, 25, 35, 40],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: sparklineOptions
            });
        }

        // Products sparkline
        if (this.elements.productsSparkline) {
            const ctx = this.elements.productsSparkline.getContext('2d');
            this.charts.productsSparkline = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(7).fill(''),
                    datasets: [{
                        data: [10, 15, 12, 18, 15, 20, 18],
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: sparklineOptions
            });
        }

        // Users sparkline
        if (this.elements.usersSparkline) {
            const ctx = this.elements.usersSparkline.getContext('2d');
            this.charts.usersSparkline = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(7).fill(''),
                    datasets: [{
                        data: [8, 12, 10, 15, 13, 18, 20],
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: sparklineOptions
            });
        }
    }

    updateRevenueChart(data) {
        if (this.charts.revenue) {
            this.charts.revenue.data.labels = data.labels;
            this.charts.revenue.data.datasets[0].data = data.data;
            this.charts.revenue.update('active');
        }
    }

    updateProductsChart(data) {
        if (this.charts.products) {
            this.charts.products.data.labels = data.map(item => item.name);
            this.charts.products.data.datasets[0].data = data.map(item => item.value);
            this.charts.products.update('active');
        }
    }

    updateSparklines(data) {
        // Update sparklines with recent data points
        const recentData = data.data.slice(-7);
        
        if (this.charts.revenueSparkline) {
            this.charts.revenueSparkline.data.datasets[0].data = recentData.map(val => val / 1000);
            this.charts.revenueSparkline.update('none');
        }
    }

    async loadRecentActivity() {
        const activities = [
            {
                icon: 'fas fa-user-plus',
                text: 'New user registered',
                time: '2 minutes ago'
            },
            {
                icon: 'fas fa-shopping-cart',
                text: 'New order placed',
                time: '5 minutes ago'
            },
            {
                icon: 'fas fa-box',
                text: 'Product added to catalog',
                time: '10 minutes ago'
            },
            {
                icon: 'fas fa-file-invoice-dollar',
                text: 'Invoice generated',
                time: '15 minutes ago'
            },
            {
                icon: 'fas fa-edit',
                text: 'Product updated',
                time: '20 minutes ago'
            }
        ];

        const activityContainer = document.getElementById('recentActivity');
        if (activityContainer) {
            activityContainer.innerHTML = activities.map(activity => `
                <div class="activity-item">
                    <div class="activity-icon">
                        <i class="${activity.icon}"></i>
                    </div>
                    <div class="activity-content">
                        <p class="activity-text">${activity.text}</p>
                        <span class="activity-time">${activity.time}</span>
                    </div>
                </div>
            `).join('');
        }
    }

    async updateBadges() {
        try {
            // Update product count
            const productCount = await this.getProductCount();
            if (this.elements.productCount) {
                this.elements.productCount.textContent = productCount;
            }

            // Mock data for other badges
            if (this.elements.invoiceCount) {
                this.elements.invoiceCount.textContent = '24';
            }
            
            if (this.elements.userCount) {
                this.elements.userCount.textContent = '15';
            }
        } catch (error) {
            console.error('Failed to update badges:', error);
        }
    }

    async loadUsersSection() {
    const usersSection = document.getElementById('usersSection');
    const loadingIndicator = document.getElementById('usersLoadingIndicator');
    
    console.log('🔄 Loading users section...');
    console.log('Users section element:', usersSection);
    console.log('Loading indicator element:', loadingIndicator);
    
    if (!usersSection) {
        console.error('❌ Users section element not found');
        return;
    }

    try {
        // Show loading indicator
        if (loadingIndicator) {
            loadingIndicator.style.display = 'block';
        } else {
            // Create loading indicator if it doesn't exist
            usersSection.innerHTML = `
                <div class="section-loading" id="usersLoadingIndicator">
                    <div class="loading-spinner"></div>
                    <p>Loading User Management...</p>
                </div>
            `;
        }

        console.log('📡 Fetching users section from server...');
        
        // Fetch the users section HTML with better error handling
        const response = await fetch('/api/admin/users_section', {
            method: 'GET',
            headers: {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Cache-Control': 'no-cache'
            },
            credentials: 'same-origin'
        });
        
        console.log('📡 Response status:', response.status);
        console.log('📡 Response headers:', response.headers);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status} - ${response.statusText}`);
        }
        
        const html = await response.text();
        console.log('📄 HTML received, length:', html.length);
        console.log('📄 HTML preview (first 200 chars):', html.substring(0, 200));
        
        if (!html || html.trim().length === 0) {
            throw new Error('Empty HTML response received');
        }
        
        // Insert the HTML content
        usersSection.innerHTML = html;
        
        console.log('✅ Users section HTML inserted successfully');
        
        // Initialize the users manager
        setTimeout(() => {
            if (typeof AdminUsersManager !== 'undefined') {
                console.log('🔧 Initializing AdminUsersManager...');
                if (!window.adminUsersManager) {
                    window.adminUsersManager = new AdminUsersManager();
                } else {
                    console.log('🔄 Refreshing existing users data...');
                    window.adminUsersManager.loadUsersData();
                }
            } else {
                console.error('❌ AdminUsersManager class not found. Make sure admin_users.js is loaded.');
            }
        }, 200);
        
    } catch (error) {
        console.error('❌ Error loading users section:', error);
        
        // Hide loading indicator
        if (loadingIndicator) {
            loadingIndicator.style.display = 'none';
        }
        
        // Show detailed error message
        usersSection.innerHTML = `
            <div class="section-error" style="
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 3rem;
                text-align: center;
                background: #fff;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
                margin: 2rem;
            ">
                <div style="
                    width: 80px;
                    height: 80px;
                    border-radius: 50%;
                    background: rgba(239, 68, 68, 0.1);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 1.5rem;
                    font-size: 2rem;
                    color: #dc2626;
                ">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h3 style="font-size: 1.25rem; font-weight: 600; color: #111827; margin-bottom: 0.5rem;">
                    Failed to Load User Management
                </h3>
                <p style="color: #6b7280; margin-bottom: 1rem;">
                    Error: ${error.message}
                </p>
                <details style="margin-bottom: 1.5rem; text-align: left; max-width: 500px;">
                    <summary style="cursor: pointer; color: #6b7280; margin-bottom: 0.5rem;">
                        Technical Details
                    </summary>
                    <pre style="
                        background: #f9fafb;
                        padding: 1rem;
                        border-radius: 6px;
                        font-size: 0.8rem;
                        color: #374151;
                        overflow-x: auto;
                    ">${error.stack || error.message}</pre>
                </details>
                <button onclick="adminDashboard.loadUsersSection()" style="
                    background: linear-gradient(135deg, #6366f1, #8b5cf6);
                    color: white;
                    border: none;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    font-weight: 500;
                    cursor: pointer;
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                ">
                    <i class="fas fa-refresh"></i>
                    Try Again
                </button>
            </div>
        `;
    }
}

    loadSectionData(section) {
        switch (section) {
            case 'products':
                this.loadProductsData();
                break;
            case 'invoices':
                this.loadInvoicesData();
                break;
            case 'users':
                this.loadUsersSection();
                break;
            case 'analytics':
                this.loadAnalyticsData();
                break;
            default:
                break;
        }
    }


    setupLogoutHandler() {
        const logoutButton = document.getElementById('logoutBtn');
        if (logoutButton) {
            logoutButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleLogout();
            });
            console.log('✅ Logout handler setup completed');
        }
    }

    handleLogout() {
        // Open the modal instead of browser confirm
        this.openLogoutModal();
    }

    // Modal management functions
    openLogoutModal() {
        console.log('🚪 Opening logout confirmation modal...');
        const adminLogoutModal = document.getElementById('adminLogoutModal');
        if (adminLogoutModal) {
            adminLogoutModal.classList.add('active');
        }
    }

    closeLogoutModal() {
        console.log('❌ Closing logout modal');
        const adminLogoutModal = document.getElementById('adminLogoutModal');
        if (adminLogoutModal) {
            adminLogoutModal.classList.remove('active');
        }
    }

    // This is called when user clicks "Logout" in the modal
    async confirmLogout() {
        console.log('✅ Logout confirmed, proceeding...');
        
        try {
            // Close the modal first
            this.closeLogoutModal();
            
            // Show loading state on logout button if possible
            const logoutBtn = document.getElementById('logoutBtn');
            if (logoutBtn) {
                const originalHTML = logoutBtn.innerHTML;
                logoutBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Logging out...</span>';
                logoutBtn.disabled = true;
            }
            
            // Call the logout API
            const response = await fetch(`${this.API_BASE_URL}/logout`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                console.log('✅ Logout API successful');
                this.showToast('Logged out successfully', 'success');
                
                // Redirect after brief delay
                setTimeout(() => {
                    window.location.href = '/api/login';
                }, 1000);
                
            } else {
                console.warn('⚠️ Logout API failed, but redirecting for security');
                this.showToast('Logout failed, redirecting anyway...', 'warning');
                
                setTimeout(() => {
                    window.location.href = '/api/login';
                }, 2000);
            }
            
        } catch (error) {
            console.error('❌ Error during logout:', error);
            this.showToast('Error during logout, redirecting...', 'error');
            
            // Always redirect for security, even on error
            setTimeout(() => {
                window.location.href = '/api/login';
            }, 2000);
            
        } finally {
            // Reset button state
            const logoutBtn = document.getElementById('logoutBtn');
            if (logoutBtn) {
                logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt"></i> <span>Logout</span>';
                logoutBtn.disabled = false;
            }
        }
    }

    async loadProductsData() {
        try {
            console.log('📦 Loading products data...');
            
            const response = await fetch(`${this.API_BASE_URL}/get_products`, {
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.displayProductsTable(data.products || []);
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('Failed to load products:', error);
            this.showToast('Failed to load products', 'error');
        }
    }

    filterProducts() {
        const searchTerm = this.elements.productSearch?.value.toLowerCase() || '';
        const categoryFilter = this.elements.categoryFilter?.value || '';
        const stockFilter = this.elements.stockFilter?.value || '';
        
        const rows = this.elements.productsTableBody?.querySelectorAll('tr') || [];
        
        rows.forEach(row => {
            const productName = row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '';
            const stock = parseInt(row.querySelector('td:nth-child(4)')?.textContent) || 0;
            
            let visible = true;
            
            // Search filter
            if (searchTerm && !productName.includes(searchTerm)) {
                visible = false;
            }
            
            // Stock filter
            if (stockFilter) {
                if (stockFilter === 'in-stock' && stock <= 10) visible = false;
                if (stockFilter === 'low-stock' && (stock <= 0 || stock > 10)) visible = false;
                if (stockFilter === 'out-of-stock' && stock > 0) visible = false;
            }
            
            row.style.display = visible ? '' : 'none';
        });
    }

    loadInvoicesData() {
        console.log('📄 Loading invoices data...');
        // Implementation for invoices - will be in separate file
    }

    loadUsersData() {
        console.log('👥 Loading users data...');
        // Implementation for users - will be in separate file
    }

    loadAnalyticsData() {
        console.log('📊 Loading analytics data...');
        // Implementation for analytics - will be in separate file
    }

    // Modal Management
    openUploadModal() {
        if (this.elements.uploadModal) {
            this.elements.uploadModal.classList.add('active');
        }
    }

    openAddProductModal() {
        if (this.elements.addProductModal) {
            this.elements.addProductModal.classList.add('active');
        }
    }

    closeModals() {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.classList.remove('active');
        });
        
        // Clear edit product state
        this.currentEditProduct = null;
    }

    // File Upload Management
    setupFileUpload() {
        const uploadZone = this.elements.uploadZone;
        const fileInput = this.elements.catalogFileInput;
        
        // Drag and drop events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => {
                uploadZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => {
                uploadZone.classList.remove('dragover');
            }, false);
        });

        uploadZone.addEventListener('drop', (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleFileUpload(files[0]);
            }
        }, false);

        uploadZone.addEventListener('click', () => {
            fileInput.click();
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileUpload(e.target.files[0]);
            }
        });
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    async handleFileUpload(file) {
        console.log('📁 Uploading file:', file.name);
        
        // Validate file type
        const allowedTypes = ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
        if (!allowedTypes.includes(file.type) && !file.name.match(/\.(csv|xlsx|xls)$/i)) {
            this.showToast('Invalid file type. Please upload CSV or Excel files.', 'error');
            return;
        }
        
        // Show upload progress
        this.showUploadProgress();
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch(`${this.API_BASE_URL}/upload_catalog`, {
                method: 'POST',
                body: formData,
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.showToast(`Successfully uploaded ${data.product_count} products`, 'success');
                    this.closeModals();
                    
                    // Refresh products if we're on products section
                    if (this.currentSection === 'products') {
                        this.loadProductsData();
                    }
                    
                    // Update badges
                    this.updateBadges();
                } else {
                    this.showToast(data.error || 'Upload failed', 'error');
                }
            } else {
                this.showToast('Upload failed', 'error');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showToast('Network error during upload', 'error');
        } finally {
            this.hideUploadProgress();
        }
    }

    showUploadProgress() {
        const uploadProgress = document.getElementById('uploadProgress');
        if (uploadProgress) {
            uploadProgress.style.display = 'block';
            
            // Simulate progress
            let progress = 0;
            const interval = setInterval(() => {
                progress += 10;
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                if (progressFill) progressFill.style.width = progress + '%';
                if (progressText) progressText.textContent = `Uploading... ${progress}%`;
                
                if (progress >= 100) {
                    clearInterval(interval);
                }
            }, 100);
        }
    }

    hideUploadProgress() {
        setTimeout(() => {
            const uploadProgress = document.getElementById('uploadProgress');
            if (uploadProgress) {
                uploadProgress.style.display = 'none';
            }
        }, 1000);
    }

    async deleteProduct(productName) {
        if (!confirm(`Are you sure you want to delete "${productName}"?`)) {
            return;
        }
        
        try {
            const response = await fetch(`${this.API_BASE_URL}/delete_product`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: productName }),
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.showToast('Product deleted successfully', 'success');
                    this.loadProductsData(); // Refresh table
                    this.updateBadges(); // Update counts
                } else {
                    this.showToast(data.error || 'Failed to delete product', 'error');
                }
            } else {
                this.showToast('Failed to delete product', 'error');
            }
        } catch (error) {
            console.error('Delete error:', error);
            this.showToast('Network error', 'error');
        }
    }

    // Quick Actions
    handleQuickAction(action) {
        console.log('⚡ Quick action:', action);
        
        switch (action) {
            case 'add-product':
                this.openAddProductModal();
                break;
            case 'upload-catalog':
                this.openUploadModal();
                break;
            case 'export-data':
                this.showToast('Export feature coming soon', 'info');
                break;
            case 'view-reports':
                this.switchSection('analytics');
                break;
            default:
                this.showToast('Feature coming soon', 'info');
        }
    }

    // Toast Notifications
    showToast(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };
        
        toast.innerHTML = `
            <i class="toast-icon ${icons[type]}"></i>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Add to container
        if (this.elements.toastContainer) {
            this.elements.toastContainer.appendChild(toast);
        }
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove
        const autoRemove = setTimeout(() => this.removeToast(toast), duration);
        
        // Manual close
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                clearTimeout(autoRemove);
                this.removeToast(toast);
            });
        }
    }

    removeToast(toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    // Connection Status
    updateConnectionStatus(connected) {
        const statusElement = this.elements.connectionStatus;
        if (statusElement) {
            const dot = statusElement.querySelector('.status-dot');
            const text = statusElement.querySelector('span');
            
            if (connected) {
                dot.classList.remove('offline');
                dot.classList.add('online');
                text.textContent = 'Connected';
            } else {
                dot.classList.remove('online');
                dot.classList.add('offline');
                text.textContent = 'Offline';
            }
        }
    }

    // Animation Helpers
    initializeAnimations() {
        // Intersection Observer for scroll animations
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const element = entry.target;
                    const animationType = element.dataset.animate;
                    
                    if (animationType) {
                        element.style.animation = `${animationType} 0.6s ease-out forwards`;
                    }
                }
            });
        }, { threshold: 0.1 });

        // Observe all elements with data-animate attribute
        document.querySelectorAll('[data-animate]').forEach(el => {
            observer.observe(el);
        });
    }

    // Event Handlers
    handleResize() {
        // Close mobile sidebar on desktop resize
        if (window.innerWidth > 768) {
            this.closeMobileSidebar();
        }
        
        // Resize charts
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.resize === 'function') {
                chart.resize();
            }
        });
    }

    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + R: Refresh data
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            this.refreshData();
        }
        
        // Escape: Close modals
        if (e.key === 'Escape') {
            this.closeModals();
        }
        
        // Ctrl/Cmd + N: Add new product
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            this.openAddProductModal();
        }
        
        // Ctrl/Cmd + U: Upload catalog
        if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
            e.preventDefault();
            this.openUploadModal();
        }
        
        // Number keys for quick section switching
        if (e.key >= '1' && e.key <= '6' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            const sections = ['dashboard', 'products', 'invoices', 'users', 'analytics', 'settings'];
            const sectionIndex = parseInt(e.key) - 1;
            if (sections[sectionIndex]) {
                this.switchSection(sections[sectionIndex]);
            }
        }
    }

    

    // Utility Functions
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Cleanup
    destroy() {
        // Clear intervals
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        
        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        
        console.log('🧹 Dashboard cleanup completed');
    }
}

// Initialize Dashboard
let adminDashboard;

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 Initializing Fixed Admin Dashboard...');
    
    // Initialize main dashboard
    adminDashboard = new EnhancedAdminDashboard();
    
    // Make dashboard globally available
    window.adminDashboard = adminDashboard;
    
    console.log('✅ Fixed dashboard initialized successfully');
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (adminDashboard) {
        adminDashboard.destroy();
    }
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { EnhancedAdminDashboard };
}