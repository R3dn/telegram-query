"""Telegram login endpoints (used by the first-run wizard and settings)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import auth
import jobs

router = APIRouter()


class PhoneRequest(BaseModel):
    phone: str


class CodeRequest(BaseModel):
    code: str


class PasswordRequest(BaseModel):
    password: str


def _busy():
    """Auth steps share the Telegram session with background jobs."""
    return JSONResponse(
        {"error": "A background job is using the Telegram session - "
                  "wait for it to finish first."},
        status_code=409)


@router.get("/api/auth/status")
def auth_status():
    return {"authenticated": auth.AUTH_STATE["authenticated"],
            "user": auth.AUTH_STATE["user"]}


@router.post("/api/auth/start")
def auth_start(req: PhoneRequest):
    if jobs.JOBS.running:
        return _busy()
    try:
        return auth.run(auth.login_start(req.phone))
    except auth.AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/auth/code")
def auth_code(req: CodeRequest):
    if jobs.JOBS.running:
        return _busy()
    try:
        return auth.run(auth.login_code(req.code))
    except auth.AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/auth/password")
def auth_password(req: PasswordRequest):
    if jobs.JOBS.running:
        return _busy()
    try:
        return auth.run(auth.login_password(req.password))
    except auth.AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/auth/logout")
def auth_logout():
    if jobs.JOBS.running:
        return _busy()
    try:
        return auth.run(auth.logout())
    except auth.AuthError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
