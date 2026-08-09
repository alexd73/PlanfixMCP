# PlanfixMCP

MCP-сервер для Planfix REST API. Инструменты генерируются из вендоренной OpenAPI-спеки
(`specs/swagger.json`) через `FastMCP.from_openapi()` пакета [fastmcp](https://gofastmcp.com):
114 операций → MCP-инструменты с короткими snake_case именами и русскими описаниями.

## Возможности

- Генерация из спеки: `FastMCP.from_openapi` (+114 операций)
- Короткие snake_case имена (`task_list`, `comment_add`) через `planfix_mcp/names.py`
- Русские описания через `planfix_mcp/descriptions.py`
- Фильтрация инструментов: по тегам OpenAPI (по умолчанию ядро `task,contact,project,comments`)
  или точечно по `operationId` (`PLANFIX_INCLUDE_OPERATION_IDS` / `PLANFIX_EXCLUDE_OPERATION_IDS`)
- Bearer-авторизация (`PLANFIX_API_TOKEN`)
- Валидация ответов по схемам спеки

## Требования

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) для окружения

## Установка и запуск

```bash
uv sync
export PLANFIX_BASE_URL=https://your-account.planfix.com/rest   # или в .env
export PLANFIX_API_TOKEN=<token>
uv run planfix-mcp           # stdio-транспорт
uv run planfix-mcp --transport http   # HTTP-транспорт
```

Переменные также читаются из `.env` (скопируйте `.env.example`).

## Конфигурация

| Переменная | CLI | Дефолт | Описание |
|---|---|---|---|
| `PLANFIX_BASE_URL` | `--base-url` | `https://your-account.planfix.com/rest` | Базовый URL REST API |
| `PLANFIX_API_TOKEN` | `--api-token` | — | Bearer-токен Planfix |
| `PLANFIX_TAGS` | `--tags` | `task,contact,project,comments` | Теги OpenAPI для включения инструментов |
| `PLANFIX_INCLUDE_OPERATION_IDS` | `--include-operation-ids` | — | Дополнительные операции по `operationId` |
| `PLANFIX_EXCLUDE_OPERATION_IDS` | `--exclude-operation-ids` | — | Исключить операции по `operationId` |
| `PLANFIX_VALIDATE_OUTPUT` | `--validate-output` | `true` | Валидация ответов по схемам спеки |

## Обновление спеки

```bash
uv run python scripts/update_spec.py
```

Если спеку попадают новые операции — перегенерировать словари и обновить тесты:

```bash
uv run python scripts/gen_dictionaries.py
```

## Тесты

```bash
uv run pytest -q
```

Интеграционные тесты используют `httpx.MockTransport` и не ходят в реальный API.