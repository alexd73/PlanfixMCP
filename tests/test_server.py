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
    assert len(tools) == 37


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
    assert len(tools) == 38


def test_read_only_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # При включенном read_only, инструменты, отличные от GET, должны исключаться
    server = build_live_server(monkeypatch, read_only=True)
    tools = asyncio.run(server.list_tools())
    
    # Проверяем, что нет инструментов с POST, PUT, DELETE, PATCH
    # (в OpenAPI спеке они обычно привязаны к методам)
    # Для упрощения проверим, что инструментов стало значительно меньше
    # по сравнению с полным списком
    
    # В этой реализации route_map_fn проверяет метод
    for tool in tools:
        # Инструменты в fastmcp не хранят метод напрямую, но мы можем проверить
        # их наличие или отсутствие. При read_only должны остаться только GET.
        pass
    
    # Проверка через MockTransport: попытка вызова post-метода должна провалиться
    # или инструмент должен быть исключен.
    # Инструменты, которые были, теперь не должны быть доступны.
    names = {t.name for t in tools}
    assert "create_task" not in names  # post-task
    assert "task_list" not in names    # post-task/list
    
    assert "task_by_id" in names # get-task-by-id /task/{id} [get]


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