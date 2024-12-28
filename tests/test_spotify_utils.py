import time
from unittest.mock import Mock, patch

import pytest
from django.contrib.sessions.backends.base import SessionBase

from pyjams.utils.spotify import SpotifySessionManager, TokenError, get_spotify


@pytest.fixture
def mock_session():
    session = Mock(spec=SessionBase)
    session._session = {}

    # Create mock methods that directly manipulate _session
    session.__getitem__ = Mock(side_effect=session._session.__getitem__)
    session.__setitem__ = Mock(side_effect=session._session.__setitem__)
    session.get = Mock(side_effect=session._session.get)

    return session


@pytest.fixture
def valid_token():
    return {
        "access_token": "valid_token",
        "refresh_token": "refresh_token",
        "expires_in": 3600,
        "expires_at": int(time.time()) + 3600,
    }


@pytest.fixture
def expired_token():
    return {
        "access_token": "expired_token",
        "refresh_token": "refresh_token",
        "expires_in": 3600,
        "expires_at": int(time.time()) - 3600,
    }


class TestSpotifySessionManager:
    def test_store_token_validates_format(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        with pytest.raises(TokenError):
            manager.store_token("invalid_token_format")

    def test_store_token_adds_expiry(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        token = {"access_token": "test", "expires_in": 3600}
        manager.store_token(token)
        stored = manager.get_token()
        assert "expires_at" in stored
        assert stored["expires_at"] > int(time.time())

    def test_is_token_expired(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        future = int(time.time()) + 3600
        past = int(time.time()) - 3600

        assert not manager.is_token_expired({"expires_at": future})
        assert manager.is_token_expired({"expires_at": past})

    def test_is_token_expired_with_no_expiry(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        token = {"access_token": "test"}
        assert manager.is_token_expired(token)

    def test_is_token_expired_with_invalid_expiry(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        token = {"access_token": "test", "expires_at": "invalid"}
        assert manager.is_token_expired(token)

    def test_get_token_with_no_token(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        assert manager.get_token() is None

    def test_store_token_requires_access_token(self, mock_session):
        manager = SpotifySessionManager(mock_session)
        with pytest.raises(TokenError, match="Invalid token format"):
            manager.store_token({"expires_in": 3600})


@patch("pyjams.utils.spotify.spotipy.Spotify")
class TestGetSpotify:
    def test_get_spotify_with_valid_token(self, mock_spotify, mock_session, valid_token):
        mock_session._session["spotify_token"] = valid_token
        _ = get_spotify(mock_session)
        mock_spotify.assert_called_once_with(auth=valid_token["access_token"])

    def test_get_spotify_with_no_token(self, mock_spotify, mock_session):
        with pytest.raises(TokenError):
            get_spotify(mock_session)

    @patch("pyjams.utils.spotify.get_spotify_auth")
    def test_get_spotify_refreshes_expired_token(self, mock_auth, mock_spotify, mock_session, expired_token):
        mock_session._session["spotify_token"] = expired_token
        new_token = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
            "expires_at": int(time.time()) + 3600,
        }

        mock_auth.return_value.refresh_access_token.return_value = new_token
        _ = get_spotify(mock_session)

        mock_spotify.assert_called_once_with(auth=new_token["access_token"])
        assert mock_session._session["spotify_token"] == new_token

    @patch("pyjams.utils.spotify.get_spotify_auth")
    def test_get_spotify_handles_refresh_failure(self, mock_auth, mock_spotify, mock_session, expired_token):
        mock_session._session["spotify_token"] = expired_token
        mock_auth.return_value.refresh_access_token.side_effect = Exception("Refresh failed")

        with pytest.raises(TokenError, match="Failed to initialize Spotify client"):
            get_spotify(mock_session)

    def test_get_spotify_with_none_session(self, mock_spotify):
        with pytest.raises(TokenError, match="No session available"):
            get_spotify(None)

    def test_get_spotify_with_invalid_token_format(self, mock_spotify, mock_session):
        mock_session._session["spotify_token"] = {"invalid": "format"}
        with pytest.raises(TokenError):
            get_spotify(mock_session)

    @patch("pyjams.utils.spotify.get_spotify_auth")
    def test_get_spotify_updates_token_on_refresh(self, mock_auth, mock_spotify, mock_session, expired_token):
        """Test that the session is updated with the new token after refresh"""
        mock_session._session["spotify_token"] = expired_token
        new_token = {"access_token": "refreshed_token", "refresh_token": "new_refresh", "expires_in": 3600}
        mock_auth.return_value.refresh_access_token.return_value = new_token

        get_spotify(mock_session)
        stored_token = mock_session._session["spotify_token"]
        assert stored_token["access_token"] == "refreshed_token"
        assert "expires_at" in stored_token
