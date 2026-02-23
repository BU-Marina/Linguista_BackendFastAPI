"""Pinterest endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, HTTPException

from library.pinterest import (
    fetch_images,
    fetch_images_from_public_search,
    get_authorization_url,
    exchange_code_for_token,
    compute_dominant_color_from_url,
)
from auth.setup import optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/pinterest', tags=['pinterest'])


@router.get('/authorize')
async def pinterest_authorize(
    state: str | None = Query(None),
    user=Depends(optional_current_user),
):
    """
    Initiate Pinterest OAuth flow.
    Returns the authorization URL for the frontend to redirect to.

    Args:
        state: Optional state parameter for CSRF protection
        user: Optional authenticated user

    Returns:
        JSON with authorization_url for frontend to redirect
    """
    from fastapi.responses import JSONResponse

    auth_url = get_authorization_url(state=state)
    return JSONResponse(content={'authorization_url': auth_url})


@router.get('/callback')
async def pinterest_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    user=Depends(optional_current_user),
):
    """
    Handle Pinterest OAuth callback.
    Exchanges authorization code for access token.

    Args:
        code: Authorization code from Pinterest
        state: State parameter (for CSRF protection)
        error: Error code if authorization was denied
        user: Optional authenticated user

    Returns:
        Dictionary with access_token and token info
        Note: In production, you should store this token securely (e.g., in database)
    """
    if error:
        raise HTTPException(
            status_code=400, detail=f'Pinterest authorization error: {error}'
        )

    if not code:
        raise HTTPException(status_code=400, detail='Missing authorization code')

    # Use the redirect_uri from settings - must match exactly what's registered in Pinterest
    from config.settings import settings

    token_data = await exchange_code_for_token(
        code, redirect_uri=settings.PINTEREST_REDIRECT_URI
    )

    # Return token data
    # In production, you should:
    # 1. Store the access_token in database associated with the user
    # 2. Store refresh_token if provided
    # 3. Handle token expiration
    return {
        'access_token': token_data.get('access_token'),
        'token_type': token_data.get('token_type', 'bearer'),
        'expires_in': token_data.get('expires_in'),
        'refresh_token': token_data.get('refresh_token'),
        'scope': token_data.get('scope'),
    }


@router.get('/images')
async def pinterest_images(
    access_token: str | None = Query(
        None,
        description='Pinterest access token from OAuth flow (optional if using public search)',
    ),
    search: str | None = Query(None),
    per_page: int = Query(20, ge=1, le=250),
    page: int = Query(1, ge=1),
    bookmark: str | None = Query(None),
    ad_account_id: str | None = Query(
        None,
        description='Optional ad account ID for Business Access to public/protected boards',
    ),
    use_public_search: bool = Query(
        False, description='Use public search parser instead of API'
    ),
    user=Depends(optional_current_user),
):
    """
    Fetch images from Pinterest.

    Can use either:
    1. Pinterest API (requires access_token and OAuth)
    2. Public search parser (scrapes Pinterest's public search pages, no OAuth needed)

    Args:
        access_token: Pinterest access token (required if use_public_search=False)
        search: Search query string (required)
        per_page: Number of results per page (1-250, default 20)
        page: Page number (for compatibility, but Pinterest uses bookmarks)
        bookmark: Pinterest bookmark for pagination (takes precedence over page, API only)
        ad_account_id: Optional ad account ID for Business Access. When specified, uses
                      the owner of that ad_account as the "operation user_account".
                      This changes which account's permissions are used, but does NOT
                      enable global public pin search - it searches within the scope of
                      what that business account can access. Requires token user_account
                      to have Business Access roles (Owner, Admin, Analyst, Campaign Manager).
                      Note: For truly global public pin search, use use_public_search=True.
        use_public_search: If True, use public search parser instead of API
        user: Optional authenticated user

    Returns:
        Pinterest response with pins/images
        Note: Pinterest API uses bookmark-based pagination. Use the 'bookmark' field
        from the response to fetch the next page.
    """
    if use_public_search:
        # Use public search parser (no OAuth required)
        logger.info(
            f'Router: calling fetch_images_from_public_search with search="{search}", per_page={per_page}, page={page}, bookmark={bookmark}'
        )
        result = await fetch_images_from_public_search(
            search=search,
            per_page=per_page,
            page=page,
            bookmark=bookmark,
        )
        logger.info(
            f'Router: fetch_images_from_public_search returned {len(result.get("items", []))} items, bookmark={result.get("bookmark")}'
        )
        return result
    else:
        # Use Pinterest API (requires OAuth token)
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail='access_token is required when use_public_search=False',
            )
        return await fetch_images(
            access_token=access_token,
            search=search,
            per_page=per_page,
            page=page,
            bookmark=bookmark,
            ad_account_id=ad_account_id,
        )


@router.get('/dominant-color')
async def pinterest_dominant_color(
    url: str = Query(..., description='External image URL (http/https)'),
    user=Depends(optional_current_user),
):
    """
    Compute dominant color for an image URL on the backend to avoid browser CORS issues.
    """
    color = await compute_dominant_color_from_url(url=url)
    return {'dominant_color': color}
