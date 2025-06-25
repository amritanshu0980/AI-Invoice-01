document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = 'http://localhost:5000';
    let revenueChartInstance = null;
    let productsChartInstance = null;

    // Utility function for API calls with retries
    async function fetchWithRetry(url, options, retries = 3, delay = 1000) {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(url, options);
                if (response.status === 401 || response.status === 403) {
                    window.location.href = `${API_BASE_URL}/api/login`;
                    throw new Error('Unauthorized - redirecting to login.');
                }
                if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
                return await response.json();
            } catch (error) {
                if (i === retries - 1) throw error;
                await new Promise(res => setTimeout(res, delay));
            }
        }
    }

    // Show loading spinner
    function showSpinner() {
        document.getElementById('loadingSpinner').classList.remove('hidden');
    }

    // Hide loading spinner
    function hideSpinner() {
        document.getElementById('loadingSpinner').classList.add('hidden');
    }

    // Load dashboard data (metrics, charts, invoices)
    function loadDashboardData() {
        showSpinner();
        fetchWithRetry(`${API_BASE_URL}/api/admin_dashboard_data`, {
            headers: { 'Session-ID': 'default' },
            credentials: 'include'
        })
        .then(data => {
            // Update metrics
            document.getElementById('total-invoices').textContent = data.totalInvoices;
            document.getElementById('total-revenue').textContent = `₹${data.totalRevenue.toLocaleString('en-IN')}`;
            document.getElementById('active-users').textContent = data.activeUsers;
            document.getElementById('products-sold').textContent = data.productsSold;

            // Update invoices table
            const invoicesTable = document.getElementById('invoices-table');
            invoicesTable.innerHTML = data.recentInvoices.map(invoice => `
                <tr class="hover:bg-gray-50 transition-colors duration-200">
                    <td class="px-4 py-3">${invoice.id}</td>
                    <td class="px-4 py-3">${invoice.client}</td>
                    <td class="px-4 py-3">₹${invoice.amount.toLocaleString('en-IN')}</td>
                    <td class="px-4 py-3">${invoice.date}</td>
                </tr>
            `).join('');

            // Destroy existing charts
            if (revenueChartInstance) revenueChartInstance.destroy();
            if (productsChartInstance) productsChartInstance.destroy();

            // Render revenue chart
            const revenueCtx = document.getElementById('revenueChart').getContext('2d');
            revenueChartInstance = new Chart(revenueCtx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Revenue (₹)',
                        data: data.revenueData,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true }
                    },
                    plugins: {
                        legend: {
                            labels: {
                                font: {
                                    size: 14,
                                    family: "'Poppins', sans-serif"
                                }
                            }
                        }
                    }
                }
            });

            // Render products chart
            const productsCtx = document.getElementById('productsChart').getContext('2d');
            productsChartInstance = new Chart(productsCtx, {
                type: 'bar',
                data: {
                    labels: data.productData.map(p => p.name),
                    datasets: [{
                        label: 'Units Sold',
                        data: data.productData.map(p => p.sold),
                        backgroundColor: ['#3b82f6', '#ef4444', '#22c55e', '#facc15', '#a855f7']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true }
                    },
                    plugins: {
                        legend: {
                            labels: {
                                font: {
                                    size: 14,
                                    family: "'Poppins', sans-serif"
                                }
                            }
                        }
                    }
                }
            });

            hideSpinner();
        })
        .catch(error => {
            console.error('Error fetching dashboard data:', error);
            document.getElementById('invoices-table').innerHTML = `<tr><td colspan="4" class="px-4 py-3 text-center text-red-600">Error loading dashboard data: ${error.message}</td></tr>`;
            hideSpinner();
        });
    }

    // Load products table
    function loadProducts() {
        showSpinner();
        fetchWithRetry(`${API_BASE_URL}/api/get_products`, {
            headers: { 'Session-ID': 'default' },
            credentials: 'include'
        })
        .then(data => {
            const productsTable = document.getElementById('products-table');
            if (data.products.length === 0) {
                productsTable.innerHTML = `<tr><td colspan="8" class="px-4 py-3 text-center text-gray-600">No products available</td></tr>`;
                hideSpinner();
                return;
            }
            productsTable.innerHTML = data.products.map(product => `
                <tr class="hover:bg-gray-50 transition-colors duration-200">
                    <td class="px-4 py-3">${product.name}</td>
                    <td class="px-4 py-3">₹${(product.price || 0).toLocaleString('en-IN')}</td>
                    <td class="px-4 py-3">${product.stock || 0}</td>
                    <td class="px-4 py-3">₹${(product['Installation Charge'] || 0).toLocaleString('en-IN')}</td>
                    <td class="px-4 py-3">₹${(product['Service Charge'] || 0).toLocaleString('en-IN')}</td>
                    <td class="px-4 py-3">₹${(product['Shipping Charge'] || 0).toLocaleString('en-IN')}</td>
                    <td class="px-4 py-3">₹${(product['Handling Fee'] || 0).toLocaleString('en-IN')}</td>
                    <td class="px-4 py-3 space-x-2">
                        <button class="edit-product bg-yellow-500 text-white px-3 py-1 rounded-lg hover:bg-yellow-600 transform hover:scale-105 transition-all duration-300"
                                data-product='${JSON.stringify(product)}'>Edit</button>
                        <button class="delete-product bg-red-500 text-white px-3 py-1 rounded-lg hover:bg-red-600 transform hover:scale-105 transition-all duration-300"
                                data-product-name='${product.name}'>Delete</button>
                    </td>
                </tr>
            `).join('');
            // Attach edit button event listeners
            document.querySelectorAll('.edit-product').forEach(button => {
                button.addEventListener('click', () => {
                    const product = JSON.parse(button.dataset.product);
                    openEditModal(product);
                });
            });
            // Attach delete button event listeners
            document.querySelectorAll('.delete-product').forEach(button => {
                button.addEventListener('click', () => {
                    const productName = button.dataset.productName;
                    deleteProduct(productName);
                });
            });
            hideSpinner();
        })
        .catch(error => {
            console.error('Error fetching products:', error);
            document.getElementById('products-table').innerHTML = `<tr><td colspan="8" class="px-4 py-3 text-center text-red-600">Error loading products: ${error.message}</td></tr>`;
            hideSpinner();
        });
    }

    // Delete product
    async function deleteProduct(productName) {
        if (!confirm(`Are you sure you want to delete the product "${productName}"?`)) {
            return;
        }
        showSpinner();
        try {
            const response = await fetchWithRetry(`${API_BASE_URL}/api/delete_product`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': 'default'
                },
                body: JSON.stringify({ name: productName }),
                credentials: 'include'
            });
            if (response.success) {
                alert(response.message);
                loadProducts();
            } else {
                alert(`Error: ${response.error}`);
                hideSpinner();
            }
        } catch (error) {
            console.error('Error deleting product:', error);
            alert(`Error deleting product: ${error.message}`);
            hideSpinner();
        }
    }

    // Load clients table
    function loadClients() {
        showSpinner();
        fetchWithRetry(`${API_BASE_URL}/api/client/get`, {
            headers: { 'Session-ID': 'default' },
            credentials: 'include'
        })
        .then(data => {
            const clientsTable = document.getElementById('clients-table');
            const client = data.client;
            if (!client || !client.name) {
                clientsTable.innerHTML = `<tr><td colspan="5" class="px-4 py-3 text-center text-gray-600">No client data available</td></tr>`;
                hideSpinner();
                return;
            }
            clientsTable.innerHTML = `
                <tr class="hover:bg-gray-50 transition-colors duration-200">
                    <td class="px-4 py-3">${client.name}</td>
                    <td class="px-4 py-3">${client.address || 'N/A'}</td>
                    <td class="px-4 py-3">${client.gst_number || 'N/A'}</td>
                    <td class="px-4 py-3">${client.phone || 'N/A'}</td>
                    <td class="px-4 py-3">${client.email || 'N/A'}</td>
                </tr>
            `;
            hideSpinner();
        })
        .catch(error => {
            console.error('Error fetching clients:', error);
            document.getElementById('clients-table').innerHTML = `<tr><td colspan="5" class="px-4 py-3 text-center text-red-600">Error loading clients: ${error.message}</td></tr>`;
            hideSpinner();
        });
    }

    // Check authentication status
    function checkAuthStatus() {
        showSpinner();
        fetchWithRetry(`${API_BASE_URL}/api/status`, { credentials: 'include' })
        .then(data => {
            if (!data.user_authenticated || data.user_role !== 'admin') {
                window.location.href = `${API_BASE_URL}/api/login`;
            } else {
                loadDashboardData();
            }
        })
        .catch(() => {
            window.location.href = `${API_BASE_URL}/api/login`;
            hideSpinner();
        });
    }

    // Open edit product modal
    function openEditModal(product) {
        const modal = document.getElementById('editProductModal');
        document.getElementById('editProductOriginalName').value = product.name;
        document.getElementById('editProductName').value = product.name;
        document.getElementById('editProductPrice').value = product.price || 0;
        document.getElementById('editProductGst').value = product.gst_rate || 18;
        document.getElementById('editProductStock').value = product.stock || 0;
        document.getElementById('editProductInstallation').value = product['Installation Charge'] || 0;
        document.getElementById('editProductService').value = product['Service Charge'] || 0;
        document.getElementById('editProductShipping').value = product['Shipping Charge'] || 0;
        document.getElementById('editProductHandling').value = product['Handling Fee'] || 0;
        document.getElementById('editProductTaxAmount').value = product.price_tax_amount || 0;
        document.getElementById('editProductDiscountAmount').value = product.price_discount_amount || 0;
        document.getElementById('editProductFinalPrice').value = product.price_final_price || 0;
        modal.classList.remove('hidden');
    }

    // Close edit product modal
    function closeEditModal() {
        const modal = document.getElementById('editProductModal');
        modal.classList.add('hidden');
    }

    // Open add product modal
    function openAddModal() {
        const modal = document.getElementById('addProductModal');
        document.getElementById('addProductForm').reset();
        modal.classList.remove('hidden');
    }

    // Close add product modal
    function closeAddModal() {
        const modal = document.getElementById('addProductModal');
        modal.classList.add('hidden');
    }

    // Handle edit product form submission
    document.getElementById('editProductForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        showSpinner();
        try {
            const response = await fetchWithRetry(`${API_BASE_URL}/api/update_product`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': 'default'
                },
                body: JSON.stringify(data),
                credentials: 'include'
            });
            if (response.success) {
                alert(response.message);
                closeEditModal();
                loadProducts();
            } else {
                alert(`Error: ${response.error}`);
                hideSpinner();
            }
        } catch (error) {
            console.error('Error updating product:', error);
            alert(`Error updating product: ${error.message}`);
            hideSpinner();
        }
    });

    // Handle add product form submission
    document.getElementById('addProductForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        showSpinner();
        try {
            const response = await fetchWithRetry(`${API_BASE_URL}/api/add_product`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-ID': 'default'
                },
                body: JSON.stringify(data),
                credentials: 'include'
            });
            if (response.success) {
                alert(response.message);
                closeAddModal();
                loadProducts();
            } else {
                alert(`Error: ${response.error}`);
                hideSpinner();
            }
        } catch (error) {
            console.error('Error adding product:', error);
            alert(`Error adding product: ${error.message}`);
            hideSpinner();
        }
    });

    // Section navigation
    const dashboardLink = document.querySelector('.sidebar a[href="#"].active');
    const productsLink = document.getElementById('products-link');
    const clientsLink = document.getElementById('clients-link');
    const logoutLink = document.getElementById('logout-link');

    const dashboardSection = document.querySelector('.dashboard-section');
    const productsSection = document.getElementById('products-section');
    const clientsSection = document.getElementById('clients-section');

    function showSection(sectionToShow, sectionsToHide, activeLink) {
        sectionsToHide.forEach(section => {
            section.classList.add('hidden');
        });
        sectionToShow.classList.remove('hidden');
        sectionToShow.classList.add('animate-fade-in');
        document.querySelectorAll('.sidebar a').forEach(link => link.classList.remove('active'));
        activeLink.classList.add('active');
    }

    dashboardLink.addEventListener('click', (e) => {
        e.preventDefault();
        showSection(dashboardSection, [productsSection, clientsSection], dashboardLink);
        loadDashboardData();
    });

    productsLink.addEventListener('click', (e) => {
        e.preventDefault();
        showSection(productsSection, [dashboardSection, clientsSection], productsLink);
        loadProducts();
    });

    clientsLink.addEventListener('click', (e) => {
        e.preventDefault();
        showSection(clientsSection, [dashboardSection, productsSection], clientsLink);
        loadClients();
    });

    logoutLink.addEventListener('click', (e) => {
        e.preventDefault();
        showSpinner();
        fetchWithRetry(`${API_BASE_URL}/api/logout`, {
            method: 'POST',
            credentials: 'include'
        })
        .then(() => window.location.href = `${API_BASE_URL}/api/login`)
        .catch(error => {
            console.error('Error logging out:', error);
            window.location.href = `${API_BASE_URL}/api/login`;
            hideSpinner();
        });
    });

    // Modal close buttons
    document.getElementById('closeEditModalBtn').addEventListener('click', closeEditModal);
    document.getElementById('closeAddModalBtn').addEventListener('click', closeAddModal);

    // Add product button
    document.getElementById('add-product-btn').addEventListener('click', openAddModal);

    // Initial check
    checkAuthStatus();
});