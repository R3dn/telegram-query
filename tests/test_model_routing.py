"""AI model routing tests (v0.7): per-task models with fallback, daily
request cap, and per-model usage recording."""
import json

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
        FakeClient.calls.append({"model": model, "messages": messages})
        text = self.responses.pop(0)

        class Resp:
            class _Msg:
                class _M:
                    content = None
                message = _M()
            class _U:
                prompt_tokens = 10
                completion_tokens = 5
            choices = [_Msg()]
            usage = _U()
        Resp.choices[0].message.content = text
        return Resp


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    FakeClient.calls = []
    # per-test routing + cap, restored after each test
    monkeypatch.setattr(config.settings, "ai_model_extract", "")
    monkeypatch.setattr(config.settings, "ai_model_synth", "")
    monkeypatch.setattr(config.settings, "ai_model_embed", "")
    monkeypatch.setattr(config.settings, "ai_daily_cap", 0)
    yield


def test_model_for_falls_back_to_general_model():
    assert config.settings.model_for("extract") == config.settings.ai_model
    assert config.settings.model_for("synth") == config.settings.ai_model
    assert config.settings.model_for("embed") == config.settings.ai_model
    config.settings.ai_model_extract = "cheap-fast"
    config.settings.ai_model_synth = "strong-slow"
    config.settings.ai_model_embed = "embed-small"
    assert config.settings.model_for("extract") == "cheap-fast"
    assert config.settings.model_for("synth") == "strong-slow"
    assert config.settings.model_for("embed") == "embed-small"
    assert config.settings.model_for("unknown-role") == config.settings.ai_model


def test_run_json_task_uses_routed_extract_model(conn, monkeypatch):
    fake = FakeClient([json.dumps({"keywords": ["k1"]})])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    config.settings.ai_model_extract = "cheap-fast"
    payload, cached = ai_tasks.run_json_task(
        "extract things", "input", task="routing-test",
        validate=lambda p: (isinstance(p, dict), None),
        cache=(conn, "routing-test", "scope1", "v1", "fp1"))
    assert cached is False and payload == {"keywords": ["k1"]}
    assert FakeClient.calls[0]["model"] == "cheap-fast"


def test_run_task_uses_routed_synth_model(monkeypatch):
    fake = FakeClient(["plain answer"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    config.settings.ai_model_synth = "strong-slow"
    out = ai_tasks.run_task("system", "user", task="routing-synth",
                            model_role="synth")
    assert out == "plain answer"
    assert FakeClient.calls[0]["model"] == "strong-slow"


def test_usage_records_the_model_that_served_the_task(monkeypatch):
    fake = FakeClient(["plain answer"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    config.settings.ai_model_synth = "strong-slow"
    ai_tasks.run_task("s", "u", task="routing-synth", model_role="synth")
    c = db.get_db()
    try:
        row = c.execute(
            "SELECT model FROM ai_usage WHERE task='routing-synth'"
        ).fetchone()
        assert row["model"] == "strong-slow"
        u = ai_tasks.usage_stats(c)
        assert u["by_model"].get("strong-slow", 0) >= 1
        c.execute("DELETE FROM ai_usage WHERE task='routing-synth'")
        c.commit()
    finally:
        c.close()


def test_daily_cap_blocks_with_honest_error(monkeypatch):
    fake = FakeClient(["plain answer"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    c = db.get_db()
    try:
        # make sure "today" is non-zero so the cap math is unambiguous
        ai_tasks.record_usage(c, "cap-seed", 1, 0, 0)
        c.commit()
        already = ai_tasks.requests_today(c)
        assert already >= 1
        # cap set exactly at today's usage -> the next request is refused
        config.settings.ai_daily_cap = already
        with pytest.raises(ai_tasks.TaskError, match="Daily AI request cap"):
            ai_tasks.run_task("s", "u", task="capped-test")
        assert FakeClient.calls == []       # the provider was never called

        # one request of headroom -> allowed, then recorded
        config.settings.ai_daily_cap = already + 1
        ai_tasks.run_task("s", "u", task="cap-allowed-test")
        assert len(FakeClient.calls) == 1
        assert ai_tasks.requests_today(c) == already + 1
        c.execute("DELETE FROM ai_usage WHERE task IN "
                  "('cap-seed', 'capped-test', 'cap-allowed-test')")
        c.commit()
    finally:
        c.close()


def test_daily_cap_zero_is_unlimited(monkeypatch):
    fake = FakeClient(["plain answer"])
    monkeypatch.setattr("ai.get_client", lambda: fake)
    ai_tasks.run_task("s", "u", task="uncapped-routing-test")
    assert len(FakeClient.calls) == 1
