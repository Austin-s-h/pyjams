document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');
    const searchSpinner = document.getElementById('searchSpinner');
    let searchTimeout;
    
    // Initialize the searchUrl from data attribute or default to tracks search endpoint
    const searchUrl = searchInput?.dataset.searchUrl || '/tracks/search/';

    function renderTrackItem(track, playlists) {
        return `
            <div class="list-group-item bg-dark text-light border-secondary hover-highlight d-flex align-items-center gap-3 p-3">
                <!-- Album Image -->
                ${track.album.image ? 
                    `<img src="${track.album.image}" alt="${track.album.name}" class="rounded shadow-sm" width="50" height="50">` :
                    `<div class="bg-secondary rounded" style="width: 50px; height: 50px;"></div>`
                }
                
                <!-- Track Details -->
                <div class="flex-grow-1">
                    <h6 class="mb-1 text-truncate">${track.name}</h6>
                    <small class="text-muted text-truncate d-block">${track.artists.join(', ')} • ${track.album.name}</small>
                </div>
                
                <!-- Playlist Dropdown -->
                <div class="dropdown">
                    <button class="btn btn-success btn-sm dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                        <i class="fas fa-plus"></i> Add
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end bg-dark border-secondary">
                        ${playlists.map(playlist => `
                            <li>
                                <button class="dropdown-item text-light hover-highlight py-2" 
                                        onclick="addTrackToPlaylist('${track.id}', '${playlist.id}')">
                                    <i class="fas fa-music me-2"></i>${playlist.name}
                                </button>
                            </li>
                        `).join('')}
                        <li><hr class="dropdown-divider border-secondary"></li>
                        <li>
                            <button class="dropdown-item text-light hover-highlight py-2" 
                                    onclick="previewTrack('${track.id}', '${track.preview_url || ''}')">
                                <i class="fas fa-play me-2"></i>Preview
                            </button>
                        </li>
                    </ul>
                </div>
            </div>
        `;
    }

    // Add track to playlist function
    window.addTrackToPlaylist = async function(trackId, playlistId) {
        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const formData = new FormData();
            formData.append('track_id', trackId);
            formData.append('playlist_id', playlistId);
            
            const response = await fetch(`/playlists/${playlistId}/tracks/add/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });
            
            const data = await response.json();
            if (response.ok) {
                PyJams.showSuccess(data.message || 'Track added successfully');
            } else {
                throw new Error(data.error || 'Failed to add track');
            }
        } catch (error) {
            PyJams.showError(error.message || 'Failed to add track');
        }
    };

    // Add track preview functionality
    window.previewTrack = function(trackId, previewUrl) {
        if (!previewUrl) {
            PyJams.showWarning("No preview available for this track");
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
            PyJams.showError("Failed to play preview");
            console.error("Audio play error:", error);
        });
    }

    // Setup search input event listeners
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            if (query.length < 2) {
                if (searchResults) searchResults.style.display = 'none';
                return;
            }

            searchTimeout = setTimeout(async () => {
                try {
                    searchSpinner?.classList.remove('d-none');
                    const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`);
                    const data = await response.json();
                    
                    if (searchResults) {
                        searchResults.innerHTML = data.tracks.map(track => 
                            renderTrackItem(track, data.playlists)
                        ).join('');
                        
                        searchResults.style.display = 'block';
                        
                        // Initialize dropdowns
                        document.querySelectorAll('.dropdown-toggle').forEach(dropdown => {
                            new bootstrap.Dropdown(dropdown);
                        });
                    }
                    
                } catch (error) {
                    console.error('Error:', error);
                    if (searchResults) {
                        searchResults.innerHTML = `
                            <div class="list-group-item bg-dark text-light text-center py-4">
                                <i class="fas fa-exclamation-circle fa-2x mb-3 text-danger"></i>
                                <p class="mb-0">Error searching tracks</p>
                            </div>`;
                    }
                } finally {
                    searchSpinner?.classList.add('d-none');
                }
            }, 300);
        });
    }

    // Hide results when clicking outside - Fix for null check
    document.addEventListener('click', function(e) {
        // Only run this code if both searchInput and searchResults exist
        if (searchInput && searchResults) {
            // Check if the click is outside both elements
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.style.display = 'none';
            }
        }
    });
});