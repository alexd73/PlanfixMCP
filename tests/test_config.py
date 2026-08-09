"""Конфигурация: приоритет CLI > env > .env, парсинг списков."""

import os

import pytest
from pydantic_settings import BaseSettings

from planfix_mcp.config import Settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("PLANFIX_"):
            monkeypatch.delenv(key, raising=False)


def make_settings(**overrides) -> Settings:
    # _env_file=None: в тестах не читаем реальный .env из корня проекта.
    return Settings(_env_file=None, **overrides)


def test_defaults() -> None:
    s = make_settings()
    assert s.base_url == "https://your-account.planfix.com/rest"
    assert s.api_token == ""
    assert s.tag_list == ["task", "contact", "project", "comments"]
    assert s.include_ids == set()
    assert s.exclude_ids == set()
    assert s.validate_output is True


def test_env_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANFIX_BASE_URL", "https://demo.planfix.ru/rest")
    monkeypatch.setenv("PLANFIX_API_TOKEN", "secret-token")
    monkeypatch.setenv("PLANFIX_TAGS", "task, project")
    monkeypatch.setenv("PLANFIX_INCLUDE_OPERATION_IDS", "ping, generate-report")
    monkeypatch.setenv("PLANFIX_EXCLUDE_OPERATION_IDS", "delete-file-id")
    monkeypatch.setenv("PLANFIX_VALIDATE_OUTPUT", "false")

    s = make_settings()
    assert s.base_url == "https://demo.planfix.ru/rest"
    assert s.api_token == "secret-token"
    assert s.tag_list == ["task", "project"]
    assert s.include_ids == {"ping", "generate-report"}
    assert s.exclude_ids == {"delete-file-id"}
    assert s.validate_output is False


def test_constructor_overrides_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANFIX_BASE_URL", "https://env.example/rest")
    s = Settings(_env_file=None, base_url="https://cli.example/rest", api_token="cli-token")
    assert s.base_url == "https://cli.example/rest"
    assert s.api_token == "cli-token"


def test_negative_validate_output_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANFIX_VALIDATE_OUTPUT", "0")
    assert make_settings().validate_output is False


def test_http_client_has_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANFIX_API_TOKEN", "abc")
    s = make_settings()
    async_client = s.http_client()
    assert str(async_client.headers["Authorization"]) == "Bearer abc"
    assert str(async_client.base_url).rstrip("/") == "https://your-account.planfix.com/rest"


def test_http_client_no_token_no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    s = make_settings()
    async_client = s.http_client()
    assert "Authorization" not in async_client.headers


def test_base_settings_model_config() -> None:
    # pydantic-settings версия, дающая source='env'/'settings', импортируется из одного пакета.
    assert issubclass(Settings, BaseSettings)
