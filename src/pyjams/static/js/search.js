let searchTimeout;
const searchInput = document.getElementById('searchInput');
const searchResults = document.getElementById('searchResults');
const resultsLoading = document.querySelector('.results-loading');
const resultsContent = document.querySelector('.results-content');

// Hide loading and results initially
searchResults.style.display = 'none';
resultsLoading.style.display = 'none';

searchInput.addEventListener('input', function(e) {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim();
    const searchContainer = searchInput.closest('.search-container');
    
    // Clear results if query is too short
    if (query.length < 3) {
        searchContainer.classList.remove('is-searching');
        searchResults.style.display = 'none';
        resultsLoading.style.display = 'none';
        return;
    }

    // Show search interface
    searchContainer.classList.add('is-searching');
    searchResults.style.display = 'block';
    resultsLoading.style.display = 'flex';
    resultsContent.style.display = 'none';

    searchTimeout = setTimeout(() => {
        fetch(`/api/search_tracks?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                resultsLoading.style.display = 'none';
                resultsContent.style.display = 'block';
                
                if (data.tracks && data.tracks.length > 0) {
                    resultsContent.innerHTML = data.tracks.map(track => `
                        <div class="search-result-item">
                            <img src="${track.album.image}" alt="${track.name}" class="result-image">
                            <div class="result-info">
                                <div class="result-name">${track.name}</div>
                                <div class="result-artist">${track.artists.join(', ')}</div>
                            </div>
                            <button onclick="addToPublicPlaylist('${track.id}')" class="add-result-btn">
                                <i class="fas fa-plus"></i>
                            </button>
                        </div>
                    `).join('');
                } else {
                    resultsContent.innerHTML = '<div class="no-results">No tracks found</div>';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resultsLoading.style.display = 'none';
                resultsContent.innerHTML = '<div class="search-error">Error searching tracks</div>';
            });
    }, 300);
});

// Update click outside handler
document.addEventListener('click', function(e) {
    const searchContainer = searchInput.closest('.search-container');
    if (!searchResults.contains(e.target) && !searchInput.contains(e.target)) {
        searchContainer.classList.remove('is-searching');
        searchResults.classList.remove('active');
    }
});

// Add focus handler
searchInput.addEventListener('focus', function() {
    if (this.value.length >= 2) {
        const searchContainer = this.closest('.search-container');
        searchContainer.classList.add('is-searching');
        searchResults.classList.add('active');
    }
});

function refreshPlaylistEmbed() {
    const playlistFrame = document.querySelector('.playlist-embed-container iframe');
    if (playlistFrame) {
        playlistFrame.style.opacity = '0';
        playlistFrame.src = playlistFrame.src;
        playlistFrame.onload = () => {
            setTimeout(() => {
                playlistFrame.style.opacity = '1';
                updatePlaylistStats();
            }, 100);
        };
    }
}

function addToPublicPlaylist(trackId) {
    fetch(addSongUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `track_id=${trackId}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            alert(data.message);
            refreshPlaylistEmbed();
        }
    })
    .catch(error => {
        alert('Error adding song to playlist');
    });
}

function updatePlaylistStats() {
    const playlistId = document.querySelector('.playlist-embed-container iframe')?.src.split('/playlist/')[1]?.split('?')[0];
    if (playlistId) {
        fetch(`/api/playlist_stats/${playlistId}`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('followerCount').textContent = data.followers;
                document.getElementById('trackCount').textContent = data.track_count;
                document.getElementById('totalDuration').textContent = data.duration;
            })
            .catch(console.error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updatePlaylistStats();
});
