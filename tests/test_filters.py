"""Фильтрация инструментов: теги ядра, include/exclude по operationId."""

import pytest
from fastmcp.server.providers.openapi.routing import MCPType
from fastmcp.utilities.openapi import HTTPRoute

from planfix_mcp.config import Settings
from planfix_mcp.filters import build_route_map_fn

# Список тегов из спеки Planfix (заглавные, как в OpenAPI).
TAGS = ["Task", "Contact", "Comments", "Project"]


def make_route(operation_id: str, tags: list[str] | None = None) -> HTTPRoute:
    return HTTPRoute(
        method="POST" if operation_id.startswith("post-") else "GET",
        path="/dummy",
        operation_id=operation_id,
        tags=tags or [],
        parameters=[],
        responses={},
    )


def test_core_tag_is_tool() -> None:
    fn = build_route_map_fn(Settings(tags="task,contact,project,comments"))
    route = make_route("get-task-list", tags=["Task"])
    assert fn(route, MCPType.EXCLUDE) == MCPType.TOOL


def test_unknown_tag_is_excluded() -> None:
    fn = build_route_map_fn(Settings(tags="task,contact,project,comments"))
    route = make_route("get-user-list", tags=["System"])
    assert fn(route, MCPType.EXCLUDE) == MCPType.EXCLUDE


def test_include_operation_by_id() -> None:
    fn = build_route_map_fn(
        Settings(include_operation_ids="get-user-list, ping")
    )
    route = make_route("get-user-list", tags=["System"])
    assert fn(route, MCPType.EXCLUDE) == MCPType.TOOL


def test_exclude_operation_by_id() -> None:
    fn = build_route_map_fn(
        Settings(tags="task", exclude_operation_ids="get-task-list")
    )
    route = make_route("get-task-list", tags=["Task"])
    assert fn(route, MCPType.EXCLUDE) == MCPType.EXCLUDE


def test_exclude_wins_over_tag_and_include() -> None:
    fn = build_route_map_fn(
        Settings(
            tags="task",
            include_operation_ids="get-task-list",
            exclude_operation_ids="get-task-list",
        )
    )
    route = make_route("get-task-list", tags=["Task"])
    assert fn(route, MCPType.EXCLUDE) == MCPType.EXCLUDE


def test_routes_without_tags_fallback_exclude() -> None:
    fn = build_route_map_fn(Settings(tags="task"))
    route = make_route("ping")
    assert fn(route, MCPType.EXCLUDE) == MCPType.EXCLUDE


@pytest.mark.parametrize(
    "tags,expected",
    [("TASK", MCPType.TOOL), ("Task", MCPType.TOOL), ("task", MCPType.TOOL)],
)
def test_tag_matching_case_insensitive(tags: str, expected: MCPType) -> None:
    fn = build_route_map_fn(Settings(tags=tags))
    route = make_route("get-task-list", tags=["Task"])
    assert fn(route, MCPType.EXCLUDE) == expected