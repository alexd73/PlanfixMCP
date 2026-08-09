"""CLI-точка входа: planfix-mcp [--transport stdio|http] [флаги настройки]."""

from __future__ import annotations

import argparse

from planfix_mcp.config import ROOT_DIR
from planfix_mcp.server import build_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="planfix-mcp",
        description="MCP-сервер для Planfix REST API (инструменты из OpenAPI-спеки).",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="Транспорт MCP (по умолчанию stdio).",
    )
    parser.add_argument("--base-url", help="Базовый URL REST API (переопределяет PLANFIX_BASE_URL).")
    parser.add_argument("--api-token", help="Bearer-токен Planfix (переопределяет PLANFIX_API_TOKEN).")
    parser.add_argument("--tags", help="Теги OpenAPI для включения инструментов (через запятую).")
    parser.add_argument(
        "--include-operation-ids",
        help="Дополнительные операции по operationId (через запятую)",
    )
    parser.add_argument(
        "--exclude-operation-ids",
        help="Операции для исключения по operationId (через запятую)",
    )
    parser.add_argument(
        "--validate-output",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Валидировать ответы по схемам спеки (по умолчанию true)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Адрес для HTTP-транспорта (по умолчанию 127.0.0.1).",
    )
    parser.add_argument("--port", type=int, default=8000, help="Порт для HTTP-транспорта (по умолчанию 8000).")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    settings_overrides: dict[str, object] = {}
    for field in ("base_url", "api_token", "tags", "include_operation_ids", "exclude_operation_ids"):
        value = getattr(args, field)
        if value is not None:
            settings_overrides[field] = value
    if args.validate_output is not None:
        settings_overrides["validate_output"] = args.validate_output

    server = build_server(settings_overrides=settings_overrides)

    if args.transport == "http":
        server.run(transport="http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()