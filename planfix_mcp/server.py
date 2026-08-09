"""Сборка FastMCP-сервера из OpenAPI-спеки Planfix."""

from __future__ import annotations

import json
import pathlib

from fastmcp import FastMCP
from fastmcp.server.providers.openapi.components import (
    OpenAPIResource,
    OpenAPIResourceTemplate,
    OpenAPITool,
)
from fastmcp.server.providers.openapi.routing import HTTPRoute
from planfix_mcp.config import ROOT_DIR, Settings
from planfix_mcp.descriptions import DESCRIPTIONS
from planfix_mcp.filters import build_route_map_fn
from planfix_mcp.names import NAMES

SERVER_NAME = "planfix-mcp"


def load_spec() -> dict:
    """Читает вендоренную спеку из specs/swagger.json."""
    spec_file = ROOT_DIR / "specs" / "swagger.json"
    return json.loads(spec_file.read_text(encoding="utf-8"))


def _component_fn(route: HTTPRoute, component: OpenAPITool | OpenAPIResource | OpenAPIResourceTemplate) -> None:
    """Подменяет англ. описание компонента русским из словаря DESCRIPTIONS."""
    description = DESCRIPTIONS.get(route.operation_id or "")
    if description and hasattr(component, "description"):
        component.description = description


def build_server(
    settings: Settings | None = None,
    settings_overrides: dict[str, object] | None = None,
    client_override: object | None = None,
) -> FastMCP:
    """Создаёт FastMCP-сервер с инструментами из спски Planfix.

    settings_overrides приоритетнее env/.env: используются для передачи
    CLI-флагов (CLI > env > .env). client_override — httpx.AsyncClient для
    тестов (MockTransport).
    """
    settings = settings or Settings(**settings_overrides or {})
    client = client_override if client_override is not None else settings.http_client()
    spec = load_spec()

    return FastMCP.from_openapi(
        spec,
        name=SERVER_NAME,
        client=client,
        route_map_fn=build_route_map_fn(settings),
        mcp_component_fn=_component_fn,
        mcp_names=NAMES,
        validate_output=settings.validate_output,
    )