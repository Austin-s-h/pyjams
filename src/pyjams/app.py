import os
from typing import Any

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth


class Config:
    """Application configuration class.

    Attributes:
        SPOTIFY_CLIENT_ID: Spotify API client ID
        SPOTIFY_CLIENT_SECRET: Spotify API client secret
        ADMIN_USERNAME: Username of admin account
        PUBLIC_PLAYLIST_ID: ID of public playlist
        SECRET_KEY: Flask secret key
        BASE_URL: Base URL of application
    """

    SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
    ADMIN_USERNAME = os.environ.get("SPOTIFY_ADMIN_USERNAME")
    PUBLIC_PLAYLIST_ID = os.environ.get("SPOTIFY_PUBLIC_PLAYLIST_ID")
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
    BASE_URL = "http://127.0.0.1:4884"


app = Flask(__name__)
app.config.from_object(Config)


def init_spotify_oauth() -> SpotifyOAuth:
    """Initialize Spotify OAuth handler.

    Returns:
        SpotifyOAuth: Configured OAuth handler

    Raises:
        SpotifyException: If client credentials are missing
    """
    if not all([app.config["SPOTIFY_CLIENT_ID"], app.config["SPOTIFY_CLIENT_SECRET"]]):
        raise SpotifyException(http_status=500, code=-1, msg="Missing Spotify client credentials")

    return SpotifyOAuth(
        client_id=app.config["SPOTIFY_CLIENT_ID"],
        client_secret=app.config["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=f"{app.config['BASE_URL']}/callback",
        scope="playlist-modify-public playlist-modify-private playlist-read-private",
        cache_path=None,
        show_dialog=True,
    )


def get_spotify() -> Spotify:
    """Get or create Spotify API client.

    Returns:
        Spotify: Authenticated Spotify client

    Raises:
        SpotifyException: If no token or invalid token
    """
    if not hasattr(g, "spotify"):
        oauth = init_spotify_oauth()
        token_info = session.get("token_info")

        if not token_info:
            raise SpotifyException(http_status=401, code=-1, msg="No token info found")

        if oauth.is_token_expired(token_info):
            token_info = oauth.refresh_access_token(token_info["refresh_token"])
            session["token_info"] = token_info

        g.spotify = Spotify(auth=token_info["access_token"])
    return g.spotify


@app.before_request
def before_request() -> None:
    """Set up request context with current user."""
    g.current_user = None
    if "token_info" in session:
        try:
            sp = get_spotify()
            g.current_user = sp.current_user()
        except SpotifyException:
            session.pop("token_info", None)
        except Exception as e:
            session.pop("token_info", None)
            app.logger.error(f"Unexpected error: {e}")


@app.context_processor
def utility_processor() -> dict[str, Any]:
    """Add utility variables to template context.

    Returns:
        Dict containing current_user and config
    """
    return {"current_user": getattr(g, "current_user", None), "config": app.config}


# Basic routes
@app.route("/")
def index() -> str:
    """Render index page with login or search interface."""
    if "token_info" not in session:
        return render_template("login.html")

    sp = get_spotify()
    query = request.args.get("q", "")
    tracks = None

    if query:
        results = sp.search(q=query, type="track", limit=12)
        tracks = results["tracks"]["items"] if results else None

    return render_template("index.html", tracks=tracks, query=query)


@app.route("/auth")
def auth() -> Any:
    """Initialize Spotify OAuth login flow."""
    try:
        auth = init_spotify_oauth()
        auth_url = auth.get_authorize_url()
        return redirect(auth_url)
    except Exception as e:
        return render_template("login.html", error=str(e))


@app.route("/callback")
def callback() -> str | Any:
    """Handle Spotify OAuth callback.

    Returns:
        Union[str, Any]: Redirect to index or error response
    """
    try:
        code = request.args.get("code")
        if not code:
            return redirect(url_for("index"))

        oauth = init_spotify_oauth()
        token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
        if not token_info:
            return redirect(url_for("index"))

        # Store token info in session
        session["token_info"] = token_info
        return redirect(url_for("index"))
    except Exception as e:
        app.logger.error(f"Callback error: {e}")
        return render_template("login.html", error="Authentication failed")


# Remove /search route since it's merged into index


# Keep essential API endpoints
@app.route("/api/search_tracks")
def search_tracks():
    """Quick search API endpoint."""
    if "token_info" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    query = request.args.get("q", "")
    if len(query) < 2:
        return jsonify({"tracks": []})

    try:
        sp = get_spotify()
        results = sp.search(q=query, type="track", limit=5)
        if not results or not results["tracks"]["items"]:
            return jsonify({"tracks": []})

        return jsonify(
            {
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
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/add_song", methods=["POST"])
def add_song() -> tuple:
    """Add a song to the public playlist.

    Returns:
        tuple: (JSON response, status code)

    Form Data:
        track_id: Spotify track ID

    Raises:
        SpotifyException: If add operation fails
    """
    try:
        if "token_info" not in session:
            return jsonify({"error": "Please login first"}), 401

        sp = get_spotify()
        track_id = request.form.get("track_id")

        if not track_id:
            return jsonify({"error": "Missing track_id"}), 400

        if not app.config["PUBLIC_PLAYLIST_ID"]:
            return jsonify({"error": "No public playlist configured"}), 400

        # Get track and playlist details
        track = sp.track(track_id)
        playlist = sp.playlist(app.config["PUBLIC_PLAYLIST_ID"])

        # Check if song already exists
        existing_tracks = sp.playlist_tracks(app.config["PUBLIC_PLAYLIST_ID"])
        if any(item["track"]["id"] == track_id for item in existing_tracks["items"]):
            return (
                jsonify({"message": f'"{track["name"]}" is already in the playlist'}),
                409,
            )

        # Add the track
        sp.playlist_add_items(app.config["PUBLIC_PLAYLIST_ID"], [track_id])
        return jsonify(
            {
                "message": f'Added "{track["name"]}" to {playlist["name"]}',
                "track": {
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "album": track["album"]["name"],
                    "image": (track["album"]["images"][0]["url"] if track["album"]["images"] else None),
                },
            }
        )
    except SpotifyException as e:
        return jsonify({"error": str(e)}), 400


@app.route("/remove_song", methods=["POST"])
def remove_song() -> tuple:
    """Remove a song from a playlist.

    Returns:
        tuple: (JSON response, status code)

    Form Data:
        track_id: Spotify track ID
        playlist_id: Optional playlist ID (defaults to public playlist)

    Raises:
        SpotifyException: If remove operation fails
    """
    try:
        if "token_info" not in session:
            return jsonify({"error": "Please login first"}), 401

        sp = get_spotify()
        track_id = request.form["track_id"]
        playlist_id = request.form.get("playlist_id", app.config["PUBLIC_PLAYLIST_ID"])

        if not playlist_id:
            return jsonify({"error": "No playlist specified"}), 400

        # Get track details for the response message
        track = sp.track(track_id)

        # Remove the track
        sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

        return jsonify({"message": f'Removed "{track["name"]}" from the playlist', "track_id": track_id})
    except SpotifyException as e:
        return jsonify({"error": str(e)}), 400


# Admin routes
@app.route("/admin")
def admin_panel() -> str | tuple:
    """Render admin control panel.

    Returns:
        Union[str, tuple]: Admin page or error response
    """
    if "token_info" not in session:
        return redirect(url_for("index"))

    sp = get_spotify()
    current_user = sp.current_user()

    if current_user["id"] != app.config["ADMIN_USERNAME"]:
        return jsonify({"error": "Unauthorized"}), 403

    return render_template(
        "admin.html",
        playlists=sp.user_playlists(current_user["id"])["items"],
        current_public_playlist=(
            sp.playlist(app.config["PUBLIC_PLAYLIST_ID"]) if app.config["PUBLIC_PLAYLIST_ID"] else None
        ),
    )


@app.route("/admin/set_public_playlist", methods=["POST"])
def set_public_playlist() -> tuple:
    """Set the public playlist for user contributions.

    Returns:
        tuple: (JSON response, status code)

    Form Data:
        playlist_id: Spotify playlist ID

    Raises:
        SpotifyException: If playlist update fails
    """
    try:
        if "token_info" not in session:
            return jsonify({"error": "Please login first"}), 401

        sp = get_spotify()
        current_user = sp.current_user()

        # Only allow admin access
        if current_user["id"] != app.config["ADMIN_USERNAME"]:
            return jsonify({"error": "Unauthorized"}), 403

        playlist_id = request.form.get("playlist_id")
        if not playlist_id:
            return jsonify({"error": "Missing playlist_id"}), 400

        # Store in environment variable
        os.environ["SPOTIFY_PUBLIC_PLAYLIST_ID"] = playlist_id
        app.config["PUBLIC_PLAYLIST_ID"] = playlist_id

        playlist = sp.playlist(playlist_id)
        return jsonify(
            {
                "message": f'Set public playlist to "{playlist["name"]}"',
                "playlist": {
                    "name": playlist["name"],
                    "id": playlist["id"],
                    "image": (playlist["images"][0]["url"] if playlist["images"] else None),
                },
            }
        )
    except SpotifyException as e:
        return jsonify({"error": str(e)}), 400


@app.route("/playlist/<playlist_id>")
def playlist_details(playlist_id: str) -> str | tuple:
    """Show detailed view of a playlist.

    Args:
        playlist_id: Spotify playlist ID

    Returns:
        Union[str, tuple]: Playlist details page or error response
    """
    if "token_info" not in session:
        return redirect(url_for("index"))

    try:
        sp = get_spotify()
        playlist = sp.playlist(playlist_id)
        tracks = sp.playlist_tracks(playlist_id)
        return render_template("playlist.html", playlist=playlist, tracks=tracks["items"])
    except SpotifyException as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/playlist_stats/<playlist_id>")
def playlist_stats(playlist_id):
    """Get playlist statistics.

    Returns follower count, track count, and total duration.
    """
    if "token_info" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    try:
        sp = get_spotify()
        playlist = sp.playlist(playlist_id)
        tracks = sp.playlist_tracks(playlist_id)

        # Calculate total duration in minutes
        total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
        total_minutes = round(total_ms / (1000 * 60))

        return jsonify(
            {
                "followers": playlist["followers"]["total"],
                "track_count": playlist["tracks"]["total"],
                "duration": f"{total_minutes} min",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.errorhandler(SpotifyException)
def handle_spotify_error(error: SpotifyException) -> tuple:
    """Handle Spotify API errors.

    Args:
        error: The SpotifyException that was raised

    Returns:
        tuple: (JSON error response, status code)
    """
    return jsonify({"error": str(error)}), error.http_status


if __name__ == "__main__":
    app.run(debug=True, port=4884)
