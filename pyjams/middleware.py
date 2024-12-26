from datetime import UTC, datetime

from django.contrib.auth import logout
from django.shortcuts import redirect

from pyjams.utils.spotify import get_spotify_auth


class SpotifyTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                # Check if token needs refresh
                if request.user.token_expires_at:
                    now = datetime.now(UTC)
                    if now >= request.user.token_expires_at:
                        sp_oauth = get_spotify_auth(request)
                        token_info = sp_oauth.refresh_access_token(request.user.refresh_token)
                        
                        # Update user tokens
                        request.user.access_token = token_info['access_token']
                        request.user.refresh_token = token_info['refresh_token']
                        request.user.token_expires_at = datetime.fromtimestamp(
                            token_info['expires_at'], 
                            tz=UTC
                        )
                        request.user.save()
                        
                        # Update session
                        request.session['spotify_token'] = token_info
                        request.session.modified = True
                        
            except Exception as e:
                print(f"Token refresh error: {e}")
                logout(request)
                return redirect('pyjams:index')

        return self.get_response(request)
