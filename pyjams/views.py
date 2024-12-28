from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from pyjams.models import FeaturedPlaylist, PlaylistManager
from pyjams.utils.messages import error, success
from pyjams.utils.spotify import (
    SpotifySessionManager,
    get_playlist_info,
    get_spotify,
    handle_spotify_callback,
    initiate_spotify_auth,
)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    """Render index page with login or search interface."""
    playlists = []
    managed_playlists = []

    if request.user.is_authenticated:
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


@login_required
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


@login_required
@require_http_methods(["GET"])
def get_playlists(request: HttpRequest) -> HttpResponse:
    """View to display user's playlists."""
    try:
        manager = SpotifySessionManager(request.session)
        token = manager.get_token()

        if not token:
            return redirect("pyjams:spotify_login")

        spotify = get_spotify(request.session)
        playlists = spotify.current_user_playlists()

        return render(request, "playlists.html", {"playlists": playlists["items"]})
    except Exception as e:
        messages.error(request, f"Error fetching playlists: {e!s}")
        return redirect("pyjams:index")


@login_required
@require_http_methods(["GET"])
def get_playlist(request: HttpRequest, playlist_id: str) -> JsonResponse:
    """Get a specific playlist by ID."""
    try:
        spotify = get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)
        return JsonResponse(playlist)
    except Exception as e:
        raise Http404(f"Playlist not found: {e!s}")


@login_required
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


@login_required
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


@login_required
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


@login_required
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


@user_passes_test(lambda u: u.is_staff)
def manage_spotify(request: HttpRequest) -> HttpResponse:
    """View for managing Spotify playlists."""
    try:
        spotify = get_spotify(request.session)
        
        # Get current user's playlists
        playlists = spotify.current_user_playlists()
        
        # Get currently featured playlist
        featured = FeaturedPlaylist.objects.filter(is_active=True).first()
        
        # Filter out already featured playlist from available ones
        available_playlists = [
            p for p in playlists['items']
            if not (featured and p['id'] == featured.spotify_id)
        ]
        
        return render(request, 'manage_spotify.html', {
            'featured_playlist': featured,
            'available_playlists': available_playlists,
        })
    except Exception as e:
        error(request, f"Error accessing Spotify: {str(e)}")
        return redirect('pyjams:index')

@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["POST"])
def feature_playlist(request: HttpRequest, playlist_id: str) -> HttpResponse:
    """Set a playlist as featured."""
    try:
        # Deactivate current featured playlist
        FeaturedPlaylist.objects.filter(is_active=True).update(
            is_active=False,
            unfeatured_date=timezone.now()
        )
        
        # Create new featured playlist
        spotify = get_spotify(request.session)
        playlist = spotify.playlist(playlist_id)
        
        FeaturedPlaylist.objects.create(
            spotify_id=playlist_id,
            name=playlist['name'],
            description=playlist.get('description', ''),
            image_url=playlist['images'][0]['url'] if playlist['images'] else None,
            featured_date=timezone.now(),
            is_active=True
        )
        
        success(request, f"'{playlist['name']}' is now featured!")
    except Exception as e:
        error(request, f"Failed to feature playlist: {str(e)}")
    
    return redirect('pyjams:manage_spotify')

@user_passes_test(lambda u: u.is_staff)
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
        error(request, f"Error unfeaturing playlist: {str(e)}")
    
    return redirect('pyjams:manage_spotify')
