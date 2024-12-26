import time
from typing import Any

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth


class TokenError(Exception):
    """Raised when there are issues with the Spotify token."""
    def __init__(self, message: str, should_logout: bool = True):
        self.message = message
        self.should_logout = should_logout
        super().__init__(message)


class SpotifySessionManager:
    """Manages Spotify authentication tokens in Django session."""
    
    def __init__(self, session: SessionBase):
        self.session = session
        
    def get_token(self) -> dict[str, Any] | None:
        """Get stored token info from session."""
        return self.session.get('spotify_token')
        
    def store_token(self, token_info: dict[str, Any]) -> None:
        """Store token info in session with validation."""
        if not isinstance(token_info, dict):
            raise TokenError("Invalid token format")
            
        required = {'access_token', 'refresh_token', 'expires_at', 'scope'}
        if not all(k in token_info for k in required):
            raise TokenError("Missing required token fields")
            
        # Ensure expires_at is an integer
        try:
            token_info['expires_at'] = int(float(token_info['expires_at']))
        except (TypeError, ValueError):
            token_info['expires_at'] = int(time.time()) + 3600
            
        self.session['spotify_token'] = token_info
        self.session.modified = True


def get_spotify_auth(request=None) -> SpotifyOAuth:
    """Get configured SpotifyOAuth instance.
    
    Args:
        request: Optional Django request object for state management
        
    Returns:
        SpotifyOAuth: Configured auth instance
    """
    import secrets
    
    # Generate/retrieve state parameter
    state = None
    if request:
        state = request.session.get('spotify_state')
        if not state:
            state = secrets.token_urlsafe(32)
            request.session['spotify_state'] = state
            request.session.modified = True
    
    redirect_uri = settings.SPOTIFY_REDIRECT_URI.rstrip('/')
    
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=redirect_uri,
        scope=' '.join([
            'playlist-modify-public',
            'playlist-modify-private',
            'user-read-private',
            'user-read-email'
        ]),
        cache_path=None,
        show_dialog=True,
        state=state
    )


def get_spotify(session: SessionBase) -> Spotify:
    """Get authenticated Spotify client from session.
    
    Args:
        session: Django session instance
        
    Returns:
        Spotify: Authenticated client
        
    Raises:
        TokenError: If token is invalid or missing
    """
    manager = SpotifySessionManager(session)
    token_info = manager.get_token()
    
    if not token_info:
        raise TokenError("No valid token found", should_logout=True)
    
    return Spotify(auth=token_info['access_token'])


def get_playlist_info(spotify: Spotify, playlist_id: str) -> tuple[dict, dict]:
    """Get playlist and its tracks.
    
    Args:
        spotify: Authenticated Spotify client
        playlist_id: Spotify playlist ID
        
    Returns:
        Tuple containing playlist info and tracks
    """
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(playlist_id)
    return playlist, tracks


def verify_spotify_state(request, state):
    """Verify the state parameter to prevent CSRF attacks."""
    stored_state = request.session.get('spotify_state')
    if not stored_state or stored_state != state:
        raise TokenError("State verification failed", should_logout=True)
    del request.session['spotify_state']


def refresh_token_if_expired(request) -> None:
    """Refresh the Spotify token if expired.
    
    Args:
        request: Django request object
        
    Raises:
        TokenError: If refresh fails
    """
    manager = SpotifySessionManager(request.session)
    token_info = manager.get_token()
    
    if not token_info:
        raise TokenError("No token found", should_logout=True)

    sp_oauth = get_spotify_auth(request)
    if sp_oauth.is_token_expired(token_info):
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            manager.store_token(token_info)
        except Exception as e:
            raise TokenError(f"Failed to refresh token: {e}", should_logout=True)
