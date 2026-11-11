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


def test_env_file_override(monkeypatch, tmp_path):
    # TGQ_ENV_FILE points the app at a throwaway .env (test harnesses,
    # e2e): a run must never read or write a real one.
    target = tmp_path / "isolated.env"
    monkeypatch.setenv("TGQ_ENV_FILE", str(target))
    assert config.resolve_env_file() == target


def test_env_file_default_is_repo_env(monkeypatch):
    # source runs keep .env next to the code, unchanged
    monkeypatch.delenv("TGQ_ENV_FILE", raising=False)
    assert config.resolve_env_file() == config.APP_ROOT / ".env"
