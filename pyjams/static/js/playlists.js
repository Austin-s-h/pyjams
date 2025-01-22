// Utility Functions
const PlaylistUtils = {
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },

    async fetchWithError(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    'X-CSRFToken': this.getCookie('csrftoken')
                }
            });
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || data.detail || 'An error occurred');
            }
            
            return data;
        } catch (error) {
            console.error('Fetch error:', error);
            throw error;
        }
    }
};

// Playlist Manager Functionality
class PlaylistManager {
    constructor() {
        this.modal = document.getElementById('playlistManagerModal');
        this.form = document.getElementById('playlistManagerForm');
        this.managerList = document.getElementById('managerList');
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Modal events
        if (this.modal) {
            this.modal.addEventListener('show.bs.modal', (event) => {
                const button = event.relatedTarget;
                const playlistId = button.dataset.playlistId;
                const playlistName = button.dataset.playlistName;
                
                this.modal.querySelector('.modal-title').textContent = `Manage "${playlistName}" Managers`;
                this.modal.querySelector('#playlistId').value = playlistId;
                
                this.loadManagers(playlistId);
            });
        }

        // Form submission
        if (this.form) {
            this.form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(this.form);
                const playlistId = formData.get('playlist_id');

                try {
                    const data = await PlaylistUtils.fetchWithError(
                        `/manage/playlist/${playlistId}/managers/add/`,
                        {
                            method: 'POST',
                            body: formData
                        }
                    );
                    PyJams.showSuccess(data.message);
                    this.loadManagers(playlistId);
                    this.form.reset();
                } catch (error) {
                    PyJams.showError(error.message);
                }
            });
        }
    }

    async loadManagers(playlistId) {
        try {
            const data = await PlaylistUtils.fetchWithError(
                `/manage/playlist/${playlistId}/managers/`
            );
            if (this.managerList) {
                this.managerList.innerHTML = data.html;
            }
        } catch (error) {
            PyJams.showError('Failed to load managers');
        }
    }
}

// Modify CreatePlaylist class to SelectPlaylist
class CreatePlaylist {
    constructor() {
        this.form = document.getElementById('createPlaylistForm');
        this.searchInput = document.getElementById('playlistSearch');
        this.resultsContainer = document.getElementById('searchResults');
        this.selectedDisplay = document.getElementById('selectedPlaylist');
        this.submitButton = document.getElementById('featureButton');
        this.searchSpinner = document.getElementById('searchSpinner');
        
        if (this.form) {
            this.init();
            // Load initial playlists
            this.loadRecentPlaylists();
        }
    }

    init() {
        this.setupSearchHandler();
        this.setupFormHandler();
    }

    setupSearchHandler() {
        this.searchInput?.addEventListener('input', debounce(async (e) => {
            const query = e.target.value.trim();
            
            // Clear results if query too short
            if (query.length < 2) {
                this.showDefaultResults();
                return;
            }

            this.setSearchLoading(true);
            try {
                await this.searchPlaylists(query);
            } finally {
                this.setSearchLoading(false);
            }
        }, 300));
    }

    async searchPlaylists(query) {
        try {
            const response = await PlaylistUtils.fetchWithError(
                `/playlists/search?q=${encodeURIComponent(query)}`
            );
            this.displayResults(response.data.search_results);
        } catch (error) {
            this.showError('Search failed. Please try again.');
        }
    }

    displayResults(playlists) {
        if (!playlists?.length) {
            this.resultsContainer.innerHTML = `
                <div class="p-3 text-muted text-center">
                    ${this.searchInput.value ? 'No playlists found' : 'No playlists available'}
                </div>`;
            return;
        }

        const heading = this.searchInput.value ? 
            'Search Results' : 
            'Your Recent Playlists';

        this.resultsContainer.innerHTML = `
            <div class="p-2 border-bottom border-secondary">
                <small class="text-muted">${heading}</small>
            </div>
            ${playlists.map(playlist => `
                <div class="playlist-result d-flex align-items-center p-2 border-bottom border-secondary hover-highlight cursor-pointer" 
                     onclick="window.selectPlaylistForFeature('${playlist.id}', '${playlist.name}', '${playlist.image_url}')">
                    <img src="${playlist.image_url || '/static/images/default-playlist.png'}" 
                         class="me-2 rounded" width="40" height="40" alt="">
                    <div>
                        <div class="fw-bold text-truncate">${playlist.name}</div>
                        <small class="text-muted">${playlist.tracks_total} tracks</small>
                    </div>
                </div>
            `).join('')}`;
    }

    showDefaultResults() {
        this.resultsContainer.innerHTML = `
            <div class="p-3 text-muted text-center">
                <i class="fas fa-music me-2"></i>Loading your playlists...
            </div>`;
    }

    setSearchLoading(isLoading) {
        this.searchSpinner?.classList.toggle('d-none', !isLoading);
    }

