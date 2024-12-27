from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from spotipy import Spotify

User = get_user_model()

class SpotifyAuthenticationBackend(BaseBackend):
    def authenticate(self, request, access_token=None, refresh_token=None, expires_in=None, **kwargs):
        if not access_token:
            return None
            
        spotify = Spotify(auth=access_token)
        try:
            spotify_user = spotify.current_user()
            
            # Store tokens in session
            if request and request.session:
                request.session['spotify_access_token'] = access_token
                request.session['spotify_refresh_token'] = refresh_token
                request.session['spotify_token_expires_at'] = (
                    datetime.now(UTC) + timedelta(seconds=expires_in)
                ).timestamp() if expires_in else None
            
            user, created = User.objects.get_or_create(
                spotify_id=spotify_user['id'],
                defaults={
                    'username': spotify_user['id'],
                    'email': spotify_user.get('email', ''),
                    'spotify_display_name': spotify_user.get('display_name', ''),
                    'first_name': (spotify_user.get('display_name', '').split()[0] 
                                 if spotify_user.get('display_name') else ''),
                }
            )
            
            return user
            
        except Exception as e:
            print(f"Spotify authentication error: {e}")
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
