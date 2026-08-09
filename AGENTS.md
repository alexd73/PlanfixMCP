# AGENTS.md — PlanfixMCP

MCP-сервер для Planfix REST API. Генерация инструментов из вендоренной OpenAPI-спеки (`specs/swagger.json`) через `FastMCP.from_openapi`. 114 операций → инструменты с короткими именами и русскими описаниями. Фильтрация инструментов (allowlist/исключения), Bearer-авторизация, валидация ответов по схемам, настройка через CLI/env/.env.

## Скилы (workflows — «как»)

Скилы установлены в `.opencode/skills/`. При каждой задаче агент ОБЯЗАН:

1. Определить, какой скил применим (даже при 1% вероятности)
2. Вызвать `skill` tool
3. Строго следовать workflow скила (включая гейты на человека)
4. Переходить к коду только после обязательных шагов (спека, план, тесты)

### Intent → Skill Mapping

- Новая фича / новый функционал → `spec-driven-development`, затем `incremental-implementation` + `test-driven-development`
- Проектирование API / интерфейса / MCP-инструментов → `api-and-interface-design`
- Планирование / декомпозиция → `planning-and-task-breakdown`
- Баг / неожиданное поведение / падение генерации из спеки → `debugging-and-error-recovery`
- Аутентификация, токены, секреты → `security-and-hardening`
- Ревью кода → `code-review-and-quality`
- Сборка / публикация / релиз → `shipping-and-launch`

### Жизненный цикл (неявные команды)

- DEFINE → `spec-driven-development`
- PLAN → `planning-and-task-breakdown`
- BUILD → `incremental-implementation` + `test-driven-development`
- VERIFY → `debugging-and-error-recovery`
- REVIEW → `code-review-and-quality`
- SHIP → `shipping-and-launch`

### Анти-рационализация (запрещено)

- «Задача слишком маленькая для скила»
- «Можно быстро написать без спеки/плана»
- «Сначала соберу контекст, потом решу»

## Специфика проекта

- Правки в OpenAPI-спеку — часть кодовой базы: при рассинхроне генерации сначала правь спеку, не обходи в коде
- Никогда не логируй и не коммить Bearer-токены и ключи API
- Не модифицируй репозитории в /home/alexd/Project/ai (только чтение); рабочий код — здесь, в PlanfixMCP
