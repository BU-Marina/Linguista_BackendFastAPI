"""Pinterest proxy client (FastAPI-compatible)."""

from __future__ import annotations

import os
import logging
import re
from typing import Optional
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

import httpx
from io import BytesIO

try:  # Optional dependency for dominant color extraction
    from PIL import Image  # type: ignore

    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - fallback when Pillow is not installed
    Image = None  # type: ignore
    PIL_AVAILABLE = False

try:
    from api.v1.utils.exceptions import ServiceUnavailable  # type: ignore
except Exception:  # fallback for non-app contexts

    class ServiceUnavailable(Exception):
        ...


from config.settings import settings

logger = logging.getLogger(__name__)

MAIN_URL = 'https://api.pinterest.com/v5/'
OAUTH_URL = 'https://www.pinterest.com/oauth/'
PUBLIC_SEARCH_URL_API = 'https://www.pinterest.com/search/pins/'
PUBLIC_SEARCH_URL = 'https://ru.pinterest.com/search/pins/'
# Pinterest public search uses this base URL with query parameter
PUBLIC_SEARCH_BASE = 'https://www.pinterest.com/resource/BaseSearchResource/get/'


def get_authorization_url(state: Optional[str] = None) -> str:
    """
    Generate Pinterest OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Authorization URL to redirect user to
    """
    params = {
        'client_id': settings.PINTEREST_APP_ID,
        'redirect_uri': settings.PINTEREST_REDIRECT_URI,
        'response_type': 'code',
        # Pinterest API v5 scopes for searching public pins
        # pins:read - read user's pins
        # boards:read - read user's boards
        # pins:read_secret - read secret pins
        # boards:read_secret - read secret boards
        # pins:read_public - read public pins (for global search) - try this first
        # search:pins - search public pins (alternative scope if pins:read_public doesn't work)
        # catalogs - access to catalog data
        'scope': 'pins:read,boards:read,pins:read_secret,boards:read_secret,pins:read_public,search:pins,catalogs',
    }
    if state:
        params['state'] = state

    query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
    return f'{OAUTH_URL}?{query_string}'


async def exchange_code_for_token(
    code: str, redirect_uri: Optional[str] = None
) -> dict:
    """
    Exchange authorization code for access token.

    Args:
        code: Authorization code from Pinterest callback
        redirect_uri: Redirect URI (must match the one used in authorization request)

    Returns:
        Dictionary with access_token and other OAuth response data
    """
    # Pinterest API v5 uses https://api.pinterest.com/v5/oauth/token
    url = 'https://api.pinterest.com/v5/oauth/token'

    # Use provided redirect_uri or fall back to settings
    # The redirect_uri MUST match exactly what was used in the authorization request
    redirect_uri = redirect_uri or settings.PINTEREST_REDIRECT_URI

    logger.debug(
        'Pinterest token exchange request: client_id=%s, redirect_uri=%s',
        settings.PINTEREST_APP_ID,
        redirect_uri,
    )

    try:
        import base64

        # Pinterest API v5 requires Basic Authentication using client_id:client_secret
        # Encode credentials for Basic Auth
        credentials = f'{settings.PINTEREST_APP_ID}:{settings.PINTEREST_APP_SECRET}'
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Remove client_id and client_secret from body since they're in Basic Auth
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            # Pinterest OAuth token exchange expects form-encoded data with Basic Auth
            resp = await client.post(url, data=token_data, headers=headers)

            # Log response for debugging
            if resp.status_code != 200:
                logger.error(
                    'Pinterest token exchange failed: Status %d, Response: %s',
                    resp.status_code,
                    resp.text[:500] if resp.text else 'No response body',
                )

            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        error_detail = (
            exc.response.text[:500] if exc.response.text else 'No error details'
        )
        logger.error(
            'Pinterest token exchange HTTP error %d: %s. URL: %s, Redirect URI: %s',
            exc.response.status_code,
            error_detail,
            exc.request.url,
            redirect_uri,
        )
        raise ServiceUnavailable(
            f'Pinterest token exchange failed: {exc.response.status_code} - {error_detail}'
        ) from exc
    except Exception as exc:
        logger.error('Pinterest token exchange failed: %s', exc, exc_info=True)
        raise ServiceUnavailable(
            f'Failed to exchange Pinterest authorization code: {str(exc)}'
        ) from exc


def _headers(access_token: Optional[str] = None) -> dict[str, str]:
    """
    Get headers for Pinterest API requests.

    Args:
        access_token: Access token to use. If None, will try to get from session/cache.
                     For now, this should be passed from the OAuth flow.

    Returns:
        Dictionary with Authorization header
    """
    if not access_token:
        raise ServiceUnavailable(
            'Pinterest access token is required. Please complete OAuth flow.'
        )

    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }


async def fetch_images(
    *,
    access_token: str,
    search: Optional[str] = None,
    per_page: int = 20,
    page: int = 1,
    bookmark: Optional[str] = None,
    ad_account_id: Optional[str] = None,
    timeout: float = 20.0,
) -> dict:
    """
    Fetch images from Pinterest API.

    Args:
        access_token: Pinterest OAuth access token
        search: Search query string (required)
        per_page: Number of results per page (1-250, default 20)
        page: Page number (for compatibility, but Pinterest uses bookmarks)
        bookmark: Pinterest bookmark for pagination (takes precedence over page)
        ad_account_id: Optional ad account ID for Business Access. When specified, uses
                      the owner of that ad_account as the "operation user_account".
                      This changes which account's permissions are used, but does NOT
                      enable global public pin search - it still searches within the scope
                      of what that business account can access. Requires token user_account
                      to have Business Access roles:
                      - For Pins on public/protected boards: Owner, Admin, Analyst, Campaign Manager
                      - For Pins on secret boards: Owner, Admin
                      Note: For truly global public pin search, use fetch_images_from_public_search().
        timeout: Request timeout in seconds

    Returns:
        Dictionary with Pinterest API response containing items and bookmark
    """
    if not search:
        # Pinterest API requires a search query
        # Return empty results if no search provided
        return {
            'items': [],
            'bookmark': None,
        }

    # Pinterest API v5 search endpoint
    # Note: The /search/pins endpoint may NOT search ALL global public pins.
    # It likely searches pins that the authenticated user (or operation user_account via ad_account_id)
    # has access to, not necessarily all public pins on Pinterest.
    # For truly global public pin search, use fetch_images_from_public_search() instead.
    url = MAIN_URL + 'search/pins'

    # Pinterest API v5 search parameters
    params = {
        'query': search,
        'page_size': min(per_page, 250),  # Pinterest max is 250
    }

    # Pinterest uses bookmark-based pagination
    # If bookmark is provided, use it; otherwise, we'll start from the beginning
    if bookmark:
        params['bookmark'] = bookmark

    # Optional: Business Access - specify ad_account_id to use the owner of that ad_account
    # as the "operation user_account". This changes WHICH account's permissions are used,
    # but does NOT expand the search to all global public pins - it still searches within
    # the scope of what that business account can access (their own pins + boards they have
    # access to). For truly global public pin search, use fetch_images_from_public_search().
    if ad_account_id:
        params['ad_account_id'] = ad_account_id

    # Log the full request for debugging
    logger.info(
        f'Pinterest search request: {url} with query="{search}", page_size={params["page_size"]}'
    )
    logger.debug(
        f'Full request URL will be: {url}?{"&".join([f"{k}={v}" for k, v in params.items()])}'
    )

    try:
        headers = _headers(access_token)
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f'Pinterest API request: {url} with params: {params}')
            logger.debug(
                f'Pinterest API headers: Authorization=Bearer {access_token[:20]}...'
            )
            resp = await client.get(url, headers=headers, params=params)

            # Log response status for debugging
            if resp.status_code == 401:
                error_text = resp.text[:1000] if resp.text else 'No response body'
                logger.error(
                    'Pinterest API 401 Unauthorized. Check if access token is valid '
                    'and has required scopes (pins:read). Response: %s',
                    error_text,
                )
            elif resp.status_code != 200:
                error_text = resp.text[:1000] if resp.text else 'No response body'
                logger.error(
                    'Pinterest API error %d: %s. Request URL: %s',
                    resp.status_code,
                    error_text,
                    resp.request.url,
                )

            resp.raise_for_status()
            data = resp.json()

            # Pinterest API v5 search/pins endpoint should return global public pin search
            # Response structure might vary - check for different possible formats
            items = data.get('items', [])

            # Check if response has different structure
            if not items and 'data' in data:
                items = data.get('data', [])
            if not items and 'pins' in data:
                items = data.get('pins', [])

            items_count = len(items)
            logger.info(
                f'Pinterest API success: received {items_count} items for query "{search}"'
            )

            # Log full response for debugging empty results
            if items_count == 0:
                logger.warning(
                    f'Pinterest search returned 0 results for query "{search}". '
                    f'Response structure: {list(data.keys())}. Full response: {data}'
                )
                # Important: Pinterest API v5 /search/pins endpoint behavior
                # - This endpoint SHOULD search all public pins globally
                # - Empty results might indicate:
                #   1. Trial access limitations (search may be restricted)
                #   2. App needs to be approved for standard API access
                #   3. The endpoint might require additional parameters
                # - Check your Pinterest Developer Dashboard for access level
                logger.warning(
                    'Pinterest /search/pins returned empty results. '
                    'This endpoint searches all public pins globally. '
                    'If you have trial access, global search may be limited. '
                    'Check your app access level in Pinterest Developer Dashboard.'
                )

            # Return normalized response with items array
            return {
                'items': items,
                'bookmark': data.get('bookmark'),
            }
    except httpx.HTTPStatusError as exc:
        # Handle HTTP errors specifically
        error_text = (
            exc.response.text[:1000] if exc.response.text else 'No response body'
        )
        logger.error(
            'Pinterest API HTTP error %d: %s. Request URL: %s, Request headers: %s',
            exc.response.status_code,
            error_text,
            exc.request.url,
            {
                k: v if k != 'Authorization' else 'Bearer ***'
                for k, v in exc.request.headers.items()
            },
        )
        raise ServiceUnavailable(
            f'Pinterest API error {exc.response.status_code}: {error_text}'
        ) from exc
    except Exception as exc:  # broad to mirror DRF behavior
        logger.error('Pinterest fetch failed: %s', exc, exc_info=True)
        raise ServiceUnavailable(f'Pinterest API request failed: {str(exc)}') from exc


