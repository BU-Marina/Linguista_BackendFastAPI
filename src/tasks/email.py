"""..."""

import asyncio
from typing import Optional

from core.celery.app import celery_app as app
from auth.email import (
    send_verification_email_async,
    send_reset_password_email_async,
)

from .constants import (
    EMAIL_VERIFY,
    EMAIL_RESET_PASSWORD,
)


@app.task(bind=True, max_retries=3, default_retry_delay=60, name=EMAIL_VERIFY)
def send_verification_email_task(
    self,
    user_username: str,
    user_mail: str,
    token: Optional[str],
):
    """
    Celery task wrapper - runs the async send inside the worker process.
    """

    try:
        asyncio.run(send_verification_email_async(user_username, user_mail, token))
    except Exception as exc:
        # retry in case of transient errors
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=60, name=EMAIL_RESET_PASSWORD)
def send_reset_password_email_task(
    self,
    user_username: str,
    user_mail: str,
    token: str,
):
    """
    Celery task wrapper - runs the async send inside the worker process.
    """

    try:
        asyncio.run(send_reset_password_email_async(user_username, user_mail, token))
    except Exception as exc:
        # retry in case of transient errors
        raise self.retry(exc=exc)
