// Dashboard State
let authKey = '';
let stats = {};
let tickets = [];
let config = {};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
});

// Check if already authenticated
function checkAuth() {
    const savedKey = sessionStorage.getItem('dashboardKey');
    if (savedKey) {
        authKey = savedKey;
        document.getElementById('auth-key').value = savedKey;
        authenticate();
    }
}

// Setup event listeners
function setupEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const section = link.getAttribute('href').substring(1);
            navigateTo(section);
        });
    });
    
    // Auth input
    document.getElementById('auth-key').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') authenticate();
    });
}

// Navigate to section
function navigateTo(section) {
    // Update active state
    document.querySelectorAll('.nav-links li').forEach(li => {
        li.classList.remove('active');
    });
    event.target.closest('li').classList.add('active');
    
    // Load section content
    loadSection(section);
}

// Load section content
function loadSection(section) {
    const content = document.querySelector('.content');
    
    switch(section) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'tickets':
            loadTicketsPage();
            break;
        case 'settings':
            loadSettings();
            break;
        case 'blacklist':
            loadBlacklist();
            break;
        case 'logs':
            loadLogs();
            break;
    }
}

// Authenticate with dashboard
async function authenticate() {
    const key = document.getElementById('auth-key').value;
    
    if (!key) {
        showError('Please enter dashboard key');
        return;
    }
    
    try {
        const response = await fetch('/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key })
        });
        
        const data = await response.json();
        
        if (data.success) {
            authKey = key;
            sessionStorage.setItem('dashboardKey', key);
            document.querySelector('.auth-section').style.display = 'none';
            loadDashboard();
            startAutoRefresh();
        } else {
            showError('Invalid dashboard key');
        }
    } catch (error) {
        showError('Failed to authenticate');
    }
}

// Start auto refresh
function startAutoRefresh() {
    setInterval(() => {
        if (document.querySelector('.nav-links li.active a').getAttribute('href') === '#dashboard') {
            loadStats();
            loadRecentTickets();
        }
    }, 30000);
}

// Load main dashboard
async function loadDashboard() {
    const content = document.querySelector('.content');
    content.innerHTML = `
        <div class="header">
            <h1>Dashboard Overview</h1>
            <div class="date">${new Date().toLocaleDateString()}</div>
        </div>
        
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <div class="stat-icon">🎫</div>
                <div class="stat-info">
                    <h3 id="total-tickets">0</h3>
                    <p>Total Tickets</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📂</div>
                <div class="stat-info">
                    <h3 id="open-tickets">0</h3>
                    <p>Open Tickets</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-info">
                    <h3 id="closed-tickets">0</h3>
                    <p>Closed Tickets</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-info">
                    <h3 id="total-users">0</h3>
                    <p>Total Users</p>
                </div>
            </div>
        </div>
        
        <div class="recent-tickets">
            <h2><i>🕒</i> Recent Tickets</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Ticket ID</th>
                            <th>User</th>
                            <th>Category</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="recent-tickets-body">
                        <tr><td colspan="6" class="loading">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    await loadStats();
    await loadRecentTickets();
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats', {
            headers: { 'X-Dashboard-Key': authKey }
        });
        stats = await response.json();
        
        document.getElementById('total-tickets').textContent = stats.total_tickets || 0;
        document.getElementById('open-tickets').textContent = stats.open_tickets || 0;
        document.getElementById('closed-tickets').textContent = stats.closed_tickets || 0;
        document.getElementById('total-users').textContent = stats.total_users || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load recent tickets
async function loadRecentTickets() {
    try {
        const response = await fetch('/api/tickets?limit=10', {
            headers: { 'X-Dashboard-Key': authKey }
        });
        const tickets = await response.json();
        
        const tbody = document.getElementById('recent-tickets-body');
        if (!tbody) return;
        
        if (tickets.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No tickets found</td></tr>';
            return;
        }
        
        tbody.innerHTML = tickets.map(ticket => `
            <tr>
                <td><code>${ticket.ticket_id}</code></td>
                <td><span title="User ID: ${ticket.user_id}">${ticket.user_id.slice(0, 8)}...</span></td>
                <td>${ticket.category}</td>
                <td><span class="status-badge status-${ticket.status}">${ticket.status}</span></td>
                <td>${new Date(ticket.created_at).toLocaleString()}</td>
                <td>
                    <button class="action-btn view-btn" onclick="viewTicket('${ticket.ticket_id}')">View</button>
                    ${ticket.status === 'open' ? 
                        `<button class="action-btn close-btn" onclick="closeTicket('${ticket.ticket_id}')">Close</button>` : 
                        ''}
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading tickets:', error);
    }
}