async def fetch_images_from_public_search(
    *,
    search: Optional[str] = None,
    per_page: int = 20,
    page: int = 1,
    bookmark: Optional[str] = None,
    timeout: float = 20.0,
) -> dict:
    """
    Fetch images from Pinterest's public search pages by parsing HTML.
    This bypasses the API and scrapes public search results.

    Args:
        search: Search query string (required)
        per_page: Number of results per page (default 20)
        page: Page number (for pagination, legacy support)
        bookmark: Bookmark token for pagination (can be page number or scroll position)
        timeout: Request timeout in seconds

    Returns:
        Dictionary with items array and bookmark (for compatibility with API format)
        The bookmark can be used to fetch the next page of results
    """
    logger.info(
        f'Pinterest public search called: search="{search}", per_page={per_page}, page={page}, bookmark={bookmark}'
    )

    if not search:
        logger.warning(
            'Pinterest public search: no search query provided, returning empty results'
        )
        return {
            'items': [],
            'bookmark': None,
        }

    # Pinterest public search URL
    url = PUBLIC_SEARCH_URL
    params = {
        'q': search,
        'rs': 'typed',  # search type
    }

    # Pinterest uses infinite scroll, but we can simulate pagination
    # If bookmark is provided, it represents a scroll position or page number
    # We'll use Playwright to scroll down and load more content
    scroll_position = 0
    if bookmark:
        try:
            # Bookmark can be a page number or scroll position
            scroll_position = int(bookmark)
        except (ValueError, TypeError):
            scroll_position = 0

    # Calculate how many times to scroll based on page/bookmark.
    # Each scroll loads approximately 20-30 pins.
    #
    # Important: Each request is a fresh Playwright session, so we need to
    # "replay" all previous scrolls to reach the same depth as the user.
    # We simulate this by making the number of scrolls proportional to the
    # logical page number (page 1, 2, 3, ...).
    BASE_SCROLLS_PER_PAGE = 2  # how many scrolls we do per logical page

    # Determine the logical page index (1-based) either from bookmark or page
    if scroll_position > 0:
        logical_page = scroll_position
    elif page > 1:
        logical_page = page
    else:
        logical_page = 1

    scrolls_needed = logical_page * BASE_SCROLLS_PER_PAGE

    try:
        # Use a browser-like user agent to avoid blocking
        base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # Build full target URL for the scraping service
        # This is the URL we want the proxy/headless browser to load
        # Use str() here for compatibility with older httpx versions
        target_url = str(httpx.URL(url, params=params))

        # Try to use Playwright (free, fast headless browser) for JavaScript rendering
        # Falls back to ScrapingBee if available, then to direct request
        # Note: On Windows, the event loop policy should be set to WindowsProactorEventLoopPolicy
        # at application startup (see main.py) for Playwright to work properly
        use_playwright = False
        try:
            import importlib.util

            use_playwright = importlib.util.find_spec('playwright') is not None
            if use_playwright:
                logger.info(
                    'Pinterest public search: Playwright is available - will use it for JS rendering and scrolling'
                )
        except ImportError:
            pass
        if not use_playwright:
            logger.info(
                'Pinterest public search: Playwright not available - will try ScrapingBee or direct request'
            )

        scrapingbee_api_key = (
            os.getenv('SCRAPINGBEE_API_KEY', '')
            or os.getenv('SCRAPING_BEE_API_KEY', '')
            or settings.SCRAPINGBEE_API_KEY
        )
        use_scrapingbee = (
            bool(scrapingbee_api_key) and not use_playwright
        )  # Only use ScrapingBee if Playwright is not available

        logger.warning('=' * 80)
        logger.warning(
            f'Pinterest public search: use_scrapingbee={use_scrapingbee}, scrapingbee_api_key={scrapingbee_api_key}'
        )
        logger.warning(f'ScrapingBee API key set: {bool(scrapingbee_api_key)}')
        logger.warning(f'Target URL: {target_url}')
        logger.warning('=' * 80)

        html_content = None  # Will be set by one of the methods below
        method_used = 'direct'  # Track which method was actually used

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            if use_playwright:
                # Use Playwright for JavaScript rendering and scrolling (free and fast)
                logger.warning('=' * 80)
                logger.warning(
                    'Pinterest public search: Using PLAYWRIGHT for JS rendering and scrolling'
                )
                logger.warning(f'Target URL: {target_url} (query="{search}")')
                logger.warning('=' * 80)
                try:
                    import sys
                    import asyncio

                    # On Windows, avoid asyncio Playwright (event loop/subprocess issues).
                    # Instead, run the sync Playwright API in a thread with its own event loop.
                    if sys.platform == 'win32':

                        def run_sync_playwright() -> str:
                            # This runs in a separate thread; we can freely create an event loop there.
                            from playwright.sync_api import (
                                sync_playwright as _sync_playwright,
                            )  # type: ignore

                            with _sync_playwright() as p:
                                browser = p.chromium.launch(headless=True)
                                context = browser.new_context(
                                    user_agent=base_headers['User-Agent'],
                                    viewport={'width': 1920, 'height': 1080},
                                )
                                page = context.new_page()

                                logger.info(
                                    f'Pinterest public search (sync): Navigating to {target_url}'
                                )
                                # Use 'load' instead of 'networkidle' - Pinterest never reaches networkidle due to infinite scroll
                                # Increase timeout to 60 seconds for slow connections
                                page.goto(target_url, wait_until='load', timeout=60000)

                                # Initial wait
                                page.wait_for_timeout(3000)

                                # Scrolling for pagination - wait for content to load
                                if scrolls_needed > 0:
                                    logger.info(
                                        f'Pinterest public search (sync): Scrolling {scrolls_needed} times to load more content'
                                    )
                                    for i in range(scrolls_needed):
                                        # Scroll incrementally
                                        scroll_amount = 1000 * (i + 1)
                                        page.evaluate(
                                            f'window.scrollTo(0, {scroll_amount})'
                                        )

                                        # Wait for Pinterest's lazy loading to trigger
                                        # Try to wait for new pins to appear (they have data-test-id="non-story-pin-image")
                                        try:
                                            # Wait a bit for network requests to start
                                            page.wait_for_timeout(1000)
                                            # Check if new content is loading by waiting for selector
                                            # This helps ensure Pinterest has time to load new content
                                            page.wait_for_timeout(
                                                2000
                                            )  # Total 3 seconds per scroll
                                        except Exception:
                                            # If waiting fails, just continue
                                            page.wait_for_timeout(2500)

                                    # Final wait to ensure all content is loaded
                                    page.wait_for_timeout(2000)

                                content = page.content()
                                browser.close()
                                return content

                        loop = asyncio.get_running_loop()
                        html_content = await loop.run_in_executor(
                            None, run_sync_playwright
                        )
                        method_used = 'playwright'

                        logger.warning(
                            f'Pinterest public search: Playwright (sync on Windows) returned HTML (length: {len(html_content)})'
                        )
                        logger.warning(
                            f'HTML contains "data-test-id": {"data-test-id" in html_content}'
                        )
                        logger.warning(
                            f'HTML contains "non-story-pin-image": {"non-story-pin-image" in html_content}'
                        )
                        logger.warning(
                            f'HTML contains "<img": {"<img" in html_content}'
                        )
                        logger.warning(
                            f'HTML contains "/pin/": {"/pin/" in html_content}'
                        )
                    else:
                        # Non-Windows: use normal async Playwright
                        from playwright.async_api import async_playwright  # type: ignore

                        async with async_playwright() as p:
                            browser = await p.chromium.launch(headless=True)
                            context = await browser.new_context(
                                user_agent=base_headers['User-Agent'],
                                viewport={'width': 1920, 'height': 1080},
                            )
                            page = await context.new_page()

                            logger.info(
                                f'Pinterest public search: Navigating to {target_url}'
                            )
                            # Use 'load' instead of 'networkidle' - Pinterest never reaches networkidle due to infinite scroll
                            # Increase timeout to 60 seconds for slow connections
                            await page.goto(
                                target_url, wait_until='load', timeout=60000
                            )

                            await page.wait_for_timeout(3000)

                            if scrolls_needed > 0:
                                logger.info(
                                    f'Pinterest public search: Scrolling {scrolls_needed} times to load more content'
                                )
                                for i in range(scrolls_needed):
                                    # Scroll down progressively
                                    scroll_amount = 1000 * (i + 1)
                                    await page.evaluate(
                                        f'window.scrollTo(0, {scroll_amount})'
                                    )

                                    # Wait for Pinterest's lazy loading to trigger
                                    # Give Pinterest time to load new content after scroll
                                    await page.wait_for_timeout(
                                        1000
                                    )  # Initial wait for network requests

                                    # Additional wait to ensure content loads
                                    # Pinterest uses lazy loading, so we need to wait for images/content to appear
                                    await page.wait_for_timeout(
                                        2000
                                    )  # Total 3 seconds per scroll

                                    logger.debug(
                                        f'Pinterest public search: Scrolled to {scroll_amount}px, waiting for content...'
                                    )

                                # Final wait to ensure all content is loaded
                                await page.wait_for_timeout(2000)
                                logger.info(
                                    'Pinterest public search: Finished scrolling, extracting HTML...'
                                )

                            html_content = await page.content()
                            method_used = 'playwright'
                            await browser.close()

                            logger.warning(
                                f'Pinterest public search: Playwright (async) returned HTML (length: {len(html_content)})'
                            )
                            logger.warning(
                                f'HTML contains "data-test-id": {"data-test-id" in html_content}'
                            )
                            logger.warning(
                                f'HTML contains "non-story-pin-image": {"non-story-pin-image" in html_content}'
                            )
                            logger.warning(
                                f'HTML contains "<img": {"<img" in html_content}'
                            )
                            logger.warning(
                                f'HTML contains "/pin/": {"/pin/" in html_content}'
                            )

                except ImportError:
                    logger.error(
                        'Playwright not installed. Install with: pip install playwright && playwright install chromium'
                    )
                    logger.warning('Falling back to ScrapingBee or direct request...')
                    html_content = None
                except Exception as exc:
                    logger.error(f'Playwright request failed: {exc}', exc_info=True)
                    logger.warning('Falling back to ScrapingBee or direct request...')
                    html_content = None

            # If Playwright didn't work or wasn't available, try ScrapingBee
            if html_content is None and use_scrapingbee:
                # Use ScrapingBee API to fetch fully rendered HTML
                proxy_url = 'https://app.scrapingbee.com/api/v1/'
                sb_params = {
                    'api_key': scrapingbee_api_key,
                    'url': target_url,
                    # Enable JS rendering so we see the same content as a real browser
                    'render_js': 'true',
                    # Keep resources for better chances of getting full content
                    'block_resources': 'false',
                    # Wait for page to fully load (wait in milliseconds)
                    'wait': '3000',  # Wait 3 seconds for React to render
                }

                # Implement scrolling using ScrapingBee's js_scenario parameter
                # This simulates scrolling to trigger Pinterest's infinite scroll
                if scrolls_needed > 0:
                    logger.warning(
                        f'Pinterest public search: Implementing scrolling for pagination (scrolls_needed={scrolls_needed})'
                    )

                    try:
                        # Build js_scenario: array of actions (wait, scroll, wait, scroll, ...)
                        # Each scroll action scrolls down and waits for content to load
                        js_scenario = []

                        # Initial wait for page to load
                        js_scenario.append({'wait': 2000})

                        # Scroll multiple times to load more content
                        # Use smaller, more frequent scrolls for better reliability
                        for i in range(scrolls_needed):
                            # Scroll down progressively (each scroll goes further)
                            scroll_amount = 800 * (i + 1)  # 800, 1600, 2400, etc.
                            js_scenario.append({'scrollY': scroll_amount})
                            # Wait for Pinterest's infinite scroll to load new content
                            js_scenario.append(
                                {'wait': 2000}
                            )  # Wait 2 seconds between scrolls

                        # Final wait to ensure all content is loaded
                        js_scenario.append({'wait': 2000})

                        # Add js_scenario to ScrapingBee parameters (must be JSON string)
                        import json

                        sb_params['js_scenario'] = json.dumps(js_scenario)

                        # Also increase base wait time
                        sb_params['wait'] = '4000'  # Longer initial wait when scrolling

                        logger.info(
                            f'Pinterest public search: Added js_scenario with {len(js_scenario)} actions to scroll {scrolls_needed} times'
                        )
                        logger.debug(
                            f'Pinterest public search: js_scenario = {json.dumps(js_scenario)}'
                        )
                    except Exception as e:
                        logger.error(
                            f'Pinterest public search: Failed to create js_scenario: {e}',
                            exc_info=True,
                        )
                        # Continue without scrolling if scenario creation fails
                logger.warning('=' * 80)
                logger.warning(
                    'Pinterest public search: Using SCRAPINGBEE with JS rendering'
                )
                logger.warning(f'Target URL: {target_url} (query="{search}")')
                logger.warning('=' * 80)
                try:
                    resp = await client.get(
                        proxy_url,
                        params=sb_params,
                        headers={'Accept': base_headers['Accept']},
                    )
                    resp.raise_for_status()
                    html_content = resp.text
                    method_used = 'scrapingbee'
                    logger.warning(
                        f'Pinterest public search: ScrapingBee returned HTML (length: {len(html_content)}, status: {resp.status_code})'
                    )
                    logger.warning(
                        f'HTML snippet (first 500 chars): {html_content[:500]}'
                    )
                    logger.warning(
                        f'HTML contains "data-test-id": {"data-test-id" in html_content}'
                    )
                    logger.warning(
                        f'HTML contains "non-story-pin-image": {"non-story-pin-image" in html_content}'
                    )
                    logger.warning(f'HTML contains "<img": {"<img" in html_content}')
                    logger.warning(f'HTML contains "/pin/": {"/pin/" in html_content}')
                except httpx.HTTPStatusError as exc:
                    # Check if it's a 400 error - js_scenario might not be supported
                    if exc.response.status_code == 400 and 'js_scenario' in str(
                        sb_params
                    ):
                        logger.warning(
                            'ScrapingBee returned 400 - js_scenario might not be supported in your plan'
                        )
                        logger.warning('Retrying without js_scenario parameter...')
                        # Remove js_scenario and try again
                        sb_params_retry = {
                            k: v for k, v in sb_params.items() if k != 'js_scenario'
                        }
                        try:
                            resp = await client.get(
                                proxy_url,
                                params=sb_params_retry,
                                headers={'Accept': base_headers['Accept']},
                            )
                            resp.raise_for_status()
                            html_content = resp.text
                            method_used = 'scrapingbee'
                            logger.warning(
                                f'Pinterest public search: ScrapingBee (without js_scenario) returned HTML (length: {len(html_content)}, status: {resp.status_code})'
                            )
                            logger.warning(
                                'Note: Scrolling not available - will extract available items only'
                            )
                        except Exception as retry_exc:
                            logger.error(f'ScrapingBee retry failed: {retry_exc}')
                            raise exc  # Re-raise original exception to fall back to direct
                    else:
                        raise exc  # Re-raise if not a 400 or different error
                except Exception as exc:
                    logger.error(
                        'ScrapingBee request failed, falling back to direct request: %s',
                        exc,
                        exc_info=True,
                    )
                    # Fallback to direct request below
                    logger.warning('Falling back to DIRECT request...')
                    # Direct request - Pinterest might return compressed content
                    resp = await client.get(url, headers=base_headers, params=params)
                    resp.raise_for_status()
                    # httpx should handle decompression automatically, but check
                    html_content = resp.text
                    # Check if content looks compressed/garbled (binary data)
                    if len(html_content) > 0 and (
                        html_content[0] in ['\x1f', '\x78']
                        or not html_content[:100].isprintable()
                    ):
                        logger.warning(
                            'HTML content appears compressed - attempting decompression'
                        )
                        try:
                            import gzip

                            html_content = gzip.decompress(resp.content).decode('utf-8')
                            logger.info('Successfully decompressed HTML content')
                        except Exception as decomp_error:
                            logger.error(f'Failed to decompress HTML: {decomp_error}')
                            # Try to decode as-is with error handling
                            html_content = resp.content.decode('utf-8', errors='ignore')
                    logger.warning(
                        f'Pinterest public search: Direct request returned HTML (length: {len(html_content)}, status: {resp.status_code})'
                    )
                    logger.warning(
                        f'HTML snippet (first 500 chars): {html_content[:500]}'
                    )
                    logger.warning(
                        f'HTML contains "data-test-id": {"data-test-id" in html_content}'
                    )
                    logger.warning(
                        f'HTML contains "non-story-pin-image": {"non-story-pin-image" in html_content}'
                    )
                    logger.warning(f'HTML contains "<img": {"<img" in html_content}')
                    logger.warning(f'HTML contains "/pin/": {"/pin/" in html_content}')

            # If neither Playwright nor ScrapingBee worked, use direct request
            if html_content is None:
                # Direct request without proxy/headless browser
                logger.warning('=' * 80)
                logger.warning(
                    'Pinterest public search: Using DIRECT request (no Playwright/ScrapingBee)'
                )
                logger.warning(f'URL: {url} with query="{search}"')
                logger.warning(
                    'NOTE: Direct requests may not get JavaScript-rendered content!'
                )
                logger.warning('=' * 80)
                resp = await client.get(url, headers=base_headers, params=params)
                resp.raise_for_status()
                html_content = resp.text
                method_used = 'direct'
                logger.warning(
                    f'Pinterest public search: Direct request returned HTML (length: {len(html_content)}, status: {resp.status_code})'
                )
                logger.warning(f'HTML snippet (first 500 chars): {html_content[:500]}')
                logger.warning(
                    f'HTML contains "data-test-id": {"data-test-id" in html_content}'
                )
                logger.warning(
                    f'HTML contains "non-story-pin-image": {"non-story-pin-image" in html_content}'
                )
                logger.warning(f'HTML contains "<img": {"<img" in html_content}')
                logger.warning(f'HTML contains "/pin/": {"/pin/" in html_content}')

            # Check if __PWS_ROOT__ is populated (React has rendered)
            pws_root_empty = (
                '<div data-reactcontainer="true" id="__PWS_ROOT__"><!--$~--><template'
                in html_content
                or '<div data-reactcontainer="true" id="__PWS_ROOT__"></div>'
                in html_content
            )
            pws_root_has_content = (
                'data-test-id="non-story-pin-image"' in html_content
                or '<div data-reactcontainer="true" id="__PWS_ROOT__"><div'
                in html_content
            )
            logger.warning(f'__PWS_ROOT__ empty (React not rendered): {pws_root_empty}')
            logger.warning(
                f'__PWS_ROOT__ has content (React rendered): {pws_root_has_content}'
            )

            # Additional debugging: check for common Pinterest HTML patterns
            logger.warning('HTML debugging:')
            logger.warning(
                f'  - Contains "__PWS_ROOT__": {"__PWS_ROOT__" in html_content}'
            )
            logger.warning(
                f'  - Contains "data-test-id": {"data-test-id" in html_content}'
            )
            logger.warning(
                f'  - Contains "non-story-pin-image": {"non-story-pin-image" in html_content}'
            )
            logger.warning(f'  - Contains "pinimg.com": {"pinimg.com" in html_content}')
            logger.warning(f'  - Contains "/pin/": {"/pin/" in html_content}')
            logger.warning(f'  - Contains "<img": {"<img" in html_content}')
            logger.warning(
                f'  - Contains "data-pin-id": {"data-pin-id" in html_content}'
            )

            # Check if HTML looks like an error page or blocked content
            if (
                'blocked' in html_content.lower()
                or 'access denied' in html_content.lower()
                or 'captcha' in html_content.lower()
            ):
                logger.error('HTML content suggests blocking or CAPTCHA challenge')
            if len(html_content) < 10000:
                logger.warning(
                    f'HTML content is very short ({len(html_content)} chars), might be an error page'
                )

            # Save HTML to file for debugging
            try:
                debug_dir = Path('debug_html')
                debug_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = (
                    debug_dir
                    / f'pinterest_search_{search}_{method_used}_{timestamp}.html'
                )
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.warning(f'Saved HTML content to: {filename.absolute()}')
            except Exception as e:
                logger.error(f'Failed to save HTML to file: {e}')

            # Pinterest embeds JSON data in script tags
            # Look for window.__initialData__ or similar patterns
            items = []

            # Try HTML extraction FIRST (more reliable for current Pinterest structure)
            logger.warning('=' * 80)
            logger.warning('Pinterest public search: Trying HTML extraction first')
            logger.warning(f'HTML content length: {len(html_content)}')
            logger.warning('=' * 80)

            # Log some HTML structure hints for debugging
            has_script_tags = '<script' in html_content
            has_pin_mentions = (
                'pin' in html_content.lower() or 'data-pin' in html_content
            )
            has_img_tags = '<img' in html_content
            has_data_pin_id = 'data-pin-id' in html_content.lower()
            has_pws_data = (
                '__pws_data__' in html_content.lower()
                or '__initialdata__' in html_content.lower()
            )
            has_test_id = 'data-test-id="non-story-pin-image"' in html_content
            logger.warning('Pinterest public search: HTML structure analysis:')
            logger.warning(f'  - script tags: {has_script_tags}')
            logger.warning(f'  - pin mentions: {has_pin_mentions}')
            logger.warning(f'  - img tags: {has_img_tags}')
            logger.warning(f'  - data-pin-id: {has_data_pin_id}')
            logger.warning(f'  - __PWS_DATA__: {has_pws_data}')
            logger.warning(f'  - data-test-id="non-story-pin-image": {has_test_id}')

            # Check if HTML looks valid
            if len(html_content) < 5000:
                logger.error(
                    f'HTML content is suspiciously short ({len(html_content)} chars) - might be an error page or blocked'
                )
                logger.warning(f'First 1000 chars of HTML: {html_content[:1000]}')
            elif 'pinterest' not in html_content.lower()[:5000]:
                logger.warning(
                    'HTML does not contain "pinterest" in first 5000 chars - might not be Pinterest page'
                )

            logger.warning('Calling _extract_pins_from_html function...')
            try:
                # Extract ALL available items from HTML (no limit or very high limit)
                # Pinterest's HTML contains a finite number of items, and we'll paginate through them
                # Use a very high limit to extract everything available
                extraction_limit = (
                    per_page * 20
                )  # Extract up to 20 pages worth (600 items if per_page=30)
                # This ensures we get all items Pinterest initially loads, even for later pages
                logger.info(
                    f'Pinterest public search: Extracting up to {extraction_limit} items (will paginate through them, scroll_position={scroll_position if bookmark else 0})'
                )

                items = _extract_pins_from_html(html_content, extraction_limit)
                logger.warning(
                    f'Returned from _extract_pins_from_html, got {len(items)} items'
                )

                # Log how many items we have vs what we need for pagination
                if bookmark and scroll_position > 0:
                    items_needed = scroll_position * per_page
                    logger.info(
                        f'Pinterest public search: Have {len(items)} items, need at least {items_needed} for page {scroll_position}'
                    )
                    if len(items) < items_needed:
                        logger.warning(
                            f'Pinterest public search: WARNING - Only {len(items)} items extracted, but need {items_needed} for page {scroll_position}. Pinterest HTML might be limited.'
                        )
            except Exception as e:
                logger.error(
                    f'Error calling _extract_pins_from_html: {e}', exc_info=True
                )
                items = []
            if items:
                logger.info(
                    f'Pinterest public search: extracted {len(items)} pins from HTML for query "{search}"'
                )
            else:
                logger.warning(
                    f'Pinterest public search: no pins extracted from HTML for query "{search}". HTML length: {len(html_content)}'
                )
                # Count occurrences of key patterns
                html_lower = html_content.lower()
                data_pin_id_count = html_lower.count('data-pin-id')
                img_count = html_lower.count('<img')
                pin_url_count = html_lower.count('/pin/')
                test_id_count = html_lower.count('data-test-id="non-story-pin-image"')
                logger.warning(
                    f'Pinterest public search: Pattern counts - data-pin-id: {data_pin_id_count}, <img> tags: {img_count}, /pin/ URLs: {pin_url_count}, data-test-id: {test_id_count}'
                )

            # If HTML extraction failed, try JSON as fallback
            if not items:
                logger.info(
                    'Pinterest public search: HTML extraction failed, trying JSON parsing as fallback'
                )
                # Try to extract JSON from script tags
                # Pinterest embeds data in various script tags with JSON
                # Look for script tags containing JSON data
                json_patterns = [
                    # Modern Pinterest patterns
                    r'<script[^>]*id="__PWS_DATA__"[^>]*>(.+?)</script>',
                    r'window\.__PWS_DATA__\s*=\s*({.+?});',
                    r'window\.__initialData__\s*=\s*({.+?});',
                    r'window\.__PWS_INITIAL_STATE__\s*=\s*({.+?});',
                    r'<script[^>]*id="initial-state"[^>]*>(.+?)</script>',
                    # Look for JSON-LD or other embedded JSON
                    r'<script[^>]*type="application/json"[^>]*>(.+?)</script>',
                ]

                for i, pattern in enumerate(json_patterns):
                    matches = re.findall(pattern, html_content, re.DOTALL)
                    logger.info(
                        f'JSON extraction: Pattern {i+1} found {len(matches)} matches'
                    )
                    if matches:
                        try:
                            # Try to parse the JSON
                            json_str = matches[0].strip()
                            # Clean up the JSON string if needed - remove potential JS wrapper
                            json_str = re.sub(
                                r'^[^{[]*', '', json_str
                            )  # Remove leading non-JSON
                            json_str = re.sub(
                                r'[^}\]]*$', '', json_str
                            )  # Remove trailing non-JSON

                            if json_str.startswith('{') or json_str.startswith('['):
                                data = json.loads(json_str)
                                logger.info(
                                    f'JSON extraction: Successfully parsed JSON, type: {type(data).__name__}'
                                )

                                # Navigate through Pinterest's data structure
                                # Pinterest's structure varies, so we'll try multiple paths
                                pins_data = None

                                # Try different possible paths in the JSON structure
                                # Modern Pinterest structure
                                if isinstance(data, dict):
                                    top_keys = list(data.keys())[:10]
                                    logger.info(
                                        f'JSON extraction: JSON top-level keys: {top_keys}'
                                    )

                                    # Try __PWS_DATA__ structure
                                    if 'props' in data:
                                        props = data.get('props', {})
                                        if 'initialReduxState' in props:
                                            redux_state = props.get(
                                                'initialReduxState', {}
                                            )
                                            pins_data = redux_state.get(
                                                'resources', {}
                                            ).get('results', {})
                                            logger.info(
                                                'JSON extraction: Found pins_data via props.initialReduxState.resources.results'
                                            )
                                        elif 'resourceResponses' in props:
                                            pins_data = props.get(
                                                'resourceResponses', []
                                            )
                                            logger.info(
                                                'JSON extraction: Found pins_data via props.resourceResponses'
                                            )

                                    # Try direct paths
                                    if not pins_data:
                                        if 'initialReduxState' in data:
                                            redux_state = data.get(
                                                'initialReduxState', {}
                                            )
                                            pins_data = redux_state.get(
                                                'resources', {}
                                            ).get('results', {})
                                            logger.info(
                                                'JSON extraction: Found pins_data via initialReduxState.resources.results'
                                            )
                                        elif 'resourceResponses' in data:
                                            pins_data = data.get(
                                                'resourceResponses', []
                                            )
                                            logger.info(
                                                'JSON extraction: Found pins_data via resourceResponses'
                                            )
                                        elif 'results' in data:
                                            pins_data = data.get('results', {})
                                            logger.info(
                                                'JSON extraction: Found pins_data via results'
                                            )
                                        elif 'data' in data:
                                            pins_data = data.get('data', {})
                                            logger.info(
                                                'JSON extraction: Found pins_data via data'
                                            )

                                    # Try recursive search for pin-like structures
                                    if not pins_data:

                                        def find_pins_recursive(
                                            obj, depth=0, max_depth=6, path=''
                                        ):
                                            if depth > max_depth:
                                                return None

                                            if isinstance(obj, list) and len(obj) > 0:
                                                # Check if list contains pin-like objects
                                                first_item = obj[0] if obj else None
                                                if isinstance(first_item, dict):
                                                    # Check for pin-like keys
                                                    has_pin_keys = any(
                                                        k in first_item
                                                        for k in [
                                                            'id',
                                                            'pin_id',
                                                            'pinId',
                                                            'image',
                                                            'images',
                                                            'media',
                                                            'dominant_color',
                                                        ]
                                                    )
                                                    has_image_ref = (
                                                        'image'
                                                        in str(first_item).lower()
                                                        or 'pinimg'
                                                        in str(first_item).lower()
                                                    )
                                                    if has_pin_keys and has_image_ref:
                                                        logger.info(
                                                            f'JSON extraction: Found pin-like list at path: {path} (length: {len(obj)})'
                                                        )
                                                        return obj

                                            elif isinstance(obj, dict):
                                                # Check if dict contains pin-like keys
                                                has_pin_keys = any(
                                                    k in obj
                                                    for k in [
                                                        'id',
                                                        'pin_id',
                                                        'pinId',
                                                        'image',
                                                        'images',
                                                        'media',
                                                    ]
                                                )
                                                has_image_ref = (
                                                    'image' in str(obj).lower()
                                                    or 'pinimg' in str(obj).lower()
                                                )

                                                if has_pin_keys and has_image_ref:
                                                    logger.info(
                                                        f'JSON extraction: Found pin-like object at path: {path}'
                                                    )
                                                    return [obj]

                                                # Recursively search - prioritize certain keys
                                                priority_keys = [
                                                    'results',
                                                    'data',
                                                    'items',
                                                    'pins',
                                                    'resources',
                                                    'response',
                                                    'resourceResponses',
                                                ]
                                                for k in priority_keys:
                                                    if k in obj:
                                                        result = find_pins_recursive(
                                                            obj[k],
                                                            depth + 1,
                                                            max_depth,
                                                            f'{path}.{k}',
                                                        )
                                                        if result:
                                                            return result

                                                # Then search all other keys
                                                for k, v in obj.items():
                                                    if k not in priority_keys:
                                                        result = find_pins_recursive(
                                                            v,
                                                            depth + 1,
                                                            max_depth,
                                                            f'{path}.{k}',
                                                        )
                                                        if result:
                                                            return result
                                            return None

                                        pins_data = find_pins_recursive(
                                            data, path='root'
                                        )
                                        if pins_data:
                                            logger.info(
                                                f'JSON extraction: Found pins_data via recursive search (type: {type(pins_data).__name__}, length: {len(pins_data) if isinstance(pins_data, list) else "N/A"})'
                                            )

                                if pins_data:
                                    # Extract pin information
                                    items = _extract_pins_from_data(pins_data, per_page)
                                    if items:
                                        logger.info(
                                            f'Pinterest public search: extracted {len(items)} pins from JSON for query "{search}"'
                                        )
                                        break
                                    else:
                                        logger.warning(
                                            f'JSON extraction: pins_data found but _extract_pins_from_data returned empty (pins_data type: {type(pins_data).__name__})'
                                        )
                                else:
                                    logger.warning(
                                        'JSON extraction: No pins_data found in JSON structure'
                                    )
                        except (json.JSONDecodeError, KeyError, TypeError) as e:
                            logger.debug(
                                f'JSON extraction: Failed to parse JSON pattern {i+1}: {type(e).__name__}: {e}'
                            )
                            continue
                        except Exception as e:
                            logger.debug(
                                f'JSON extraction: Unexpected error with pattern {i+1}: {type(e).__name__}: {e}'
                            )
                            continue

                logger.info(
                    f'Pinterest public search: After JSON extraction (fallback), items count: {len(items)}'
                )

            # Note: We don't filter out "unknown" authors anymore because HTML extraction
            # doesn't have access to author information, but the pins are still valid.
            # The "unknown" author filter was too aggressive and removed valid pins.
            if items:
                logger.info(
                    f'Pinterest public search: Keeping {len(items)} items (including those with unknown authors from HTML extraction)'
                )

            if not items:
                logger.warning(
                    f'Pinterest public search: returning empty results for query "{search}"'
                )

            # Pagination approach: Extract many items on first load, then paginate through them
            # Since scrolling doesn't work reliably with ScrapingBee, we extract all available items
            # and paginate through them on the backend
            # IMPORTANT: Each request gets the SAME HTML from Pinterest, so we extract the same items
            # We need to track total extracted BEFORE pagination to know if more items exist
            total_extracted_before_pagination = len(items)

            # Slice items for this logical page
            if bookmark and scroll_position > 0:
                # Calculate start index based on logical page (1-based)
                items_to_skip = (scroll_position - 1) * per_page
                start_idx = min(
                    items_to_skip, max(0, total_extracted_before_pagination - per_page)
                )
                end_idx = start_idx + per_page
                paginated_items = items[start_idx:end_idx]
                logger.info(
                    f'Pinterest public search: Pagination page {scroll_position} - returning items '
                    f'{start_idx} to {start_idx + len(paginated_items)} '
                    f'(total extracted: {total_extracted_before_pagination})'
                )
                items = paginated_items
            else:
                # First page - return first per_page items
                items = items[:per_page]
                items_returned_count = len(items)
                logger.info(
                    f'Pinterest public search: First page - returning {items_returned_count} items (total extracted: {total_extracted_before_pagination} items available, per_page={per_page})'
                )

            # Compute dominant_color for returned items (public parser only)
            if items:
                logger.info(
                    f'Pinterest public search: Computing dominant_color for {len(items)} items'
                )
                for item in items:
                    try:
                        if not item.get('dominant_color') and item.get('image_url'):
                            color = await _compute_dominant_color_from_url(
                                item['image_url'], client
                            )
                            if color:
                                item['dominant_color'] = color
                    except Exception as color_err:
                        logger.debug(
                            f'Pinterest public search: Failed to compute dominant_color for item: {color_err}'
                        )

            # Generate bookmark for next page.
            # IMPORTANT: Pinterest uses true infinite scroll, so the total number of
            # available results is usually much larger than what we can load in one
            # Playwright session. We therefore do NOT try to guess whether more items
            # exist based on the current HTML count – we assume more pages are
            # available as long as we successfully returned at least one item.
            next_bookmark = None
            if items:
                if bookmark and scroll_position > 0:
                    # We are on a subsequent logical page, always offer the next one.
                    next_bookmark = str(scroll_position + 1)
                    logger.info(
                        f'Pinterest public search: Generated bookmark "{next_bookmark}" for next page '
                        f'(page={scroll_position}, returned={len(items)}, total_extracted={total_extracted_before_pagination})'
                    )
                else:
                    # First logical page – always offer page 2 if we have any items.
                    next_bookmark = '2'
                    logger.info(
                        f'Pinterest public search: Generated bookmark "2" for next page '
                        f'(returned={len(items)}, total_extracted={total_extracted_before_pagination}, per_page={per_page})'
                    )
            else:
                logger.warning(
                    'Pinterest public search: No items found, returning bookmark=None'
                )

            return {
                'items': items,  # Already limited/trimmed above
                'bookmark': next_bookmark,  # Return bookmark for pagination
            }

    except httpx.HTTPStatusError as exc:
        error_text = (
            exc.response.text[:1000] if exc.response.text else 'No response body'
        )
        logger.error(
            'Pinterest public search HTTP error %d: %s. Request URL: %s',
            exc.response.status_code,
            error_text,
            exc.request.url,
        )
        raise ServiceUnavailable(
            f'Pinterest public search error {exc.response.status_code}: {error_text}'
        ) from exc
    except Exception as exc:
        logger.error('Pinterest public search failed: %s', exc, exc_info=True)
        raise ServiceUnavailable(
            f'Pinterest public search request failed: {str(exc)}'
        ) from exc


