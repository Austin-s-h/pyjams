from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from spotipy import Spotify


class SpotifyAuthenticationBackend(BaseBackend):
    def authenticate(self, request, access_token=None):
        if not access_token:
            return None
            
        spotify = Spotify(auth=access_token)
        try:
            spotify_user = spotify.current_user()
            user, created = User.objects.get_or_create(
                username=spotify_user['id'],
                defaults={
                    'email': spotify_user.get('email', ''),
                    'first_name': spotify_user.get('display_name', '')
                }
            )
            return user
        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
