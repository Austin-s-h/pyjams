document.addEventListener('DOMContentLoaded', function() {
    // Create Playlist Form Handler
    const createPlaylistForm = document.getElementById('createPlaylistForm');
    if (createPlaylistForm) {
        createPlaylistForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            try {
                const response = await fetch('/admin/create_public_playlist', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                if (response.ok) {
                    PyJams.showSuccess(data.message);
                    location.reload();
                } else {
                    PyJams.showError(data.detail || 'Error creating playlist');
                }
            } catch (error) {
                console.error('Error:', error);
                PyJams.showError('Error creating playlist');
            }
        });
    }

    // Playlist Manager Form Handler
    const playlistManagerForm = document.getElementById('playlistManagerForm');
    if (playlistManagerForm) {
        playlistManagerForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const response = await fetch('/admin/add_manager', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (response.ok) {
                    PyJams.showSuccess('Manager added successfully');
                    location.reload();
                } else {
                    PyJams.showError(data.detail || 'Error adding manager');
                }
            } catch (error) {
                console.error('Error:', error);
                PyJams.showError('Error adding manager');
            }
        });
    }
});

// Utility Functions
window.openManagerModal = function(playlistId, playlistName) {
    document.getElementById('playlistId').value = playlistId;
    document.getElementById('playlistManagerModalLabel').textContent = `Add Manager to "${playlistName}"`;
}