// Load tickets page
async function loadTicketsPage() {
    const content = document.querySelector('.content');
    content.innerHTML = `
        <div class="header">
            <h1>All Tickets</h1>
            <div class="filters">
                <select id="ticket-filter" onchange="filterTickets()">
                    <option value="all">All Tickets</option>
                    <option value="open">Open Tickets</option>
                    <option value="closed">Closed Tickets</option>
                </select>
            </div>
        </div>
        
        <div class="recent-tickets">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Ticket ID</th>
                            <th>User</th>
                            <th>Category</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Closed</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="all-tickets-body">
                        <tr><td colspan="7" class="loading">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    await loadAllTickets();
}

// Load all tickets
async function loadAllTickets(filter = 'all') {
    try {
        const response = await fetch(`/api/tickets?status=${filter}&limit=100`, {
            headers: { 'X-Dashboard-Key': authKey }
        });
        const tickets = await response.json();
        
        const tbody = document.getElementById('all-tickets-body');
        if (!tbody) return;
        
        if (tickets.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No tickets found</td></tr>';
            return;
        }
        
        tbody.innerHTML = tickets.map(ticket => `
            <tr>
                <td><code>${ticket.ticket_id}</code></td>
                <td><span title="User ID: ${ticket.user_id}">${ticket.user_id.slice(0, 8)}...</span></td>
                <td>${ticket.category}</td>
                <td><span class="status-badge status-${ticket.status}">${ticket.status}</span></td>
                <td>${new Date(ticket.created_at).toLocaleString()}</td>
                <td>${ticket.closed_at ? new Date(ticket.closed_at).toLocaleString() : '-'}</td>
                <td>
                    <button class="action-btn view-btn" onclick="viewTicket('${ticket.ticket_id}')">View</button>
                    ${ticket.status === 'open' ? 
                        `<button class="action-btn close-btn" onclick="closeTicket('${ticket.ticket_id}')">Close</button>` : 
                        ''}
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading tickets:', error);
    }
}

// Filter tickets
function filterTickets() {
    const filter = document.getElementById('ticket-filter').value;
    loadAllTickets(filter);
}

// View ticket details
async function viewTicket(ticketId) {
    try {
        const response = await fetch(`/api/tickets/${ticketId}`, {
            headers: { 'X-Dashboard-Key': authKey }
        });
        const ticket = await response.json();
        
        // Show modal with ticket details
        showTicketModal(ticket);
    } catch (error) {
        console.error('Error viewing ticket:', error);
        showError('Failed to load ticket details');
    }
}

// Close ticket
async function closeTicket(ticketId) {
    if (!confirm('Are you sure you want to close this ticket?')) return;
    
    try {
        const response = await fetch(`/api/tickets/${ticketId}/close`, {
            method: 'POST',
            headers: { 'X-Dashboard-Key': authKey }
        });
        
        if (response.ok) {
            showSuccess('Ticket closed successfully');
            loadRecentTickets();
            if (document.getElementById('all-tickets-body')) {
                filterTickets();
            }
        }
    } catch (error) {
        console.error('Error closing ticket:', error);
        showError('Failed to close ticket');
    }
}

