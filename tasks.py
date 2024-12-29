from pathlib import Path

from invoke import task


@task
def clean(ctx):
    """Remove build artifacts."""
    ctx.run("rm -rf dist/")
    ctx.run("rm -rf build/")
    ctx.run("rm -rf *.egg-info")


@task
def lint(ctx):
    """Run code quality checks."""
    ctx.run("ruff check .")
    ctx.run("ruff format .")
    ctx.run("mypy .")


@task
def test(ctx):
    """Run tests."""
    ctx.run("pytest")


@task
def verify(ctx):
    """Run all checks before deployment."""
    lint(ctx)
    test(ctx)


@task
def install(ctx):
    """Install dependencies using uv."""
    ctx.run("uv pip install -e .[dev]")


@task
def heroku_login(ctx):
    """Ensure logged into Heroku CLI."""
    ctx.run("heroku auth:whoami || heroku login")


@task
def configure_env(ctx):
    """Configure Heroku environment variables from .env file"""
    ctx.run("set -o allexport; source .env; set +o allexport")


@task
def migrate(ctx):
    """Run database migrations."""
    ctx.run("python manage.py migrate")


@task
def makemigrations(ctx):
    """Create new migrations based on model changes."""
    ctx.run("python manage.py makemigrations")


@task
def serve(ctx):
    """Run the development server."""
    ctx.run("heroku local")


@task
def logs(ctx):
    """Show Heroku logs."""
    ctx.run("heroku logs --tail")


@task
def scale(ctx, dynos=1):
    """Scale Heroku dynos."""
    ctx.run(f"heroku ps:scale web={dynos}")


@task
def collectstatic(ctx):
    """Collect static files for production deployment."""
    static_root = Path("staticfiles")
    static_dir = Path("src/pyjams/static")

    # Ensure directories exist
    static_root.mkdir(exist_ok=True)

    # Clear existing files
    ctx.run(f"rm -rf {static_root}/*")

    # Copy static files
    if static_dir.exists():
        ctx.run(f"cp -r {static_dir}/* {static_root}/")
        print(f"Collected static files to {static_root}")
    else:
        print(f"Warning: Static directory {static_dir} not found")


@task(pre=[verify, migrate, collectstatic])
def deploy(ctx):
    """Deploy to Heroku with static files and migrations."""
    ctx.run("git push heroku master")
