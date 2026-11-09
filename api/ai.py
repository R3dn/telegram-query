"""Ask-AI endpoint.

Grounded question answering over the local archive. Retrieved message
excerpts are sent to the configured AI provider - the UI discloses this.
Provider failures surface as readable errors, never raw 500s.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import ai
import config

from . import open_db

router = APIRouter()


log = logging.getLogger("tgq")

MAX_QUESTION_CHARS = 2000


@router.get("/api/ai/usage")
def ai_usage():
    """Local usage statistics per AI task (requests + tokens)."""
    import ai_tasks
    with open_db() as conn:
        return ai_tasks.usage_stats(conn)


class AskScope(BaseModel):
    """Explicit retrieval scope (AI scope chips, v0.4)."""
    chat_ids: list[int] = Field(default_factory=list)
    date_from: str | None = Field(default=None, max_length=10)
    date_to: str | None = Field(default=None, max_length=10)


class AskRequest(BaseModel):
    question: str = Field(max_length=MAX_QUESTION_CHARS)
    scope: AskScope | None = None


def _provider_error(exc: Exception):
    """Map provider/SDK exceptions to friendly, actionable errors."""
    import openai

    import ai as ai_module
    if isinstance(exc, ai_module.AIBusyError):
        return JSONResponse({"error": str(exc)}, status_code=503)
    if isinstance(exc, openai.APITimeoutError):
        return JSONResponse(
            {"error": "The AI provider timed out. Try again, or use a "
                      "faster model / closer endpoint."},
            status_code=502)
    if isinstance(exc, openai.APIConnectionError):
        return JSONResponse(
            {"error": "Could not reach the AI provider - check AI_BASE_URL "
                      "and that the endpoint is running."},
            status_code=502)
    if isinstance(exc, openai.AuthenticationError):
        return JSONResponse(
            {"error": "The AI provider rejected the API key - check "
                      "AI_API_KEY in Settings."},
            status_code=400)
    if isinstance(exc, openai.NotFoundError):
        return JSONResponse(
            {"error": "The AI provider does not recognize this model name - "
                      "check AI_MODEL in Settings."},
            status_code=400)
    if isinstance(exc, openai.RateLimitError):
        return JSONResponse(
            {"error": "The AI provider rate-limited this request - wait a "
                      "moment and try again."},
            status_code=429)
    if isinstance(exc, openai.BadRequestError):
        return JSONResponse(
            {"error": f"The AI provider rejected the request: {exc}"[:300]},
            status_code=400)
    return None


@router.post("/api/ask")
def ask(req: AskRequest):
    question = req.question.strip()
    if not question:
        return JSONResponse({"error": "Enter a question"}, status_code=400)
    if not config.settings.ai_configured:
        return JSONResponse(
            {"error": "AI is not configured - set AI_API_KEY in your .env file "
                      "(any OpenAI-compatible endpoint works)."},
            status_code=400)
    try:
        result = ai.ask_db(question, scope=req.scope.model_dump()
                           if req.scope else None)
    except Exception as exc:  # noqa: BLE001 - mapped to readable errors below
        mapped = _provider_error(exc)
        if mapped is not None:
            return mapped
        log.exception("ask failed")
        return JSONResponse(
            {"error": "The AI request failed - see the app logs for details."},
            status_code=500)
    sources = result.pop("sources", [])
    # only fields safe for the client; msg ids let the UI jump to originals
    result["sources"] = [
        {k: m[k] for k in ("chat_id", "msg_id", "chat_title", "date",
                           "sender_name", "text", "has_media")}
        for m in sources
    ]
    result["provider_host"] = config.settings.ai_provider_host
    result["provider_model"] = config.settings.ai_model
    return result
