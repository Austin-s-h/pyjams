import os
import sys


def main():
    """Run the application server."""
    if os.getenv("ENV") == "production":
        # Use gunicorn in production
        from gunicorn.app.wsgiapp import run

        sys.argv = ["gunicorn", "pyjams.app:app", "-c", "gunicorn.conf"]
        run()
    else:
        # Use uvicorn in development
        import uvicorn

        uvicorn.run("pyjams.app:app", host="127.0.0.1", port=4884, reload=True)


if __name__ == "__main__":
    main()
