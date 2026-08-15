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
from planfix_mcp.export import build_export_tools
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
    if route.operation_id in ["get-task-comments", "get-contact-comments"]:
        # Добавляем default для полей, чтобы клиент всегда получал описание и информацию об изменениях
        if "parameters" in vars(component) and "properties" in component.parameters and "fields" in component.parameters["properties"]:
            component.parameters["properties"]["fields"]["default"] = "id,description,additionalDescriptionData,changeStatus,changeTaskStartDate,changeTaskExpectDate"
    if description and hasattr(component, "description"):
        component.description = description


def build_server(
    settings: Settings | None = None,
    settings_overrides: dict[str, object] | None = None,
    client_override: object | None = None,
) -> FastMCP:
    """Создаёт FastMCP-сервер с инструментами из спски Planfix."""
    settings = settings or Settings(**settings_overrides or {})
    client = client_override if client_override is not None else settings.http_client()
    spec = load_spec()

    server = FastMCP.from_openapi(
        spec,
        name=SERVER_NAME,
        client=client,
        route_map_fn=build_route_map_fn(settings),
        mcp_component_fn=_component_fn,
        mcp_names=NAMES,
        validate_output=settings.validate_output,
    )

    for tool in build_export_tools(client, settings):
        server.add_tool(tool)

    if settings.exclude_technical_comments:
        _apply_technical_comment_filter(server)

    return server


def _apply_technical_comment_filter(server: FastMCP) -> None:
    """Обертка для фильтрации технических комментариев."""
    target_tools = {"task_comments", "contact_comments"}
    for tool_name in target_tools:
        if tool_name in server.tools:
            tool = server.tools[tool_name]
            original_run = tool.run
            
            async def wrapped_run(*args, **kwargs):
                result = await original_run(*args, **kwargs)
                if isinstance(result, dict) and "comments" in result:
                    result["comments"] = [
                        c for c in result["comments"]
                        if not (c.get("changeStatus") or c.get("changeTaskStartDate") or c.get("changeTaskExpectDate"))
                    ]
                return result
            
            tool.run = wrapped_run
