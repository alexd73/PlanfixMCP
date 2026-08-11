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

## Настройка API Token

1. **Получение токена**: перейдите в **Управление аккаунтом** -> **Интеграции** -> **REST API**. Создайте приложение или выберите существующее, затем скопируйте `Bearer-токен`. [Подробности в справке](https://planfix.com/ru/help/REST_API_%D0%90%D0%B2%D1%82%D0%BE%D1%80%D0%B8%D0%B7%D0%B0%D1%86%D0%B8%D1%8F).
2. **Настройка**: скопируйте файл `.env.example` в `.env` и вставьте полученный токен в поле `PLANFIX_API_TOKEN`.

## Настройка прав доступа (Scopes)

В настройках приложения (Управление аккаунтом -> Интеграции -> REST API) выберите права:
- **Рекомендуемый минимум (только чтение):** `common_metadata` + все права `*_readonly` (task, comment, project, contact, object, file).
- **Для записи (создание/обновление):** добавьте `*_add`, `*_update`.
- **Избегайте:** `system_settings`, `user_add`, `user_update` — они избыточны.

Затем запустите сервер (через stdio для MCP-клиента):
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

## Разработка и вклад в проект

Мы приветствуем Pull Requests! Если вы хотите помочь в развитии проекта:

1. **Развертывание окружения**:
   ```bash
   uv sync
   ```
2. **Запуск тестов**:
   Перед отправкой изменений убедитесь, что все тесты проходят:
   ```bash
   uv run pytest -q
   ```
3. **Обновление OpenAPI-спеки**:
   Если API Planfix изменилось, обновите локальную копию спеки и перегенерируйте словари:
   ```bash
   uv run python scripts/update_spec.py
   uv run python scripts/gen_dictionaries.py
   ```
4. **Pull Requests**:
   - Создайте отдельную ветку для ваших изменений.
   - Убедитесь, что код соответствует стилю проекта (Python 3.10+, snake_case).
   - **Важно**: Никогда не коммитьте `.env` файлы или API-токены.
