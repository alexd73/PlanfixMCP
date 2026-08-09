"""Словари имён и описаний: покрытие спеки, уникальность, формат."""

import json
import re

import pytest

from planfix_mcp.config import ROOT_DIR
from planfix_mcp.descriptions import DESCRIPTIONS
from planfix_mcp.names import NAMES

METHODS = ("get", "post", "put", "patch", "delete")


def spec_operation_ids() -> set[str]:
    spec = json.loads((ROOT_DIR / "specs" / "swagger.json").read_text(encoding="utf-8"))
    ids = set()
    for item in spec["paths"].values():
        for method in METHODS:
            op = item.get(method)
            if op and op.get("operationId"):
                ids.add(op["operationId"])
    return ids


def test_names_cover_all_operations() -> None:
    missing = sorted(spec_operation_ids() - set(NAMES))
    assert not missing, f"Нет имён для: {missing}"


def test_descriptions_cover_all_operations() -> None:
    missing = sorted(spec_operation_ids() - set(DESCRIPTIONS))
    assert not missing, f"Нет описаний для: {missing}"


def test_names_unique() -> None:
    dupes = {v for v in NAMES.values() if list(NAMES.values()).count(v) > 1}
    assert not dupes, f"Дублирующиеся имена: {dupes}"


def test_names_snake_case_ascii() -> None:
    pattern = re.compile(r"^[a-z][a-z0-9_]*$")
    bad = [name for name in NAMES.values() if not pattern.match(name)]
    assert not bad, f"Имена не в snake_case: {bad}"


def test_names_short() -> None:
    long = {op: name for op, name in NAMES.items() if len(name) > 30}
    assert not long, f"Слишком длинные имена: {long}"


def test_names_do_not_include_verb_prefix_on_reads() -> None:
    # Контроль схемы: чтение по ресурсу (task_by_id), мутации с глаголом (update_task).
    # Мутационные глаголы для чтений запрещены; 'download' — чтение (GET файла),
    # 'upload'/'import' — только на POST, поэтому не входят в проверку GET.
    producers = {"create", "update", "delete", "add", "import", "upload"}
    reads = {op: name for op, name in NAMES.items() if op.startswith("get-")}
    for op, name in reads.items():
        assert not name.startswith(tuple(producers)), f"Чтение с verb-префиксом: {op} -> {name}"


def test_descriptions_non_empty_and_russian() -> None:
    for op, desc in DESCRIPTIONS.items():
        assert desc and desc.strip(), f"Пустое описание для {op}"
        assert any("\u0400" <= ch <= "\u04ff" for ch in desc), (
            f"Описание для {op} не на русском"
        )


def test_dictionaries_have_no_extra_keys() -> None:
    ids = spec_operation_ids()
    assert set(NAMES) == ids
    assert set(DESCRIPTIONS) == ids


@pytest.mark.parametrize("op_id", sorted(spec_operation_ids()))
def test_every_operation_has_name_and_description(op_id: str) -> None:
    assert op_id in NAMES
    assert op_id in DESCRIPTIONS