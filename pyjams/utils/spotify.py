import time
from datetime import UTC, datetime
from typing import Any

import spotipy
from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth import authenticate, login


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
        token = self.session.get('spotify_token')
        if token and ('expires_at' not in token or token['expires_at'] is None):
            token['expires_at'] = int(time.time()) + token.get('expires_in', 3600)
        return token
        
    def store_token(self, token_info: dict[str, Any]) -> None:
        """Store token info in session with validation."""
        if not isinstance(token_info, dict):
            raise TokenError("Invalid token format")
            
        # Ensure expires_at is valid
        if 'expires_at' not in token_info or token_info['expires_at'] is None:
            token_info['expires_at'] = int(time.time()) + token_info.get('expires_in', 3600)
            
        self.session['spotify_token'] = token_info
        self.session.modified = True
        
    def is_token_expired(self, token_info: dict[str, Any]) -> bool:
        """Check if token is expired."""
        if 'expires_at' not in token_info:
            return False
        return datetime.fromtimestamp(token_info['expires_at'], UTC) <= datetime.now(UTC)


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


def get_spotify(session) -> spotipy.Spotify:
    """Get a configured Spotify client using session tokens."""
    try:
        if not session:
            raise TokenError("No session available", should_logout=True)
        
        manager = SpotifySessionManager(session)
        token_info = manager.get_token()
        
        if not token_info:
            raise TokenError("No Spotify tokens in session", should_logout=True)
        
        # Check if token is expired
        if manager.is_token_expired(token_info):
            # Refresh token
            spotify_oauth = get_spotify_auth()
            token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])
            manager.store_token(token_info)
        
        return spotipy.Spotify(auth=token_info['access_token'])
        
    except Exception as e:
        raise TokenError(f"Failed to initialize Spotify client: {str(e)}", should_logout=True)


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


def refresh_token_if_expired(request) -> None:
    """Refresh the Spotify token if expired.
    
    Args:
        request: Django request object
        
    Raises:
        TokenError: If refresh fails
    """
    try:
        manager = SpotifySessionManager(request.session)
        token_info = manager.get_token()
        
        if not token_info:
            raise TokenError("No token found", should_logout=True)

        sp_oauth = get_spotify_auth(request)
        
        if manager.is_token_expired(token_info):
            try:
                token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
                manager.store_token(token_info)
            except Exception as e:
                # Clear corrupted session data
                request.session.flush()
                raise TokenError(f"Failed to refresh token: {e}", should_logout=True)
                
    except Exception as e:
        request.session.flush()
        raise TokenError(f"Token refresh error: {str(e)}", should_logout=True)


def initiate_spotify_auth(request) -> str:
    """Start Spotify OAuth flow.
    
    Args:
        request: Django request object
        
    Returns:
        str: Authorization URL to redirect to
    """
    sp_oauth = get_spotify_auth(request)
    auth_url = sp_oauth.get_authorize_url()
    
    # Store state in session
    state = sp_oauth.state
    request.session['spotify_state'] = state
    request.session.modified = True
    
    return auth_url

def handle_spotify_callback(request, code: str, state: str) -> tuple[bool, str]:
    """Process Spotify OAuth callback and authenticate user.
    
    Args:
        request: Django request object
        code: Authorization code from Spotify
        state: State parameter for CSRF verification
        
    Returns:
        tuple[bool, str]: Success status and message
    """
    try:
        # Verify state
        verify_spotify_state(request, state)
        
        # Get token
        sp_oauth = get_spotify_auth(request)
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        
        # Store token in session
        manager = SpotifySessionManager(request.session)
        manager.store_token(token_info)
        
        # Authenticate user
        user = authenticate(
            request,
            access_token=token_info['access_token'],
            refresh_token=token_info['refresh_token'],
            expires_in=token_info['expires_in']
        )
        
        if not user:
            return False, "Authentication failed"
            
        login(request, user)
        return True, f"Welcome {user.spotify_display_name}!"
        
    except Exception as e:
        return False, str(e)

def verify_spotify_state(request, state: str) -> None:
    """Verify the state parameter from Spotify OAuth callback.
    
    Args:
        request: Django request object
        state: State parameter from callback
        
    Raises:
        TokenError: If state verification fails
    """
    stored_state = request.session.get('spotify_state')
    if not state or not stored_state or state != stored_state:
        raise TokenError("State verification failed", should_logout=True)
    
    # Clear state after verification    del request.session['spotify_state']    request.session.modified = Truedef verify_spotify_state(request, state: str) -> None:    """Verify the state parameter from Spotify OAuth callback.        Args:        request: Django request object        state: State parameter from callback            Raises:        TokenError: If state verification fails    """    stored_state = request.session.get('spotify_state')    if not state or not stored_state or state != stored_state:        raise TokenError("State verification failed", should_logout=True)        # Clear state after verification
    del request.session['spotify_state']
    request.session.modified = True
