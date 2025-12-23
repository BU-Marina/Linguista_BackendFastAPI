"""Email logic."""

import asyncio

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

from config.settings import settings

# settings = Settings()


def make_mail_conf() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=getattr(settings, "SMTP_STARTTLS", True),
        MAIL_SSL_TLS=getattr(settings, "SMTP_SSL_TLS", False),
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
        MAIL_FROM_NAME=getattr(settings, "SMTP_FROM_NAME", None),
        # template_folder="templates/email"
    )


async def send_email_async(subject: str, recipients: list[str], body: str):
    conf = make_mail_conf()
    fm = FastMail(conf)
    print('!!send email', recipients, body)
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html"
    )
    try:
        await asyncio.wait_for(fm.send_message(message), timeout=30)
        print('.done')
    except Exception as e:
        import logging
        logging.exception(f"Failed to send verification email: {e}")
        raise


async def send_verification_email_async(
    user_username,
    user_mail,
    token,
    request=None,
):
    verify_url = f"{settings.FRONTEND_VERIFY_URL}?token={token}"
    subject = "Confirm your email"
    body = f"Hi {user_username or ''}, click to verify: {verify_url}"

    print('??continue to send...')

    # отправка в фоне / асинхронно
    await send_email_async(subject, [user_mail], body)


async def send_reset_password_email_async(
        user_username,
        user_mail,
        token,
        request=None,
    ):
    reset_url = f"{settings.FRONTEND_RESET_URL}?token={token}"
    subject = "Reset account password"
    body = f"Hi {user_username or ''}, click to reset your password: {reset_url}"

    print('??continue to send...')

    # отправка в фоне / асинхронно
    await send_email_async(subject, [user_mail], body)
