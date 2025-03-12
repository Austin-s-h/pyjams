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
    },

    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-bg-${type} border-0 fade show`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        const toastContainer = document.querySelector('.toast-container') || document.createElement('div');
        if (!document.querySelector('.toast-container')) {
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();
        
        // Remove toast after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    },

    // Consolidated loading state management
    setButtonLoading(button, isLoading, loadingText, originalText, iconClass = 'fa-spinner fa-spin') {
        if (!button) return;
        
        button.disabled = isLoading;
        if (isLoading) {
            button.dataset.originalHtml = button.innerHTML;
            button.innerHTML = `<i class="fas ${iconClass} me-1"></i>${loadingText || 'Loading...'}`;
        } else {
            button.innerHTML = originalText || button.dataset.originalHtml || button.innerHTML;
            delete button.dataset.originalHtml;
        }
    }
};

// Expose common utilities globally
window.PyJams = {
    showSuccess: (message) => PlaylistUtils.showToast(message, 'success'),
    showError: (message) => PlaylistUtils.showToast(message, 'danger'),
    showWarning: (message) => PlaylistUtils.showToast(message, 'warning'),
    
    // Debounce helper function
    debounce: function(func, wait) {
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
};

// Playlist Manager Functionality
class PlaylistManager {
    constructor() {
        this.modal = document.getElementById('playlistManagerModal');
        this.form = document.getElementById('playlistManagerForm');
        this.managerList = document.getElementById('managerList');
        this.loadingStates = {};
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

        // Add event listener for refresh button if it exists
        const refreshBtn = document.getElementById('refreshManagersBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                const playlistId = this.modal.querySelector('#playlistId').value;
                this.loadManagers(playlistId);
            });
        }
    }

    async loadManagers(playlistId) {
        if (this.loadingStates[playlistId]) return;
        
        try {
            this.loadingStates[playlistId] = true;
            this.setLoadingState(true);
            
            const data = await PlaylistUtils.fetchWithError(
                `/manage/playlist/${playlistId}/managers/`
            );
            if (this.managerList) {
                this.managerList.innerHTML = data.html;
            }
        } catch (error) {
            PlaylistUtils.showToast('Failed to load managers', 'danger');
        } finally {
            this.loadingStates[playlistId] = false;
            this.setLoadingState(false);
        }
    }
    
    setLoadingState(isLoading) {
        const refreshBtn = document.getElementById('refreshManagersBtn');
        if (refreshBtn) {
            refreshBtn.disabled = isLoading;
            refreshBtn.innerHTML = isLoading ? 
                '<i class="fas fa-spinner fa-spin"></i>' : 
                '<i class="fas fa-sync-alt"></i>';
        }
        
        if (this.managerList && isLoading && this.managerList.children.length === 0) {
            this.managerList.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <p class="mt-2 text-muted">Loading managers...</p>
                </div>
            `;
        }
    }

    async removeManager(playlistId, userId) {
        if (this.loadingStates[`remove-${userId}`]) return;
        
        try {
            this.loadingStates[`remove-${userId}`] = true;
            const button = document.querySelector(`.remove-manager-btn[data-user-id="${userId}"]`);
            if (button) {
                const originalHtml = button.innerHTML;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                button.disabled = true;
            }
            
            const data = await PlaylistUtils.fetchWithError(
                `/manage/playlist/${playlistId}/managers/remove/${userId}/`,
                { method: 'POST' }
            );
            
            PlaylistUtils.showToast(data.message || 'Manager removed successfully');
            this.loadManagers(playlistId);
            
        } catch (error) {
            PlaylistUtils.showToast(error.message || 'Failed to remove manager', 'danger');
        } finally {
            this.loadingStates[`remove-${userId}`] = false;
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
        this.isLoading = false;
        this.loadedOnce = false;
        
        if (this.form) {
            this.init();
            // Load initial playlists
            this.loadRecentPlaylists();
        }
    }

    init() {
        this.setupSearchHandler();
        this.setupFormHandler();
        this.setupRefreshButton();
    }

    setupRefreshButton() {
        const refreshBtn = document.getElementById('refreshPlaylistsBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshPlaylists());
        }
    }

    async refreshPlaylists() {
        if (this.isLoading) return;
        
        this.searchInput.value = '';
        await this.loadRecentPlaylists(true);
    }

    setupSearchHandler() {
        this.searchInput?.addEventListener('input', 
            PyJams.debounce(async (e) => {
                const query = e.target.value.trim();
                
                // Clear results if query is empty or too short
                if (!query || query.length < 2) {
                    if (query.length === 0) {
                        // If the search is cleared, reload recent playlists
                        this.loadRecentPlaylists();
                    } else {
                        // If query is just too short, show loading state
                        this.showDefaultResults();
                    }
                    return;
                }

                this.setSearchLoading(true);
                try {
                    await this.searchPlaylists(query);
                } finally {
                    this.setSearchLoading(false);
                }
            }, 300)
        );
    }

    async searchPlaylists(query) {
        try {
            const response = await PlaylistUtils.fetchWithError(
                `/playlists/search?q=${encodeURIComponent(query)}&timestamp=${Date.now()}`
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
                    <button class="btn btn-sm btn-outline-secondary mt-2" id="retryLoadBtn">
                        <i class="fas fa-sync-alt me-1"></i>Retry
                    </button>
                </div>`;
                
            document.getElementById('retryLoadBtn')?.addEventListener('click', () => {
                this.refreshPlaylists();
            });
            return;
        }

        const heading = this.searchInput.value ? 
            'Search Results' : 
            'Your Recent Playlists';

        this.resultsContainer.innerHTML = `
            <div class="playlist-container">
                <div class="results-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <small class="text-muted">${heading}</small>
                        ${!this.searchInput.value ? `
                        <button class="btn btn-sm btn-link py-0 px-1" id="refreshPlaylistsBtn" title="Refresh playlists">
                            <i class="fas fa-sync-alt"></i>
                        </button>` : ''}
                    </div>
                </div>
                <div class="scrollable-container">
                    ${playlists.map(playlist => `
                        <div class="playlist-result d-flex align-items-center p-2 border-bottom border-secondary hover-highlight cursor-pointer" 
                            onclick="window.selectPlaylistForFeature('${playlist.id}', '${playlist.name}', '${playlist.image_url}')">
                            <img src="${playlist.image_url || '/static/images/default-playlist.png'}" 
                                class="me-2 rounded" width="40" height="40" alt="" 
                                onerror="this.src='/static/images/default-playlist.png'">
                            <div class="flex-grow-1 overflow-hidden">
                                <div class="fw-bold text-truncate">${playlist.name}</div>
                                <small class="text-muted">${playlist.tracks_total} tracks</small>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>`;
            
        // Check if we have enough playlists to scroll and add a helper message
        const playlistContainer = this.resultsContainer.querySelector('.scrollable-container');
        if (playlistContainer && playlists.length > 5) {
            // Add a subtle indicator that the list is scrollable
            const scrollIndicator = document.createElement('div');
            scrollIndicator.className = 'text-center text-muted small mt-2 mb-1';
            scrollIndicator.textContent = 'Scroll for more playlists';
            playlistContainer.appendChild(scrollIndicator);
        }
        
        document.getElementById('refreshPlaylistsBtn')?.addEventListener('click', () => {
            this.refreshPlaylists();
        });
    }

    showDefaultResults() {
        this.resultsContainer.innerHTML = `
            <div class="playlist-container">
                <div class="p-3 text-center">
                    <div class="spinner-border spinner-border-sm text-primary mb-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="text-muted">Loading your playlists...</div>
                </div>
            </div>`;
    }

    showError(message) {
        this.resultsContainer.innerHTML = `
            <div class="playlist-container">
                <div class="p-3 text-danger text-center">
                    <i class="fas fa-exclamation-circle me-2"></i>${message}
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-primary" id="retryLoadBtn">
                            <i class="fas fa-sync-alt me-1"></i>Try Again
                        </button>
                    </div>
                </div>
            </div>`;
            
        document.getElementById('retryLoadBtn')?.addEventListener('click', () => {
            this.refreshPlaylists();
        });
    }
    
    setSearchLoading(isLoading) {
        this.isLoading = isLoading;
        this.searchSpinner?.classList.toggle('d-none', !isLoading);
        
        const refreshBtn = document.getElementById('refreshPlaylistsBtn');
        if (refreshBtn) {
            refreshBtn.disabled = isLoading;
            refreshBtn.innerHTML = isLoading ? 
                '<i class="fas fa-spinner fa-spin"></i>' : 
                '<i class="fas fa-sync-alt"></i>';
        }
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

    // Improved method to load recent playlists
    async loadRecentPlaylists(forceRefresh = false) {
        if (this.isLoading && !forceRefresh) return;
        
        // Only show loading state if we don't have results already,
        // unless this is a forced refresh
        if (!this.loadedOnce || forceRefresh) {
            this.showDefaultResults();
        }
        
        this.setSearchLoading(true);
        
        try {
            const timestamp = forceRefresh ? Date.now() : '';
            const response = await PlaylistUtils.fetchWithError(`/playlists/search?timestamp=${timestamp}`);
            this.displayResults(response.data.search_results);
            this.loadedOnce = true;
        } catch (error) {
            this.showError('Failed to load playlists');
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

// Track Management Functionality
class TrackManager {
    constructor() {
        this.initialize();
    }
    
    initialize() {
        this.setupTrackPreview();
        this.setupTrackRemoval();
    }
    
    setupTrackPreview() {
        // Track preview functionality
        window.previewTrack = (trackId) => {
            const previewUrl = document.querySelector(`tr[data-track-id="${trackId}"]`)?.dataset.previewUrl;
            if (!previewUrl) {
                PlaylistUtils.showToast("No preview available for this track", "warning");
                return;
            }
            
            // Stop any currently playing previews
            const audioElements = document.querySelectorAll('.track-preview-audio');
            audioElements.forEach(audio => audio.pause());
            
            // Create and play new audio preview
            const audio = new Audio(previewUrl);
            audio.className = 'track-preview-audio';
            document.body.appendChild(audio);
            
            audio.play().catch(error => {
                PlaylistUtils.showToast("Failed to play preview", "danger");
                console.error("Audio play error:", error);
            });
            
            // Update button to show playing state
            const playButton = document.querySelector(`tr[data-track-id="${trackId}"] .play-preview-btn`);
            if (playButton) {
                const originalHtml = playButton.innerHTML;
                playButton.innerHTML = '<i class="fas fa-pause"></i>';
                
                audio.addEventListener('ended', () => {
                    playButton.innerHTML = originalHtml;
                    audio.remove();
                });
                
                playButton.addEventListener('click', () => {
                    if (!audio.paused) {
                        audio.pause();
                        playButton.innerHTML = originalHtml;
                    } else {
                        audio.play();
                        playButton.innerHTML = '<i class="fas fa-pause"></i>';
                    }
                }, { once: true });
            }
        };
    }
    
    setupTrackRemoval() {
        // Track removal functionality
        window.removeTrack = async (trackId) => {
            if (!confirm('Are you sure you want to remove this track?')) return;
            
            const trackRow = document.querySelector(`tr[data-track-id="${trackId}"]`);
            if (!trackRow) return;
            
            const playlistId = document.querySelector('[data-playlist-id]')?.dataset.playlistId;
            if (!playlistId) {
                PlaylistUtils.showToast("Playlist ID not found", "danger");
                return;
            }
            
            // Visual feedback
            trackRow.classList.add('removing');
            
            try {
                const response = await PlaylistUtils.fetchWithError(
                    `/playlists/${playlistId}/tracks/remove/${trackId}/`,
                    { method: 'POST' }
                );
                
                PlaylistUtils.showToast(response.message || "Track removed successfully");
                
                // Animate row removal
                trackRow.style.height = `${trackRow.offsetHeight}px`;
                setTimeout(() => {
                    trackRow.style.height = '0';
                    trackRow.style.opacity = '0';
                    
                    setTimeout(() => {
                        trackRow.remove();
                        // Renumber the rows
                        document.querySelectorAll('table tbody tr').forEach((row, index) => {
                            row.querySelector('td:first-child').textContent = index + 1;
                        });
                    }, 300);
                }, 100);
                
            } catch (error) {
                PlaylistUtils.showToast(error.message || "Failed to remove track", "danger");
                trackRow.classList.remove('removing');
            }
        };
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    new PlaylistManager();
    new CreatePlaylist();
    new SetFeaturedPlaylist();
    new TrackManager();
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

// Expose playlist refresh globally
window.refreshPlaylist = function() {
    location.reload();
};
