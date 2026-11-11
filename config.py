"""Centralized configuration for Telegram Query.

All settings come from environment variables; a ``.env`` file is loaded
automatically (see ``.env.example`` for the full reference).

Path resolution (v1.0 adds packaged desktop runs; source runs unchanged):

Source runs (``python app.py``)
  ``APP_ROOT`` is the repository; ``.env`` sits next to it and mutable
  data defaults to ``<repo>/data`` - identical to every earlier version.

Frozen runs (PyInstaller, ``TelegramQuery.exe``)
  ``APP_ROOT`` is PyInstaller's read-only support directory (holds the
  code and the bundled ``web/dist``). Mutable data moves to
  ``%LOCALAPPDATA%\\TelegramQuery`` (per-user, always writable, never
  inside Program Files). The ``.env`` file lives there as well.

Per-path resolution order:
  1. explicit environment variable (``TG_SESSION_PATH`` / ``TG_DB_PATH`` /
     ``TG_DATA_DIR``)
  2. legacy files next to the application root (source runs only)
  3. default under the data dir
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

IS_FROZEN = bool(getattr(sys, "frozen", False))

# Read-only application code + assets (web/dist). Frozen: _MEIPASS dir.
APP_ROOT = (Path(getattr(sys, "_MEIPASS", "")).resolve() if IS_FROZEN
            else Path(__file__).resolve().parent)
# On-disk installation root (the directory containing TelegramQuery.exe).
INSTALL_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else APP_ROOT
# Built React frontend served by FastAPI.
WEB_DIST = APP_ROOT / "web" / "dist"


def _default_data_dir() -> Path:
    """Where mutable user data lives by default.

    Frozen: ``%LOCALAPPDATA%\\TelegramQuery`` - per-user, always writable,
    survives upgrades and uninstalls, never inside Program Files.
    Source: ``<repo>/data`` (unchanged since v0.3).
    """
    if IS_FROZEN:
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "TelegramQuery"
        return Path.home() / "AppData" / "Local" / "TelegramQuery"
    return APP_ROOT / "data"


def resolve_data_dir() -> Path:
    """Effective data dir: ``TG_DATA_DIR`` override or the platform default."""
    raw = os.environ.get("TG_DATA_DIR", "").strip()
    return Path(raw).expanduser().resolve() if raw else _default_data_dir()


DATA_DIR = resolve_data_dir()


def resolve_env_file() -> Path:
    """Where the writable ``.env`` lives.

    ``TGQ_ENV_FILE`` overrides everything (test harnesses point the app
    at a throwaway file so a run can never read or touch a real
    ``.env``). Frozen builds keep the ``.env`` in the (writable) data
    dir - never inside Program Files; source runs keep it next to the
    code, unchanged since v0.3."""
    override = os.environ.get("TGQ_ENV_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if IS_FROZEN:
        return DATA_DIR / ".env"
    return APP_ROOT / ".env"


# Written by the setup wizard; tests redirect this.
ENV_FILE = resolve_env_file()

load_dotenv(ENV_FILE)

__version__ = "1.0.1"


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

    # ai model routing (v0.7): per-task-type models over the same endpoint.
    # Empty falls back to ai_model - one provider, different price/quality
    # tiers: 'extract' = cheap/fast structured tasks, 'synth' = general
    # reasoning and prose, 'embed' = optional embeddings (v0.8 benchmark).
    ai_model_extract: str
    ai_model_synth: str
    ai_model_embed: str
    # 0 = unlimited; >0 caps total AI requests per UTC day (honest errors
    # when reached - deterministic features are never affected)
    ai_daily_cap: int
    # Max provider requests in flight at once (protects the request
    # threadpool from being fully occupied by long AI calls; queued
    # asks wait, then fail honestly when the timeout elapses)
    ai_max_concurrency: int

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

    def model_for(self, role: str) -> str:
        """Effective model for a task role: 'extract' | 'synth' | 'embed'.
        Unset roles fall back to the general AI_MODEL - routing is always
        optional and never hardcodes a provider or model."""
        if role == "extract" and self.ai_model_extract:
            return self.ai_model_extract
        if role == "synth" and self.ai_model_synth:
            return self.ai_model_synth
        if role == "embed" and self.ai_model_embed:
            return self.ai_model_embed
        return self.ai_model

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
    data_dir = resolve_data_dir()
    # Legacy candidates only apply to source runs. Frozen installs always
    # resolve to the canonical user-data dir; older archives found beside
    # the exe are migrated there first (see migration.py) - a frozen app
    # must never write next to Program Files.
    legacy_session = () if IS_FROZEN else (session_file(APP_ROOT / "tg_session"),)
    legacy_db = () if IS_FROZEN else (APP_ROOT / "messages.db",)
    return Settings(
        host=_env("HOST", default="127.0.0.1"),
        port=int(_env("PORT", default="8000")),
        log_level=_env("LOG_LEVEL", default="INFO").upper(),

        tg_api_id=_env("TG_API_ID", "TELEGRAM_API_ID"),
        tg_api_hash=_env("TG_API_HASH", "TELEGRAM_API_HASH"),
        session_path=_resolve_path(
            ("TG_SESSION_PATH", "TG_SESSION"),
            legacy_session,
            session_file(data_dir / "tg_session")),
        sync_days=int(_env("SYNC_DAYS", default="3")),

        data_dir=data_dir,
        db_path=_resolve_path(
            ("TG_DB_PATH",),
            legacy_db,
            data_dir / "messages.db"),

        ai_base_url=_env("AI_BASE_URL"),
        ai_api_key=_env("AI_API_KEY"),
        ai_model=_env("AI_MODEL", default="gpt-4o-mini"),
        ai_temperature=float(_env("AI_TEMPERATURE", default="0.2")),
        ai_max_sources=int(_env("AI_MAX_SOURCES", default="80")),
        groups_hint=_env("TGQ_GROUPS_HINT"),
        ai_model_extract=_env("AI_MODEL_EXTRACT"),
        ai_model_synth=_env("AI_MODEL_SYNTH"),
        ai_model_embed=_env("AI_MODEL_EMBED"),
        ai_daily_cap=max(0, int(_env("TGQ_AI_DAILY_CAP", default="0"))),
        ai_max_concurrency=max(1, int(_env("TGQ_AI_MAX_CONCURRENCY",
                                           default="4"))),
        normalization_level=_env("NORMALIZATION", default="extended").strip().lower(),
    )


settings = load_settings()


def reload_settings() -> None:
    """Re-read ``.env`` and rebuild :data:`settings`.

    Used by the desktop launcher after an auto-migration may have copied
    a ``.env`` into the data dir (too late for the initial import-time
    load). Existing environment variables always win over the file, so an
    explicit override is never clobbered.
    """
    load_dotenv(ENV_FILE)
    globals()["settings"] = load_settings()


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
