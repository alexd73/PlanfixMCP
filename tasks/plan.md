# Implementation Plan: PlanfixMCP

## Overview

MCP-сервер для Planfix REST API на пакете `fastmcp` (v3.4.6): `FastMCP.from_openapi()` строит
инструменты из вендоренной спеки `specs/swagger.json` (114 операций). Инструменты фильтруются
до ядра по умолчанию (Task + Comments + Project + Contact → 37), получают snake_case имена
и русские описания через статические словари, авторизуются Bearer-токеном, ответы валидируются
по схемам. Настройка — CLI/env/.env.

## Architecture Decisions

- **fastmcp (gofastmcp) v3.4.6**, а не официальный SDK `mcp`: единственный источник
  `FastMCP.from_openapi`, поддерживает `route_maps`/`route_map_fn` (allowlist/исключения),
  `mcp_component_fn`, `mcp_names`, `validate_output`, безопасный `httpx.AsyncClient`.
- **Статические словари** `names.py` + `descriptions.py`: полный охват 114 operationId,
  НЕ извлекаем имена/описания динамически из англ. спеки.
- **Схема имён:** плоский snake_case, выведенный из operationId (`get-task-list` → `task_list`).
- **Фильтрация инструментов через `route_map_fn`** — она видит полный маршрут (`HTTPRoute`)
  и вызывается для всех, включая исключённые. Поддерживает оба требования пользователя:
  - **по тегам**: `PLANFIX_TAGS` (дефолт `task,contact,project,comments`) — агент.reHandler;
  - **по операциям/route**: `PLANFIX_INCLUDE_OPERATION_IDS` (allowlist) и
    `PLANFIX_EXCLUDE_OPERATION_IDS` (исключения по `operationId`);
  Венчается `RouteMap(MCPType.EXCLUDE)` как дефолт для неразрешённых маршрутов.
- **Конфиг:** `pydantic-settings` с env-префиксом `PLANFIX_` и `.env`, приоритет CLI > env > .env.
  Токен и URL для подключения задаются пользователем в env без правки кода.
- **Валидация ответов:** `validate_output=True` по умолчанию (схемы из спеки).

## Task List

### Phase 1: Foundation
- [x] Task 1: vendor спеку + каркас пакета (pyproject, uv sync, server.py minimal)
  - Acceptance: сервер собирается, спека в `specs/swagger.json`, 114 операций в тесте.
  - Verify: `uv run python -c "from planfix_mcp.server import build_server; print(len(build_server()._tools))"` (или `list_tools`).

### Phase 2: Словари
- [x] Task 2: `names.py` + `descriptions.py` — все 114 операций, имя snake_case/рус. описание.
  - Acceptance: `test_names` зелёный (покрытие 114, уникальность, формат).
  - Verify: `uv run pytest tests/test_names.py -q`.

### Phase 3: Фильтрация
- [x] Task 3: `filters.py` — `route_map_fn`: ядро по тегам (Task/Contact/Project/Comments),
      + `PLANFIX_INCLUDE_OPERATION_IDS`/`PLANFIX_EXCLUDE_OPERATION_IDS` из конфига;
      фолбэк `RouteMap(MCPType.EXCLUDE)` для остальных маршрутов.
  - Acceptance: `test_filters` зелёный (ядро=37, включение/исключение операции работает).
  - Verify: `uv run pytest tests/test_filters.py -q`.

### Phase 4: Конфиг
- [x] Task 4: `config.py` (Settings + CLI/транспорт), `.env.example`, `.gitignore`.
  - Acceptance: парсится env/.env/CLI; `PLANFIX_API_TOKEN` и `PLANFIX_BASE_URL` задаются
    пользователем через env без правки кода; токен нигде не логируется.
  - Verify: unit-тест на парсинг + мануальный запуск `--help`.

### Phase 5: Валидация и сборка
- [x] Task 5: включить `validate_output`, дописать `test_server` (list_tools, вызов через MockTransport).
  - Acceptance: полный `uv run pytest -q` зелёный.
  - Verify: `uv run pytest -q`.

### Phase 6: Интеграция + README
- [x] Task 6: README, `opencode.json`-конфиг MCP-сервера (stdio), ручная проверка вызова `task_list`.
  - Acceptance: сервер вызывается из MCP-клиента; README документирует настройку.
  - Verify: подключение к клиенту + вызов инструмента.

### Phase 7: Проверка `--transport http`
- [x] Task 7: флаг HTTP-транспорта; smoke-запуск (+ `tests/test_main.py`).
  - Acceptance: `uv run planfix-mcp --transport http` поднимает сервер.
  - Verify: ручной вызов через curl/`mcp inspector`.

## Phase Checkgates

- [x] After Phase 1: `list_tools` показывает ядро (после фильтрации).
- [x] After Phase 3: ядро = 37; env-токен и URL передаются без правки кода.
- [x] After Phase 5: полный тестовый прогон зелёный.
- [x] After Phase 6-7: ручная демонстрация инструмента.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| fastmcp активно меняется | Средний | пиним `fastmcp==3.4.6`, пересмотр deps при апгрейде |
| Спека может измениться / добавить операции | Low | vendor + скрипт update_spec.py; guard-test на 114 операций |
| Коллизии slug имён | Low | `_get_unique_name` fastmcp добавляет суффиксы; test_names фиксирует |
| HTTP-эндпоинты за $ref | Средний | openapi-core справляется; фиксируем спекой в тестах |

## Open Questions

- Нужен ли префикс нейминга `planfix_` в будущем (для мульти-MCP). Пока — без префикса.
- Какие именно теги приписывать инструментам «города» / видимость в клиенте.