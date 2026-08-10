# Spec: PlanfixMCP

## Objective

MCP-сервер, который даёт LLM-ассистентам доступ к Planfix REST API. Весь API-код генерируется
из вендоренной OpenAPI-спеки (`specs/swagger.json`) через `FastMCP.from_openapi()` пакета
`fastmcp` (gofastmcp): 114 операций → MCP-инструменты с короткими именами в snake_case
(`task_list`, `comment_add`) и русскими описаниями.

**Пользователи:** LLM-ассистенты (opencode, Claude Desktop и др.), работающие с задачами,
контактами и проектами Planfix.

**Приёмка:**
- Спека вендорена в `specs/swagger.json`, содержит ровно 114 операций (проверяется тестом).
- `list_tools` возвращает инструменты с ядром snake_case-именами и русскими описаниями.
- По умолчанию экспонируется «ядро»: Task + Comments + Project + Contact (37 инструментов);
  остальные подключаются настройкой.
- Bearer-авторизация: токен прикладывается к каждому запросу Planfix, никогда не логируется
  и не попадает в git.
- Ответы валидируются по схемам спеки (валидация выхода).
- Конфиг через CLI/env/.env: base URL, токен, теги ядра, include/exclude операций, флаг валидации.
- **Подключение через env:** пользователь задаёт `PLANFIX_API_TOKEN` и `PLANFIX_BASE_URL`
  переменными окружения (или `.env`), без правки кода — токен и URL подхватываются при старте
  сервера.
- **Ограничение инструментов**: пользователь может указать набор открытых инструментов двумя
  способами (доступны оба, комбинируются):
  - **по тегам** OpenAPI (`PLANFIX_TAGS` / флаг `--tags`, по умолчанию ядро `task,contact,project,comments`);
  - **по операциям/route** (`PLANFIX_INCLUDE_OPERATION_IDS` allowlist и
    `PLANFIX_EXCLUDE_OPERATION_IDS` — точечное включение/исключение через `operationId`);
    ограничение реализовано через `route_map_fn` в `filters.py`.
- Готов к подключению как stdio-сервер через `opencode.json`; ручная проверка вызова `task_list`.

## Tech Stack

- Python >=3.10 (окружение: 3.11.9), venv через `uv`
- `fastmcp==3.4.6` — содержит `FastMCP.from_openapi` (в официальном SDK `mcp` его нет)
- транзитивно: `mcp>=1.24,<2.0`, `httpx`, `pydantic`, `pydantic-settings`, openapi-core
- тесты: `pytest`, `httpx.MockTransport` (без реальных запросов к Planfix)

## Commands

```
Обновить спеку:     uv run python scripts/update_spec.py
Установка:          uv sync
Запуск (stdio):     uv run planfix-mcp
Запуск (HTTP):      uv run planfix-mcp --transport http
Список инструментов: uv run python -m planfix_mcp.list_tools
Тесты:              uv run pytest -q
```

## Project Structure

```
PlanfixMCP/
├─ pyproject.toml                 # зависимости + [project.scripts] planfix-mcp
├─ uv.lock
├─ specs/
│  └─ swagger.json                # вендореная OpenAPI-спека (источник истины)
├─ planfix_mcp/
│  ├─ __init__.py                 # версия пакета
│  ├─ __main__.py                 # python -m planfix_mcp
│  ├─ server.py                   # сборка FastMCP.from_openapi
│  ├─ config.py                   # Settings (pydantic-settings) + транспорт
│  ├─ names.py                    # operationId → snake_case имя (все 114)
│  ├─ descriptions.py             # operationId → русское описание (все 114)
│  └─ filters.py                  # route_map_fn / RouteMap (теги и allowlist/exclude)
├─ scripts/
│  └─ update_spec.py              # скачивание свежей спеки
├─ tests/
│  ├─ conftest.py                 # фикстура спеки + MockTransport
│  ├─ test_spec.py                # 114 операций, спека валидна
│  ├─ test_names.py               # покрытие 114, имена snake_case и уникальны
│  ├─ test_filters.py             # ядро = 37, include/exclude работают
│  └─ test_server.py              # сборка сервера, list_tools, вызов через mock
├─ .env.example                   # шаблон переменных
├─ .env                           # НЕ коммитится (токен)
├─ .gitignore
├─ docs/
│  └─ spec.md                     # этот документ
├─ tasks/
│  ├─ plan.md
│  └─ todo.md
└─ README.md
```

