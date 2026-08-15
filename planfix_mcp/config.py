"""Конфигурация PlanfixMCP: env / .env / CLI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

CORE_TAGS = ("task", "contact", "project", "comments")

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки сервера.

    Все поля читаются из переменных окружения с префиксом PLANFIX_ (или из .env).
    Приоритет CLI-флагов над env обеспечивается в __main__ через модель_args/override.
    """

    model_config = SettingsConfigDict(
        env_prefix="PLANFIX_",
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "https://your-account.planfix.com/rest"
    api_token: str = ""
    tags: str = ",".join(CORE_TAGS)
    include_operation_ids: str = ""
    exclude_operation_ids: str = ""
    validate_output: bool = True
    exclude_technical_comments: bool = False
    read_only: bool = False
    export_dir: str = "export"
    export_account: str = ""
    comments_per_file: int = 100

    @property
    def export_root(self) -> Path:
        """Абсолютный базовый каталог выгрузки (из PLANFIX_EXPORT_DIR).

        Относительный путь резолвится от рабочего каталога процесса (cwd),
        чтобы выгрузка попадала в проект, из которого запущен сервер.
        """
        path = Path(self.export_dir)
        return path if path.is_absolute() else Path.cwd() / path

    @property
    def account_name(self) -> str:
        """Имя аккаунта: PLANFIX_EXPORT_ACCOUNT или поддомен из base_url."""
        if self.export_account:
            return self.export_account
        host = urlparse(self.base_url).hostname or ""
        return host.split(".")[0] if host else ""

    @property
    def tag_list(self) -> list[str]:
        return [t.strip().lower() for t in self.tags.split(",") if t.strip()]

    @property
    def include_ids(self) -> set[str]:
        return {t.strip() for t in self.include_operation_ids.split(",") if t.strip()}

    @property
    def exclude_ids(self) -> set[str]:
        return {t.strip() for t in self.exclude_operation_ids.split(",") if t.strip()}

    def http_client(self) -> httpx.AsyncClient:
        """Безопасный клиент с Bearer-заголовком. Токен не логируется."""
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=30.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()