"""Custom uvicorn launcher that configures asyncio for Playwright on Windows.

Run this instead of using the `uvicorn` CLI directly:

    python run_server.py
"""

from __future__ import annotations

import asyncio
import sys

import uvicorn


def main() -> None:
    # On Windows, Playwright needs an event loop that supports subprocesses.
    # That is provided by WindowsSelectorEventLoopPolicy, NOT Proactor.
    if sys.platform == 'win32' and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    uvicorn.run(
        'main:app',
        host='127.0.0.1',
        port=8000,
        reload=True,
    )


if __name__ == '__main__':
    main()
