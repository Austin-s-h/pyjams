// Global error handling
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    // You could send this to your error tracking service
});

// Global notification system
class NotificationManager {
    static show(message, type = 'success') {
        const notificationEl = document.getElementById('notification');
        const messageEl = document.getElementById('notification-message');
        
        if (!notificationEl || !messageEl) return;
        
        messageEl.textContent = message;
        notificationEl.className = `notification ${type}`;
        notificationEl.style.display = 'flex';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            notificationEl.style.display = 'none';
        }, 5000);
    }

    static hide() {
        const notificationEl = document.getElementById('notification');
        if (notificationEl) {
            notificationEl.style.display = 'none';
        }
    }
}

// Alert management
class AlertManager {
    static show(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = 'alert';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        
        const container = document.querySelector('.flash-messages');
        if (container) {
            container.appendChild(alertDiv);
            // Auto-remove after 5 seconds
            setTimeout(() => alertDiv.remove(), 5000);
        }
    }
}

// Close button handler for alerts
document.addEventListener('click', function(e) {
    if (e.target.matches('[data-dismiss="alert"], [data-dismiss="alert"] *')) {
        const alert = e.target.closest('.alert');
        if (alert) {
            alert.remove();
        }
    }
});

// Admin Panel Functionality
class AdminPanel {
    constructor() {
        this.filterInput = document.getElementById('playlistFilter');
        this.sortSelect = document.getElementById('sortPlaylists');
        this.tableBody = document.getElementById('playlistTableBody');
        this.playlistCards = document.querySelectorAll('.playlist-card');
        
        this.ITEMS_PER_PAGE = 25;
        this.currentPage = 1;
        this.filteredItems = Array.from(this.playlistCards);

        this.init();
    }

    init() {
        if (!this.tableBody) return; // Only initialize on admin page

        this.addEventListeners();
        this.updatePagination();
        this.displayCurrentPage();
    }

    addEventListeners() {
        // Filter input
        this.filterInput?.addEventListener('input', () => {
            clearTimeout(this.filterTimeout);
            this.filterTimeout = setTimeout(() => this.filterAndSortPlaylists(), 300);
        });

        // Sort select
        this.sortSelect?.addEventListener('change', () => this.filterAndSortPlaylists());

        // Pagination
        document.getElementById('prevPage')?.addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.updatePagination();
                this.displayCurrentPage();
            }
        });

        document.getElementById('nextPage')?.addEventListener('click', () => {
            const totalPages = Math.ceil(this.filteredItems.length / this.ITEMS_PER_PAGE);
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.updatePagination();
                this.displayCurrentPage();
            }
        });
    }

    updatePagination() {
        const totalPages = Math.ceil(this.filteredItems.length / this.ITEMS_PER_PAGE);
        document.getElementById('currentPage').textContent = this.currentPage;
        document.getElementById('totalPages').textContent = totalPages;
        document.getElementById('prevPage').disabled = this.currentPage === 1;
        document.getElementById('nextPage').disabled = this.currentPage === totalPages;
    }

    displayCurrentPage() {
        const start = (this.currentPage - 1) * this.ITEMS_PER_PAGE;
        const end = start + this.ITEMS_PER_PAGE;
        
        this.tableBody.innerHTML = '';
        this.filteredItems.slice(start, end).forEach(item => {
            const newItem = item.cloneNode(true);
            const button = newItem.querySelector('.set-public-btn');
            if (button) {
                button.onclick = () => this.setPublicPlaylist(button.dataset.playlistId);
            }
            this.tableBody.appendChild(newItem);
        });
    }

    filterAndSortPlaylists() {
        const filterValue = this.filterInput.value.toLowerCase();
        const sortValue = this.sortSelect.value;
        
        this.filteredItems = Array.from(this.playlistCards).filter(item => {
            const name = item.dataset.name || '';
            return name.includes(filterValue);
        });

        this.filteredItems.sort((a, b) => {
            if (sortValue === 'name') {
                return (a.dataset.name || '').localeCompare(b.dataset.name || '');
            }
            return parseInt(b.dataset.tracks || '0') - parseInt(a.dataset.tracks || '0');
        });

        this.currentPage = 1;
        this.updatePagination();
        this.displayCurrentPage();
    }

    setPublicPlaylist(playlistId) {
        if (!playlistId) {
            NotificationManager.show('Invalid playlist ID', 'error');
            return;
        }

        fetch('/admin/set_public_playlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `playlist_id=${playlistId}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                NotificationManager.show(data.error, 'error');
            } else {
                NotificationManager.show(data.message, 'success');
                setTimeout(() => window.location.reload(), 1500);
            }
        })
        .catch(error => {
            NotificationManager.show('Error setting public playlist', 'error');
            console.error('Error:', error);
        });
    }
}

// Initialize components when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize admin panel if on admin page
    if (document.querySelector('.admin-layout')) {
        new AdminPanel();
    }
});

// Initialize notification close buttons
document.addEventListener('click', function(e) {
    if (e.target.matches('.notification .close-btn')) {
        NotificationManager.hide();
    }
});

// Export utilities for other scripts
window.PyJams = {
    NotificationManager,
    AlertManager,
    showError: (message) => NotificationManager.show(message, 'error'),
    showSuccess: (message) => NotificationManager.show(message, 'success'),
    showInfo: (message) => AlertManager.show(message, 'info'),
    AdminPanel
};