## Code Style

- Python 3.11, `snake_case`, аннотации типов везде.
- Комментарии не добавляем; осмысленные докстринги в публичных функциях.
- Имена инструментов: плоский snake_case, производятся из operationId (`get-task-list` → `task_list`).
- Русские описания инструментов живут в `descriptions.py`, отдельно от имени.

## Configuration (env / .env / CLI)

Все параметры считываются из переменных окружения; поддерживаются `.env` (через
`pydantic-settings`) и CLI-флаги (приоритет CLI > env > .env > дефолт).

| Переменная | CLI | Дефолт | Описание |
|---|---|---|---|
| `PLANFIX_BASE_URL` | `--base-url` | `https://your-account.planfix.com/rest` | Базовый URL REST API; подставляется пользователем при подключении |
| `PLANFIX_API_TOKEN` | `--api-token` | — | Bearer-токен Planfix; **обязателен**, не логируется |
| `PLANFIX_TAGS` | `--tags` | `task,contact,project,comments` | Ограничение инструментов OpenAPI-тегами (через `route_map_fn`) |
| `PLANFIX_INCLUDE_OPERATION_IDS` | `--include-operation-ids` | — | Доп. allowlist операций по `operationId` |
| `PLANFIX_EXCLUDE_OPERATION_IDS` | `--exclude-operation-ids` | — | Исключение операций по `operationId` |
| `PLANFIX_EXCLUDE_TECHNICAL_COMMENTS` | `--exclude-technical` | `false` | Исключать технические события (изменения статусов/сроков) из ленты комментариев |
| `PLANFIX_VALIDATE_OUTPUT` | `--validate-output` | `true` | Валидация ответов по схемам спеки |

**Логика фильтрации** (в `filters.py`, через `route_map_fn`):
1. Маршрут включается, если его тег в `PLANFIX_TAGS` **или** его `operationId` в
   `PLANFIX_INCLUDE_OPERATION_IDS`.
2. Маршрут исключается, если его `operationId` в `PLANFIX_EXCLUDE_OPERATION_IDS`.

Подключение из MCP-клиента: пользователь задаёт токен и URL в env (или `.env`), правки кода не требуются.

```yaml
# opencode.json
mcp:
  planfix:
    type: local
    command: ["uv", "run", "planfix-mcp"]
    enabled: true
    environment:
      PLANFIX_BASE_URL: "{env:PLANFIX_BASE_URL}"
      PLANFIX_API_TOKEN: "{env:PLANFIX_API_TOKEN}"
      PLANFIX_TAGS: "task,contact,project,comments"
```

## Testing Strategy

- `pytest`; фикстура загружает реальную вендоренную спеку.
- UIN-тесты: словари имён/описаний (полнота, уникальность), фильтрация (ядро/их включения).
- Интеграционные: сборка сервера → `list_tools` через memory/MockTransport-клиент, проверка имён/описаний.
- Никаких реальных сетевых вызовов; спецификация набора operationId зафиксирована в `test_spec.py`.

## Boundaries

- **Always:** запускать тесты перед сдачей; держать `descriptions.ru`/`names` в синхроне со спекой ключи через тест.
- **Ask first:** правки спеки, добавление зависимостей, смена транспорта, изменение схемы имён.
- **Never:** коммитить токен/`.env`; логировать `Authorization`; править имя/описание мимо `names.py`/`descriptions.py`.

## Success Criteria

- `uv run pytest -q` — зелёный.
- Сервер собирается, `list_tools` отдаёт ядро (37) с русскими описаниями.
- Флаг `--transport http` поднимает HTTP-сервер.
- MCP-сервер подключён через `opencode.json`; вызов инструмента работает через mock/реальную проверку.

## Open Questions

1. Транспорт: по умолчанию `stdio`; HTTP — опциональный `--transport`.
2. Обновления спеки — вручную (`scripts/update_spec.py` + ревью diff перед коммитом).