def _extract_pins_from_data(data: dict | list, limit: int = 20) -> list[dict]:
    """
    Extract pin information from Pinterest's JSON data structure.

    Args:
        data: Pinterest JSON data (dict or list)
        limit: Maximum number of pins to extract

    Returns:
        List of pin dictionaries in API-compatible format
    """
    items = []

    try:
        # Pinterest's data structure can vary
        # Try to find pin objects in various formats
        if isinstance(data, list):
            for item in data[:limit]:
                pin = _parse_pin_object(item)
                if pin:
                    items.append(pin)
        elif isinstance(data, dict):
            # Look for common keys that contain pin data
            for key in ['data', 'results', 'pins', 'items', 'pinData']:
                if key in data:
                    pins = data[key]
                    if isinstance(pins, list):
                        for pin_data in pins[:limit]:
                            pin = _parse_pin_object(pin_data)
                            if pin:
                                items.append(pin)
                    elif isinstance(pins, dict):
                        # Might be a dict of pin IDs to pin objects
                        for pin_data in list(pins.values())[:limit]:
                            pin = _parse_pin_object(pin_data)
                            if pin:
                                items.append(pin)
    except Exception as e:
        logger.debug(f'Error extracting pins from data: {e}')

    return items


def _parse_pin_object(pin_data: dict) -> dict | None:
    """
    Parse a single pin object from Pinterest's data structure.

    Args:
        pin_data: Raw pin data dictionary

    Returns:
        Parsed pin dictionary in API-compatible format, or None if invalid
    """
    try:
        # Pinterest pin structure varies, try to extract common fields
        pin_id = pin_data.get('id') or pin_data.get('pin_id') or pin_data.get('pinId')

        # Get image URL
        image_url = None
        if 'images' in pin_data:
            images = pin_data['images']
            # Try different image size keys
            for size in ['originals', '736x', '564x', '474x', '236x']:
                if size in images and isinstance(images[size], dict):
                    image_url = images[size].get('url')
                    if image_url:
                        break
                elif isinstance(images, dict) and 'url' in images:
                    image_url = images.get('url')
                    break

        if not image_url:
            # Try alternative paths
            image_url = (
                pin_data.get('image_url')
                or pin_data.get('imageUrl')
                or pin_data.get('media', {}).get('image', {}).get('url')
                if isinstance(pin_data.get('media'), dict)
                else None
            )

        if not image_url or not pin_id:
            return None

        # Get pin description/title
        description = (
            pin_data.get('description')
            or pin_data.get('title')
            or pin_data.get('rich_summary', {}).get('display_description')
            if isinstance(pin_data.get('rich_summary'), dict)
            else None
        ) or ''

        # Get author/creator info
        creator = pin_data.get('creator') or pin_data.get('owner') or {}
        author_username = (
            creator.get('username')
            or creator.get('id')
            or pin_data.get('creator_username')
            or pin_data.get('board', {}).get('owner', {}).get('username')
            if isinstance(pin_data.get('board'), dict)
            else None
        ) or 'unknown'

        author_name = creator.get('full_name') or creator.get('name') or author_username

        # Get pin link
        pin_link = (
            pin_data.get('link')
            or pin_data.get('url')
            or f'https://www.pinterest.com/pin/{pin_id}/'
        )

        # Get board info
        board = pin_data.get('board') or {}
        board_name = board.get('name') or ''

        return {
            'id': pin_id,
            'image_url': image_url,
            'description': description,
            'link': pin_link,
            'author': {
                'username': author_username,
                'name': author_name,
            },
            'board': {
                'name': board_name,
            },
        }
    except Exception as e:
        logger.debug(f'Error parsing pin object: {e}')
        return None


