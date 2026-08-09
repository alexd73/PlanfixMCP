"""Скачивание актуальной OpenAPI-спеки Planfix в specs/swagger.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

SPEC_URL = "https://help.planfix.com/restapidocs/swagger.json"
TARGET = Path(__file__).resolve().parent.parent / "specs" / "swagger.json"


def main() -> None:
    print(f"Скачиваю спеку из {SPEC_URL}")
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(SPEC_URL)
        response.raise_for_status()
        spec = response.json()

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    operations = sum(
        1
        for path_item in spec.get("paths", {}).values()
        for method in ("get", "post", "put", "patch", "delete")
        if method in path_item
    )
    print(f"Сохранено {len(spec.get('paths', {}))} путей, {operations} операций -> {TARGET}")


if __name__ == "__main__":
    sys.exit(main())