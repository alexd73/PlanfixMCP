"""Фильтрация инструментов: теги OpenAPI + allowlist/exclude по operationId."""

from __future__ import annotations

from fastmcp.server.providers.openapi.routing import MCPType
from fastmcp.utilities.openapi import HTTPRoute

from planfix_mcp.config import Settings


def build_route_map_fn(settings: Settings):
    """Возвращает route_map_fn для FastMCP.from_openapi.

    Маршрут включается (TOOL), если:
      - у него есть тег из settings.tag_list, ИЛИ
      - его operation_id в settings.include_ids.
    Маршрут исключается (EXCLUDE), если:
      - его operation_id в settings.exclude_ids.
    Иначе — EXCLUDE (фолбэк: доступны только разрешённые инструменты).
    """

    allowed_tags = {t.lower() for t in settings.tag_list}
    include_ids = settings.include_ids
    exclude_ids = settings.exclude_ids

    def route_map_fn(route: HTTPRoute, mcp_type: MCPType) -> MCPType | None:
        operation_id = route.operation_id or ""

        # 1. Исключения (приоритетны)
        if settings.read_only and route.method.upper() != "GET":
            return MCPType.EXCLUDE
        if operation_id in exclude_ids:
            return MCPType.EXCLUDE

        # 2. Разрешения
        route_tags = {t.lower() for t in (route.tags or [])}
        if route_tags & allowed_tags:
            return MCPType.TOOL
        if operation_id in include_ids:
            return MCPType.TOOL

        return MCPType.EXCLUDE


    return route_map_fn


def build_exclusion_route_maps():
    """Фолбэк-карты для передачи в route_maps (здесь не используем route_maps)."""
    return []