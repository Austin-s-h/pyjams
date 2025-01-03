# PyJams

A Django-based web application for managing and sharing Spotify playlists collaboratively.

## Features

- Spotify OAuth2 Authentication
- Playlist Management System
- User Role Management
- Collaborative Playlist Features
- Real-time Search Integration
- Responsive Design

## Technology Stack

- Python 3.13+
- Django 5.1
- Spotify Web API (via Spotipy)
- PostgreSQL (for production)
- SQLite (for development)
- HTMX for dynamic interactions
- Bootstrap for styling
- WhiteNoise for static file serving

## Project Structure

```
pyjams/
├── pyjams/                 # Main Django app
│   ├── migrations/        # Database migrations
│   ├── static/           # Static assets
│   ├── templates/        # HTML templates
│   ├── utils/            # Utility modules
│   └── views/            # View controllers
├── tests/                # Test suite
├── manage.py             # Django management script
├── Procfile             # Heroku deployment config
└── pyproject.toml       # Project dependencies and config
```

## Setup your own 

To deploy your own version of pyjams that you administrate, you must create a Spotify Developer account and retrieve some credentials. Additionally, you must log in with heroku and create an application. Please follow this guide on [Heroku](https://devcenter.heroku.com/articles/getting-started-with-python?singlepage=true)

1. Clone the repository:
   ```bash
   git clone https://github.com/Austin-s-h/pyjams.git
   cd pyjams
   ```

2. System Dependencies:
   Tested on WSL2 (Ubuntu)
   ```bash
   # uv https://docs.astral.sh/uv/
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # heroku cli https://devcenter.heroku.com/articles/heroku-cli
   curl https://cli-assets.heroku.com/install.sh | sh
   # Create your own application, add postgres addon
   heroku create
   heroku addons:create heroku-postgresql:essential-0
   ```

3. Virtual Environment:
   ```bash
   uv venv
   source .venv/bin/activate
   uv sync --all-extras
   ```

4. Setup Environment Variables and save with heroku config
   ```bash
   cp .env.example .env
   ```


4. Run migrations:
   ```bash
   inv makemigrations && inv migrate
   ```

5. Start development server:
   ```bash
   heroku local
   ```

## Deployment

The application is configured for Heroku deployment. TODO: collect refrences

```bash
inv verify      # Run tests and checks
inv deploy      # Deploy to Heroku
```

## Work in Progress

- [ ] Playlist versioning system
- [ ] Advanced search filters
- [ ] User activity tracking
- [ ] Playlist recommendations
- [ ] Bulk track management

## Future Improvements

1. Performance Optimizations
   - Implement caching for Spotify API responses
   - Add async support for long-running operations
   - Optimize database queries

2. Feature Enhancements
   - Collaborative playlist suggestions
   - Integration with more music services
   - Social features (comments, likes, shares)
   - Custom playlist analytics

3. Technical Improvements
   - Add more comprehensive test coverage
   - Implement WebSocket support for real-time updates
   - Enhanced error handling and monitoring
   - API documentation with OpenAPI/Swagger

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License
