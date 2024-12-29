from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from django.contrib import auth, messages
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from pyjams.models import FeaturedPlaylist, Permission, PlaylistManager
from pyjams.utils.messages import error, success
from pyjams.utils.spotify import (
    get_playlist_info,
    get_spotify,
    handle_spotify_callback,
    initiate_spotify_auth,
)

P = ParamSpec("P")
R = TypeVar("R")


def require_permissions(*permissions: Permission) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to check if user has all required permissions."""

    def decorator(view_func: Callable[P, R]) -> Callable[P, R]:
        @wraps(view_func)
        def _wrapped_view(*args: P.args, **kwargs: P.kwargs) -> R:
            request = args[0] if args else kwargs.get("request")
            if not request or not request.user.is_authenticated:
                return redirect("pyjams:spotify_login")
            if not request.user.has_permissions(*permissions):
                return HttpResponseForbidden("Insufficient permissions")

            return view_func(*args, **kwargs)

        return _wrapped_view

    return decorator


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    """Render index page with login or search interface."""
    playlists = []
    managed_playlists = []

    if request.user.is_authenticated:
        if not request.user.has_permissions(Permission.VIEW):
            return HttpResponseForbidden("Insufficient permissions")

        try:
            _ = get_spotify(request.session)
            playlists = FeaturedPlaylist.objects.filter(is_active=True)

            # Get playlists managed by current user
            managed_playlists = [
                p
                for p in playlists
                if PlaylistManager.objects.filter(playlist=p, user_id=request.user.spotify_id, is_active=True).exists()
            ]
        except Exception as e:
            print(f"Error fetching Spotify data: {e}")

    context = {
        "playlists": playlists,
        "managed_playlists": managed_playlists,
    }

    if request.headers.get("HX-Request"):
        return render(request, "components/playlist_list.html", context)
    return render(request, "index.html", context)


@require_permissions(Permission.VIEW)
@require_http_methods(["GET"])
def playlist_details(request: HttpRequest, playlist_id: str) -> HttpResponse:
    spotify = get_spotify(request.session)
    current_user = spotify.current_user()

    playlist, tracks = get_playlist_info(spotify, playlist_id)
    public_playlist = FeaturedPlaylist.objects.get(spotify_id=playlist_id)

    managers = PlaylistManager.get_active_managers(public_playlist.id)

    total_ms = sum(item["track"]["duration_ms"] for item in tracks["items"] if item["track"])
    stats = {
        "followers": playlist["followers"]["total"],
        "track_count": len(tracks["items"]),
        "duration": f"{round(total_ms / (1000 * 60))} min",
    }

    return render(
        request,
        "playlist.html",
        {
            "playlist": playlist,
            "tracks": tracks["items"],
            "current_user": current_user,
            "public_playlist": public_playlist,
            "playlist_managers": managers,
            "is_manager": any(m.user_id == current_user["id"] for m in managers),
            "stats": stats,
        },
    )


@require_permissions(Permission.MANAGE_PLAYLIST)
@require_http_methods(["POST"])
def create_playlist(request: HttpRequest) -> JsonResponse:
    """Create a new playlist."""
    spotify = get_spotify(request.session)
    name = request.POST.get("name")
    description = request.POST.get("description", "")

    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)

    try:
        user_id = spotify.current_user()["id"]
        playlist = spotify.user_playlist_create(user_id, name, public=True, description=description)
        success(request, "Playlist created successfully!")
        return JsonResponse({"playlist": playlist})
    except Exception as e:
        error(request, f"Failed to create playlist: {e!s}")
        return JsonResponse({"error": str(e)}, status=400)


@require_permissions(Permission.MANAGE_PLAYLIST)
@require_http_methods(["POST"])
def add_track(request: HttpRequest) -> JsonResponse:
    """Add a track to a playlist."""
    spotify = get_spotify(request.session)
    track_id = request.POST.get("track_id")
    playlist_id = request.POST.get("playlist_id")

    if not all([track_id, playlist_id]):
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    try:
        spotify.playlist_add_items(playlist_id, [track_id])
        success(request, "Track added successfully!")
        # Render updated track list
        playlist, tracks = get_playlist_info(spotify, playlist_id)
        html = render_to_string(
            "components/track_list.html", {"tracks": tracks["items"], "is_manager": True}, request=request
        )
        return JsonResponse({"message": "Track added successfully", "html": html})
    except Exception as e:
        error(request, f"Failed to add track: {e!s}")
        return JsonResponse({"error": str(e)}, status=400)


@require_permissions(Permission.MANAGE_PLAYLIST)
@require_http_methods(["POST"])
def remove_track(request: HttpRequest) -> JsonResponse:
    """Remove a track from a playlist."""
    spotify = get_spotify(request.session)
    track_id = request.POST.get("track_id")
    playlist_id = request.POST.get("playlist_id")

    if not all([track_id, playlist_id]):
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    try:
        spotify.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])
        success(request, "Track removed successfully!")
        return JsonResponse({"message": "Track removed successfully"})
    except Exception as e:
        error(request, f"Failed to remove track: {e!s}")
        return JsonResponse({"error": str(e)}, status=400)


@require_permissions(Permission.SEARCH)
@require_http_methods(["GET"])
def search_tracks(request: HttpRequest) -> HttpResponse | JsonResponse:
    q = request.GET.get("q", "")
    if len(q) < 2:
        return render(request, "components/search_results.html", {"tracks": []})

    spotify = get_spotify(request.session)
    results = spotify.search(q=q, type="track", limit=5)

    tracks = [
        {
            "id": track["id"],
            "name": track["name"],
            "artists": [artist["name"] for artist in track["artists"]],
            "album": {
                "name": track["album"]["name"],
                "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
            },
            "duration_ms": track["duration_ms"],
            "preview_url": track.get("preview_url"),
        }
        for track in results["tracks"]["items"]
    ]

    if request.headers.get("HX-Request"):
        return render(request, "components/search_results.html", {"tracks": tracks})
    return JsonResponse({"tracks": tracks})


@require_http_methods(["GET"])
def privacy(request: HttpRequest) -> HttpResponse:
    """Render privacy policy page."""
    return render(request, "privacy.html")


@require_http_methods(["GET"])
def terms(request: HttpRequest) -> HttpResponse:
    """Render terms of service page."""
    return render(request, "terms.html")


@require_http_methods(["GET", "POST"])
def logout(request: HttpRequest) -> HttpResponse:
    """Logout user and clear session."""
    if request.user.is_authenticated:
        auth.logout(request)
        messages.success(request, "You have been logged out.")
    request.session.clear()
    return redirect("pyjams:index")


@require_http_methods(["GET"])
def spotify_login(request: HttpRequest) -> HttpResponse:
    """Initiate Spotify OAuth flow."""
    auth_url = initiate_spotify_auth(request)
    return redirect(auth_url)


@require_http_methods(["GET"])
def spotify_callback(request: HttpRequest) -> HttpResponse:
    """Handle Spotify OAuth callback."""
    code = request.GET.get("code")
    state = request.GET.get("state")

    if not code:
        messages.error(request, "Authorization failed: No code received")
        return redirect("pyjams:index")

    success, message = handle_spotify_callback(request, code, state)
    if success:
        messages.success(request, message)
    else:
        messages.error(request, f"Authentication failed: {message}")

    return redirect("pyjams:index")


@require_http_methods(["GET"])
def manage_playlists(request: HttpRequest) -> HttpResponse:
    """Consolidated view for playlist management."""
    context: dict[str, Any] = {
        "site_featured": None,
        "community_featured": [],
        "user_playlists": [],
        "available_playlists": [],
    }

    if request.user.is_authenticated:
        try:
            spotify = get_spotify(request.session)

            # Get featured playlists - viewable by all authenticated users
            context["site_featured"] = FeaturedPlaylist.get_site_featured()
            context["community_featured"] = FeaturedPlaylist.get_community_featured()

            # Get user's playlists if they can create featured playlists
            if request.user.has_permissions(Permission.CREATE_FEATURED):
                playlists = spotify.current_user_playlists()
                context["user_playlists"] = playlists["items"]

            # Get all playlists for admin site featuring
            if request.user.has_permissions(Permission.MANAGE_FEATURED):
                all_playlists = spotify.current_user_playlists()
                featured_ids = {p.spotify_id for p in context["community_featured"]}
                site_featured = context["site_featured"]
                if site_featured is not None:
                    featured_ids.add(site_featured.spotify_id)
                context["available_playlists"] = [p for p in all_playlists["items"] if p["id"] not in featured_ids]

        except Exception as e:
            error(request, f"Error loading playlists: {e!s}")

    return render(request, "manage_playlists.html", context)


@require_permissions(Permission.CREATE_FEATURED)
@require_http_methods(["POST"])
def feature_community_playlist(request: HttpRequest, playlist_id: str) -> HttpResponse:
    """Feature a playlist in the community section."""
    try:
        spotify = get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)

        # Check if user already has a featured playlist
        if FeaturedPlaylist.objects.filter(creator=request.user, featured_type="community", is_active=True).exists():
            error(request, "You already have a featured playlist")
            return redirect("pyjams:playlists")

        FeaturedPlaylist.objects.create(
            spotify_id=playlist_id,
            name=playlist["name"],
            description=playlist.get("description", ""),
            image_url=playlist["images"][0]["url"] if playlist["images"] else None,
            featured_type="community",
            creator=request.user,
            is_active=True,
        )
        success(request, f"'{playlist['name']}' is now featured in the community!")
    except Exception as e:
        error(request, f"Failed to feature playlist: {e!s}")

    return redirect("pyjams:playlists")


@require_permissions(Permission.MANAGE_FEATURED)
@require_http_methods(["POST"])
def feature_site_playlist(request: HttpRequest, playlist_id: str) -> HttpResponse:
    """Set the site-wide featured playlist."""
    try:
        # Deactivate current site featured playlist
        FeaturedPlaylist.objects.filter(featured_type="site", is_active=True).update(
            is_active=False, unfeatured_date=timezone.now()
        )

        spotify = get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)

        FeaturedPlaylist.objects.create(
            spotify_id=playlist_id,
            name=playlist["name"],
            description=playlist.get("description", ""),
            image_url=playlist["images"][0]["url"] if playlist["images"] else None,
            featured_type="site",
            creator=request.user,
            is_active=True,
        )
        success(request, f"'{playlist['name']}' is now the site featured playlist!")
    except Exception as e:
        error(request, f"Failed to feature playlist: {e!s}")

    return redirect("pyjams:playlists")


@require_permissions(Permission.ADMIN)
@require_http_methods(["POST"])
def feature_playlist(request: HttpRequest, playlist_id: str) -> HttpResponse:
    """Set a playlist as featured."""
    try:
        # Deactivate current featured playlist
        FeaturedPlaylist.objects.filter(is_active=True).update(is_active=False, unfeatured_date=timezone.now())

        # Create new featured playlist
        spotify = get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)

        FeaturedPlaylist.objects.create(
            spotify_id=playlist_id,
            name=playlist["name"],
            description=playlist.get("description", ""),
            image_url=playlist["images"][0]["url"] if playlist["images"] else None,
            featured_date=timezone.now(),
            is_active=True,
        )

        success(request, f"'{playlist['name']}' is now featured!")
    except Exception as e:
        error(request, f"Failed to feature playlist: {e!s}")

    return redirect("pyjams:manage_spotify")


@require_permissions(Permission.ADMIN)
@require_http_methods(["POST"])
def unfeature_playlist(request: HttpRequest, playlist_id: int) -> HttpResponse:
    """Remove a playlist from featured status."""
    try:
        playlist = FeaturedPlaylist.objects.get(id=playlist_id, is_active=True)
        playlist.is_active = False
        playlist.unfeatured_date = timezone.now()
        playlist.save()

        success(request, f"'{playlist.name}' has been removed from featured.")
    except FeaturedPlaylist.DoesNotExist:
        error(request, "Playlist not found or already unfeatured.")
    except Exception as e:
        error(request, f"Error unfeaturing playlist: {e!s}")

    return redirect("pyjams:manage_spotify")


@require_permissions(Permission.MANAGE_USERS)
@require_http_methods(["POST"])
def add_playlist_manager(request: HttpRequest, playlist_id: int) -> JsonResponse:
    """Add a new manager to a playlist."""
    user_id = request.POST.get("user_id")
    if not user_id:
        return JsonResponse({"error": "User ID is required"}, status=400)

    try:
        playlist = FeaturedPlaylist.objects.get(id=playlist_id, is_active=True)
        success, message = PlaylistManager.add_manager(playlist.id, user_id)
        if success:
            return JsonResponse({"message": message})
        return JsonResponse({"error": message}, status=400)
    except FeaturedPlaylist.DoesNotExist:
        return JsonResponse({"error": "Playlist not found"}, status=404)


@require_permissions(Permission.MANAGE_USERS)
@require_http_methods(["POST"])
def remove_playlist_manager(request: HttpRequest, playlist_id: int) -> JsonResponse:
    """Remove a manager from a playlist."""
    user_id = request.POST.get("user_id")
    if not user_id:
        return JsonResponse({"error": "User ID is required"}, status=400)

    success, message = PlaylistManager.remove_manager(playlist_id, user_id)
    if success:
        return JsonResponse({"message": message})
    return JsonResponse({"error": message}, status=400)


@require_permissions(Permission.MANAGE_USERS)
@require_http_methods(["GET"])
def get_playlist_managers(request: HttpRequest, playlist_id: int) -> JsonResponse:
    """Get all managers for a playlist."""
    try:
        managers = PlaylistManager.get_active_managers(playlist_id)
        return JsonResponse({"managers": [{"user_id": m.user_id, "added_date": m.added_date} for m in managers]})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
