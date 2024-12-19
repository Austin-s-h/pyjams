from flask import Flask, render_template, request, redirect, url_for, jsonify, session, g
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from typing import Optional
import os

class Config:
    SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
    ADMIN_USERNAME = os.environ.get('SPOTIFY_ADMIN_USERNAME')
    PUBLIC_PLAYLIST_ID = os.environ.get('SPOTIFY_PUBLIC_PLAYLIST_ID')
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    BASE_URL = 'http://127.0.0.1:4884'

app = Flask(__name__)
app.config.from_object(Config)

def init_spotify_oauth() -> SpotifyOAuth:
    if not all([app.config['SPOTIFY_CLIENT_ID'], app.config['SPOTIFY_CLIENT_SECRET']]):
        raise SpotifyException(http_status=500, code=-1, 
                             msg="Missing Spotify client credentials")
    
    return SpotifyOAuth(
        client_id=app.config['SPOTIFY_CLIENT_ID'],
        client_secret=app.config['SPOTIFY_CLIENT_SECRET'],
        redirect_uri=f"{app.config['BASE_URL']}/callback",
        scope='playlist-modify-public playlist-modify-private playlist-read-private',
        cache_path=None,
        show_dialog=True
    )

def get_spotify() -> Spotify:
    if not hasattr(g, 'spotify'):
        oauth = init_spotify_oauth()
        token_info = session.get('token_info')
        
        if not token_info:
            raise SpotifyException(http_status=401, code=-1, msg="No token info found")
            
        if oauth.is_token_expired(token_info):
            token_info = oauth.refresh_access_token(token_info['refresh_token'])
            session['token_info'] = token_info
            
        g.spotify = Spotify(auth=token_info['access_token'])
    return g.spotify

@app.before_request
def before_request():
    g.current_user = None
    if 'token_info' in session:
        try:
            sp = get_spotify()
            g.current_user = sp.current_user()
        except:
            session.pop('token_info', None)

@app.context_processor
def utility_processor():
    return {
        'current_user': getattr(g, 'current_user', None),
        'config': app.config
    }

# Basic routes
@app.route('/')
def index():
    if 'token_info' not in session:
        return render_template('login.html')
    
    sp = get_spotify()
    return render_template('index.html', 
                         user=sp.current_user(), 
                         playlists=sp.current_user_playlists())

@app.route('/login')
def login():
    """Initialize Spotify OAuth flow"""
    try:
        auth = init_spotify_oauth()
        auth_url = auth.get_authorize_url()
        return redirect(auth_url)
    except Exception as e:
        return render_template('login.html', error=str(e))

@app.route('/callback')
def callback():
    """Handle the callback from Spotify OAuth"""
    try:
        code = request.args.get('code')
        if not code:
            return redirect(url_for('index'))
            
        oauth = init_spotify_oauth()
        token_info = oauth.get_access_token(code, as_dict=True, check_cache=False)
        if not token_info:
            return redirect(url_for('index'))
            
        # Store token info in session
        session['token_info'] = token_info
        return redirect(url_for('index'))
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Playlist management routes
@app.route('/search')
def search():
    if 'token_info' not in session:
        return redirect(url_for('login'))
        
    sp = get_spotify()
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'track,artist,album')
    
    if not query:
        return render_template('search.html',
                            featured=sp.featured_playlists(),
                            new_releases=sp.new_releases())
    
    results = sp.search(q=query, type=search_type, limit=12)
    public_playlist = sp.playlist(app.config['PUBLIC_PLAYLIST_ID']) if app.config['PUBLIC_PLAYLIST_ID'] else None
    
    return render_template('search.html',
                         query=query,
                         results=results,
                         search_type=search_type,
                         public_playlist=public_playlist)

@app.route('/playlist/<playlist_id>')
def playlist_details(playlist_id):
    """Show detailed playlist information"""
    try:
        if 'token_info' not in session:
            return redirect(url_for('login'))
            
        sp = get_spotify()
        playlist = sp.playlist(playlist_id)
        tracks = sp.playlist_tracks(playlist_id)
        
        return render_template(
            'playlist.html',
            playlist=playlist,
            tracks=tracks['items']
        )
    except SpotifyException as e:
        return render_template('error.html', error=str(e))

