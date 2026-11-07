"""Setup endpoint tests: .env semantics, contracts, masking, provider test."""
import config
from api import setup as setup_api

ENV_KEYS = ("TG_API_ID", "TG_API_HASH", "AI_API_KEY", "AI_BASE_URL", "AI_MODEL")


def use_tmp_env(monkeypatch, tmp_path):
    """Redirect the .env writer to a temp file for this test."""
    env_file = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    return env_file


def test_update_env_creates_file(monkeypatch, tmp_path):
    f = use_tmp_env(monkeypatch, tmp_path)
    config.update_env({"TG_API_ID": "123456", "TG_API_HASH": "abcdef" * 3})
    text = f.read_text(encoding="utf-8")
    assert "setup wizard" in text          # header comment for new files
    assert "TG_API_ID=123456" in text
    assert config.settings.tg_api_id == "123456"


def test_update_env_preserves_comments_and_others(monkeypatch, tmp_path):
    f = use_tmp_env(monkeypatch, tmp_path)
    f.write_text(
        "# my notes\n"
        "HOST=127.0.0.1\n"
        "TG_API_ID=999\n"
        "SOMETHING_ELSE=yes\n",
        encoding="utf-8")
    config.update_env({"TG_API_ID": "111", "AI_API_KEY": "sk-new"})
    lines = f.read_text(encoding="utf-8").splitlines()
    assert "# my notes" in lines
    assert "HOST=127.0.0.1" in lines
    assert "SOMETHING_ELSE=yes" in lines
    assert "TG_API_ID=111" in lines
    assert "AI_API_KEY=sk-new" in lines


def test_update_env_quotes_special_values(monkeypatch, tmp_path):
    f = use_tmp_env(monkeypatch, tmp_path)
    config.update_env({"AI_BASE_URL": "http://localhost:11434/v1 # local"})
    text = f.read_text(encoding="utf-8")
    assert 'AI_BASE_URL="' in text  # '#' in the value forces quoting


def test_setup_telegram_endpoint(api_client, monkeypatch, tmp_path):
    f = use_tmp_env(monkeypatch, tmp_path)
    r = api_client.post("/api/setup/telegram",
                        json={"api_id": " 12345 ", "api_hash": "h" * 32})
    assert r.status_code == 200
    body = r.json()
    assert body == {"telegram_configured": True}
    assert "h" * 32 not in r.text        # hash never echoed
    assert "TG_API_ID=12345" in f.read_text(encoding="utf-8")


def test_setup_telegram_rejects_non_numeric(api_client, monkeypatch, tmp_path):
    use_tmp_env(monkeypatch, tmp_path)
    # pattern validation rejects non-numeric api ids before the endpoint
    r = api_client.post("/api/setup/telegram",
                        json={"api_id": "abc", "api_hash": "h" * 32})
    assert r.status_code == 422


def test_setup_ai_endpoint_and_masking(api_client, monkeypatch, tmp_path):
    f = use_tmp_env(monkeypatch, tmp_path)
    r = api_client.post("/api/setup/ai", json={
        "base_url": "http://localhost:11434/v1",
        "api_key": "sk-secret-key-123",
        "model": "llama3",
    })
    assert r.status_code == 200
    assert r.json() == {"ai_configured": True}
    assert "sk-secret-key-123" not in r.text  # key never echoed
    text = f.read_text(encoding="utf-8")
    assert "AI_MODEL=llama3" in text
    assert "AI_BASE_URL=" in text
    assert config.settings.ai_configured is True


def test_setup_ai_requires_key(api_client, monkeypatch, tmp_path):
    use_tmp_env(monkeypatch, tmp_path)
    # whitespace-only / empty keys fail pattern validation (422); the
    # endpoint's explicit check remains as defense-in-depth
    r = api_client.post("/api/setup/ai", json={"api_key": "  "})
    assert r.status_code == 422
    r = api_client.post("/api/setup/ai", json={"api_key": ""})
    assert r.status_code == 422


class _FakeResp:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


def test_ai_test_ok(api_client, monkeypatch):
    calls = {}

    def fake_client(api_key, base_url):
        calls["api_key"], calls["base_url"] = api_key, base_url
        return type("Client", (), {"chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": staticmethod(
                    lambda **kw: _FakeResp("OK"))})})()})()

    monkeypatch.setattr(setup_api, "_make_client", fake_client)
    r = api_client.post("/api/setup/ai/test", json={
        "base_url": "http://x/v1", "api_key": "sk-t", "model": "m1"})
    body = r.json()
    assert body["ok"] is True and body["reply"] == "OK"
    assert calls == {"api_key": "sk-t", "base_url": "http://x/v1"}


def test_ai_test_provider_error_is_friendly(api_client, monkeypatch):
    def fake_client(api_key, base_url):
        raise RuntimeError("Error code: 401 - invalid api key")

    monkeypatch.setattr(setup_api, "_make_client", fake_client)
    r = api_client.post("/api/setup/ai/test", json={"api_key": "bad"})
    body = r.json()
    assert body["ok"] is False
    assert "unauthorized" in body["error"].lower()


def test_ai_test_requires_key(api_client):
    # pattern validation rejects empty/whitespace keys before the endpoint
    r = api_client.post("/api/setup/ai/test", json={"api_key": " "})
    assert r.status_code == 422
    r = api_client.post("/api/setup/ai/test", json={"api_key": ""})
    assert r.status_code == 422
