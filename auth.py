"""Telegram account login from the web UI.

Each login step is a short synchronous request against the shared Telegram
session; the API layer refuses to run a step while a background job is
using the session. Between steps, pending login state (phone + code hash)
is held in memory only and never written to disk.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberUnoccupiedError,
    SessionPasswordNeededError,
)

import config

log = logging.getLogger("tgq.auth")

# {"authenticated": True|False|None(unknown), "user": str|None}
AUTH_STATE = {"authenticated": None, "user": None}

# pending login between steps - memory only
_PENDING = {"phone": None, "code_hash": None}


class AuthError(Exception):
    """User-facing login error with a friendly message."""


def _client() -> TelegramClient:
    if not config.settings.telegram_configured:
        raise AuthError("Telegram API credentials are not configured. "
                        "Set TG_API_ID and TG_API_HASH in your .env file.")
    return TelegramClient(str(config.settings.session_path),
                          int(config.settings.tg_api_id),
                          config.settings.tg_api_hash)


def _user_label(me) -> str:
    name = " ".join(filter(None, [me.first_name, me.last_name])).strip()
    return f"@{me.username} ({name})" if me.username else (name or str(me.id))


async def _set_state_from_client(client: TelegramClient) -> bool:
    ok = await client.is_user_authorized()
    if ok:
        me = await client.get_me()
        AUTH_STATE["authenticated"] = True
        AUTH_STATE["user"] = _user_label(me)
    else:
        AUTH_STATE["authenticated"] = False
        AUTH_STATE["user"] = None
    return ok


async def refresh_auth_state() -> dict:
    """Check the stored session against Telegram (cheap when logged out)."""
    if not config.settings.telegram_configured:
        AUTH_STATE.update(authenticated=False, user=None)
        return dict(AUTH_STATE)
    if not config.session_file(config.settings.session_path).exists():
        AUTH_STATE.update(authenticated=False, user=None)
        return dict(AUTH_STATE)
    client = _client()
    try:
        await client.connect()
        await _set_state_from_client(client)
    except Exception as e:  # network down etc. - keep "unknown"
        log.warning("auth state check failed: %s", e)
    finally:
        await client.disconnect()
    return dict(AUTH_STATE)


async def login_start(phone: str) -> dict:
    """Send the login code to *phone*. Returns next-step info."""
    phone = phone.strip()
    if not phone:
        raise AuthError("Enter your phone number in international format, "
                        "e.g. +966501234567")
    client = _client()
    try:
        await client.connect()
        if await client.is_user_authorized():
            await _set_state_from_client(client)
            return {"stage": "done", **dict(AUTH_STATE)}
        try:
            sent = await client.send_code_request(phone)
        except FloodWaitError as e:
            raise AuthError(f"Telegram says: too many attempts. Wait "
                            f"{e.seconds}s and try again.") from e
        except ApiIdInvalidError as e:
            raise AuthError("Telegram rejected TG_API_ID / TG_API_HASH. "
                            "Double-check them in .env.") from e
        _PENDING["phone"] = phone
        _PENDING["code_hash"] = sent.phone_code_hash
        return {"stage": "code"}
    finally:
        await client.disconnect()


async def login_code(code: str) -> dict:
    """Submit the code Telegram sent. May move on to the 2FA step."""
    code = (code or "").strip().replace(" ", "")
    if not _PENDING["phone"] or not _PENDING["code_hash"]:
        raise AuthError("No pending login - start again with your phone number.")
    if not code:
        raise AuthError("Enter the code Telegram sent you.")
    client = _client()
    try:
        await client.connect()
        try:
            await client.sign_in(phone=_PENDING["phone"], code=code,
                                 phone_code_hash=_PENDING["code_hash"])
        except SessionPasswordNeededError:
            return {"stage": "password"}
        except PhoneCodeInvalidError as e:
            raise AuthError("That code is not valid - check Telegram's message "
                            "and try again.") from e
        except PhoneCodeExpiredError as e:
            raise AuthError("The code expired - request a new one.") from e
        except PhoneNumberUnoccupiedError as e:
            raise AuthError("This phone number has no Telegram account.") from e
        await _set_state_from_client(client)
        _PENDING.clear()
        return {"stage": "done", **dict(AUTH_STATE)}
    finally:
        await client.disconnect()


async def login_password(password: str) -> dict:
    """Submit the two-step-verification password."""
    if not password:
        raise AuthError("Enter your two-step verification password.")
    client = _client()
    try:
        await client.connect()
        try:
            await client.sign_in(password=password)
        except PasswordHashInvalidError as e:
            raise AuthError("Wrong password - try again.") from e
        except SessionPasswordNeededError as e:
            raise AuthError("A password is required - enter it above.") from e
        await _set_state_from_client(client)
        _PENDING.clear()
        return {"stage": "done", **dict(AUTH_STATE)}
    finally:
        await client.disconnect()


async def logout() -> dict:
    """Log out and delete the local session file."""
    if not config.session_file(config.settings.session_path).exists():
        AUTH_STATE.update(authenticated=False, user=None)
        return {"logged_out": True, **dict(AUTH_STATE)}
    client = _client()
    try:
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()   # deletes the session file
        else:
            await client.disconnect()
            Path(config.session_file(config.settings.session_path)) \
                .unlink(missing_ok=True)
    except Exception as e:
        log.warning("logout failed: %s", e)
        raise AuthError("Could not log out - is Telegram reachable?") from e
    AUTH_STATE.update(authenticated=False, user=None)
    return {"logged_out": True, **dict(AUTH_STATE)}


def run(coro):
    """Run one auth coroutine synchronously (called from API handlers)."""
    return asyncio.run(coro)