@app.route('/add_song', methods=['POST'])
def add_song():
    """Add a song to the public playlist"""
    try:
        if 'token_info' not in session:
            return jsonify({'error': 'Please login first'}), 401
            
        sp = get_spotify()
        track_id = request.form.get('track_id')
        
        if not track_id:
            return jsonify({'error': 'Missing track_id'}), 400
            
        if not app.config['PUBLIC_PLAYLIST_ID']:
            return jsonify({'error': 'No public playlist configured'}), 400
            
        # Get track and playlist details
        track = sp.track(track_id)
        playlist = sp.playlist(app.config['PUBLIC_PLAYLIST_ID'])
        
        # Check if song already exists
        existing_tracks = sp.playlist_tracks(app.config['PUBLIC_PLAYLIST_ID'])
        if any(item['track']['id'] == track_id for item in existing_tracks['items']):
            return jsonify({
                'message': f'"{track["name"]}" is already in the playlist'
            }), 409
        
        # Add the track
        sp.playlist_add_items(app.config['PUBLIC_PLAYLIST_ID'], [track_id])
        return jsonify({
            'message': f'Added "{track["name"]}" to {playlist["name"]}',
            'track': {
                'name': track['name'],
                'artist': track['artists'][0]['name'],
                'album': track['album']['name'],
                'image': track['album']['images'][0]['url'] if track['album']['images'] else None
            }
        })
    except SpotifyException as e:
        return jsonify({'error': str(e)}), 400

@app.route('/remove_song', methods=['POST'])
def remove_song():
    try:
        sp = get_spotify()
        track_id = request.form['track_id']
        playlist_id = request.form.get('playlist_id', app.config['SPOTIFY_PLAYLIST_ID'])
        
        sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])
        return jsonify({'message': 'Song removed successfully'})
    except SpotifyException as e:
        return jsonify({'error': str(e)}), 400

# Admin routes
@app.route('/admin')
def admin_panel():
    if 'token_info' not in session:
        return redirect(url_for('login'))
        
    sp = get_spotify()
    current_user = sp.current_user()
    
    if current_user['id'] != app.config['ADMIN_USERNAME']:
        return jsonify({'error': 'Unauthorized'}), 403
        
    return render_template('admin.html',
                         playlists=sp.user_playlists(current_user['id'])['items'],
                         current_public_playlist=sp.playlist(app.config['PUBLIC_PLAYLIST_ID']) 
                         if app.config['PUBLIC_PLAYLIST_ID'] else None)

@app.route('/admin/set_public_playlist', methods=['POST'])
def set_public_playlist():
    """Set the public playlist that all users can add to"""
    try:
        if 'token_info' not in session:
            return jsonify({'error': 'Please login first'}), 401
            
        sp = get_spotify()
        current_user = sp.current_user()
        
        # Only allow admin access
        if current_user['id'] != app.config['ADMIN_USERNAME']:
            return jsonify({'error': 'Unauthorized'}), 403
            
        playlist_id = request.form.get('playlist_id')
        if not playlist_id:
            return jsonify({'error': 'Missing playlist_id'}), 400
            
        # Store in environment variable
        os.environ['SPOTIFY_PUBLIC_PLAYLIST_ID'] = playlist_id
        app.config['PUBLIC_PLAYLIST_ID'] = playlist_id
        
        playlist = sp.playlist(playlist_id)
        return jsonify({
            'message': f'Set public playlist to "{playlist["name"]}"',
            'playlist': {
                'name': playlist['name'],
                'id': playlist['id'],
                'image': playlist['images'][0]['url'] if playlist['images'] else None
            }
        })
    except SpotifyException as e:
        return jsonify({'error': str(e)}), 400

@app.errorhandler(SpotifyException)
def handle_spotify_error(error):
    return jsonify({'error': str(error)}), error.http_status

if __name__ == '__main__':
    app.run(debug=True, port=4884)