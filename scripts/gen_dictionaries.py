"""Генерация заготовок словарей имён и описаний из спеки.

Выводит на stdout фрагменты для planfix_mcp/names.py и planfix_mcp/descriptions.py.
Использование при обновлении спеки: uv run python scripts/gen_dictionaries.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from planfix_mcp.config import ROOT_DIR


def snake_case(name: str) -> str:
    name = re.sub(r"[\s\-\.]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def short_name(operation_id: str) -> str:
    """Превращает operationId в короткое snake_case имя.

    get-task-list -> task_list
    post-task-by-id -> task_by_id
    post-task-add-comment -> task_add_comment
    get-comment-id -> comment_id
    """
    name = snake_case(operation_id)
    for prefix in ("get_", "post_", "put_", "patch_", "delete_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name


def main() -> None:
    spec_file = ROOT_DIR / "specs" / "swagger.json"
    spec = json.loads(spec_file.read_text(encoding="utf-8"))

    rows: list[tuple[str, str, str, str]] = []
    for path, item in spec.get("paths", {}).items():
        for method in ("get", "post", "put", "patch", "delete"):
            op = item.get(method)
            if not op:
                continue
            op_id = op.get("operationId", "")
            rows.append((op_id, method.upper(), path, op.get("summary", "")))

    rows.sort(key=lambda r: r[0])
    print(f"# {len(rows)} операций\n")
    print("NAMES:")
    for op_id, *_ in rows:
        print(f'    "{op_id}": "{short_name(op_id)}",')
    print("\nSUMMARYS:")
    for op_id, _, _, summary in rows:
        print(f'    "{op_id}": "{summary.replace(chr(34), "")}",')


if __name__ == "__main__":
    sys.exit(main())