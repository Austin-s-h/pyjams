from datetime import UTC, datetime

from django.contrib.auth import logout
from django.shortcuts import redirect

from pyjams.utils.spotify import get_spotify_auth


class SpotifyTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and 'spotify_token' in request.session:
            try:
                # Check if token needs refresh
                token_info = request.session['spotify_token']
                now = datetime.now(UTC)
                expires_at = datetime.fromtimestamp(token_info['expires_at'], tz=UTC)
                
                if now >= expires_at:
                    sp_oauth = get_spotify_auth(request)
                    new_token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
                    
                    # Update session with new token info
                    request.session['spotify_token'] = {
                        'access_token': new_token_info['access_token'],
                        'refresh_token': new_token_info['refresh_token'],
                        'expires_at': new_token_info['expires_at'],
                        'scope': new_token_info['scope']
                    }
                    request.session.modified = True
                    
            except Exception as e:
                print(f"Token refresh error: {e}")
                request.session.pop('spotify_token', None)
                logout(request)
                return redirect('pyjams:index')

        return self.get_response(request)
