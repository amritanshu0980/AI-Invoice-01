/**
 * Admin Users Management JavaScript
 * Handles all user management functionality in the admin dashboard
 */

class AdminUsersManager {
    constructor() {
        this.currentPage = 1;
        this.itemsPerPage = 10;
        this.totalUsers = 0;
        this.allUsers = [];
        this.filteredUsers = [];
        this.currentUserRole = 'admin'; // Will be set from session
        this.searchTerm = '';
        this.roleFilter = 'all';
        this.statusFilter = 'all';
        
        this.init();
    }

    async init() {
        console.log('🚀 Initializing Admin Users Manager...');
        
        // Get current user info
        await this.getCurrentUserInfo();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial data
        await this.loadUsersData();
        
        // Setup role options based on current user
        this.setupRoleOptions();
        
        console.log('✅ Admin Users Manager initialized');
    }

    async getCurrentUserInfo() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (data.user_info) {
                this.currentUserRole = data.user_info.role;
                console.log(`Current user role: ${this.currentUserRole}`);
            }
        } catch (error) {
            console.error('Error getting current user info:', error);
        }
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('userSearchInput');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.searchTerm = e.target.value.toLowerCase();
                this.filterAndDisplayUsers();
            }, 300));
        }

        // Filter functionality
        const roleFilter = document.getElementById('roleFilter');
        if (roleFilter) {
            roleFilter.addEventListener('change', (e) => {
                this.roleFilter = e.target.value;
                this.filterAndDisplayUsers();
            });
        }

        const statusFilter = document.getElementById('statusFilter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.statusFilter = e.target.value;
                this.filterAndDisplayUsers();
            });
        }

        // Form submissions
        const addUserForm = document.getElementById('addUserForm');
        if (addUserForm) {
            addUserForm.addEventListener('submit', (e) => this.handleAddUser(e));
        }

        const editUserForm = document.getElementById('editUserForm');
        if (editUserForm) {
            editUserForm.addEventListener('submit', (e) => this.handleEditUser(e));
        }

        // Modal close on overlay click
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeAllModals();
                }
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });
    }

    async loadSectionData(section) {
        switch(section) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'products':
                this.loadProductsData();
                break;
            case 'invoices':
                this.loadInvoicesData();
                break;
            case 'users':
                // ADD THIS CASE FOR DYNAMIC LOADING:
                await this.loadUsersSection();
                break;
            case 'analytics':
                this.loadAnalyticsData();
                break;
            case 'settings':
                this.loadSettingsData();
                break;
        }
    }

    async loadUsersSection() {
        const usersSection = document.getElementById('usersSection');
        const loadingIndicator = document.getElementById('usersLoadingIndicator');
        
        if (!usersSection) {
            console.error('Users section not found');
            return;
        }

        try {
            // Show loading indicator
            if (loadingIndicator) {
                loadingIndicator.style.display = 'block';
            }

            console.log('🔄 Loading users section...');
            
            // Fetch the users section HTML
            const response = await fetch('/api/admin/users_section');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const html = await response.text();
            
            // Hide loading indicator
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            
            // Insert the HTML content
            usersSection.innerHTML = html;
            
            console.log('✅ Users section loaded successfully');
            
            // Initialize the users manager if it's not already initialized
            if (!window.adminUsersManager) {
                // Wait a bit for the DOM to be ready
                setTimeout(() => {
                    if (window.AdminUsersManager) {
                        window.adminUsersManager = new window.AdminUsersManager();
                    } else {
                        console.warn('⚠️ AdminUsersManager class not found. Make sure admin_users.js is loaded.');
                    }
                }, 100);
            } else {
                // If already initialized, just refresh the data
                window.adminUsersManager.loadUsersData();
            }
            
        } catch (error) {
            console.error('❌ Error loading users section:', error);
            
            // Hide loading indicator
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            
            // Show error message
            usersSection.innerHTML = `
                <div class="section-error">
                    <div class="error-icon">
                        <i class="fas fa-exclamation-triangle"></i>
                    </div>
                    <h3>Failed to Load User Management</h3>
                    <p>Error: ${error.message}</p>
                    <button class="btn-primary" onclick="this.loadUsersSection()">
                        <i class="fas fa-retry"></i>
                        Try Again
                    </button>
                </div>
            `;
        }
    }


    setupRoleOptions() {
        const roleSelects = [
            document.getElementById('userRole'),
            document.getElementById('editUserRole')
        ];

        roleSelects.forEach(select => {
            if (!select) return;

            select.innerHTML = '';

            if (this.currentUserRole === 'super_admin') {
                // Super admin can create all types of users
                select.innerHTML = `
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="super_admin">Super Admin</option>
                `;
            } else if (this.currentUserRole === 'admin') {
                // Admin can only create regular users
                select.innerHTML = `
                    <option value="user">User</option>
                `;
            }
        });
    }

    async loadUsersData() {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/admin/users');
            const data = await response.json();
            
            if (data.success) {
                this.allUsers = data.users || [];
                this.updateStatsCards(data.stats || {});
                this.filterAndDisplayUsers();
            } else {
                this.showError('Failed to load users: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error loading users:', error);
            this.showError('Failed to load users. Please try again.');
        } finally {
            this.showLoading(false);
        }
    }

    updateStatsCards(stats) {
        const elements = {
            totalUsersCount: document.getElementById('totalUsersCount'),
            activeUsersCount: document.getElementById('activeUsersCount'),
            adminUsersCount: document.getElementById('adminUsersCount'),
            newUsersCount: document.getElementById('newUsersCount')
        };

        Object.entries(elements).forEach(([key, element]) => {
            if (element) {
                const statKey = key.replace('Count', '').replace(/([A-Z])/g, '_$1').toLowerCase();
                element.textContent = stats[statKey] || 0;
            }
        });
    }

    filterAndDisplayUsers() {
        this.filteredUsers = this.allUsers.filter(user => {
            const matchesSearch = !this.searchTerm || 
                user.full_name?.toLowerCase().includes(this.searchTerm) ||
                user.username?.toLowerCase().includes(this.searchTerm) ||
                user.email?.toLowerCase().includes(this.searchTerm) ||
                user.department?.toLowerCase().includes(this.searchTerm);

            const matchesRole = this.roleFilter === 'all' || user.role === this.roleFilter;
            const matchesStatus = this.statusFilter === 'all' || user.status === this.statusFilter;

            return matchesSearch && matchesRole && matchesStatus;
        });

        this.totalUsers = this.filteredUsers.length;
        this.currentPage = 1; // Reset to first page
        this.displayUsers();
        this.updatePagination();
        this.updateTableSubtitle();
    }

    displayUsers() {
        const tbody = document.getElementById('usersTableBody');
        const emptyState = document.getElementById('usersTableEmpty');
        
        if (!tbody) return;

        if (this.filteredUsers.length === 0) {
            tbody.innerHTML = '';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';

        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        const pageUsers = this.filteredUsers.slice(startIndex, endIndex);

        tbody.innerHTML = pageUsers.map(user => this.createUserRow(user)).join('');
    }

    createUserRow(user) {
        const canEdit = this.canEditUser(user);
        const canDelete = this.canDeleteUser(user);

        return `
            <tr>
                <td>
                    <div class="user-info">
                        <div class="user-avatar" style="background: ${this.generateAvatarColor(user.username)}">
                            ${this.getUserInitials(user.full_name || user.username)}
                        </div>
                        <div class="user-details">
                            <div class="user-name">${this.escapeHtml(user.full_name || user.username)}</div>
                            <div class="user-email">${this.escapeHtml(user.email || user.username)}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="role-badge ${user.role}">${this.formatRole(user.role)}</span>
                </td>
                <td>${this.escapeHtml(user.department || '-')}</td>
                <td>
                    <span class="status-badge ${user.status}">
                        <i class="fas fa-circle"></i>
                        ${this.formatStatus(user.status)}
                    </span>
                </td>
                <td>${this.formatDate(user.last_login)}</td>
                <td>${this.formatDate(user.created_at)}</td>
                <td>
                    <div class="action-buttons">
                        ${canEdit ? `
                            <button class="action-btn edit" onclick="adminUsersManager.editUser(${user.id})" title="Edit User">
                                <i class="fas fa-edit"></i>
                            </button>
                        ` : ''}
                        ${canDelete ? `
                            <button class="action-btn delete" onclick="adminUsersManager.deleteUser(${user.id}, '${this.escapeHtml(user.full_name || user.username)}')" title="Delete User">
                                <i class="fas fa-trash"></i>
                            </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    }

    canEditUser(user) {
        if (this.currentUserRole === 'super_admin') {
            return true; // Super admin can edit anyone
        }
        if (this.currentUserRole === 'admin') {
            return user.role === 'user'; // Admin can only edit regular users
        }
        return false;
    }

    canDeleteUser(user) {
        if (this.currentUserRole === 'super_admin') {
            return true; // Super admin can delete anyone
        }
        if (this.currentUserRole === 'admin') {
            return user.role === 'user'; // Admin can only delete regular users
        }
        return false;
    }

    updatePagination() {
        const totalPages = Math.ceil(this.totalUsers / this.itemsPerPage);
        
        // Update pagination info
        const startItem = this.totalUsers === 0 ? 0 : (this.currentPage - 1) * this.itemsPerPage + 1;
        const endItem = Math.min(this.currentPage * this.itemsPerPage, this.totalUsers);
        
        const paginationStart = document.getElementById('paginationStart');
        const paginationEnd = document.getElementById('paginationEnd');
        const paginationTotal = document.getElementById('paginationTotal');
        
        if (paginationStart) paginationStart.textContent = startItem;
        if (paginationEnd) paginationEnd.textContent = endItem;
        if (paginationTotal) paginationTotal.textContent = this.totalUsers;

        // Update pagination buttons
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');
        
        if (prevBtn) prevBtn.disabled = this.currentPage === 1;
        if (nextBtn) nextBtn.disabled = this.currentPage === totalPages || totalPages === 0;

        // Update page numbers
        this.updatePageNumbers(totalPages);
    }

    updatePageNumbers(totalPages) {
        const numbersContainer = document.getElementById('paginationNumbers');
        if (!numbersContainer) return;

        numbersContainer.innerHTML = '';

        if (totalPages <= 1) return;

        const maxVisible = 5;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);

        if (endPage - startPage + 1 < maxVisible) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }

        for (let i = startPage; i <= endPage; i++) {
            const pageBtn = document.createElement('button');
            pageBtn.className = `page-number ${i === this.currentPage ? 'active' : ''}`;
            pageBtn.textContent = i;
            pageBtn.onclick = () => this.goToPage(i);
            numbersContainer.appendChild(pageBtn);
        }
    }

    updateTableSubtitle() {
        const subtitle = document.getElementById('usersTableSubtitle');
        if (!subtitle) return;

        let text = `Showing ${this.totalUsers} user${this.totalUsers !== 1 ? 's' : ''}`;
        
        if (this.searchTerm || this.roleFilter !== 'all' || this.statusFilter !== 'all') {
            text += ' (filtered)';
        }

        subtitle.textContent = text;
    }

    // Pagination methods
    changePage(direction) {
        const totalPages = Math.ceil(this.totalUsers / this.itemsPerPage);
        const newPage = this.currentPage + direction;
        
        if (newPage >= 1 && newPage <= totalPages) {
            this.goToPage(newPage);
        }
    }

    goToPage(page) {
        this.currentPage = page;
        this.displayUsers();
        this.updatePagination();
    }

    // Modal management
    openAddUserModal() {
        const modal = document.getElementById('addUserModal');
        if (modal) {
            modal.classList.add('active');
            this.resetForm('addUserForm');
        }
    }

    closeAddUserModal() {
        const modal = document.getElementById('addUserModal');
        if (modal) {
            modal.classList.remove('active');
        }
    }

    openEditUserModal() {
        const modal = document.getElementById('editUserModal');
        if (modal) {
            modal.classList.add('active');
        }
    }

    closeEditUserModal() {
        const modal = document.getElementById('editUserModal');
        if (modal) {
            modal.classList.remove('active');
        }
    }

    openDeleteUserModal() {
        const modal = document.getElementById('deleteUserModal');
        if (modal) {
            modal.classList.add('active');
        }
    }

    closeDeleteUserModal() {
        const modal = document.getElementById('deleteUserModal');
        if (modal) {
            modal.classList.remove('active');
        }
    }

    closeAllModals() {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.classList.remove('active');
        });
    }

    // User CRUD operations
    async handleAddUser(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const userData = Object.fromEntries(formData.entries());
        
        try {
            const response = await fetch('/api/admin/users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess('User created successfully');
                this.closeAddUserModal();
                await this.loadUsersData();
            } else {
                this.showError(data.error || 'Failed to create user');
            }
        } catch (error) {
            console.error('Error creating user:', error);
            this.showError('Failed to create user. Please try again.');
        }
    }

    async editUser(userId) {
        try {
            const response = await fetch(`/api/admin/users/${userId}`);
            const data = await response.json();
            
            if (data.success) {
                this.populateEditForm(data.user);
                this.openEditUserModal();
            } else {
                this.showError(data.error || 'Failed to load user data');
            }
        } catch (error) {
            console.error('Error loading user:', error);
            this.showError('Failed to load user data. Please try again.');
        }
    }

    populateEditForm(user) {
        const fields = {
            editUserId: user.id,
            editUserFullName: user.full_name,
            editUserUsername: user.username,
            editUserEmail: user.email,
            editUserPhone: user.phone,
            editUserDepartment: user.department,
            editUserRole: user.role,
            editUserStatus: user.status
        };

        Object.entries(fields).forEach(([fieldId, value]) => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.value = value || '';
            }
        });
    }

    async handleEditUser(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const userData = Object.fromEntries(formData.entries());
        const userId = userData.user_id;
        
        try {
            const response = await fetch(`/api/admin/users/${userId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess('User updated successfully');
                this.closeEditUserModal();
                await this.loadUsersData();
            } else {
                this.showError(data.error || 'Failed to update user');
            }
        } catch (error) {
            console.error('Error updating user:', error);
            this.showError('Failed to update user. Please try again.');
        }
    }

    deleteUser(userId, userName) {
        this.currentDeleteUserId = userId;
        const nameElement = document.getElementById('deleteUserName');
        if (nameElement) {
            nameElement.textContent = userName;
        }
        this.openDeleteUserModal();
    }

    async confirmDeleteUser() {
        if (!this.currentDeleteUserId) return;
        
        try {
            const response = await fetch(`/api/admin/users/${this.currentDeleteUserId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showSuccess('User deleted successfully');
                this.closeDeleteUserModal();
                await this.loadUsersData();
            } else {
                this.showError(data.error || 'Failed to delete user');
            }
        } catch (error) {
            console.error('Error deleting user:', error);
            this.showError('Failed to delete user. Please try again.');
        }
    }

    // Utility methods
    resetForm(formId) {
        const form = document.getElementById(formId);
        if (form) {
            form.reset();
        }
    }

    generateTempPassword() {
        const length = 12;
        const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
        let password = '';
        
        for (let i = 0; i < length; i++) {
            password += charset.charAt(Math.floor(Math.random() * charset.length));
        }
        
        const field = document.getElementById('tempPassword');
        if (field) {
            field.value = password;
        }
    }

    generateResetPassword() {
        const length = 12;
        const charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*';
        let password = '';
        
        for (let i = 0; i < length; i++) {
            password += charset.charAt(Math.floor(Math.random() * charset.length));
        }
        
        const field = document.getElementById('resetPassword');
        if (field) {
            field.value = password;
        }
    }

    togglePasswordVisibility(fieldId) {
        const field = document.getElementById(fieldId);
        const button = field?.nextElementSibling;
        const icon = button?.querySelector('i');
        
        if (field && icon) {
            if (field.type === 'password') {
                field.type = 'text';
                icon.className = 'fas fa-eye-slash';
            } else {
                field.type = 'password';
                icon.className = 'fas fa-eye';
            }
        }
    }

    generateAvatarColor(username) {
        const colors = [
            'linear-gradient(135deg, #667eea, #764ba2)',
            'linear-gradient(135deg, #f093fb, #f5576c)',
            'linear-gradient(135deg, #4facfe, #00f2fe)',
            'linear-gradient(135deg, #43e97b, #38f9d7)',
            'linear-gradient(135deg, #fa709a, #fee140)',
            'linear-gradient(135deg, #a8edea, #fed6e3)',
            'linear-gradient(135deg, #ff9a9e, #fecfef)',
            'linear-gradient(135deg, #a18cd1, #fbc2eb)'
        ];
        
        const index = username.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
        return colors[index % colors.length];
    }

    getUserInitials(name) {
        if (!name) return '?';
        
        const words = name.trim().split(' ');
        if (words.length >= 2) {
            return (words[0][0] + words[1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }

    formatRole(role) {
        const roles = {
            'super_admin': 'Super Admin',
            'admin': 'Admin',
            'user': 'User'
        };
        return roles[role] || role;
    }

    formatStatus(status) {
        const statuses = {
            'active': 'Active',
            'inactive': 'Inactive'
        };
        return statuses[status] || status;
    }

    formatDate(dateString) {
        if (!dateString) return 'Never';
        
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (error) {
            return 'Invalid Date';
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

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

    showLoading(show) {
        const loading = document.getElementById('usersTableLoading');
        const table = document.querySelector('.users-table-container');
        
        if (loading) loading.style.display = show ? 'block' : 'none';
        if (table) table.style.display = show ? 'none' : 'block';
    }

    showSuccess(message) {
        // You can integrate with your existing notification system
        console.log('✅ Success:', message);
        // Example: showNotification(message, 'success');
    }

    showError(message) {
        // You can integrate with your existing notification system
        console.error('❌ Error:', message);
        // Example: showNotification(message, 'error');
    }

    // Refresh functionality
    async refreshUsers() {
        await this.loadUsersData();
        this.showSuccess('Users data refreshed');
    }
}

// Global functions for HTML onclick handlers
function openAddUserModal() {
    window.adminUsersManager.openAddUserModal();
}

function closeAddUserModal() {
    window.adminUsersManager.closeAddUserModal();
}

function closeEditUserModal() {
    window.adminUsersManager.closeEditUserModal();
}

function closeDeleteUserModal() {
    window.adminUsersManager.closeDeleteUserModal();
}

function generateTempPassword() {
    window.adminUsersManager.generateTempPassword();
}

function generateResetPassword() {
    window.adminUsersManager.generateResetPassword();
}

function togglePasswordVisibility(fieldId) {
    window.adminUsersManager.togglePasswordVisibility(fieldId);
}

function refreshUsers() {
    window.adminUsersManager.refreshUsers();
}

function changePage(direction) {
    window.adminUsersManager.changePage(direction);
}

function confirmDeleteUser() {
    window.adminUsersManager.confirmDeleteUser();
}

// Initialize the admin users manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.adminUsersManager = new AdminUsersManager();
});

// Export for module usage if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminUsersManager;
}