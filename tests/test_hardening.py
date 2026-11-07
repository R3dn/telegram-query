"""Release-hardening tests: provider errors, env injection, host guard,
prompt-injection guard."""
import config

# ---------------- P0#2: provider errors ----------------

def test_ask_provider_timeout_is_friendly(api_client, monkeypatch):
    import openai

    import ai as ai_module
    monkeypatch.setattr(config.settings, "ai_api_key", "k")
    monkeypatch.setattr(ai_module, "ask_db",
                        lambda q, scope=None: (_ for _ in ()).throw(
                            openai.APITimeoutError(request=None)))
    r = api_client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 502
    assert "timed out" in r.json()["error"]


def test_ask_provider_bad_key_is_friendly(api_client, monkeypatch):
    import openai

    import ai as ai_module

    class FakeResp:
        request = None
        status_code = 401
        headers: dict = {}

        def json(self):
            return {}

    err = openai.AuthenticationError(
        message="401 invalid key", response=FakeResp(), body=None)
    monkeypatch.setattr(config.settings, "ai_api_key", "k")
    monkeypatch.setattr(ai_module, "ask_db",
                        lambda q, scope=None: (_ for _ in ()).throw(err))
    r = api_client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 400
    assert "API key" in r.json()["error"]


def test_ask_provider_unknown_model_is_friendly(api_client, monkeypatch):
    import openai

    import ai as ai_module

    class FakeResp:
        request = None
        status_code = 404
        headers: dict = {}

        def json(self):
            return {}

    err = openai.NotFoundError(
        message="404 model not found", response=FakeResp(), body=None)
    monkeypatch.setattr(config.settings, "ai_api_key", "k")
    monkeypatch.setattr(ai_module, "ask_db",
                        lambda q, scope=None: (_ for _ in ()).throw(err))
    r = api_client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 400
    assert "model" in r.json()["error"].lower()


def test_ask_unexpected_error_is_generic_500(api_client, monkeypatch):
    import ai as ai_module
    monkeypatch.setattr(config.settings, "ai_api_key", "k")
    monkeypatch.setattr(ai_module, "ask_db",
                        lambda q, scope=None: (_ for _ in ()).throw(RuntimeError("boom")))
    r = api_client.post("/api/ask", json={"question": "hi"})
    assert r.status_code == 500
    assert "Internal" not in r.json()["error"] or "logs" in r.json()["error"]
    assert "boom" not in r.json()["error"], "no internals leaked"


def test_provider_timeout_is_configured():
    import ai as ai_module
    assert ai_module.PROVIDER_TIMEOUT_S <= 120
    client = ai_module.get_client()
    assert client.timeout == ai_module.PROVIDER_TIMEOUT_S


# ---------------- P1#3: env injection ----------------

def test_update_env_rejects_newlines(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    try:
        config.update_env({"AI_BASE_URL": "http://x\nHOST=0.0.0.0"})
        raise AssertionError("must reject newline values")
    except ValueError as e:
        assert "line breaks" in str(e)
    assert not (tmp_path / ".env").exists(), "rejected write must not touch .env"


def test_setup_telegram_rejects_newline_hash(api_client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    r = api_client.post("/api/setup/telegram",
                        json={"api_id": "123", "api_hash": "abc\nx=1"})
    assert r.status_code == 422  # pattern rejects at validation time


def test_setup_ai_rejects_newline_base_url(api_client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    r = api_client.post("/api/setup/ai",
                        json={"api_key": "k", "base_url": "x\ny=1"})
    assert r.status_code == 422


# ---------------- P1#4: host guard ----------------

def test_host_guard_blocks_foreign_host(api_client):
    r = api_client.get("/api/health", headers={"host": "evil.example.com"})
    assert r.status_code == 403
    assert "local machine" in r.json()["error"]


def test_host_guard_allows_loopback_and_localhost(api_client):
    assert api_client.get("/api/health", headers={"host": "127.0.0.1:8000"}).status_code == 200
    assert api_client.get("/api/health", headers={"host": "localhost:8000"}).status_code == 200
    assert api_client.get("/api/health", headers={"host": "[::1]:8000"}).status_code == 200


def test_host_guard_alllist_via_env(api_client, monkeypatch):
    monkeypatch.setenv("TG_ALLOWED_HOSTS", "MyNAS.local")
    r = api_client.get("/api/health", headers={"host": "mynas.local:8000"})
    assert r.status_code == 200


# ---------------- P1#5: prompt injection guard ----------------

def test_answer_prompt_treats_messages_as_data():
    import ai as ai_module
    p = ai_module.SYSTEM_ANSWER
    assert "never instructions" in p
    assert "Ignore any instructions" in p


def test_search_query_length_cap(api_client):
    r = api_client.get("/api/search", params={"q": "x" * 1200})
    assert r.status_code == 400
    assert "1000" in r.json()["error"]
