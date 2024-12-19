# PyJams - Spotify Playlist Manager

A Flask web application that allows users to manage Spotify playlists collaboratively. Perfect for offices, events, or any shared space where music brings people together.

## Features

- 🔐 Secure Spotify OAuth Authentication
- 🔍 Real-time track search with audio previews
- 🎵 Collaborative playlist management
- 🖼️ Rich media display with album artwork
- 👥 Admin controls for playlist management
- ⚡ Fast, responsive interface

## Setup

1. Create a Spotify Developer account and register your application at https://developer.spotify.com/dashboard
2. Install the project:

```bash
uv sync --all-extras
```

3. Set up your environment variables:

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SECRET_KEY="your_flask_secret_key"
export ADMIN_USERNAME="your_spotify_username"
export PUBLIC_PLAYLIST_ID="your_playlist_id"  # Optional
```

4. Run the development server:

```bash
uv run src/pyjams/app.py
```

## Development

### Project Structure

```
pyjams/
├── pyproject.toml         # Project configuration and dependencies
├── src/
│   └── pyjams/
│       ├── app.py        # Main Flask application
│       ├── static/
│       │   └── css/
│       │       └── styles.css
│       └── templates/
│           ├── base.html    # Base template with layout
│           └── index.html   # Main application page
└── tests/                # Test suite directory
```

### Development Dependencies

- pytest for testing
- ruff for linting and formatting
- mypy for type checking
- python-dotenv for local development

## Roadmap

### In Progress

- [ ] User profile customization
- [ ] Playlist statistics dashboard
- [ ] Mobile-responsive design

### Planned

- [ ] Dark/light theme toggle
- [ ] Keyboard shortcuts
- [ ] Playlist history
- [ ] Advanced search filters

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request

## License

MIT License - See LICENSE file for details