def _is_valid_pin_id(pin_id: str) -> bool:
    """
    Check if a pin ID is valid (not a UI element, navigation link, or file reference).

    Args:
        pin_id: Pin ID to validate

    Returns:
        True if pin ID appears to be a valid Pinterest pin ID, False otherwise
    """
    if not pin_id:
        return False

    pin_id_lower = pin_id.lower().strip()

    # Exclude common UI/navigation words
    excluded_ids = [
        'create',
        'search',
        'home',
        'explore',
        'ideas',
        'saved',
        'profile',
        'settings',
        'help',
        'about',
        'business',
        'terms',
        'privacy',
        'pin',
        'pins',
        'board',
        'boards',
        'user',
        'users',
        'login',
        'signup',
        'sign',
        'up',
        'in',
        'out',
    ]

    if pin_id_lower in excluded_ids:
        return False

    # Exclude file references (JS modules, CSS, etc.)
    if any(
        ext in pin_id_lower
        for ext in ['.mjs', '.js', '.css', '.json', '.html', '.svg', '[id]', '[', ']']
    ):
        return False

    # Valid pin IDs are typically long alphanumeric strings (usually 10+ characters)
    # They often contain letters, numbers, and sometimes hyphens/underscores
    # Short IDs (less than 8 chars) are likely UI elements
    if len(pin_id) < 8:
        return False

    # Should contain alphanumeric characters
    if not re.search(r'[a-zA-Z0-9]', pin_id):
        return False

    # Pinterest pin IDs are typically hexadecimal-like strings
    # They don't usually contain brackets or special file extensions
    if re.search(r'[\[\]{}()]', pin_id):
        return False

    return True


