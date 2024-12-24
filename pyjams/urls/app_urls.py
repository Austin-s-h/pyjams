from django.urls import path

from pyjams import views

app_name = 'pyjams'

urlpatterns = [
    path('', views.index, name='index'),
    path('playlist/<str:playlist_id>/', views.playlist_details, name='playlist_details'),
    path('playlists/', views.get_playlists, name='get_playlists'),
    path('playlist/<str:playlist_id>/details/', views.get_playlist, name='get_playlist'),
    path('playlist/create/', views.create_playlist, name='create_playlist'),
    path('track/add/', views.add_track, name='add_track'),
    path('track/remove/', views.remove_track, name='remove_track'),
    path('search/', views.search_tracks, name='search_tracks'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('logout/', views.logout, name='logout'),
    path('spotify/login/', views.spotify_login, name='spotify_login'),
    path('callback/', views.spotify_callback, name='spotify_callback'),
]
