"""Centralized configuration for Telegram Query.

All settings come from environment variables; a ``.env`` file next to the
application root is loaded automatically (see ``.env.example`` for the full
reference).

Path resolution order (keeps existing installations working untouched):
  1. explicit environment variable (``TG_SESSION_PATH`` / ``TG_DB_PATH``)
  2. legacy files next to the application root (``tg_session.session`` /
     ``messages.db``)
  3. new default under the data dir (``TG_DATA_DIR``, default ``<app>/data``)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent

load_dotenv(APP_ROOT / ".env")

ENV_FILE = APP_ROOT / ".env"   # written by the setup wizard; tests redirect this

__version__ = "0.4.0"


def _env(*names: str, default: str = "") -> str:
    """First non-empty environment variable among *names*."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def session_file(session_path: Path) -> Path:
    """The actual SQLite session file Telethon will use for this path."""
    return session_path if session_path.suffix == ".session" \
        else session_path.with_suffix(".session")


def ensure_parent(path: Path) -> Path:
    """Make sure the parent directory of *path* exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_path(env_names: tuple[str, ...], legacy: tuple[Path, ...],
                  default: Path) -> Path:
    for n in env_names:
        v = os.environ.get(n)
        if v:
            return Path(v).expanduser()
    for c in legacy:
        if c.exists():
            return c
    return default


@dataclass
class Settings:
    # server
    host: str
    port: int
    log_level: str

    # telegram
    tg_api_id: str
    tg_api_hash: str
    session_path: Path
    sync_days: int

    # storage
    data_dir: Path
    db_path: Path

    # ai provider (any OpenAI-compatible endpoint)
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_temperature: float
    ai_max_sources: int
    groups_hint: str

    # search normalization: "standard" (v0.3 rules) or "extended"
    # (Arabic-Indic digits, elongation collapse, Arabizi folding, Gulf
    # dialect word map). Changing the level requires a one-time reindex of
    # existing archives - the app schedules that automatically.
    normalization_level: str

    @property
    def telegram_configured(self) -> bool:
        return bool(self.tg_api_id and self.tg_api_hash)

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_api_key)

    @property
    def ai_provider_host(self) -> str:
        """Host of the AI endpoint (for display only - never the key)."""
        if not self.ai_base_url:
            return "api.openai.com"
        try:
            from urllib.parse import urlparse
            return urlparse(self.ai_base_url).netloc or self.ai_base_url
        except Exception:
            return self.ai_base_url


def load_settings() -> Settings:
    raw_data_dir = _env("TG_DATA_DIR")
    data_dir = (Path(raw_data_dir).expanduser().resolve()
                if raw_data_dir else APP_ROOT / "data")
    return Settings(
        host=_env("HOST", default="127.0.0.1"),
        port=int(_env("PORT", default="8000")),
        log_level=_env("LOG_LEVEL", default="INFO").upper(),

        tg_api_id=_env("TG_API_ID", "TELEGRAM_API_ID"),
        tg_api_hash=_env("TG_API_HASH", "TELEGRAM_API_HASH"),
        session_path=_resolve_path(
            ("TG_SESSION_PATH", "TG_SESSION"),
            (session_file(APP_ROOT / "tg_session"),),
            session_file(data_dir / "tg_session")),
        sync_days=int(_env("SYNC_DAYS", default="3")),

        data_dir=data_dir,
        db_path=_resolve_path(
            ("TG_DB_PATH",),
            (APP_ROOT / "messages.db",),
            data_dir / "messages.db"),

        ai_base_url=_env("AI_BASE_URL"),
        ai_api_key=_env("AI_API_KEY"),
        ai_model=_env("AI_MODEL", default="gpt-4o-mini"),
        ai_temperature=float(_env("AI_TEMPERATURE", default="0.2")),
        ai_max_sources=int(_env("AI_MAX_SOURCES", default="80")),
        groups_hint=_env("TGQ_GROUPS_HINT"),
        normalization_level=_env("NORMALIZATION", default="extended").strip().lower(),
    )


settings = load_settings()


def _format_env_value(value: str) -> str:
    """Quote .env values that would otherwise be mis-parsed."""
    if any(c in value for c in ' \t#"\''):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def update_env(mapping: dict[str, str], path: Path | None = None) -> None:
    """Persist key=value pairs to the .env file and hot-reload settings.

    Lines for existing keys are replaced in place; comments and unrelated
    lines are preserved. The file is created with a header if missing.
    Secret values are never logged. Values containing newlines are rejected
    (they could inject arbitrary configuration lines).
    """
    for k, v in mapping.items():
        if "\n" in v or "\r" in v:
            raise ValueError(f"{k} must not contain line breaks")
    target = Path(path) if path else ENV_FILE
    lines = target.read_text(encoding="utf-8").splitlines() \
        if target.exists() else []
    remaining = dict(mapping)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else None
        if key in remaining:
            out.append(f"{key}={_format_env_value(remaining.pop(key))}")
        else:
            out.append(line)
    if remaining:
        if out and out[-1].strip():
            out.append("")
        elif not out:
            out.append("# Written by the Telegram Query setup wizard")
        for k, v in remaining.items():
            out.append(f"{k}={_format_env_value(v)}")
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    for k, v in mapping.items():
        os.environ[k] = v
    globals()["settings"] = load_settings()
