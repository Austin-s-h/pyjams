// Global error handling
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    // Only call showError if PyJams exists and is initialized
    if (window.PyJams && typeof window.PyJams.showError === 'function') {
        window.PyJams.showError('An unexpected error occurred');
    }
});

// Global PyJams namespace
window.PyJams = {
    showToast: (message, type = 'success') => {
        const toastEl = document.getElementById('liveToast');
        if (!toastEl) {
            // Fallback to console if toast element doesn't exist
            console.log(`${type.toUpperCase()}: ${message}`);
            return;
        }

        // Get bootstrap toast instance
        let toast;
        try {
            toast = new bootstrap.Toast(toastEl);
        } catch (error) {
            console.error('Failed to create toast:', error);
            return;
        }

        // Set title and message if elements exist
        const titleEl = toastEl.querySelector('#toastTitle');
        const msgEl = toastEl.querySelector('#toastMessage');
        
        if (titleEl) titleEl.textContent = type.charAt(0).toUpperCase() + type.slice(1);
        if (msgEl) msgEl.textContent = message;
        
        // Update toast appearance
        toastEl.className = `toast ${type === 'error' ? 'bg-danger' : 'bg-success'} text-white`;
        
        // Show the toast
        toast.show();
    },
    showSuccess: (message) => window.PyJams.showToast(message, 'success'),
    showError: (message) => window.PyJams.showToast(message, 'error'),
    showWarning: (message) => window.PyJams.showToast(message, 'warning')
};

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

        if (this.tableBody) {
            this.init();
        }
    }

    init() {
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
            window.PyJams.showError('Invalid playlist ID');
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
                window.PyJams.showError(data.error);
            } else {
                window.PyJams.showSuccess(data.message);
                setTimeout(() => window.location.reload(), 1500);
            }
        })
        .catch(error => {
            window.PyJams.showError('Error setting public playlist');
            console.error('Error:', error);
        });
    }
}

// Initialize components when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
        .forEach(el => new bootstrap.Tooltip(el));
    
    document.querySelectorAll('[data-bs-toggle="popover"]')
        .forEach(el => new bootstrap.Popover(el));
    
    document.querySelectorAll('.dropdown-toggle')
        .forEach(el => new bootstrap.Dropdown(el));

    // Initialize admin panel if on admin page
    if (document.querySelector('.admin-layout')) {
        new AdminPanel();
    }
});
