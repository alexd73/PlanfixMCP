# PlanfixMCP

MCP-сервер для Planfix REST API, предоставляющий инструменты для работы с задачами, контактами, проектами и комментариями в LLM-ассистентах.

## Установка и запуск

1. Установите [uv](https://docs.astral.sh/uv/).
2. Склонируйте проект и установите зависимости:
   ```bash
   git clone <url>
   cd PlanfixMCP
   uv sync
   ```
3. Создайте файл `.env` на основе `.env.example` и укажите в нем:
   - `PLANFIX_BASE_URL`: Базовый URL вашего REST API (например, `https://account.planfix.com/rest`).
   - `PLANFIX_API_TOKEN`: Ваш Bearer-токен.

4. Запустите сервер (через stdio для MCP-клиента):
   ```bash
   uv run planfix-mcp
   ```

## Конфигурация

Все параметры задаются через `.env` файл или переменные окружения:

| Переменная | Описание |
|---|---|
| `PLANFIX_BASE_URL` | Базовый URL REST API Planfix. |
| `PLANFIX_API_TOKEN` | Bearer-токен авторизации. |
| `PLANFIX_EXCLUDE_TECHNICAL_COMMENTS` | Если `true`, скрывает технические события (смена статусов, дат) в ленте комментариев. |
| `PLANFIX_TAGS` | Список тегов OpenAPI для фильтрации инструментов (по умолчанию: `task,contact,project,comments`). |

## Использование в MCP-клиентах

Добавьте в ваш `opencode.json` (или аналогичный конфиг клиента):

```json
{
  "planfix": {
    "type": "local",
    "command": ["uv", "run", "planfix-mcp"],
    "environment": {
      "PLANFIX_BASE_URL": "{env:PLANFIX_BASE_URL}",
      "PLANFIX_API_TOKEN": "{env:PLANFIX_API_TOKEN}",
      "PLANFIX_EXCLUDE_TECHNICAL_COMMENTS": "true"
    }
  }
}
```

## Установка через AI-агента

Вы можете поручить установку и настройку этого MCP-сервера AI-агенту, используя следующий промпт:

> "Клонируй репозиторий PlanfixMCP по адресу `<url>`, установи зависимости через `uv sync` и помоги мне создать файл `.env` с настройками доступа к API Planfix (`PLANFIX_BASE_URL` и `PLANFIX_API_TOKEN`). После этого проверь работоспособность тестами и добавь конфигурацию сервера в мой `opencode.json`."
