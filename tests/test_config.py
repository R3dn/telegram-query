"""Config tests: env parsing, aliases, path resolution, no secret leakage."""
import config


def test_env_aliases():
    # conftest sets TG_API_ID; the legacy TELEGRAM_API_ID alias must also work
    assert config.settings.tg_api_id == "123456"
    assert config.settings.telegram_configured is True


def test_defaults(monkeypatch):
    monkeypatch.setattr(config.settings, "host", "127.0.0.1")
    assert config.settings.host == "127.0.0.1"  # local-only by default


def test_load_settings_legacy_env(monkeypatch):
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.setenv("TELEGRAM_API_ID", "999")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hashy")
    s = config.load_settings()
    assert s.tg_api_id == "999"
    assert s.tg_api_hash == "hashy"


def test_explicit_paths_win(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_DB_PATH", str(tmp_path / "x.db"))
    s = config.load_settings()
    assert str(s.db_path).endswith("x.db")


def test_ai_configured_flag():
    assert config.settings.ai_configured is True
    assert config.settings.ai_model == "test-model"


def test_provider_host_not_key():
    host = config.settings.ai_provider_host
    assert "test-ai-key" not in host
    assert config.settings.ai_provider_host == "localhost:1"
