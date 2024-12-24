import spotipy
from django.conf import settings
from spotipy.oauth2 import SpotifyOAuth


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

def get_spotify(request: dict) -> spotipy.Spotify:
    """Get an authenticated Spotify client using credentials from Django settings."""
    cache_handler = spotipy.cache_handler.DjangoSessionCacheHandler(request)
    auth_manager = SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope='playlist-modify-public playlist-modify-private',
        cache_handler=cache_handler
    )
    
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        raise TokenError("Invalid or expired token. Please log in again.", should_logout=True)
        
    return spotipy.Spotify(auth_manager=auth_manager)

def get_playlist_info(spotify: spotipy.Spotify, playlist_id: str) -> tuple[dict, dict]:
    """Fetch playlist details and tracks from Spotify API."""
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(
        playlist_id,
        fields="items(track(id,name,artists(name),album(name,images),duration_ms))"
    )
    return playlist, tracks
