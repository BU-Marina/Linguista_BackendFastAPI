"""App. Объект приложения."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response as StarletteResponse
from starlette.types import Receive, Scope, Send

from api.routers import main_router
from api.v1.notifications.ws import router as ws_notifications_router
from api.v1.exercises.ws import router as ws_exercises_router
from config.settings import MEDIA_ROOT, MEDIA_URL, settings

app = FastAPI()

# убедиться, что каталог существует
Path(MEDIA_ROOT).mkdir(parents=True, exist_ok=True)


# Custom StaticFiles class that adds CORS headers
class CORSStaticFiles(StaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            # Handle OPTIONS preflight requests
            if scope['method'] == 'OPTIONS':
                response = StarletteResponse(
                    status_code=200,
                    headers={
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, OPTIONS, HEAD',
                        'Access-Control-Allow-Headers': '*',
                    },
                )
                await response(scope, receive, send)
                return

            # Create a wrapper to add CORS headers to the response
            # This must handle both 200 and 304 responses
            async def send_wrapper(message):
                if message['type'] == 'http.response.start':
                    # Convert headers to a mutable list
                    headers_list = list(message.get('headers', []))

                    # Convert to dict for easier manipulation (handle both bytes and string keys)
                    headers_dict = {}
                    for key, value in headers_list:
                        # Normalize key to lowercase bytes
                        if isinstance(key, str):
                            key = key.lower().encode('latin-1')
                        elif isinstance(key, bytes):
                            key = key.lower()
                        headers_dict[key] = value

                    # Add CORS headers (always overwrite if they exist)
                    # These must be present even for 304 responses
                    headers_dict[b'access-control-allow-origin'] = b'*'
                    headers_dict[
                        b'access-control-allow-methods'
                    ] = b'GET, OPTIONS, HEAD'
                    headers_dict[b'access-control-allow-headers'] = b'*'

                    # Also add Cache-Control to prevent caching issues
                    # Or at least ensure CORS headers are in the cache
                    if b'cache-control' not in headers_dict:
                        headers_dict[b'cache-control'] = b'public, max-age=3600'

                    # Convert back to list of tuples
                    message['headers'] = list(headers_dict.items())
                await send(message)

            await super().__call__(scope, receive, send_wrapper)
        else:
            await super().__call__(scope, receive, send)


# монтируем только если используем локальный storage (например в dev)
if not settings.USE_S3:
    app.mount(
        MEDIA_URL.rstrip('/'), CORSStaticFiles(directory=str(MEDIA_ROOT)), name='media'
    )


# Additional middleware to ensure CORS headers are always added to media files
# This runs after StaticFiles as a fallback and handles all response types including 304
@app.middleware('http')
async def ensure_media_cors(request: Request, call_next):
    response = await call_next(request)
    # Ensure CORS headers are present for all media file responses
    # This is critical for 304 Not Modified responses which might bypass StaticFiles wrapper
    if request.url.path.startswith(MEDIA_URL.rstrip('/')):
        # Always set CORS headers, even if they were already set
        # This ensures they're present even for cached (304) responses
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS, HEAD'
        response.headers['Access-Control-Allow-Headers'] = '*'
        # Add Vary header to ensure proper caching behavior with CORS
        # This tells the browser to cache responses separately based on Origin
        vary_header = response.headers.get('Vary', '')
        if 'Origin' not in vary_header:
            response.headers['Vary'] = f'{vary_header}, Origin'.strip(', ')
        # For 304 responses, we need to ensure headers are sent
        # Force re-validation to avoid stale cached responses without CORS headers
        if response.status_code == 304:
            # Add cache control to ensure browser re-validates
            response.headers['Cache-Control'] = 'public, must-revalidate'
    return response


# CORS for local/dev and configurable origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# WebSocket routes at root level (without /api/v1 prefix)
app.include_router(ws_notifications_router)
app.include_router(ws_exercises_router)

app.include_router(main_router)
