import os
from datetime import datetime

from fastapi import HTTPException
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import Field, Session, SQLModel, create_engine


# Config
class Settings:
    SPOTIFY_CLIENT_ID: str = os.environ.get("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    ADMIN_USERNAME: str = os.environ.get("SPOTIFY_ADMIN_USERNAME", "")
    PUBLIC_PLAYLIST_ID: str = os.environ.get("SPOTIFY_PUBLIC_PLAYLIST_ID", "")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    BASE_URL: str = "http://127.0.0.1:4884"
    DATABASE_URL: str = "sqlite:///pyjams.db"


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


async def get_spotify(session: dict) -> Spotify:
    """Get or create Spotify API client."""
    if "token_info" not in session:
        raise HTTPException(status_code=401, detail="No token info found")

    oauth = init_spotify_oauth()
    token_info = session.get("token_info")

    if oauth.is_token_expired(token_info):
        token_info = oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info

    return Spotify(auth=token_info["access_token"])
