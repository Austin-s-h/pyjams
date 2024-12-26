from django.contrib import auth
from django.shortcuts import redirect

from pyjams.utils.spotify import get_spotify_auth


class SpotifyTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            token_info = request.session.get('spotify_token')
            if token_info and isinstance(token_info, dict):  # Verify token_info is valid
                try:
                    sp_oauth = get_spotify_auth()
                    if token_info.get('expires_at') and sp_oauth.is_token_expired(token_info):
                        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
                        # Store only necessary token data
                        request.session['spotify_token'] = {
                            'access_token': token_info['access_token'],
                            'refresh_token': token_info['refresh_token'],
                            'expires_at': token_info['expires_at'],
                            'scope': token_info['scope']
                        }
                        request.session.modified = True
                except Exception:
                    # If token refresh fails, clear session and redirect to login
                    request.session.flush()
                    return redirect('pyjams:spotify_login')

        response = self.get_response(request)
        return response
