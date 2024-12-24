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
    """Get SpotifyOAuth instance with dynamic redirect URI.
    
    If request is provided, uses the request host to build the callback URL.
    Otherwise falls back to settings.SPOTIFY_REDIRECT_URI.
    """
    redirect_uri = settings.SPOTIFY_REDIRECT_URI
    
    if request:
        # Build callback URL using request host
        scheme = request.scheme
        host = request.get_host()
        path = reverse('pyjams:spotify_callback')
        redirect_uri = f"{scheme}://{host}{path}"

    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=redirect_uri,
        scope='playlist-modify-public playlist-modify-private user-read-private user-read-email'
    )

def get_spotify(session):
    """Get an authenticated Spotify client from the session."""
    token_info = session.get('spotify_token')
    if not token_info:
        raise ValueError("No Spotify token found in session")
    
    return Spotify(auth=token_info['access_token'])

def get_playlist_info(spotify, playlist_id):
    """Get playlist and its tracks."""
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(playlist_id)
    return playlist, tracks
