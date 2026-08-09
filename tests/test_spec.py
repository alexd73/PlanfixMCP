"""Проверка вендоренной спеки: 114 операций, обязательные поля."""

import json
import pathlib

from planfix_mcp.config import ROOT_DIR

SPEC_FILE = ROOT_DIR / "specs" / "swagger.json"
METHODS = ("get", "post", "put", "patch", "delete")


def load_spec() -> dict:
    return json.loads(SPEC_FILE.read_text(encoding="utf-8"))


def collect_operations(spec: dict) -> list[tuple[str, str, dict]]:
    ops = []
    for path, item in spec.get("paths", {}).items():
        for method in METHODS:
            op = item.get(method)
            if op:
                ops.append((method.upper(), path, op))
    return ops


def test_spec_file_exists() -> None:
    assert SPEC_FILE.exists()


def test_spec_is_valid_openapi3() -> None:
    spec = load_spec()
    assert spec["openapi"].startswith("3.")
    assert isinstance(spec["paths"], dict) and spec["paths"]


def test_operation_count_is_114() -> None:
    assert len(collect_operations(load_spec())) == 114


def test_all_operations_have_operation_id() -> None:
    for method, path, op in collect_operations(load_spec()):
        assert op.get("operationId"), f"{method} {path}: нет operationId"


def test_operation_ids_unique() -> None:
    ids = [op["operationId"] for _, _, op in collect_operations(load_spec())]
    assert len(ids) == len(set(ids))