def _is_valid_pin_image_url(url: str) -> bool:
    """
    Check if a URL is a valid pin image (not a logo/placeholder).

    Args:
        url: Image URL to check

    Returns:
        True if URL appears to be a valid pin image, False otherwise
    """
    if not url:
        return False

    url_lower = url.lower()

    # Exclude Pinterest logo/placeholder images
    excluded_patterns = [
        'facebook_share_image',
        'logo',
        'pinterest-logo',
        'pinterest_logo',
        'favicon',
        'icon',
        'placeholder',
        'default',
        's.pinimg.com/images/',  # Static images directory (logos, etc.)
    ]

    for pattern in excluded_patterns:
        if pattern in url_lower:
            return False

    # Valid pin images should be from pinimg.com CDN and have image extensions
    # or be from pinterest.com/pin/ paths
    is_pinimg = 'pinimg.com' in url_lower
    has_image_ext = any(
        ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    )
    is_pin_path = '/pin/' in url_lower

    # Must be from pinimg CDN with image extension, or be a pin path
    return (is_pinimg and has_image_ext) or (is_pin_path and has_image_ext)


def _infer_image_size_from_url(url: str) -> tuple[int | None, int | None]:
    """
    Infer approximate image dimensions from common Pinterest CDN URL patterns.
    Examples:
        https://i.pinimg.com/736x/...jpg    -> (736, None)
        https://i.pinimg.com/400x300/...   -> (400, 300)
        https://i.pinimg.com/originals/... -> (1200, 1200) (treated as large square)
    """
    try:
        parts = url.split('/')
        for part in parts:
            m = re.match(r'(\d+)x(\d+)', part)
            if m:
                w = int(m.group(1))
                h = int(m.group(2))
                return w, h
            # Sometimes only width is encoded like "736x"
            m2 = re.match(r'(\d+)x$', part)
            if m2:
                w = int(m2.group(1))
                return w, None
        # Originals – treat as very large
        if 'originals' in url:
            return 1200, 1200
    except Exception:
        pass
    return None, None


