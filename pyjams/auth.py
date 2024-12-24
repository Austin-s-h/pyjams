import spotipy
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from spotipy.oauth2 import SpotifyOAuth

from pyjams.settings import settings


class SpotifyAuthenticationBackend(BaseBackend):
    def authenticate(self, request, access_token=None):
        if not access_token:
            return None
            
        try:
            sp = spotipy.Spotify(auth=access_token)
            user_data = sp.current_user()
            
            try:
                user = User.objects.get(username=user_data['id'])
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=user_data['id'],
                    email=user_data.get('email', ''),
                    first_name=user_data.get('display_name', '').split()[0]
                )
                
            return user
        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

def get_spotify_auth():
    return SpotifyOAuth(
        client_id=settings.SPOTIFY_CLIENT_ID,
        client_secret=settings.SPOTIFY_CLIENT_SECRET,
        redirect_uri=settings.SPOTIFY_REDIRECT_URI,
        scope=' '.join([
            'user-read-private',
            'user-read-email',
            'playlist-read-private', 
            'playlist-modify-public',
            'playlist-modify-private'
        ])
    )
