# PyJams - Spotify Playlist Manager

A Flask web application that allows users to manage Spotify playlists collaboratively. Perfect for offices, events, or any shared space where music brings people together.

## Features

- 🔐 Secure Spotify OAuth Authentication
- 🔍 Real-time track search
- 🎵 Collaborative playlist management
- 🖼️ Rich media display with album artwork
- 👥 Admin controls for playlist management
- ⚡ Fast, responsive interface
- 📊 Admin dashboard with playlist statistics
- 🔄 Real-time playlist updates
- 📱 Mobile-friendly interface

## Current Focus

1. Guest Mode Implementation
   - Allow non-authenticated users to contribute to public playlists
   - Maintain admin controls while expanding access
   - Implement rate limiting and moderation features
   - Have updated the user permissions model such that there are guest, user, moderator, and admin levels. The admin is the owner of the Spotify application and deployment of the server. A user is anyone who successfully logs in with Spotify, a moderator must be set by an admin, and the admin is set by spotify_id on startup.

2. Production Readiness
   - Migration from development server to production server
   - Integration with uvicorn for better performance
   - Enhanced error handling and logging

3. Deployment Pipeline
   - Streamlined deployment process
   - Hosting solution research
   - CI/CD implementation
4. Moving to Heroku configuration for deployment.
This requires moving from Sqlite to PostgreSQL
Also added tasks and other fun things
## Setup

1. Create a Spotify Developer account and register your application at https://developer.spotify.com/dashboard
2. Install the project:

```bash
uv sync --all-extras
```

3. Set up your environment variables:

Save as .env or load into your shell. Right now, this is used to set the application that you want to authorize Spotify with,
but I am wondering if these permissions aren't necessary for every user to configure.

Determine who is going to be the administrator and retrieve their public Spotify ID from https://www.spotify.com/us/account/profile/

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_ADMIN_USERNAME="your_spotify_username" # typically all numerical
```

4. Run the development server:

```bash
invoke serve
```

5. Run production server
invoke prod

## Development

### New Features

#### Admin Dashboard
- Comprehensive playlist management
- Real-time statistics
- Grid/list view toggle
- Advanced sorting and filtering
- Quick actions for playlist management

#### Styling Updates
- Modern, responsive design
- Dark theme optimization
- Improved mobile experience
- Enhanced notification system
- Fluid grid layouts

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

## Project Structure