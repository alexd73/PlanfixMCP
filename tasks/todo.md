# PlanfixMCP — Task List

## Phase 1: Foundation

### Task 1: Vendor спеки + каркас пакета
**Description:** Скачать свежую спеку в `specs/swagger.json`, инициализировать `pyproject.toml`
с зависимостью `fastmcp==3.4.6`, создать модуль `planfix_mcp` с минимальным `server.py`
(`FastMCP.from_openapi`) и скрипт `scripts/update_spec.py`.

**Acceptance criteria:**
- [x] `specs/swagger.json` — корректный OpenAPI 3.0.1 с ровно 114 операциями
- [x] `uv sync` успешно ставит `fastmcp`
- [x] Сервер собирается без токена/URL (тест строит его с mock-клиентом)

**Verification:**
- [x] `uv run python -c "import planfix_mcp"` — без ошибок
- [x] `uv run pytest tests/test_spec.py -q` — зелёный

**Dependencies:** None

**Files:** `pyproject.toml`, `planfix_mcp/*`, `scripts/update_spec.py`, `tests/test_spec.py`

**Scope:** M (3-5 файлов)

## Phase 2: Словари

### Task 2: Словари имён и описаний
**Description:** Создать `names.py` (operationId → snake_case имя) и `descriptions.py`
(operationId → русское описание) для всех 114 операций.

**Acceptance criteria:**
- [x] Покрыты все 114 operationId из спеки (тест сверяет со спекой)
- [x] Имена уникальны и в snake_case (без дефисов)
- [x] Описания непустые

**Verification:**
- [x] `uv run pytest tests/test_names.py -q` — зелёный

**Dependencies:** Task 1

**Files:** `planfix_mcp/names.py`, `planfix_mcp/descriptions.py`, `tests/test_names.py`

**Scope:** M

## Phase 3: Фильтрация

### Task 3: Фильтрация инструментов через route_map_fn
**Description:** Реализовать `filters.py`: `route_map_fn`, включающий маршруты по тегам
(`PLANFIX_TAGS`, дефолт `task,contact,project,comments`) или по allowlist операций
(`PLANFIX_INCLUDE_OPERATION_IDS`), исключающий по `PLANFIX_EXCLUDE_OPERATION_IDS`; фолбэк —
`RouteMap(MCPType.EXCLUDE)` для остальных.

**Acceptance criteria:**
- [x] По умолчанию экспонируется 37 инструментов ядра
- [x] Добавление операции через include-флаг увеличивает число инструментов
- [x] Исключаемая операция исчезает из списка

**Verification:**
- [x] `uv run pytest tests/test_filters.py -q` — зелёный

**Dependencies:** Task 1, Task 2 (имена для сверки)

**Files:** `planfix_mcp/filters.py`, `tests/test_filters.py`

**Scope:** Small

## Phase 4: Конфиг

### Task 4: Конфиг (env/.env/CLI)
**Description:** `config.py` на `pydantic-settings` с префиксом `PLANFIX_`, CLI-флаги
(`--base-url`, `--api-token`, `--tags`, `--include-operation-ids`, `--exclude-operation-ids`,
`--validate-output`, `--transport`). `.env.example`, `.gitignore` для `.env`.

**Acceptance criteria:**
- [x] Токен и URL задаются через env без правки кода («подключение через env»)
- [x] Приоритет CLI > env > .env
- [x] Токен не логируется, не попадает в `.env.example`

**Verification:**
- [x] `uv run pytest tests/test_config.py -q` — зелёный
- [x] `uv run planfix-mcp --help` показывает флаги

**Dependencies:** Task 1

**Files:** `planfix_mcp/config.py`, `.env.example`, `.gitignore`, `tests/test_config.py`

**Scope:** Small

## Phase 5: Валидация и сборка

### Task 5: Валидация ответов и интеграционный тест
**Description:** Включить `validate_output=True`; `server.py` применяет `names.py`,
`descriptions.py` (через `mcp_component_fn`); добавить `test_server` с MockTransport.

**Acceptance criteria:**
- [x] Полный `uv run pytest -q` зелёный
- [x] `list_tools` отдаёт ядро с русскими описаниями
- [x] Вызов инструмента через MockTransport возвращает структурированный результат

**Verification:**
- [x] `uv run pytest -q` — зелёный

**Dependencies:** Tasks 1-4

**Files:** `planfix_mcp/server.py`, `tests/test_server.py`

**Scope:** Medium

## Phase 6: Интеграция и README

### Task 6: README + подключение в opencode.json
**Description:** Написать README с инструкцией подключения (env), добавить блок MCP-сервера
в `opencode.json`, ручная проверка.

**Acceptance criteria:**
- [x] README документирует env-переменные и фильтрацию (теги/route)
- [x] MCP-сервер видим в клиенте opencode

**Verification:**
- [x] Вызов `task_list` из клиента работает (реальный вызов: 59 задач, result=success)

**Dependencies:** Task 5

**Files:** `README.md`, `opencode.json`

**Scope:** Small

## Phase 7: HTTP-транспорт

### Task 7: Опция `--transport http`
**Description:** Дать флаг HTTP-запуска (streamable-http), smoke-тест.

**Acceptance criteria:**
- [x] `uv run planfix-mcp --transport http` поднимает сервер (smoke: uvicorn, отвечает HTTP 404 на `/`, эндпоинт `/mcp`)
- [x] HTTP-режим не ломает stdio (test_main + полный suite)

**Verification:**
- [x] curl/`mcp inspector` отвечает (smoke-запуск на свободном порту, teardown по PID)

**Dependencies:** Task 5

**Files:** `planfix_mcp/__main__.py`

**Scope:** Small

## Checkpoints

### После Phase 1
- [ ] Сервер строится; спека валидна (114)

### После Phase 3
- [ ] Ядро = 37; include/exclude работают

### После Phase 5
- [ ] Полный прогон зелёный

### После Phase 6-7
- [x] Ручная демонстрация инструмента из MCP-клиента (task_list → 59 задач; HTTP smoke зелёный)