from django.contrib import admin
from django.urls import include, path

from pyjams import views

# Project-level URL patterns
urlpatterns = [
    path("admin/", admin.site.urls),
]

# Group routes by resource type
app_patterns = [
    path(
        "",
        include(
            (
                [
                    # Core pages
                    path("", views.index, name="index"),
                    path("privacy/", views.privacy, name="privacy"),
                    # Authentication
                    path("auth/spotify/", views.spotify_login, name="spotify_login"),
                    path("callback/", views.spotify_callback, name="spotify_callback"),
                    path("auth/logout/", views.logout, name="logout"),
                    path("profile/", views.profile, name="profile"),
                    # Playlists
                    path("playlists/", views.manage_playlists, name="playlists"),
                    path("playlists/create/", views.create_playlist, name="create_playlist"),
                    path("playlists/search/", views.search_playlists, name="search_playlists"),
                    path("playlists/<str:playlist_id>/", views.playlist_details, name="playlist_details"),
                    # Featured playlists
                    path(
                        "playlists/<str:playlist_id>/feature/site/",
                        views.feature_site_playlist,
                        name="feature_site_playlist",
                    ),
                    path(
                        "playlists/<str:playlist_id>/feature/community/",
                        views.feature_community_playlist,
                        name="feature_community_playlist",
                    ),
                    path("playlists/<int:playlist_id>/unfeature/", views.unfeature_playlist, name="unfeature_playlist"),
                    # Playlist managers
                    path(
                        "playlists/<int:playlist_id>/managers/",
                        views.get_playlist_managers,
                        name="get_playlist_managers",
                    ),
                    path(
                        "playlists/<int:playlist_id>/managers/add/",
                        views.add_playlist_manager,
                        name="add_playlist_manager",
                    ),
                    path(
                        "playlists/<int:playlist_id>/managers/remove/",
                        views.remove_playlist_manager,
                        name="remove_playlist_manager",
                    ),
                    # Search
                    path("search/", views.search, name="search"),
                    # Tracks
                    path("playlists/<str:playlist_id>/tracks/add/", views.add_track, name="add_track"),
                    path("playlists/<str:playlist_id>/tracks/remove/", views.remove_track, name="remove_track"),
                    path("tracks/search/", views.search_tracks, name="search_tracks"),
                ],
                "pyjams",
            )
        ),
    ),
]

urlpatterns += app_patterns