// Show ticket modal
function showTicketModal(ticket) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Ticket ${ticket.ticket_id}</h2>
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            </div>
            <div class="modal-body">
                <p><strong>User:</strong> ${ticket.user_id}</p>
                <p><strong>Category:</strong> ${ticket.category}</p>
                <p><strong>Status:</strong> <span class="status-badge status-${ticket.status}">${ticket.status}</span></p>
                <p><strong>Created:</strong> ${new Date(ticket.created_at).toLocaleString()}</p>
                ${ticket.closed_at ? `<p><strong>Closed:</strong> ${new Date(ticket.closed_at).toLocaleString()}</p>` : ''}
                ${ticket.claimed_by ? `<p><strong>Claimed by:</strong> ${ticket.claimed_by}</p>` : ''}
                
                <h3>Messages</h3>
                <div class="messages">
                    ${ticket.messages ? ticket.messages.map(msg => `
                        <div class="message">
                            <strong>${msg.user_id}:</strong>
                            <p>${msg.content}</p>
                            <small>${new Date(msg.timestamp).toLocaleString()}</small>
                        </div>
                    `).join('') : '<p>No messages</p>'}
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// Load settings
async function loadSettings() {
    try {
        const response = await fetch('/api/config', {
            headers: { 'X-Dashboard-Key': authKey }
        });
        config = await response.json();
        
        const content = document.querySelector('.content');
        content.innerHTML = `
            <div class="header">
                <h1>Settings</h1>
            </div>
            
            <div class="config-section">
                <h2><i>⚙️</i> Bot Configuration</h2>
                <div class="config-grid">
                    <div class="config-item">
                        <label>Max Tickets Per User</label>
                        <input type="number" id="max-tickets" value="${config.max_tickets_per_user || 1}" min="1" max="10">
                    </div>
                    
                    <div class="config-item">
                        <label>Support Role ID</label>
                        <input type="text" id="support-role" value="${config.support_role || ''}">
                    </div>
                    
                    <div class="config-item">
                        <label>Admin Role ID</label>
                        <input type="text" id="admin-role" value="${config.admin_role || ''}">
                    </div>
                    
                    <div class="config-item">
                        <label>Log Channel ID</label>
                        <input type="text" id="log-channel" value="${config.log_channel || ''}">
                    </div>
                </div>
                
                <h2 style="margin-top: 30px;"><i>📋</i> Ticket Categories</h2>
                <div id="categories-container"></div>
                
                <button class="save-btn" onclick="saveConfig()">Save Changes</button>
            </div>
        `;
        
        // Load categories
        loadCategories();
    } catch (error) {
        console.error('Error loading settings:', error);
        showError('Failed to load settings');
    }
}

// Load categories
function loadCategories() {
    const container = document.getElementById('categories-container');
    if (!container) return;
    
    container.innerHTML = config.ticket_types.map((cat, index) => `
        <div class="config-item category-item" data-index="${index}">
            <h4>Category ${index + 1}</h4>
            <label>Label</label>
            <input type="text" class="cat-label" value="${cat.label}" placeholder="Category Name">
            
            <label>Emoji</label>
            <input type="text" class="cat-emoji" value="${cat.emoji}" placeholder="Emoji">
            
            <label>Description</label>
            <textarea class="cat-desc" placeholder="Category Description">${cat.description}</textarea>
            
            <button class="action-btn" onclick="removeCategory(${index})" style="background: var(--danger); margin-top: 10px;">Remove</button>
        </div>
    `).join('');
    
    // Add button
    container.innerHTML += `
        <button class="action-btn" onclick="addCategory()" style="background: var(--success);">Add Category</button>
    `;
}

// Add new category
function addCategory() {
    config.ticket_types.push({
        label: 'New Category',
        value: 'new_category',
        description: 'Description here',
        emoji: '❓',
        color: 0x00FF00
    });
    loadCategories();
}

// Remove category
function removeCategory(index) {
    config.ticket_types.splice(index, 1);
    loadCategories();
}

