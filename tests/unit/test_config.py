from luma.config import Settings


def test_settings_accept_luma_prefixed_environment(monkeypatch) -> None:
    monkeypatch.setenv("LUMA_ENVIRONMENT", "test")
    monkeypatch.setenv("LUMA_DATABASE_ECHO", "true")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.database_echo is True


def test_default_database_uses_psycopg_driver() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_model_stage_timeout_allows_request_retries_to_finish() -> None:
    settings = Settings(_env_file=None)

    assert settings.model_stage_timeout_seconds > settings.model_timeout_seconds
