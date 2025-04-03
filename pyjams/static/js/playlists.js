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
            
            // Check content type to handle non-JSON responses
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || data.detail || 'An error occurred');
                }
                
                return data;
            } else {
                // Handle non-JSON responses
                const text = await response.text();
                console.error('Received non-JSON response:', text.substring(0, 500) + '...');
                
                if (response.redirected) {
                    // If the response was a redirect, follow it
                    window.location.href = response.url;
                    return {};
                }
                
                // Check if the response contains login form or authentication required
                if (text.includes('login') || text.includes('sign in') || 
                    text.includes('authentication') || text.includes('<form') ||
                    !response.ok) {
                    throw new Error('Authentication required or permission denied. Please log in and try again.');
                }
                
                throw new Error(`Server returned non-JSON response (HTTP ${response.status}). Check console for details.`);
            }
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
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
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

// Main playlist management class
class PlaylistManager {
    constructor() {
        this.searchTimeout = null;
        this.audioPlayer = null;
        this.modal = document.getElementById('playlistManagerModal');
        this.form = document.getElementById('playlistManagerForm');
        this.managerList = document.getElementById('managerList');
        this.loadingStates = {};
        this.initializeEventListeners();
        this.setupEventListeners();
    }

    initializeEventListeners() {
        // Search modal listeners
        const searchModal = document.getElementById('searchModal');
        if (searchModal) {
            const searchInput = searchModal.querySelector('#trackSearch');
            searchInput?.addEventListener('input', (e) => this.handleTrackSearch(e));
        }

        // Manager modal listeners
        const managerModal = document.getElementById('managerModal');
        if (managerModal) {
            const addManagerForm = managerModal.querySelector('#addManagerForm');
            addManagerForm?.addEventListener('submit', (e) => this.handleAddManager(e));
        }
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

    async handleTrackSearch(event) {
        clearTimeout(this.searchTimeout);
        const query = event.target.value.trim();
        const resultsContainer = document.getElementById('searchResults');
        const spinner = document.getElementById('searchSpinner');

        if (query.length < 2) {
            resultsContainer.innerHTML = '<p class="text-muted text-center">Enter at least 2 characters to search</p>';
            return;
        }

        spinner.classList.remove('d-none');
        
        this.searchTimeout = setTimeout(async () => {
            try {
                const response = await fetch(`/tracks/search/?q=${encodeURIComponent(query)}`);
                const html = await response.text();
                resultsContainer.innerHTML = html;
            } catch (error) {
                resultsContainer.innerHTML = '<p class="text-danger text-center">Error searching tracks</p>';
                console.error('Search error:', error);
            } finally {
                spinner.classList.add('d-none');
            }
        }, 300);
    }

    async addTrack(trackId, playlistId) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        try {
            const formData = new FormData();
            formData.append('track_id', trackId);
            formData.append('playlist_id', playlistId);

            const response = await fetch(`/playlists/${playlistId}/tracks/add/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                this.showToast('success', 'Track added successfully');
                const trackList = document.querySelector('.table tbody');
                if (trackList && data.html) {
                    trackList.innerHTML = data.html;
                }
            } else {
                throw new Error(data.error || 'Failed to add track');
            }
        } catch (error) {
            this.showToast('error', error.message);
        }
    }

    async removeTrack(trackId, playlistId) {
        if (!confirm('Are you sure you want to remove this track?')) return;

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        try {
            const formData = new FormData();
            formData.append('track_id', trackId);
            formData.append('playlist_id', playlistId);

            const response = await fetch(`/playlists/${playlistId}/tracks/remove/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                const trackRow = document.querySelector(`tr[data-track-id="${trackId}"]`);
                trackRow?.remove();
                this.showToast('success', 'Track removed successfully');
            } else {
                throw new Error(data.error || 'Failed to remove track');
            }
        } catch (error) {
            this.showToast('error', error.message);
        }
    }

    previewTrack(trackId) {
        if (this.audioPlayer) {
            this.audioPlayer.pause();
            this.audioPlayer = null;
        }

        const trackElement = document.querySelector(`tr[data-track-id="${trackId}"]`);
        const previewUrl = trackElement?.dataset.previewUrl;

        if (!previewUrl) {
            this.showToast('error', 'No preview available for this track');
            return;
        }

        this.audioPlayer = new Audio(previewUrl);
        this.audioPlayer.play();
    }

    showToast(type, message) {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    }

