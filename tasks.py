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
def deploy(ctx):
    """Deploy to Heroku."""
    verify(ctx)
    ctx.run("git push heroku main")


# @task
# def publish(ctx):
#     """Publish package to PyPI."""
#     clean(ctx)
#     ctx.run("python setup.py sdist bdist_wheel")
#     ctx.run("twine upload dist/*")


@task
def serve(ctx):
    """Run the development server."""
    ctx.run("uvicorn pyjams.app:app --host=127.0.0.1 --port=4884 --reload")


@task
def prod(ctx):
    """Run the production server using gunicorn."""
    ctx.run("gunicorn pyjams.app:app -c gunicorn.conf")


@task
def logs(ctx):
    """Show Heroku logs."""
    ctx.run("heroku logs --tail")


@task
def scale(ctx, dynos=1):
    """Scale Heroku dynos."""
    ctx.run(f"heroku ps:scale web={dynos}")