def _image_quality_score(item: dict) -> float:
    """
    Compute a heuristic quality score for an image based on its URL.
    Higher score = better image for our use-case.
    """
    url = item.get('image_url') or ''
    w, h = _infer_image_size_from_url(url)

    if not w and not h:
        # Unknown size – neutral score
        return 0.0

    # Estimate area; if height unknown, approximate with width
    if not h:
        h = w or 0
    area = (w or 0) * (h or 0)

    # Aspect ratio heuristic: penalize extreme ratios (very tall or very wide)
    ratio_penalty = 1.0
    if w and h and h > 0:
        aspect = w / h
        # Acceptable range ~ portrait/landscape photos
        if aspect < 0.5 or aspect > 2.5:
            ratio_penalty = 0.6  # penalize infographics / banners slightly

    return float(area) * ratio_penalty


async def _compute_dominant_color_from_url(
    url: str,
    client: httpx.AsyncClient,
    timeout: float = 10.0,
) -> str | None:
    """
    Compute a simple average/dominant color for an image URL.
    This runs on the backend to avoid browser CORS limitations.
    Returns a hex color string like "#aabbcc" or None on failure.
    """
    if not PIL_AVAILABLE:
        # Pillow not installed – skip color computation
        return None

    try:
        resp = await client.get(url, timeout=timeout)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert('RGB')
        # Downscale heavily to speed up averaging
        img = img.resize((32, 32))
        pixels = list(img.getdata())
        if not pixels:
            return None
        r = sum(p[0] for p in pixels) / len(pixels)
        g = sum(p[1] for p in pixels) / len(pixels)
        b = sum(p[2] for p in pixels) / len(pixels)
        return f'#{int(r):02x}{int(g):02x}{int(b):02x}'
    except Exception as e:
        logger.debug(f'Failed to compute dominant color for {url}: {e}')
        return None