    async loadManagers(playlistId) {
        if (this.loadingStates[playlistId]) return;
        
        try {
            this.loadingStates[playlistId] = true;
            this.setLoadingState(true);
            
            const data = await PlaylistUtils.fetchWithError(
                `/playlists/${playlistId}/managers/`
            );
            if (this.managerList) {
                this.managerList.innerHTML = data.html || this.renderManagerList(data.managers);
            }
        } catch (error) {
            PlaylistUtils.showToast('Failed to load managers', 'danger');
        } finally {
            this.loadingStates[playlistId] = false;
            this.setLoadingState(false);
        }
    }
    
    renderManagerList(managers) {
        if (!managers || managers.length === 0) {
            return `<div class="list-group-item text-center py-3">No managers found</div>`;
        }
        
        return managers.map(manager => `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div>${manager.user_id}</div>
                <button class="btn btn-sm btn-danger remove-manager-btn" 
                    data-user-id="${manager.user_id}" 
                    onclick="playlistManager.removeManager(${manager.playlist_id}, '${manager.user_id}')">
                    <i class="fas fa-times"></i> Remove
                </button>
            </div>
        `).join('');
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
                `/playlists/${playlistId}/managers/remove/`,
                { 
                    method: 'POST',
                    body: new FormData().append('user_id', userId)
                }
            );
            
            PlaylistUtils.showToast(data.message || 'Manager removed successfully');
            this.loadManagers(playlistId);
            
        } catch (error) {
            PlaylistUtils.showToast(error.message || 'Failed to remove manager', 'danger');
        } finally {
            this.loadingStates[`remove-${userId}`] = false;
        }
    }

    setLoadingState(isLoading) {
        // Implement loading state management
        const loadingIndicator = document.getElementById('managersLoadingIndicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = isLoading ? 'block' : 'none';
        }
    }
}

