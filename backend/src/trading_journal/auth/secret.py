"""Persisted cookie-signing secret.

The secret lives in the ``app_config`` table under key ``cookie_secret``. It is
generated once on first startup and reused on every boot, so operators never
supply it via env. It only signs the (currently unmounted) password-reset /
email-verify tokens — sessions are opaque DB tokens (``DatabaseStrategy``), so
rotating or losing this secret never logs anyone out.
"""

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from trading_journal.models.app_config import AppConfig

COOKIE_SECRET_KEY = "cookie_secret"

# Loaded from the DB by ``ensure_cookie_secret`` at startup; ``None`` until then.
_cookie_secret: str | None = None
# Used only when startup hasn't run (e.g. tests, which don't run the lifespan).
_ephemeral_fallback: str | None = None


async def ensure_cookie_secret(session: AsyncSession) -> str:
    """Get-or-create the persisted cookie secret, caching it in-process.

    Idempotent: safe to call on every boot. The app's lifespan calls this once
    before serving traffic, so the first-insert path never races. Requires the
    ``app_config`` table to exist — guaranteed because migrations run (and must
    succeed) before the app starts.
    """
    global _cookie_secret
    if _cookie_secret is not None:
        return _cookie_secret
    row = await session.get(AppConfig, COOKIE_SECRET_KEY)
    if row is None:
        value = secrets.token_urlsafe(48)
        session.add(AppConfig(key=COOKIE_SECRET_KEY, value=value))
        await session.commit()
    else:
        value = row.value
    _cookie_secret = value
    return value


def get_cookie_secret() -> str:
    """Return the loaded secret for token signing.

    Falls back to a process-ephemeral random value if startup hasn't populated it
    (tests construct the app without running its lifespan). Safe because the
    secret only signs reset/verify tokens, which those code paths don't exercise.
    """
    global _ephemeral_fallback
    if _cookie_secret is not None:
        return _cookie_secret
    if _ephemeral_fallback is None:
        _ephemeral_fallback = secrets.token_urlsafe(48)
    return _ephemeral_fallback
