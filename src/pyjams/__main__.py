import uvicorn


def main():
    """Run the application server."""
    uvicorn.run("pyjams.app:app", host="127.0.0.1", port=4884, reload=True)


if __name__ == "__main__":
    main()