async def compute_dominant_color_from_url(
    url: str,
    timeout: float = 10.0,
) -> str | None:
    """
    Public helper to compute dominant color for an external image URL.
    Returns a hex color like "#aabbcc" or None if unavailable.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return None

    async with httpx.AsyncClient(timeout=timeout) as client:
        return await _compute_dominant_color_from_url(
            url=url, client=client, timeout=timeout
        )


def _extract_pins_from_html(html: str, limit: int = 20) -> list[dict]:
    """
    Extract pin information directly from HTML if JSON parsing fails.
    This is a fallback method that parses HTML structure.

    Args:
        html: HTML content from Pinterest search page
        limit: Maximum number of pins to extract

    Returns:
        List of pin dictionaries
    """
    logger.warning('=' * 80)
    logger.warning('HTML EXTRACTION FUNCTION CALLED')
    logger.warning(f'HTML length: {len(html)}')
    logger.warning('=' * 80)

    items = []

    try:
        logger.warning(f'HTML extraction: Starting with HTML length {len(html)}')

        # Pinterest uses various data attributes and structures
        # Try multiple patterns to extract pin information

        # Pattern 0: Look for data-test-id="non-story-pin-image" divs (modern Pinterest structure)
        # These contain the actual pin images in the grid
        # Extract the div and its image, then find the pin ID from surrounding context
        # Note: srcset may appear before or after src, so we extract img attributes and parse separately
        test_id_pattern = (
            r'<div[^>]*data-test-id="non-story-pin-image"[^>]*>.*?<img([^>]*)>'
        )
        test_id_matches = list(
            re.finditer(test_id_pattern, html, re.DOTALL | re.IGNORECASE)
        )
        logger.warning(
            f'HTML extraction: Pattern 0 (data-test-id="non-story-pin-image") found {len(test_id_matches)} matches'
        )

        if test_id_matches:
            seen_urls = set()
            for div_match in test_id_matches:
                img_attrs = div_match.group(1)
                # Extract src and srcset from img attributes (order-independent)
                src_match = re.search(r'src="([^"]+)"', img_attrs, re.IGNORECASE)
                srcset_match = re.search(r'srcset="([^"]+)"', img_attrs, re.IGNORECASE)

                src_url = src_match.group(1) if src_match else None
                srcset = srcset_match.group(1) if srcset_match else None

                if not src_url:
                    continue

                # ALWAYS prefer highest quality image from srcset if available
                # The src attribute is usually the smallest thumbnail (236x), while srcset has larger sizes
                img_url = None
                if srcset:
                    # Extract all valid Pinterest image URLs from srcset
                    sizes = re.findall(
                        r'https://i\.pinimg\.com/[^\s,]+', srcset, re.IGNORECASE
                    )
                    if sizes:
                        # Prefer larger sizes in order: originals > 736x > 474x > 236x > any other
                        preferred_url = None
                        for size_pref in ['originals', '736x', '474x', '236x']:
                            for size_url in sizes:
                                if size_pref in size_url and _is_valid_pin_image_url(
                                    size_url
                                ):
                                    preferred_url = size_url
                                    break
                            if preferred_url:
                                break
                        # If no preferred size found, use first valid URL from srcset
                        if not preferred_url:
                            for size_url in sizes:
                                if _is_valid_pin_image_url(size_url):
                                    preferred_url = size_url
                                    break
                        # Use srcset URL if found
                        if preferred_url:
                            img_url = preferred_url

                # Only fall back to src_url if srcset didn't provide a valid URL
                if not img_url:
                    img_url = src_url

                # Skip duplicates
                if img_url in seen_urls:
                    continue
                seen_urls.add(img_url)

                if not _is_valid_pin_image_url(img_url):
                    continue

                pin_id = None
                # Search in context around this exact matched div occurrence.
                start = max(0, div_match.start() - 5000)
                end = min(len(html), div_match.end() + 5000)
                context = html[start:end]

                # Prefer explicit href="/pin/{id}/" links first, then generic /pin/ matches.
                pin_id_matches = list(
                    re.finditer(
                        r'href=["\'](?:https?://(?:www\.)?pinterest\.com)?/pin/([^/"\']+)/?[^"\']*["\']',
                        context,
                        re.IGNORECASE,
                    )
                )
                if not pin_id_matches:
                    pin_id_matches = list(
                        re.finditer(r'/pin/([^/"]+)/', context, re.IGNORECASE)
                    )
                if pin_id_matches:
                    div_pos_in_context = div_match.start() - start
                    closest_match = min(
                        pin_id_matches,
                        key=lambda m: abs(m.start() - div_pos_in_context),
                    )
                    pin_id = closest_match.group(1)
                    logger.warning(
                        f'Pattern 0: Found closest pin_id "{pin_id}" in context'
                    )
                else:
                    # Try searching in a wider area if not found in immediate context
                    wider_start = max(0, div_match.start() - 10000)
                    wider_end = min(len(html), div_match.end() + 10000)
                    wider_context = html[wider_start:wider_end]
                    wider_pin_id_matches = list(
                        re.finditer(
                            r'href=["\'](?:https?://(?:www\.)?pinterest\.com)?/pin/([^/"\']+)/?[^"\']*["\']',
                            wider_context,
                            re.IGNORECASE,
                        )
                    )
                    if not wider_pin_id_matches:
                        wider_pin_id_matches = list(
                            re.finditer(r'/pin/([^/"]+)/', wider_context, re.IGNORECASE)
                        )
                    if wider_pin_id_matches:
                        # Find the pin_id closest to our div position
                        div_pos = div_match.start()
                        closest_match = None
                        closest_distance = float('inf')
                        for match in wider_pin_id_matches:
                            match_pos = wider_start + match.start()
                            distance = abs(match_pos - div_pos)
                            if distance < closest_distance:
                                closest_distance = distance
                                closest_match = match
                        if closest_match:
                            pin_id = closest_match.group(1)
                            logger.warning(
                                f'Pattern 0: Found pin_id "{pin_id}" in wider context (distance: {closest_distance})'
                            )
                    else:
                        logger.warning(
                            f'Pattern 0: No pin_id found in context for image {img_url[:50]}...'
                        )

                # Skip only if pin_id is invalid (not None - None is allowed)
                if pin_id and not _is_valid_pin_id(pin_id):
                    logger.warning(f'Pattern 0: Invalid pin_id "{pin_id}", skipping')
                    continue

                # Make img_url absolute (should already be, but just in case)
                if not img_url.startswith('http'):
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = 'https://www.pinterest.com' + img_url

                # Generate link - use pin_id if available, otherwise use image URL or generic link
                if pin_id:
                    pin_link = f'https://www.pinterest.com/pin/{pin_id}/'
                else:
                    # If no pin_id, try to extract from image URL or use a generic link
                    pin_link = (
                        img_url
                        if img_url.startswith('http')
                        else 'https://www.pinterest.com'
                    )

                items.append(
                    {
                        'id': pin_id,  # Can be None
                        'image_url': img_url,
                        'description': '',
                        'link': pin_link,
                        'author': {
                            'username': 'unknown',
                            'name': 'unknown',
                        },
                        'board': {
                            'name': '',
                        },
                    }
                )

                # Don't break early - process all matches, limit will be applied at the end

            if items:
                logger.info(
                    f'HTML extraction: Found {len(items)} pins using pattern 0 (data-test-id)'
                )

        # Pattern 0.5: Fallback - find data-test-id divs and search for nearby pin links
        if not items:
            test_id_divs = list(
                re.finditer(
                    r'<div[^>]*data-test-id="non-story-pin-image"[^>]*>',
                    html,
                    re.IGNORECASE,
                )
            )
            logger.info(
                f'HTML extraction: Pattern 0.5 (data-test-id divs without link) found {len(test_id_divs)} matches'
            )

            seen_urls = set()
            for div_match in test_id_divs[
                : limit * 2
            ]:  # Check more divs to find valid ones
                # Get context around this div (1000 chars before and after)
                start = max(0, div_match.start() - 1000)
                end = min(len(html), div_match.end() + 1000)
                context = html[start:end]

                # Look for image URL in this context
                img_match = re.search(
                    r'<img[^>]*src="([^"]+)"[^>]*>', context, re.IGNORECASE
                )
                if not img_match:
                    continue

                img_url = img_match.group(1)
                if img_url in seen_urls or not _is_valid_pin_image_url(img_url):
                    continue
                seen_urls.add(img_url)

                # Look for pin ID in the context
                pin_id_match = re.search(r'/pin/([^/"]+)/', context)
                if not pin_id_match:
                    continue

                pin_id = pin_id_match.group(1)
                if not _is_valid_pin_id(pin_id):
                    continue

                # Make img_url absolute
                if not img_url.startswith('http'):
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    elif img_url.startswith('/'):
                        img_url = 'https://www.pinterest.com' + img_url

                items.append(
                    {
                        'id': pin_id,
                        'image_url': img_url,
                        'description': '',
                        'link': f'https://www.pinterest.com/pin/{pin_id}/',
                        'author': {
                            'username': 'unknown',
                            'name': 'unknown',
                        },
                        'board': {
                            'name': '',
                        },
                    }
                )

                if len(items) >= limit:
                    break

            if items:
                logger.info(
                    f'HTML extraction: Found {len(items)} pins using pattern 0.5 (data-test-id with context search)'
                )

        # Pattern 1: Look for img tags with pin data attributes (modern Pinterest)
        if not items:
            img_patterns = [
                r'<img[^>]*data-pin-id="([^"]+)"[^>]*src="([^"]+)"[^>]*alt="([^"]*)"',
                r'<img[^>]*src="([^"]+)"[^>]*data-pin-id="([^"]+)"[^>]*alt="([^"]*)"',
                r'<img[^>]*data-pin-id="([^"]+)"[^>]*src="([^"]+)"',
                r'<img[^>]*src="([^"]+)"[^>]*data-pin-id="([^"]+)"',
            ]

            for i, pattern in enumerate(img_patterns):
                matches = re.findall(pattern, html, re.IGNORECASE)
                logger.warning(
                    f'HTML extraction: Pattern 1.{i+1} (img with data-pin-id) found {len(matches)} matches'
                )
                if matches:
                    for match in matches[:limit]:
                        if len(match) >= 2:
                            # Determine which is pin_id and which is img_url
                            if 'pin' in match[0].lower() or match[0].startswith('/'):
                                pin_id = match[0]
                                img_url = match[1] if len(match) > 1 else None
                            else:
                                pin_id = match[1] if len(match) > 1 else None
                                img_url = match[0]

                            alt_text = match[2] if len(match) > 2 else ''

                            # Clean up pin_id - remove data-pin-id= prefix if present
                            if pin_id:
                                pin_id = re.sub(
                                    r'^data-pin-id=["\']?', '', pin_id, flags=re.I
                                )
                                pin_id = pin_id.strip('"\'')

                            # Validate we have both pin_id and img_url
                            if (
                                img_url
                                and pin_id
                                and (
                                    img_url.startswith('http')
                                    or img_url.startswith('//')
                                )
                            ):
                                # Make sure img_url is absolute
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif img_url.startswith('/'):
                                    img_url = 'https://www.pinterest.com' + img_url

                                # Validate it's a real pin image and valid pin ID
                                if _is_valid_pin_image_url(
                                    img_url
                                ) and _is_valid_pin_id(pin_id):
                                    items.append(
                                        {
                                            'id': pin_id,
                                            'image_url': img_url,
                                            'description': alt_text or '',
                                            'link': f'https://www.pinterest.com/pin/{pin_id}/',
                                            'author': {
                                                'username': 'unknown',
                                                'name': 'unknown',
                                            },
                                            'board': {
                                                'name': '',
                                            },
                                        }
                                    )
                if items:
                    logger.warning(
                        f'HTML extraction: Found {len(items)} pins using pattern 1'
                    )
                    break

        # Pattern 1.5: Extract pin IDs from /pin/ URLs and find Pinterest image URLs
        if not items:
            # Find all /pin/{id}/ URLs - but filter out UI elements
            pin_url_pattern = r'/pin/([^/"]+)/?'
            all_pin_matches = re.findall(pin_url_pattern, html, re.IGNORECASE)
            # Filter to only valid pin IDs (exclude UI elements like "create", "search", etc.)
            pin_matches = [pid for pid in all_pin_matches if _is_valid_pin_id(pid)]
            logger.info(
                f'HTML extraction: Found {len(all_pin_matches)} total /pin/ URLs, {len(pin_matches)} valid pin IDs (filtered out UI elements)'
            )

            # Find all Pinterest image URLs (i.pinimg.com) - filter out logos/placeholders
            pinterest_img_pattern = (
                r'https?://[^"\'<>]*pinimg\.com[^"\'<>]+\.(?:jpg|jpeg|png|webp)'
            )
            all_img_matches = re.findall(pinterest_img_pattern, html, re.IGNORECASE)
            # Filter out logo/placeholder images
            img_matches = [
                url for url in all_img_matches if _is_valid_pin_image_url(url)
            ]
            logger.info(
                f'HTML extraction: Found {len(all_img_matches)} total Pinterest image URLs, {len(img_matches)} valid pin images (filtered out logos/placeholders)'
            )

            if pin_matches:
                seen_pin_ids = set()
                # Get unique pin IDs
                unique_pin_ids = []
                for pin_id in pin_matches:
                    if pin_id not in seen_pin_ids:
                        seen_pin_ids.add(pin_id)
                        unique_pin_ids.append(pin_id)

                # Match pin IDs with image URLs
                # Pinterest image URLs often contain the pin ID or are in a similar order
                for i, pin_id in enumerate(unique_pin_ids[:limit]):
                    img_url = None

                    # Try to find image URL that might be associated with this pin
                    # Strategy: use images in order, or try to find pin ID in image URL
                    if i < len(img_matches):
                        img_url = img_matches[i]
                    else:
                        # Try to find image URL containing this pin ID
                        for img in img_matches:
                            if pin_id in img or img not in [
                                item.get('image_url') for item in items
                            ]:
                                img_url = img
                                break

                    # If still no image, use first available valid image
                    if not img_url and img_matches:
                        img_url = img_matches[0]

                    # Only add if we have a valid pin ID and image URL
                    if (
                        img_url
                        and _is_valid_pin_image_url(img_url)
                        and _is_valid_pin_id(pin_id)
                    ):
                        items.append(
                            {
                                'id': pin_id,
                                'image_url': img_url,
                                'description': '',
                                'link': f'https://www.pinterest.com/pin/{pin_id}/',
                                'author': {
                                    'username': 'unknown',
                                    'name': 'unknown',
                                },
                                'board': {
                                    'name': '',
                                },
                            }
                        )
                    elif not _is_valid_pin_id(pin_id):
                        logger.debug(
                            f'HTML extraction: Skipping invalid pin ID: {pin_id}'
                        )

                if items:
                    logger.info(
                        f'HTML extraction: Found {len(items)} pins using pattern 1.5 (pin URLs + image matching)'
                    )

        # Pattern 2: Look for anchor tags with pin links (common Pinterest structure)
        if not items:
            link_patterns = [
                r'<a[^>]*href="(/pin/([^/"]+)/?)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"',
                r'<a[^>]*href="(/pin/([^/"]+)/?)"[^>]*>.*?<img[^>]*src="([^"]+)"',
                r'href="(/pin/([^/"]+)/?)"[^>]*>.*?<img[^>]*src="([^"]+)"',
            ]
            for i, link_pattern in enumerate(link_patterns):
                matches = re.findall(link_pattern, html, re.DOTALL | re.IGNORECASE)
                logger.info(
                    f'HTML extraction: Pattern 2.{i+1} (anchor tags) found {len(matches)} matches'
                )
                if matches:
                    for match in matches[:limit]:
                        if len(match) >= 3:
                            link = (
                                match[0]
                                if match[0].startswith('/')
                                else f'/pin/{match[1]}/'
                            )
                            pin_id = match[1]
                            img_url = match[2] if len(match) > 2 else match[1]
                            alt_text = match[3] if len(match) > 3 else ''

                            # Make img_url absolute
                            if img_url and not img_url.startswith('http'):
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif img_url.startswith('/'):
                                    img_url = 'https://www.pinterest.com' + img_url

                            if (
                                img_url
                                and pin_id
                                and _is_valid_pin_image_url(img_url)
                                and _is_valid_pin_id(pin_id)
                            ):
                                items.append(
                                    {
                                        'id': pin_id,
                                        'image_url': img_url,
                                        'description': alt_text or '',
                                        'link': f'https://www.pinterest.com{link}',
                                        'author': {
                                            'username': 'unknown',
                                            'name': 'unknown',
                                        },
                                        'board': {
                                            'name': '',
                                        },
                                    }
                                )
                    if items:
                        logger.info(
                            f'HTML extraction: Found {len(items)} pins using pattern 2'
                        )
                        break

        # Pattern 3: Look for divs/articles with pin data attributes (modern Pinterest)
        if not items:
            div_patterns = [
                r'<div[^>]*data-pin-id="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"',
                r'<article[^>]*data-pin-id="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"',
                r'<div[^>]*data-test-pin-id="([^"]+)"[^>]*>.*?<img[^>]*src="([^"]+)"',
            ]
            for i, div_pattern in enumerate(div_patterns):
                matches = re.findall(div_pattern, html, re.DOTALL | re.IGNORECASE)
                logger.info(
                    f'HTML extraction: Pattern 3.{i+1} (div/article tags) found {len(matches)} matches'
                )
                if matches:
                    for pin_id, img_url in matches[:limit]:
                        if img_url and pin_id:
                            # Make img_url absolute
                            if not img_url.startswith('http'):
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif img_url.startswith('/'):
                                    img_url = 'https://www.pinterest.com' + img_url

                            # Validate it's a real pin image and valid pin ID
                            if _is_valid_pin_image_url(img_url) and _is_valid_pin_id(
                                pin_id
                            ):
                                items.append(
                                    {
                                        'id': pin_id,
                                        'image_url': img_url,
                                        'description': '',
                                        'link': f'https://www.pinterest.com/pin/{pin_id}/',
                                        'author': {
                                            'username': 'unknown',
                                            'name': 'unknown',
                                        },
                                        'board': {
                                            'name': '',
                                        },
                                    }
                                )
                    if items:
                        logger.info(
                            f'HTML extraction: Found {len(items)} pins using pattern 3'
                        )
                        break

        # Pattern 4: Look for Pinterest's lazy-loaded images with data-src
        if not items:
            lazy_pattern = r'<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>'
            matches = re.findall(lazy_pattern, html, re.IGNORECASE)
            logger.info(
                f'HTML extraction: Pattern 4 (lazy-loaded) found {len(matches)} matches'
            )
            if matches:
                for img_url, alt_text in matches[:limit]:
                    if img_url and _is_valid_pin_image_url(img_url):
                        # Try to extract pin ID from URL
                        pin_id_match = re.search(r'/pin/([^/]+)/', img_url)
                        if not pin_id_match:
                            # Try to extract from pinimg URL structure
                            pin_id_match = re.search(
                                r'/([a-zA-Z0-9_-]{10,})\.(?:jpg|jpeg|png|webp)', img_url
                            )
                        pin_id = pin_id_match.group(1) if pin_id_match else None

                        # Skip if we can't extract a valid pin ID
                        if not pin_id or not _is_valid_pin_id(pin_id):
                            continue

                        # Make img_url absolute
                        if not img_url.startswith('http'):
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            elif img_url.startswith('/'):
                                img_url = 'https://www.pinterest.com' + img_url

                        # Validate it's a real pin image and valid pin ID
                        if _is_valid_pin_image_url(img_url) and _is_valid_pin_id(
                            pin_id
                        ):
                            items.append(
                                {
                                    'id': pin_id,
                                    'image_url': img_url,
                                    'description': alt_text or '',
                                    'link': f'https://www.pinterest.com/pin/{pin_id}/',
                                    'author': {
                                        'username': 'unknown',
                                        'name': 'unknown',
                                    },
                                    'board': {
                                        'name': '',
                                    },
                                }
                            )
                if items:
                    logger.info(
                        f'HTML extraction: Found {len(items)} pins using pattern 4'
                    )

        # Pattern 4.5: Look for background-image CSS properties with Pinterest URLs
        if not items:
            bg_img_pattern = (
                r'background-image\s*:\s*url\(["\']?([^"\')]+pinimg[^"\')]+)["\']?\)'
            )
            all_bg_matches = re.findall(bg_img_pattern, html, re.IGNORECASE)
            # Filter out logo/placeholder images
            bg_matches = [url for url in all_bg_matches if _is_valid_pin_image_url(url)]
            logger.info(
                f'HTML extraction: Pattern 4.5 (background-image) found {len(all_bg_matches)} total URLs, {len(bg_matches)} valid pin images'
            )
            if bg_matches:
                seen_urls = set()
                for img_url in bg_matches[:limit]:
                    if img_url not in seen_urls and _is_valid_pin_image_url(img_url):
                        seen_urls.add(img_url)
                        # Try to extract pin ID from URL or generate one
                        pin_id_match = re.search(r'/pin/([^/]+)/', img_url)
                        if not pin_id_match:
                            # Try to extract from pinimg URL structure - look for long alphanumeric strings
                            pin_id_match = re.search(
                                r'/([a-zA-Z0-9_-]{10,})\.(?:jpg|jpeg|png|webp)', img_url
                            )
                        pin_id = pin_id_match.group(1) if pin_id_match else None

                        # If we can't extract a valid pin ID from URL, skip this image
                        # (we need a valid pin ID to create a proper pin link)
                        if not pin_id or not _is_valid_pin_id(pin_id):
                            continue

                        items.append(
                            {
                                'id': pin_id,
                                'image_url': img_url,
                                'description': '',
                                'link': f'https://www.pinterest.com/pin/{pin_id}/',
                                'author': {
                                    'username': 'unknown',
                                    'name': 'unknown',
                                },
                                'board': {
                                    'name': '',
                                },
                            }
                        )
                if items:
                    logger.info(
                        f'HTML extraction: Found {len(items)} pins using pattern 4.5 (background-image)'
                    )

        # Pattern 5: Last resort - look for any Pinterest image URLs in the HTML
        if not items:
            # Look for Pinterest CDN image URLs (pinimg.com)
            pinterest_img_pattern = (
                r'https?://[^"\'<>]*pinimg\.com[^"\'<>]+\.(?:jpg|jpeg|png|webp)'
            )
            all_matches = list(re.finditer(pinterest_img_pattern, html, re.IGNORECASE))
            logger.info(
                f'HTML extraction: Pattern 5 (CDN URLs) found {len(all_matches)} total Pinterest image URLs'
            )

            seen_urls = set()
            valid_url_count = 0
            for match in all_matches:
                img_url = match.group(0)
                # Filter out logo/placeholder images
                if not _is_valid_pin_image_url(img_url):
                    continue

                if img_url not in seen_urls and len(items) < limit:
                    seen_urls.add(img_url)
                    valid_url_count += 1
                    # Try to extract pin ID from URL
                    pin_id_match = re.search(r'/pin/([^/]+)/', img_url)
                    if not pin_id_match:
                        # Try to extract from pinimg URL structure
                        pin_id_match = re.search(
                            r'/([a-zA-Z0-9_-]{10,})\.(?:jpg|jpeg|png|webp)', img_url
                        )
                    pin_id = (
                        pin_id_match.group(1) if pin_id_match else f'pin_{len(items)}'
                    )

                    items.append(
                        {
                            'id': pin_id,
                            'image_url': img_url,
                            'description': '',
                            'link': f'https://www.pinterest.com/pin/{pin_id}/',
                            'author': {
                                'username': 'unknown',
                                'name': 'unknown',
                            },
                            'board': {
                                'name': '',
                            },
                        }
                    )
            logger.info(
                f'HTML extraction: Pattern 5 (CDN URLs) found {valid_url_count} valid pin images (filtered from {len(all_matches)} total), extracted {len(items)} unique pins'
            )

        logger.warning(f'HTML extraction: Total items extracted: {len(items)}')

        # Deduplicate by image URL to prevent same image appearing multiple times
        seen_urls = {}
        deduplicated_items = []
        for item in items:
            img_url = item.get('image_url', '')
            if img_url and img_url not in seen_urls:
                seen_urls[img_url] = True
                deduplicated_items.append(item)

        if len(deduplicated_items) < len(items):
            logger.info(
                f'HTML extraction: Deduplicated {len(items)} items to {len(deduplicated_items)} unique items'
            )

        items = deduplicated_items
        # Rank by inferred visual quality (larger, reasonable aspect ratio first)
        try:
            items.sort(key=_image_quality_score, reverse=True)
            logger.info(
                'HTML extraction: Sorted items by inferred image quality (size and aspect ratio)'
            )
        except Exception as sort_err:
            logger.warning(
                f'HTML extraction: Failed to sort by quality score: {sort_err}'
            )

    except Exception as e:
        logger.error(f'Error extracting pins from HTML: {e}', exc_info=True)

    return items[:limit]
