"""AI task infrastructure tests: parsing, repair, caching, usage."""
import pytest

import ai_tasks
import config
import db


class FakeClient:
    calls = []

    def __init__(self, responses):
        self.responses = list(responses)
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, model=None, messages=None, temperature=None):
        FakeClient.calls.append(messages)
        text = self.responses.pop(0)

        class Resp:
            class _Msg:
                class _M:
                    content = None
                message = _M()
            class _U:
                prompt_tokens = 7
                completion_tokens = 3
            choices = [_Msg()]
            usage = _U()
        Resp.choices[0].message.content = text
        return Resp


@pytest.fixture(autouse=True)
def _reset():
    FakeClient.calls = []
    yield


def _always_ok(payload):
    return True, None


def _never_ok(payload):
    return False, "schema says no"


def test_run_json_task_happy_path(conn, monkeypatch):
    fake = FakeClient(['{"x": 1}'])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    result, from_cache = ai_tasks.run_json_task(
        "sys", "user", task="t", validate=_always_ok)
    assert result == {"x": 1} and from_cache is False


def test_run_json_task_repair_then_fail(conn, monkeypatch):
    """One repair attempt, then an honest error - never fabricate."""
    fake = FakeClient(["garbage", "still garbage"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    with pytest.raises(ai_tasks.TaskError):
        ai_tasks.run_json_task("sys", "user", task="t", validate=_always_ok)
    assert len(FakeClient.calls) == 2


def test_run_json_task_schema_repair(conn, monkeypatch):
    fake = FakeClient(['{"x": 1}', '{"x": 2}'])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    # first response fails schema, repair passes
    seen = []
    def validate(p):
        seen.append(p)
        return (p.get("x") == 2, None) if seen else (False, "x must be 2")
    result, _ = ai_tasks.run_json_task("sys", "user", task="t", validate=validate)
    assert result == {"x": 2} and len(FakeClient.calls) == 2


def test_cache_hit_skips_provider(conn, monkeypatch):
    fake = FakeClient(['{"x": 1}', '{"x": 3}', '{"x": 4}'])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    cache = (conn, "t", "scope1", "v1", "fp1")
    r1, c1 = ai_tasks.run_json_task("sys", "u", task="t",
                                    validate=_always_ok, cache=cache)
    r2, c2 = ai_tasks.run_json_task("sys", "u", task="t",
                                    validate=_always_ok, cache=cache)
    assert c1 is False and c2 is True
    assert len(FakeClient.calls) == 1, "identical sources must not re-call"
    assert r1 == r2
    # a different fingerprint is a different cache entry
    r3, c3 = ai_tasks.run_json_task("sys", "u", task="t", validate=_always_ok,
                                    cache=(conn, "t", "scope1", "v1", "fp2"))
    assert c3 is False and r3 == {"x": 3}
    # prompt version change invalidates
    r4, c4 = ai_tasks.run_json_task("sys", "u", task="t", validate=_always_ok,
                                    cache=(conn, "t", "scope1", "v2", "fp1"))
    assert c4 is False and r4 == {"x": 4}


def test_usage_recorded(conn, monkeypatch):
    fake = FakeClient(['{"x": 1}'])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    ai_tasks.run_json_task("sys", "user", task="deals",
                           validate=_always_ok)
    stats = ai_tasks.usage_stats(db.get_db())
    assert stats["total"]["requests"] >= 1
    assert stats["by_task"]["deals"]["tokens_in"] >= 1


def test_no_provider_configured(monkeypatch, conn):
    monkeypatch.setattr(config.settings, "ai_api_key", "")
    with pytest.raises(ai_tasks.TaskError):
        ai_tasks.run_json_task("s", "u", task="t", validate=_always_ok)


def test_fingerprint_stable_and_sensitive(conn):
    rows = [{"chat_id": -1, "msg_id": 1, "text": "abc"},
            {"chat_id": -2, "msg_id": 2, "text": "def"}]
    assert ai_tasks.fingerprint_rows(rows) == ai_tasks.fingerprint_rows(rows)
    changed = [dict(rows[0], text="edited"), rows[1]]
    assert ai_tasks.fingerprint_rows(changed) != ai_tasks.fingerprint_rows(rows)
    assert ai_tasks.scope_hash("a", {"x": 1}) == ai_tasks.scope_hash("a", {"x": 1})
    assert ai_tasks.scope_hash("a", {"x": 1}) != ai_tasks.scope_hash("a", {"x": 2})
