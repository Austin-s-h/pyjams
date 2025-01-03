document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');
    const searchSpinner = document.getElementById('searchSpinner');
    let searchTimeout;

    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        const query = this.value.trim();
        
        if (query.length < 2) {
            searchResults.style.display = 'none';
            return;
        }

        searchTimeout = setTimeout(async () => {
            try {
                searchSpinner?.classList.remove('d-none');
                const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                searchResults.innerHTML = data.tracks.map(track => `
                    <div class="list-group-item bg-dark text-light border-secondary d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">${track.name}</h6>
                            <small>${track.artists.join(', ')} • ${track.album.name}</small>
                        </div>
                        <button class="btn btn-success btn-sm add-track" 
                                data-track-id="${track.id}">
                            <i class="fas fa-plus"></i> Add
                        </button>
                    </div>
                `).join('');
                
                searchResults.style.display = 'block';
                
                // Update add track handler
                document.querySelectorAll('.add-track').forEach(button => {
                    button.addEventListener('click', async (e) => {
                        const trackId = e.target.closest('.add-track').dataset.trackId;
                        
                        if (!currentPlaylistId) {
                            // Show playlist selection modal if no playlist is selected
                            const modal = new bootstrap.Modal(document.getElementById('selectPlaylistModal'));
                            modal.show();
                            return;
                        }

                        try {
                            const formData = new FormData();
                            formData.append('track_id', trackId);
                            formData.append('playlist_id', currentPlaylistId);
                            
                            const response = await fetch(`/playlists/${currentPlaylistId}/tracks/add/`, {
                                method: 'POST',
                                headers: {
                                    'X-CSRFToken': PlaylistUtils.getCookie('csrftoken')
                                },
                                body: formData
                            });
                            
                            const result = await response.json();
                            if (response.ok) {
                                PyJams.showSuccess(result.message);
                                searchInput.value = '';
                                searchResults.style.display = 'none';
                            } else {
                                PyJams.showError(result.error || 'Error adding track');
                            }
                        } catch (error) {
                            console.error('Error:', error);
                            PyJams.showError('Error adding track');
                        }
                    });
                });
            } catch (error) {
                console.error('Error:', error);
                searchResults.innerHTML = '<div class="list-group-item bg-dark text-light">Error searching tracks</div>';
            } finally {
                searchSpinner?.classList.add('d-none');
            }
        }, 300);
    });

    // Hide search results when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });
});

// Add playlist selection handler
window.selectPlaylist = function(playlistId, playlistName) {
    currentPlaylistId = playlistId;
    document.getElementById('selectPlaylistModal').querySelector('.btn-close').click();
    PyJams.showSuccess(`Selected playlist: ${playlistName}`);
}
