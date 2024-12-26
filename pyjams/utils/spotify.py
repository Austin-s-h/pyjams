import spotipy
from django.conf import settings
from django.contrib import messages
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from django.urls import reverse


class TokenError(Exception):
    """Raised when there are issues with the Spotify token."""
    def __init__(self, message: str, should_logout: bool = True):
        self.message = message
        self.should_logout = should_logout
        super().__init__(message)


def get_spotify_auth(request=None):
    """Get SpotifyOAuth instance with proper settings."""
    auth = SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI.rstrip('/'),  # Ensure no trailing slash
        scope='playlist-modify-public playlist-modify-private user-read-private user-read-email',
        cache_path=None,  # Don't use file cache
        show_dialog=True  # Always show auth dialog
    )
    return auth

def get_spotify(session):
    """Get authenticated Spotify client from session data."""
    from spotipy import Spotify
    
    token_info = session.get('spotify_token')
    if not token_info or not isinstance(token_info, dict):
        raise TokenError("No valid token found", should_logout=True)
        
    required_keys = {'access_token', 'refresh_token', 'expires_at'}
    if not all(key in token_info for key in required_keys):
        raise TokenError("Incomplete token data", should_logout=True)
        
    return Spotify(auth=token_info['access_token'])

def get_playlist_info(spotify, playlist_id):
    """Get playlist and its tracks."""
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(playlist_id)
    return playlist, tracks

def verify_spotify_state(request, state):
    """Verify the state parameter to prevent CSRF attacks."""
    stored_state = request.session.get('spotify_state')
    if not stored_state or stored_state != state:
        raise TokenError("State verification failed", should_logout=True)
    del request.session['spotify_state']

def refresh_token_if_expired(request):
    """Refresh the Spotify token if expired."""
    token_info = request.session.get('spotify_token')
    if not token_info:
        raise TokenError("No token found", should_logout=True)

    sp_oauth = get_spotify_auth(request)
    if sp_oauth.is_token_expired(token_info):
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            request.session['spotify_token'] = token_info
        except Exception as e:
            raise TokenError(f"Failed to refresh token: {e}", should_logout=True)
