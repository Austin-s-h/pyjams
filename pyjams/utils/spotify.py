import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import spotipy
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import AbstractUser
from django.contrib.sessions.backends.base import SessionBase
from django.http import HttpRequest
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Define User type properly for type checking
_UserModel = get_user_model()
User = cast(type[AbstractUser], _UserModel)


class SpotifyAuthenticationBackend(BaseBackend):
    def authenticate(
        self,
        request: HttpRequest | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        expires_in: int | None = None,
        **kwargs: Any,
    ) -> AbstractUser | None:
        if not access_token:
            return None

        spotify = Spotify(auth=access_token)
        try:
            spotify_user = spotify.current_user()

            # Store tokens in session
            if request and request.session:
                request.session["spotify_access_token"] = access_token
                request.session["spotify_refresh_token"] = refresh_token
                request.session["spotify_token_expires_at"] = (
                    (datetime.now(UTC) + timedelta(seconds=expires_in)).timestamp() if expires_in else None
                )

            user, created = User.objects.get_or_create(
                spotify_id=spotify_user["id"],
                defaults={
                    "username": spotify_user["id"],
                    "email": spotify_user.get("email", ""),
                    "spotify_display_name": spotify_user.get("display_name", ""),
                    "first_name": (
                        spotify_user.get("display_name", "").split()[0] if spotify_user.get("display_name") else ""
                    ),
                },
            )

            return user

        except Exception as e:
            print(f"Spotify authentication error: {e}")
            return None

    def get_user(self, user_id: int) -> AbstractUser | None:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


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

    def get_token(self) -> dict[str, Any]:
        """Get the stored token from the session.

        Raises:
            TokenError: If no valid token is found
        """
        if not self.session:
            raise TokenError("No session available")

        token = self.session.get("spotify_token")
        if not isinstance(token, dict):
            raise TokenError("Invalid token format in session")

        return token

    def store_token(self, token: dict[str, Any]) -> None:
        """Store the token in the session with expiry."""
        if not isinstance(token, dict) or "access_token" not in token:
            raise TokenError("Invalid token format")

        if "expires_at" not in token and "expires_in" in token:
            token["expires_at"] = int(time.time()) + int(token["expires_in"])

        if self.session:
            self.session["spotify_token"] = token

    def is_token_expired(self, token: dict[str, Any]) -> bool:
        """Check if the token is expired."""
        if not isinstance(token, dict):
            return True
        try:
            expiry = token.get("expires_at")
            if expiry is None:
                return True
            return int(expiry) < int(time.time())
        except (TypeError, ValueError, AttributeError):
            return True

    def refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Refresh an expired token.

        Args:
            token: The expired token dict

        Returns:
            The new token dict

        Raises:
            TokenError: If refresh fails
        """
        if not isinstance(token, dict):
            raise TokenError("Invalid token format")

        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise TokenError("No refresh token available")

        spotify_oauth = get_spotify_auth()
        new_token = spotify_oauth.refresh_access_token(refresh_token)
        if not new_token:
            raise TokenError("Failed to refresh token")

        self.store_token(new_token)
        return new_token


def get_spotify_auth(request: HttpRequest | None = None) -> SpotifyOAuth:
    """Get configured SpotifyOAuth instance."""
    import secrets

    state = None
    if request and request.session:
        if "spotify_state" not in request.session:
            state = secrets.token_urlsafe(32)
            request.session["spotify_state"] = state
            request.session["state_timestamp"] = int(time.time())
            request.session.modified = True
        else:
            # Check state age (5 minute timeout)
            timestamp = request.session.get("state_timestamp", 0)
            if int(time.time()) - timestamp > 300:
                state = secrets.token_urlsafe(32)
                request.session["spotify_state"] = state
                request.session["state_timestamp"] = int(time.time())
                request.session.modified = True
            else:
                state = request.session["spotify_state"]

    redirect_uri = settings.SPOTIFY_REDIRECT_URI.rstrip("/")

    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=redirect_uri,
        scope=" ".join(["playlist-modify-public", "playlist-modify-private", "user-read-private", "user-read-email"]),
        cache_path=None,
        show_dialog=True,
        state=state,
    )


def get_spotify(session: SessionBase | None) -> spotipy.Spotify:
    """Get a configured Spotify client using session tokens."""
    try:
        if not session:
            raise TokenError("No session available", should_logout=True)

        manager = SpotifySessionManager(session)
        try:
            token_info = manager.get_token()
        except TokenError:
            raise TokenError("No Spotify tokens in session", should_logout=True)

        # Check if token is expired
        if manager.is_token_expired(token_info):
            # Refresh token
            spotify_oauth = get_spotify_auth()
            refresh_token = token_info.get("refresh_token")
            if not refresh_token:
                raise TokenError("No refresh token available", should_logout=True)

            new_token_info = spotify_oauth.refresh_access_token(refresh_token)
            if not new_token_info:
                raise TokenError("Failed to refresh token", should_logout=True)

            manager.store_token(new_token_info)
            token_info = new_token_info

        access_token = token_info.get("access_token")
        if not access_token:
            raise TokenError("No access token available", should_logout=True)

        return spotipy.Spotify(auth=access_token)

    except Exception as e:
        raise TokenError(f"Failed to initialize Spotify client: {e!s}", should_logout=True)


def get_playlist_info(spotify: Spotify, playlist_id: str) -> tuple[dict, dict]:  # type: ignore
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


def refresh_token_if_expired(request: HttpRequest) -> None:
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
                new_token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
                if new_token_info is None:
                    raise TokenError("Failed to refresh token", should_logout=True)
                manager.store_token(new_token_info)
            except Exception as e:
                request.session.flush()
                raise TokenError(f"Failed to refresh token: {e}", should_logout=True)

    except Exception as e:
        request.session.flush()
        raise TokenError(f"Token refresh error: {e!s}", should_logout=True)


def initiate_spotify_auth(request: HttpRequest) -> str:
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
    request.session["spotify_state"] = state
    request.session.modified = True

    return auth_url


def handle_spotify_callback(request: HttpRequest, code: str, state: str) -> tuple[bool, str]:
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
            access_token=token_info["access_token"],
            refresh_token=token_info["refresh_token"],
            expires_in=token_info["expires_in"],
        )

        if not user:
            return False, "Authentication failed"

        login(request, user)
        return True, f"Welcome {user.spotify_display_name}!"

    except Exception as e:
        return False, str(e)


def verify_spotify_state(request: HttpRequest, state: str) -> None:
    """Verify the state parameter from Spotify OAuth callback."""
    stored_state = request.session.get("spotify_state")
    stored_timestamp = request.session.get("state_timestamp", 0)

    if not state or not stored_state or state != stored_state:
        raise TokenError("State verification failed", should_logout=True)

    if int(time.time()) - stored_timestamp > 300:  # 5 minute timeout
        raise TokenError("State token expired", should_logout=True)

    # Clean up after verification
    del request.session["spotify_state"]
    del request.session["state_timestamp"]
    request.session.modified = True
