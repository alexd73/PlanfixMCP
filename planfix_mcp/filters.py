"""Фильтрация инструментов: теги OpenAPI + allowlist/exclude по operationId."""

from __future__ import annotations

from fastmcp.server.providers.openapi.routing import MCPType
from fastmcp.utilities.openapi import HTTPRoute

from planfix_mcp.config import Settings

# POST-маршруты, которые читают данные (списки фильтров, записи справочников,
# записи data-тегов), но чей operation_id не начинается с "get-".
# Остаются доступными в read_only-режиме наравне с get-*.
READ_ONLY_SAFE_POST_IDS: frozenset[str] = frozenset({
    "post-task-filters",
    "post-contact-filters",
    "post-list-data-tag-entries",
    "post-list-directory-entries",
    "post-directory-entries-filters",
})


def build_route_map_fn(settings: Settings):
    """Возвращает route_map_fn для FastMCP.from_openapi.

    Маршрут включается (TOOL), если:
      - у него есть тег из settings.tag_list, ИЛИ
      - его operation_id в settings.include_ids.
    Маршрут исключается (EXCLUDE), если:
      - его operation_id в settings.exclude_ids.
    Иначе — EXCLUDE (фолбэк: доступны только разрешённые инструменты).

    В read_only-режиме дополнительно исключаются все мутации: разрешены
    только GET-маршруты, POST-маршруты с operation_id на "get-"
    (списки/чтение данных) и POST-маршруты из READ_ONLY_SAFE_POST_IDS.
    """

    allowed_tags = {t.lower() for t in settings.tag_list}
    include_ids = settings.include_ids
    exclude_ids = settings.exclude_ids

    def route_map_fn(route: HTTPRoute, mcp_type: MCPType) -> MCPType | None:
        operation_id = route.operation_id or ""

        # 1. Исключения (приоритетны)
        if settings.read_only:
            is_get = route.method.upper() == "GET"
            is_read_list = operation_id.startswith("get-")
            is_safe_post = operation_id in READ_ONLY_SAFE_POST_IDS
            if not (is_get or is_read_list or is_safe_post):
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