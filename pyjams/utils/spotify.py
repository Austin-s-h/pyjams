from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from django.conf import settings


class TokenError(Exception):
    """Raised when there are issues with the Spotify token."""
    def __init__(self, message: str, should_logout: bool = True):
        self.message = message
        self.should_logout = should_logout
        super().__init__(message)


def get_spotify_oauth():
    """Create SpotifyOAuth object with configured settings."""
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=settings.SPOTIFY_SCOPE
    )

def get_spotify_oauth_url() -> str:
    """Get the Spotify OAuth login URL."""
    sp_oauth = get_spotify_oauth()
    return sp_oauth.get_authorize_url()

def get_spotify(session: dict) -> spotipy.Spotify:
    """Create authenticated Spotify client from session tokens."""
    token_info = session.get('token_info')
    if not token_info:
        raise TokenError("No Spotify token found in session. Please log in again.")
    
    return spotipy.Spotify(auth=token_info['access_token'])


def get_playlist_info(spotify: spotipy.Spotify, playlist_id: str) -> tuple[dict, dict]:
    """Fetch playlist details and tracks from Spotify API."""
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(
        playlist_id,
        fields="items(track(id,name,artists(name),album(name,images),duration_ms))"
    )
    return playlist, tracks
