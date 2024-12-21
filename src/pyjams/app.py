import os
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from pyjams.models import Admin, SQLModel, TokenError, engine, get_session, get_spotify, init_spotify_oauth, settings

# Get the directory containing the current file
BASE_DIR = Path(__file__).resolve().parent

# FastAPI app setup
app = FastAPI()

# Update static files mounting
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# Update template filter for current year
def get_current_year(input_value):
    """Template filter that returns the current year."""
    return datetime.now().year


templates.env.filters["current_year"] = get_current_year


# Flash message implementation
def get_flashed_messages(request: Request, with_categories=False) -> list[tuple[str, str]] | list[str]:
    """Get and clear flash messages from session."""
    messages = request.session.pop("flash_messages", [])
    if with_categories:
        return messages
    return [message for _, message in messages]


def flash(request: Request, message: str, category: str = "info"):
    """Add a flash message to the session."""
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append((category, message))


# Update Jinja2 environment
templates.env.globals["get_flashed_messages"] = get_flashed_messages

# Create database tables
SQLModel.metadata.create_all(engine)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
)


def spotify_error_handler(func: Callable):
    """Decorator to handle common Spotify API errors."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = next((arg for arg in args if isinstance(arg, Request)), kwargs.get("request"))
        if not request:
            raise ValueError("Request object not found in arguments")

        try:
            return await func(*args, **kwargs)
        except TokenError as te:
            print(f"TokenError: {te}")
            request.session.clear()
            return render_template(
                "error.html",
                {
                    "request": request,
                    "title": "Session Expired",
                    "message": "Your session has expired. Please log in again.",
                    "back_url": "/",
                },
            )
        except SpotifyException as e:
            return render_template(
                "error.html",
                {
                    "request": request,
                    "title": "Spotify Error",
                    "message": str(e),
                    "back_url": request.headers.get("referer", "/"),
                },
            )
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return render_template(
                "error.html",
                {
                    "request": request,
                    "title": "Unexpected Error",
                    "message": "Something went wrong. Please try again.",
                    "back_url": request.headers.get("referer", "/"),
                },
            )

    return wrapper


def render_template(template_name: str, context: dict):
    """Helper function to render templates with common context."""
    context["settings"] = settings
    context["get_flashed_messages"] = lambda **kwargs: get_flashed_messages(context["request"], **kwargs)
    return templates.TemplateResponse(template_name, context)


async def get_playlist_info(spotify: Spotify, playlist_id: str):
    """Helper function to get playlist details."""
    playlist = spotify.playlist(playlist_id)
    tracks = spotify.playlist_tracks(playlist_id)
    return playlist, tracks


# Routes
@app.get("/")
@spotify_error_handler
async def index(request: Request):
    """Render index page with login or search interface."""
    if "token_info" not in request.session:
        return render_template("login.html", {"request": request})

    spotify = await get_spotify(request.session)
    query = request.query_params.get("q", "")
    tracks = None

    if query:
        results = spotify.search(q=query, type="track", limit=12)
        tracks = results["tracks"]["items"] if results else None

    return render_template("index.html", {"request": request, "tracks": tracks, "query": query})


@app.get("/auth")
@spotify_error_handler
async def auth(request: Request):
    """Initialize Spotify OAuth login flow."""
    oauth = init_spotify_oauth()

    if "token_info" in request.session:
        token_info = request.session["token_info"]
        if not oauth.is_token_expired(token_info):
            return RedirectResponse(url="/")

        try:
            token_info = oauth.refresh_access_token(token_info["refresh_token"])
            request.session["token_info"] = token_info
            return RedirectResponse(url="/")
        except Exception as e:
            print(f"Token refresh error: {e}")
            request.session.pop("token_info", None)

    return RedirectResponse(url=oauth.get_authorize_url())


@app.get("/callback")
async def callback(code: str, request: Request):
    """Handle Spotify OAuth callback."""
    try:
        if not code:
            return RedirectResponse(url="/")

        oauth = init_spotify_oauth()
        token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
        if not token_info:
            return RedirectResponse(url="/")

        # Store token info in session
        request.session.clear()  # Clear any existing session data
        request.session["token_info"] = token_info

        # Get and store user info
        spotify = Spotify(auth=token_info["access_token"])
        current_user = spotify.current_user()
        request.session["user_name"] = current_user["display_name"]
        request.session["user_id"] = current_user["id"]  # Store user ID

        # Set admin status if applicable
        if current_user["id"] == settings.ADMIN_USERNAME:
            request.session["admin"] = True
            session = next(get_session())
            # Check if admin already exists
            admin = session.query(Admin).filter(Admin.spotify_id == current_user["id"]).first()
            if not admin:
                admin = Admin(spotify_id=current_user["id"], name=current_user["display_name"])
                session.add(admin)
                session.commit()

        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"Callback error: {e}")  # Add logging
        request.session.clear()
        return RedirectResponse(url="/", status_code=303)


@app.get("/api/search_tracks")
@spotify_error_handler
async def search_tracks(q: str, request: Request):
    if len(q) < 2:
        return {"tracks": []}

    spotify = await get_spotify(request.session)
    results = spotify.search(q=q, type="track", limit=5)
    if not results or not results["tracks"]["items"]:
        return {"tracks": []}

    return {
        "tracks": [
            {
                "id": track["id"],
                "name": track["name"],
                "artists": [artist["name"] for artist in track["artists"]],
                "album": {
                    "name": track["album"]["name"],
                    "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                },
                "duration_ms": track["duration_ms"],
            }
            for track in results["tracks"]["items"]
        ]
    }


@app.post("/add_song")
@spotify_error_handler
async def add_song(request: Request, track_id: str = Form(...)):
    spotify = await get_spotify(request.session)
    if not settings.PUBLIC_PLAYLIST_ID:
        flash(request, "No public playlist configured", "error")
        raise HTTPException(status_code=400, detail="No public playlist configured")

    track = spotify.track(track_id)
    playlist = spotify.playlist(settings.PUBLIC_PLAYLIST_ID)

    existing_tracks = spotify.playlist_tracks(settings.PUBLIC_PLAYLIST_ID)
    if any(item["track"]["id"] == track_id for item in existing_tracks["items"]):
        return JSONResponse(status_code=409, content={"message": f'"{track["name"]}" is already in the playlist'})

    spotify.playlist_add_items(settings.PUBLIC_PLAYLIST_ID, [track_id])
    return {
        "message": f'Added "{track["name"]}" to {playlist["name"]}',
        "track": {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "album": track["album"]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
        },
    }


@app.post("/remove_song")
@spotify_error_handler
async def remove_song(request: Request, track_id: str = Form(...), playlist_id: str | None = Form(None)):
    spotify = await get_spotify(request.session)
    playlist_id = playlist_id or settings.PUBLIC_PLAYLIST_ID
    if not playlist_id:
        raise HTTPException(status_code=400, detail="No playlist specified")

    track = spotify.track(track_id)
    spotify.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

    return {"message": f'Removed "{track["name"]}" from the playlist', "track_id": track_id}


# Admin routes
@app.get("/admin")
@spotify_error_handler
async def admin_panel(request: Request):
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()
    if current_user["id"] != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Unauthorized")

    playlists = spotify.user_playlists(current_user["id"])["items"]
    current_public_playlist = spotify.playlist(settings.PUBLIC_PLAYLIST_ID) if settings.PUBLIC_PLAYLIST_ID else None

    return render_template(
        "admin.html", {"request": request, "playlists": playlists, "current_public_playlist": current_public_playlist}
    )


@app.post("/admin/set_public_playlist")
@spotify_error_handler
async def set_public_playlist(request: Request, playlist_id: str = Form(...)):
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()
    if current_user["id"] != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        playlist = spotify.playlist(playlist_id)
        # Note: In a real app, you'd want to store this in a database instead
        os.environ["SPOTIFY_PUBLIC_PLAYLIST_ID"] = playlist_id
        settings.PUBLIC_PLAYLIST_ID = playlist_id

        return {
            "message": f'Set public playlist to "{playlist["name"]}"',
            "playlist": {
                "name": playlist["name"],
                "id": playlist["id"],
                "image": playlist["images"][0]["url"] if playlist["images"] else None,
            },
        }
    except SpotifyException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/playlist/{playlist_id}")
@spotify_error_handler
async def playlist_details(playlist_id: str, request: Request):
    spotify = await get_spotify(request.session)
    playlist, tracks = await get_playlist_info(spotify, playlist_id)
    current_user = spotify.current_user()

    return render_template(
        "playlist.html",
        {
            "request": request,
            "playlist": playlist,
            "tracks": tracks["items"],
            "current_user": current_user,
        },
    )


@app.get("/api/playlist_stats/{playlist_id}")
@spotify_error_handler
async def playlist_stats(playlist_id: str, request: Request):
    spotify = await get_spotify(request.session)
    playlist, tracks = await get_playlist_info(spotify, playlist_id)

    total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
    total_minutes = round(total_ms / (1000 * 60))

    return {
        "followers": playlist["followers"]["total"],
        "track_count": playlist["tracks"]["total"],
        "duration": f"{total_minutes} min",
    }


@app.get("/privacy")
async def privacy_policy(request: Request):
    """Render privacy policy page."""
    return render_template("privacy.html", {"request": request})
