"""Start the hosted aquarium: `python server.py`.

The same app `uvicorn web.app:app` serves, wrapped so a host that runs a file
rather than an ASGI target still starts the right thing. That matters here
more than it usually would: this repo's `main.py` is the pygame desktop game,
and platforms that guess an entry point look for exactly that name. Guessing
it would open a window on a machine with no screen.

`PORT` is honoured when the host sets one and defaults to 8080 when it does
not, which covers both conventions without needing to know which is in play.
"""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "web.app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        # The simulation lives in the process, so there is exactly one of it.
        # A second worker would be a second world, and whichever one a viewer
        # landed on would be a different game from the one their neighbour is
        # watching.
        workers=1,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
