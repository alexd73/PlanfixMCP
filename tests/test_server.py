"""Интеграционные тесты сервера: сборка, list_tools, вызов через MockTransport."""

import asyncio

import httpx
import pytest

from planfix_mcp.config import Settings
from planfix_mcp.descriptions import DESCRIPTIONS
from planfix_mcp.server import build_server


def build_live_server(monkeypatch: pytest.MonkeyPatch, **overrides) -> object:
    monkeypatch.setenv("PLANFIX_API_TOKEN", "test-token")
    return build_server(settings=Settings(_env_file=None, **overrides))


def test_build_server_returns_tools() -> None:
    server = build_server(settings=Settings(_env_file=None, api_token="test-token"))
    tools = asyncio.run(server.list_tools())
    assert len(tools) == 39


def test_default_names_and_russian_descriptions(monkeypatch: pytest.MonkeyPatch) -> None:
    server = build_live_server(monkeypatch)
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}

    assert "task_list" in names
    assert "create_task" in names
    assert "update_task" in names
    assert "contact_list" in names
    assert "project_list" in names

    by_name = {t.name: t for t in tools}
    assert "задача" in by_name["task_list"].description.lower() or "задач" in by_name["task_list"].description.lower()
    assert "Удалить комментарий" in by_name["delete_comment"].description


def test_include_operation_adds_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    server = build_live_server(monkeypatch, include_operation_ids="ping")
    tools = asyncio.run(server.list_tools())
    assert any(t.name == "ping" for t in tools)
    assert len(tools) == 40


def test_read_only_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # В read_only остаются GET-маршруты и POST-маршруты с operation_id,
    # начинающимся с "get-" (чтение списков/данных). Мутации исключаются.
    server = build_live_server(monkeypatch, read_only=True)
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}

    # Мутации отсутствуют
    assert "create_task" not in names          # post-task
    assert "update_task" not in names          # post-task-by-id
    assert "add_task_comment" not in names     # post-task-add-comment
    assert "update_task_comment" not in names  # post-task-update-comment
    assert "delete_comment" not in names       # delete-comment-id
    assert "delete_file" not in names          # delete-file-id

    # Читающие списки (POST, но operation_id начинается с "get-") доступны
    assert "task_list" in names          # get-task-list
    assert "task_comments" in names      # get-task-comments
    assert "comment_list" in names       # get-comment-list
    assert "contact_list" in names       # get-contact-list
    assert "contact_comments" in names   # get-contact-comments
    assert "project_list" in names       # get-project-list
    assert "task_filters" in names       # post-task-filters (не get-)

    # GET-маршруты доступны
    assert "task_by_id" in names         # get-task-by-id /task/{id} [get]
    assert "contact_by_id" in names      # get-contact-by-id [get]


def test_all_tool_descriptions_are_russian(monkeypatch: pytest.MonkeyPatch) -> None:
    server = build_live_server(monkeypatch)
    tools = asyncio.run(server.list_tools())
    for tool in tools:
        assert any("\u0400" <= ch <= "\u04ff" for ch in tool.description), f"{tool.name}: не русское описание"


@pytest.mark.anyio
async def test_task_list_call_via_mock_transport() -> None:
    async def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer mock"
        return httpx.Response(200, json={"tasks": [{"id": 1, "title": "Задача"}]})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_handler),
        base_url="https://mock.planfix.ru/rest",
        headers={"Authorization": "Bearer mock"},
    )
    server = build_server(settings=Settings(_env_file=None, api_token="mock"), client_override=client)

    tool = next(t for t in await server.list_tools() if t.name == "task_list")
    result = await tool.run({})
    assert result is not None