"""Setup endpoints: configure Telegram and AI credentials from the wizard.

Keys are write-only: responses confirm configuration state and never echo
secret values back to the browser or into logs.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config

router = APIRouter()


class TelegramCreds(BaseModel):
    # strict patterns also prevent .env line injection via newlines/equals
    api_id: str = Field(min_length=1, max_length=32, pattern=r"^\s*[0-9]+\s*$")
    api_hash: str = Field(min_length=8, max_length=256,
                          pattern=r"^\s*[A-Za-z0-9_]+\s*$")


class AiProvider(BaseModel):
    base_url: str = Field(default="", max_length=512,
                          pattern=r"^[\x20-\x7e]*$")  # printable-ASCII URL
    api_key: str = Field(default="", max_length=512,
                         pattern=r"^[A-Za-z0-9_\-\.=]+$")
    model: str = Field(default="", max_length=128,
                       pattern=r"^[A-Za-z0-9_\-\.:/\[\]]*$")


def _err(message: str):
    return JSONResponse({"error": message}, status_code=400)


@router.post("/api/setup/telegram")
def setup_telegram(req: TelegramCreds):
    api_id = req.api_id.strip()
    api_hash = req.api_hash.strip()
    if not api_id.lstrip("-").isdigit():
        return _err("API ID must be a number - copy the numeric api_id "
                    "from my.telegram.org.")
    config.update_env({"TG_API_ID": api_id, "TG_API_HASH": api_hash})
    return {"telegram_configured": True}


@router.post("/api/setup/ai")
def setup_ai(req: AiProvider):
    api_key = req.api_key.strip()
    if not api_key:
        return _err("Enter your API key.")
    mapping = {"AI_API_KEY": api_key}
    if req.base_url.strip():
        mapping["AI_BASE_URL"] = req.base_url.strip()
    if req.model.strip():
        mapping["AI_MODEL"] = req.model.strip()
    config.update_env(mapping)
    return {"ai_configured": True}


def _make_client(api_key: str, base_url: str | None):
    """Provider client factory - monkeypatched in tests."""
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url, timeout=30)


@router.post("/api/setup/ai/test")
def setup_ai_test(req: AiProvider):
    """Try a tiny request against the provider WITHOUT saving anything,
    so users can verify their key/model before they commit to them."""
    api_key = req.api_key.strip()
    if not api_key:
        return _err("Enter your API key first.")
    base_url = req.base_url.strip() or None
    model = req.model.strip() or "gpt-4o-mini"
    try:
        client = _make_client(api_key, base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        text = (resp.choices[0].message.content or "").strip()
        return {"ok": True, "model": model, "reply": text[:20]}
    except Exception as e:  # noqa: BLE001 - surfaced to the wizard as text
        return {"ok": False, "error": _friendly_error(e)}


def _friendly_error(e: Exception) -> str:
    msg = str(e)
    low = msg.lower()
    if "401" in msg or "unauthorized" in low or "invalid api key" in low:
        return "The provider rejected this API key (unauthorized)."
    if "404" in msg or "not found" in low:
        return "The provider does not recognize this model name."
    if "connection" in low or "timed out" in low or "timeout" in low:
        return "Could not reach the endpoint - check the base URL."
    return f"Provider error: {msg[:160]}"
