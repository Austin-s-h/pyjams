# PyJams - Spotify Playlist Manager

A Flask web application that allows users to manage their Spotify playlists through a simple interface.

## Features

- 🔐 Spotify OAuth Authentication
- 🔍 Search tracks with audio previews
- 📝 View and manage playlists
- ➕ Add tracks to any playlist
- ➖ Remove tracks from playlists
- 🎵 Audio preview support
- 🖼️ Album artwork display

## Setup

1. Create a Spotify Developer account and register your application
2. Set environment variables:

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SECRET_KEY="your_secret_key"  # for Flask sessions
```

3. Install dependencies:

```bash
pip install flask spotipy
```

4. Run the application:

```bash
python src/pyjams/app.py
```

## TODO

### Essential Features

- [ ] Add CSS styling (create style.css)
- [ ] Create index.html template
- [ ] Add error.html template
- [ ] Add navigation between pages
- [ ] Add logout functionality
- [ ] Add user profile page

### Improvements

- [ ] Add pagination for search results
- [ ] Add playlist creation functionality
- [ ] Add playlist editing (name, description)
- [ ] Add bulk song addition/removal
- [ ] Add sorting and filtering options
- [ ] Add keyboard shortcuts
- [ ] Add loading states during API calls

### Technical Debt

- [ ] Add proper type hints throughout
- [ ] Add tests
- [ ] Add proper logging
- [ ] Add error recovery mechanisms
- [ ] Add rate limiting handling
- [ ] Add session timeout handling
- [ ] Add proper security headers

### UI/UX Improvements

- [ ] Add mobile-responsive design
- [ ] Add dark/light theme toggle
- [ ] Add better feedback for actions
- [ ] Add animations for state changes
- [ ] Add drag-and-drop reordering
- [ ] Add search history
- [ ] Add favorite/recent playlists

## Project Structure

```
src/pyjams/
├── app.py              # Main application file
├── static/
│   └── style.css      # (TODO) CSS styles
└── templates/
    ├── error.html     # Error page template
    ├── index.html     # (TODO) Main page template
    ├── login.html     # Login page template
    ├── playlist.html  # Playlist view template
    └── search.html    # Search interface template
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License
