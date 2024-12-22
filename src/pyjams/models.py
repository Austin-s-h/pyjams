import os
from datetime import datetime

from pydantic import Field as PydanticField
from pydantic_settings import BaseSettings
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


class Settings(BaseSettings):
    """Application settings."""

    SPOTIFY_CLIENT_ID: str = PydanticField(..., description="Spotify API client ID")
    SPOTIFY_CLIENT_SECRET: str = PydanticField(..., description="Spotify API client secret")
    SPOTIFY_ADMIN_USERNAME: str = PydanticField(..., description="Spotify admin user ID")
    PUBLIC_PLAYLIST_ID: str = PydanticField("", description="Current public playlist ID")
    SECRET_KEY: str = PydanticField(default_factory=lambda: os.urandom(24).hex())
    BASE_URL: str = "http://127.0.0.1:4884"
    DATABASE_URL: str = "sqlite:///pyjams.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


class Admin(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Playlist(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str
    is_active: bool = Field(default=False)
    admin_id: int = Field(foreign_key="admin.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PublicPlaylist(SQLModel, table=True):
    """Model for public playlists that can be managed by users."""

    id: int | None = Field(default=None, primary_key=True)
    spotify_id: str = Field(unique=True, index=True)
    name: str = Field()
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: str = Field(foreign_key="admin.spotify_id")
    is_active: bool = Field(default=True)

    # Relationships
    managers: list["PlaylistManager"] = Relationship(back_populates="playlist")


class PlaylistManager(SQLModel, table=True):
    """Model for users who can manage a public playlist."""

    id: int | None = Field(default=None, primary_key=True)
    playlist_id: int = Field(foreign_key="publicplaylist.id")
    user_id: str = Field(foreign_key="admin.spotify_id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    # Relationships
    playlist: PublicPlaylist = Relationship(back_populates="managers")


# Database setup
engine = create_engine(settings.DATABASE_URL)


def get_session():
    with Session(engine) as session:
        yield session


def init_spotify_oauth() -> SpotifyOAuth:
    """Initialize Spotify OAuth instance."""
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=f"{settings.BASE_URL}/callback",  # Use configured base URL
        scope=[
            "playlist-modify-public",
            "playlist-modify-private",
            "playlist-read-private",
            "playlist-read-collaborative",
            "user-read-private",
            "user-read-email",
        ],
    )


class TokenError(Exception):
    """Raised when there are issues with the Spotify token."""

    pass


async def get_spotify(session) -> Spotify:
    """Get authenticated Spotify client."""
    if "token_info" not in session:
        raise TokenError("No token info in session")

    token_info = session["token_info"]

    # Validate token info structure
    if not isinstance(token_info, dict) or "access_token" not in token_info:
        raise TokenError("Invalid token info structure")

    # Check if token is expired
    oauth = init_spotify_oauth()
    if oauth.is_token_expired(token_info):
        try:
            token_info = oauth.refresh_access_token(token_info["refresh_token"])
            session["token_info"] = token_info
        except Exception as e:
            raise TokenError(f"Failed to refresh token: {e!s}")

    return Spotify(auth=token_info["access_token"])
