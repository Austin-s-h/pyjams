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

// Create Playlist Functionality
class CreatePlaylist {
    constructor() {
        this.form = document.getElementById('createPlaylistForm');
        if (this.form) {
            this.setupEventListeners();
        }
    }

    setupEventListeners() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(this.form);
            
            try {
                const data = await PlaylistUtils.fetchWithError(
                    '/admin/create_public_playlist',
                    {
                        method: 'POST',
                        body: formData
                    }
                );
                PyJams.showSuccess(data.message);
                location.reload();
            } catch (error) {
                PyJams.showError(error.message);
            }
        });
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    new PlaylistManager();
    new CreatePlaylist();
});

// Export for global access
window.openManagerModal = function(playlistId, playlistName) {
    document.getElementById('playlistId').value = playlistId;
    document.getElementById('playlistManagerModalLabel').textContent = 
        `Add Manager to "${playlistName}"`;
}