    setSubmitLoading(isLoading) {
        if (this.submitButton) {
            this.submitButton.disabled = isLoading;
            this.submitButton.innerHTML = isLoading ? 
                '<i class="fas fa-spinner fa-spin me-1"></i>Featuring...' : 
                '<i class="fas fa-star me-1"></i>Feature Playlist';
        }
    }

    setupFormHandler() {
        this.form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!this.validateForm()) return;

            this.setSubmitLoading(true);
            try {
                await this.submitForm();
            } finally {
                this.setSubmitLoading(false);
            }
        });
    }

    validateForm() {
        const playlistId = this.form.querySelector('[name="playlist_id"]').value;
        const featureType = this.form.querySelector('[name="feature_type"]').value;
        
        if (!playlistId || !featureType) {
            PyJams.showError('Please select both a playlist and feature type');
            return false;
        }
        return true;
    }

    async submitForm() {
        const formData = new FormData(this.form);
        const playlistId = formData.get('playlist_id');
        const featureType = formData.get('feature_type');
        
        const endpoint = `/playlists/${playlistId}/feature/${featureType}/`;

        try {
            const data = await PlaylistUtils.fetchWithError(endpoint, {
                method: 'POST',
                body: formData
            });
            PyJams.showSuccess(data.message || 'Playlist featured successfully');
            this.closeModal();
            location.reload();
        } catch (error) {
            PyJams.showError(error.message || 'Failed to feature playlist');
        }
    }

    closeModal() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('createPlaylistModal'));
        modal?.hide();
        this.form.reset();
        this.showDefaultResults();
        this.selectedDisplay.innerHTML = '<span class="text-muted">No playlist selected</span>';
    }

    // Add new method to load recent playlists
    async loadRecentPlaylists() {
        this.setSearchLoading(true);
        try {
            const response = await PlaylistUtils.fetchWithError('/playlists/search');
            this.displayResults(response.data.search_results);
        } catch (error) {
            this.showError('Failed to load playlists');
            this.showDefaultResults();
        } finally {
            this.setSearchLoading(false);
        }
    }
}

// Set Featured Playlist Functionality
class SetFeaturedPlaylist {
    constructor() {
        this.form = document.getElementById('setFeaturedPlaylistForm');
        this.submitButton = this.form?.querySelector('button[type="submit"]');
        this.modal = document.getElementById('setFeaturedPlaylistModal');
        this.playlistSelect = document.getElementById('playlist_select');
        if (this.form) {
            this.setupEventListeners();
        }
    }

    setupEventListeners() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (!this.validateForm()) {
                return;
            }

            this.setLoading(true);
            const formData = new FormData(this.form);
            const playlistId = formData.get('playlist_id');
            
            try {
                // Use the correct feature endpoint based on feature type
                const featureType = formData.get('feature_type');
                const endpoint = featureType === 'site' ? 
                    `/playlists/${playlistId}/feature/site/` :
                    `/playlists/${playlistId}/feature/community/`;

                const data = await PlaylistUtils.fetchWithError(
                    endpoint,
                    {
                        method: 'POST',
                        body: formData
                    }
                );

                PyJams.showSuccess(data.message || 'Playlist featured successfully');
                this.closeModal();
                location.reload();
            } catch (error) {
                PyJams.showError(error.message);
            } finally {
                this.setLoading(false);
            }
        });
    }

    validateForm() {
        const playlistId = this.form.querySelector('[name="playlist_id"]').value;
        const featureType = this.form.querySelector('[name="feature_type"]').value;
        
        if (!playlistId) {
            PyJams.showError('Please select a playlist');
            return false;
        }
        if (!featureType) {
            PyJams.showError('Please select a feature type');
            return false;
        }
        return true;
    }

    setLoading(isLoading) {
        if (this.submitButton) {
            this.submitButton.disabled = isLoading;
            this.submitButton.innerHTML = isLoading ? 
                '<i class="fas fa-spinner fa-spin me-1"></i>Featuring...' : 
                '<i class="fas fa-star me-1"></i>Feature Playlist';
        }
    }

    closeModal() {
        if (this.modal) {
            const bsModal = bootstrap.Modal.getInstance(this.modal);
            bsModal?.hide();
            this.form.reset();
        }
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    new PlaylistManager();
    new CreatePlaylist();
    new SetFeaturedPlaylist();
});

// Export for global access
window.openManagerModal = function(playlistId, playlistName) {
    document.getElementById('playlistId').value = playlistId;
    document.getElementById('playlistManagerModalLabel').textContent = 
        `Add Manager to "${playlistName}"`;
}

// Add global helper function
window.selectPlaylistForFeature = function(id, name, imageUrl) {
    const form = document.getElementById('createPlaylistForm');
    form.querySelector('[name="playlist_id"]').value = id;
    
    document.getElementById('selectedPlaylist').innerHTML = `
        <div class="d-flex align-items-center">
            <img src="${imageUrl || '/static/images/default-playlist.png'}" 
                 class="me-2 rounded" width="40" height="40" alt="">
            <div class="fw-bold">${name}</div>
        </div>
    `;
};

// Debounce helper function
function debounce(func, wait) {
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