// Playlist creation and featuring class
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
        this.loadAttempts = 0;
        
        if (this.form) {
            this.init();
            // Load initial playlists with a slight delay
            setTimeout(() => this.loadRecentPlaylists(), 300);
        }
    }

    init() {
        this.setupSearchHandler();
        this.setupFormHandler();
        this.setupRefreshButton();
        this.setupFeatureTypeHandler();
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
            const timestamp = Date.now();
            const url = `/playlists/search?q=${encodeURIComponent(query)}&timestamp=${timestamp}`;
            console.log('Searching playlists:', url);
            
            const response = await fetch(url, {
                headers: {
                    'X-CSRFToken': PlaylistUtils.getCookie('csrftoken'),
                    'Accept': 'application/json'
                }
            });
            
            // Check for authentication issues
            if (response.status === 401 || response.redirected) {
                this.showSeriousError('Your Spotify session has expired. Please reconnect.');
                return;
            }
            
            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }
            
            this.displayResults(data.data.search_results);
        } catch (error) {
            console.error('Playlist search error:', error);
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
        
        try {
            // Use the standardized endpoint
            const response = await PlaylistUtils.fetchWithError(`/playlists/${playlistId}/feature/`, {
                method: 'POST',
                body: formData
            });
            
            PyJams.showSuccess(response.message || 'Playlist featured successfully');
            this.closeModal();
            
            // Reload the page after a short delay to show the success message
            setTimeout(() => location.reload(), 1000);
        } catch (error) {
            PyJams.showError(error.message || 'Failed to feature playlist');
            console.error('Feature playlist error details:', error);
        }
    }

    closeModal() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('createPlaylistModal'));
        modal?.hide();
        this.form.reset();
        this.showDefaultResults();
        this.selectedDisplay.innerHTML = '<span class="text-muted">No playlist selected</span>';
    }

    async loadRecentPlaylists(forceRefresh = false) {
        if (this.isLoading && !forceRefresh) return;
        
        if (!this.loadedOnce || forceRefresh) {
            this.showDefaultResults();
        }
        
        this.setSearchLoading(true);
        this.loadAttempts++;
        
        try {
            // Add timestamp to avoid caching issues
            const timestamp = Date.now();
            const url = `/playlists/search?timestamp=${timestamp}${forceRefresh ? '&refresh=true' : ''}`;
            console.log('Loading playlists from:', url);
            
            const response = await PlaylistUtils.fetchWithError(url);
            
            if (!response.data || !response.data.search_results) {
                throw new Error('Invalid response format');
            }
            
            this.displayResults(response.data.search_results);
            this.loadedOnce = true;
            this.loadAttempts = 0; // Reset attempt counter on success
            
            console.log(`Loaded ${response.data.search_results.length} playlists successfully`);
        } catch (error) {
            console.error('Failed to load playlists:', error);
            
            // After 3 failed attempts, show a more serious error
            if (this.loadAttempts >= 3) {
                this.showSeriousError('There was an issue loading your playlists. You may need to reconnect your Spotify account.');
            } else {
                this.showError('Failed to load playlists. Retrying...');
                // Auto retry after a delay for the first couple attempts
                setTimeout(() => this.loadRecentPlaylists(true), 2000);
            }
        } finally {
            this.setSearchLoading(false);
        }
    }

    showSeriousError(message) {
        this.resultsContainer.innerHTML = `
            <div class="playlist-container">
                <div class="p-3 text-danger text-center">
                    <i class="fas fa-exclamation-triangle me-2"></i>${message}
                    <div class="mt-3">
                        <a href="/spotify/login" class="btn btn-primary">
                            <i class="fab fa-spotify me-1"></i>Reconnect Spotify
                        </a>
                        <button class="btn btn-secondary ms-2" id="retryLoadBtn">
                            <i class="fas fa-sync-alt me-1"></i>Try Again
                        </button>
                    </div>
                </div>
            </div>`;
            
        document.getElementById('retryLoadBtn')?.addEventListener('click', () => {
            this.loadAttempts = 0; // Reset attempts
            this.refreshPlaylists();
        });
    }

    setupFeatureTypeHandler() {
        const featureTypeSelect = this.form?.querySelector('[name="feature_type"]');
        const playlistIdInput = this.form?.querySelector('[name="playlist_id"]');
        const submitButton = document.getElementById('featureButton');
        
        if (featureTypeSelect && submitButton) {
            featureTypeSelect.addEventListener('change', () => {
                // Enable button only if both a playlist is selected and feature type is chosen
                const hasPlaylistSelected = playlistIdInput && playlistIdInput.value;
                const hasFeatureType = featureTypeSelect.value;
                submitButton.disabled = !(hasPlaylistSelected && hasFeatureType);
            });
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
                // Use the unified feature endpoint instead of separate endpoints
                const endpoint = `/playlists/${playlistId}/feature/`;

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
                    `/playlists/${playlistId}/tracks/remove/`,
                    { 
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        },
                        body: `track_id=${trackId}&playlist_id=${playlistId}`
                    }
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
    const playlistManager = new PlaylistManager();
    window.playlistManager = playlistManager; // Make it globally accessible
    window.playlistCreator = new CreatePlaylist(); // Make it globally accessible
    new SetFeaturedPlaylist();
    new TrackManager();
});

// Export for global access
window.openManagerModal = function(playlistId, playlistName) {
    document.getElementById('playlistId').value = playlistId;
    document.getElementById('playlistManagerModalLabel').textContent = 
        `Add Manager to "${playlistName}"`;
};

// Add global helper function
window.selectPlaylistForFeature = function(id, name, imageUrl) {
    const selectedDisplay = document.getElementById('selectedPlaylist');
    if (!selectedDisplay) {
        console.error('Cannot find selectedPlaylist element');
        return;
    }
    
    selectedDisplay.innerHTML = `
        <div class="d-flex align-items-center">
            <img src="${imageUrl || '/static/images/default-playlist.png'}" 
                 class="me-2 rounded" width="40" height="40" alt=""
                 onerror="this.src='/static/images/default-playlist.png'">
            <div class="fw-bold">${name}</div>
        </div>
    `;

    const form = document.getElementById('createPlaylistForm');
    if (form) {
        const playlistIdInput = form.querySelector('[name="playlist_id"]');
        if (playlistIdInput) {
            playlistIdInput.value = id;
        }
        
        const submitButton = document.getElementById('featureButton');
        if (submitButton) {
            const featureType = form.querySelector('[name="feature_type"]').value;
            submitButton.disabled = !featureType;
            
            // Optionally focus the feature type dropdown if it's not selected
            const featureTypeSelect = form.querySelector('[name="feature_type"]');
            if (featureTypeSelect && !featureTypeSelect.value) {
                featureTypeSelect.focus();
            }
        }
    }
};

// Expose playlist refresh globally
window.refreshPlaylist = function() {
    location.reload();
};
