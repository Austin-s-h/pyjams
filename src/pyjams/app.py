import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from pyjams.models import Admin, SQLModel, engine, get_session, get_spotify, init_spotify_oauth, settings

# Get the directory containing the current file
BASE_DIR = Path(__file__).resolve().parent

# FastAPI app setup
app = FastAPI()

# Update static files mounting
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Create database tables
SQLModel.metadata.create_all(engine)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
)


# Routes
@app.get("/")
async def index(request: Request):
    """Render index page with login or search interface."""
    if "token_info" not in request.session:
        return templates.TemplateResponse("login.html", {"request": request})

    try:
        spotify = await get_spotify(request.session)
        query = request.query_params.get("q", "")
        tracks = None

        if query:
            results = spotify.search(q=query, type="track", limit=12)
            tracks = results["tracks"]["items"] if results else None

        return templates.TemplateResponse("index.html", {"request": request, "tracks": tracks, "query": query})
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request})


@app.get("/auth")
async def auth():
    """Initialize Spotify OAuth login flow."""
    try:
        oauth = init_spotify_oauth()
        auth_url = oauth.get_authorize_url()
        return RedirectResponse(url=auth_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        request.session["token_info"] = token_info

        # Get and store user info
        spotify = Spotify(auth=token_info["access_token"])
        current_user = spotify.current_user()
        request.session["user_name"] = current_user["display_name"]

        # Set admin status if applicable
        if current_user["id"] == settings.ADMIN_USERNAME:
            request.session["admin"] = True
            session = next(get_session())
            admin = Admin(spotify_id=current_user["id"], name=current_user["display_name"])
            session.add(admin)
            session.commit()

        # Use absolute URL for redirect
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        print(f"Callback error: {e}")  # Add logging
        raise HTTPException(status_code=500, detail=str(e))


# API routes
@app.get("/api/search_tracks")
async def search_tracks(q: str, request: Request):
    if len(q) < 2:
        return {"tracks": []}

    try:
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
                    "album": {"image": track["album"]["images"][0]["url"] if track["album"]["images"] else None},
                }
                for track in results["tracks"]["items"]
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/add_song")
async def add_song(request: Request, track_id: str = Form(...)):
    try:
        spotify = await get_spotify(request.session)
        if not settings.PUBLIC_PLAYLIST_ID:
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
    except SpotifyException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/remove_song")
async def remove_song(request: Request, track_id: str = Form(...), playlist_id: str | None = Form(None)):
    try:
        spotify = await get_spotify(request.session)
        playlist_id = playlist_id or settings.PUBLIC_PLAYLIST_ID
        if not playlist_id:
            raise HTTPException(status_code=400, detail="No playlist specified")

        track = spotify.track(track_id)
        spotify.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

        return {"message": f'Removed "{track["name"]}" from the playlist', "track_id": track_id}
    except SpotifyException as e:
        raise HTTPException(status_code=400, detail=str(e))


# Admin routes
@app.get("/admin")
async def admin_panel(request: Request):
    spotify = await get_spotify(request.session)
    current_user = spotify.current_user()
    if current_user["id"] != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Unauthorized")

    playlists = spotify.user_playlists(current_user["id"])["items"]
    current_public_playlist = spotify.playlist(settings.PUBLIC_PLAYLIST_ID) if settings.PUBLIC_PLAYLIST_ID else None

    return templates.TemplateResponse(
        "admin.html", {"request": request, "playlists": playlists, "current_public_playlist": current_public_playlist}
    )


@app.post("/admin/set_public_playlist")
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
async def playlist_details(playlist_id: str, request: Request):
    try:
        spotify = await get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)
        tracks = spotify.playlist_tracks(playlist_id)
        return templates.TemplateResponse(
            "playlist.html", {"request": request, "playlist": playlist, "tracks": tracks["items"]}
        )
    except SpotifyException as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/playlist_stats/{playlist_id}")
async def playlist_stats(playlist_id: str, request: Request):
    try:
        spotify = await get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)
        tracks = spotify.playlist_tracks(playlist_id)

        total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
        total_minutes = round(total_ms / (1000 * 60))

        return {
            "followers": playlist["followers"]["total"],
            "track_count": playlist["tracks"]["total"],
            "duration": f"{total_minutes} min",
        }
    except SpotifyException as e:
        raise HTTPException(status_code=400, detail=str(e))
