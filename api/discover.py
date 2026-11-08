"""Discovery API (v0.7): trending topics, cross-group stories, group
activity, the unanswered-questions radar, entities, conversation
reconstruction, and the (optional) AI topic timeline.

Everything here is deterministic and provider-free except the topic
timeline, which fails with honest errors when no provider is configured.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import ai_tasks
import config
import discover
import entities

from . import open_db, parse_groups

router = APIRouter()


def _clamp(v: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(v), hi))
    except (TypeError, ValueError):
        return lo


# ---------------------------------------------------------------------------
# Trending / stories / activity
# ---------------------------------------------------------------------------

@router.get("/api/discover/trending")
def trending(days: int = 7, groups: str = "", limit: int = 20,
             sort: str = "burst", min_volume: int = 3):
    with open_db() as conn:
        return discover.trending(
            conn, days=_clamp(days, 1, 90),
            chat_ids=parse_groups(groups) or None,
            limit=_clamp(limit, 1, 100),
            sort=sort if sort in ("burst", "volume") else "burst",
            min_volume=_clamp(min_volume, 1, 50))


@router.get("/api/discover/stories")
def stories(days: int = 7, groups: str = "", limit: int = 15):
    with open_db() as conn:
        return discover.stories(
            conn, days=_clamp(days, 1, 90),
            chat_ids=parse_groups(groups) or None,
            limit=_clamp(limit, 1, 50))


@router.get("/api/discover/activity")
def activity(days: int = 30, groups: str = ""):
    with open_db() as conn:
        return discover.activity(conn, days=_clamp(days, 1, 365),
                                 chat_ids=parse_groups(groups) or None)


@router.post("/api/discover/rebuild")
def rebuild():
    """One-time/full discovery rebuild as a visible job (queued
    automatically after the v0.7 upgrade for existing archives)."""
    import jobs
    started = jobs.JOBS.start("discover", jobs.run_discover_job)
    return {"started": started}


# ---------------------------------------------------------------------------
# Unanswered questions
# ---------------------------------------------------------------------------

@router.get("/api/discover/questions")
def questions(status: str = "open", groups: str = "", limit: int = 50):
    if status not in ("open", "answered", "ignored"):
        return JSONResponse({"error": "status must be open|answered|ignored"},
                            status_code=400)
    with open_db() as conn:
        return discover.question_list(
            conn, status=status, chat_ids=parse_groups(groups) or None,
            limit=limit)


class QuestionStatus(BaseModel):
    status: str = Field(pattern="^(open|answered|ignored)$")
    answered_by: int | None = None


@router.post("/api/discover/questions/{chat_id}/{msg_id}")
def set_question(chat_id: int, msg_id: int, req: QuestionStatus):
    with open_db() as conn:
        try:
            changed = discover.set_question_status(
                conn, chat_id, msg_id, req.status, req.answered_by)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if not changed:
            return JSONResponse({"error": "question not found"},
                                status_code=404)
        return {"ok": True, "status": req.status}


class QuestionScan(BaseModel):
    days: int = Field(default=30, ge=1, le=90)


@router.post("/api/discover/questions/scan")
def scan_questions(req: QuestionScan = None):
    """Bounded re-scan of recent messages for unanswered questions
    (deterministic; existing human statuses are never overwritten)."""
    with open_db() as conn:
        stats = discover.scan_questions(conn, days=(req.days if req else 30))
        open_count = conn.execute(
            "SELECT COUNT(*) c FROM open_questions WHERE status='open'"
        ).fetchone()["c"]
    return {"ok": True, **stats, "open": open_count}


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

@router.get("/api/discover/entities/settings")
def entities_settings():
    with open_db() as conn:
        return {"auto": entities.auto_enabled(conn),
                "ai_configured": config.settings.ai_configured}


@router.post("/api/discover/entities/auto")
def entities_auto(req: dict):
    enabled = bool(req.get("enabled"))
    with open_db() as conn:
        entities.set_auto(conn, enabled)
        return {"auto": entities.auto_enabled(conn)}


@router.get("/api/discover/entities")
def list_entities(q: str = "", limit: int = 50, sort: str = "recent",
                  groups: str = ""):
    with open_db() as conn:
        return entities.list_entities(
            conn, q=q, limit=limit,
            sort=sort if sort in ("recent", "mentions") else "recent",
            chat_ids=parse_groups(groups) or None)


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "other"
    aliases: list[str] = Field(default_factory=list, max_length=30)


@router.post("/api/discover/entities")
def create_entity(req: EntityCreate):
    with open_db() as conn:
        try:
            return entities.add_entity(conn, req.name, kind=req.kind,
                                       aliases=req.aliases, source="manual")
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/discover/entities/{entity_id}")
def get_entity(entity_id: int, mentions_limit: int = 30,
               mentions_offset: int = 0):
    with open_db() as conn:
        e = entities.entity_detail(
            conn, entity_id, mentions_limit=_clamp(mentions_limit, 1, 100),
            mentions_offset=max(0, mentions_offset))
        if not e:
            return JSONResponse({"error": "entity not found"},
                                status_code=404)
        return e


class EntityPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = None
    aliases: list[str] | None = Field(default=None, max_length=30)
    ignored: bool | None = None


@router.patch("/api/discover/entities/{entity_id}")
def patch_entity(entity_id: int, req: EntityPatch):
    with open_db() as conn:
        try:
            updated = entities.update_entity(
                conn, entity_id, name=req.name, kind=req.kind,
                aliases=req.aliases,
                ignored=None if req.ignored is None else req.ignored)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if not updated:
            return JSONResponse({"error": "entity not found"},
                                status_code=404)
        return updated


class EntityMerge(BaseModel):
    source_id: int
    target_id: int


@router.post("/api/discover/entities/merge")
def merge_entity(req: EntityMerge):
    with open_db() as conn:
        try:
            merged = entities.merge_entities(conn, req.source_id, req.target_id)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if not merged:
            return JSONResponse({"error": "entity not found"},
                                status_code=404)
        return merged


@router.delete("/api/discover/entities/{entity_id}")
def delete_entity(entity_id: int):
    with open_db() as conn:
        if not entities.delete_entity(conn, entity_id):
            return JSONResponse({"error": "entity not found"},
                                status_code=404)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Topic timeline (the only AI surface in discovery)
# ---------------------------------------------------------------------------

class TimelineRequest(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    chat_ids: list[int] = Field(default_factory=list)
    days: int = Field(default=30, ge=1, le=365)


@router.post("/api/discover/topic-timeline")
def topic_timeline(req: TimelineRequest):
    with open_db() as conn:
        try:
            return discover.topic_timeline(
                conn, req.term,
                chat_ids=[c for c in req.chat_ids if isinstance(c, int)] or None,
                days=req.days)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except ai_tasks.TaskError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