// Save configuration
async function saveConfig() {
    // Get values from inputs
    const updatedConfig = {
        max_tickets_per_user: parseInt(document.getElementById('max-tickets').value),
        support_role: document.getElementById('support-role').value,
        admin_role: document.getElementById('admin-role').value,
        log_channel: document.getElementById('log-channel').value,
        ticket_types: []
    };
    
    // Get categories
    document.querySelectorAll('.category-item').forEach(item => {
        const index = item.dataset.index;
        updatedConfig.ticket_types.push({
            label: item.querySelector('.cat-label').value,
            value: item.querySelector('.cat-label').value.toLowerCase().replace(/ /g, '_'),
            description: item.querySelector('.cat-desc').value,
            emoji: item.querySelector('.cat-emoji').value,
            color: 0x00FF00
        });
    });
    
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Dashboard-Key': authKey
            },
            body: JSON.stringify(updatedConfig)
        });
        
        if (response.ok) {
            showSuccess('Configuration saved successfully');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showError('Failed to save configuration');
    }
}

// Load blacklist
async function loadBlacklist() {
    try {
        const response = await fetch('/api/blacklist', {
            headers: { 'X-Dashboard-Key': authKey }
        });
        const blacklist = await response.json();
        
        const content = document.querySelector('.content');
        content.innerHTML = `
            <div class="header">
                <h1>Blacklist Management</h1>
                <button class="action-btn" onclick="showAddBlacklist()" style="background: var(--success);">Add User</button>
            </div>
            
            <div class="recent-tickets">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>User ID</th>
                                <th>Reason</th>
                                <th>Blacklisted By</th>
                                <th>Date</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="blacklist-body">
                            ${blacklist.map(entry => `
                                <tr>
                                    <td>${entry.user_id}</td>
                                    <td>${entry.reason}</td>
                                    <td>${entry.blacklisted_by}</td>
                                    <td>${new Date(entry.blacklisted_at).toLocaleString()}</td>
                                    <td>
                                        <button class="action-btn" onclick="unblacklist('${entry.user_id}')" style="background: var(--danger);">Remove</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading blacklist:', error);
        showError('Failed to load blacklist');
    }
}

// Show add blacklist modal
function showAddBlacklist() {
    const userId = prompt('Enter User ID to blacklist:');
    if (!userId) return;
    
    const reason = prompt('Enter reason for blacklisting:');
    if (!reason) return;
    
    addToBlacklist(userId, reason);
}

// Add to blacklist
async function addToBlacklist(userId, reason) {
    try {
        const response = await fetch('/api/blacklist/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Dashboard-Key': authKey
            },
            body: JSON.stringify({ user_id: userId, reason })
        });
        
        if (response.ok) {
            showSuccess('User added to blacklist');
            loadBlacklist();
        }
    } catch (error) {
        console.error('Error adding to blacklist:', error);
        showError('Failed to add user to blacklist');
    }
}

// Remove from blacklist
async function unblacklist(userId) {
    if (!confirm('Are you sure you want to remove this user from blacklist?')) return;
    
    try {
        const response = await fetch('/api/blacklist/remove', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Dashboard-Key': authKey
            },
            body: JSON.stringify({ user_id: userId })
        });
        
        if (response.ok) {
            showSuccess('User removed from blacklist');
            loadBlacklist();
        }
    } catch (error) {
        console.error('Error removing from blacklist:', error);
        showError('Failed to remove user from blacklist');
    }
}

// Load logs
async function loadLogs() {
    const content = document.querySelector('.content');
    content.innerHTML = `
        <div class="header">
            <h1>System Logs</h1>
        </div>
        
        <div class="recent-tickets">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Level</th>
                            <th>Message</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="3">Coming soon...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

// Show error message
function showError(message) {
    const toast = createToast(message, 'error');
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// Show success message
function showSuccess(message) {
    const toast = createToast(message, 'success');
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Create toast notification
function createToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'error' ? 'var(--danger)' : 'var(--success)'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    return toast;
}
