"""Тесты инструментов export_tasks и task_summary: дерево, чанки, пагинация, безопасность."""

from __future__ import annotations

import json

import httpx
import pytest

from planfix_mcp.config import Settings
from planfix_mcp.export import (
    DEFAULT_TASK_FIELDS,
    build_export_tools,
    _build_tree,
    _comment_url,
    _compile_filters,
    _render_markdown,
    _resolve_output_dir,
    _safe_filename,
    _strip_html,
)

pytestmark = pytest.mark.anyio


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://mock.planfix.ru/rest",
        headers={"Authorization": "Bearer mock"},
    )


def make_tools(client, **overrides):
    settings = Settings(
        _env_file=None,
        api_token="mock",
        base_url="https://mock.planfix.ru/rest",
        **overrides,
    )
    export_tasks, task_summary = build_export_tools(client, settings)
    return export_tasks, task_summary, settings


def make_task(task_id: int, name: str = "Задача", project: str = "Проект", parent: int | None = None) -> dict:
    task = {
        "id": task_id,
        "name": name,
        "description": f"Описание {name}",
        "status": {"id": 1, "name": "В работе"},
        "project": {"id": 5, "name": project},
        "dateTime": {"datetime": "2026-08-01T00:00Z"},
        "startDateTime": {"datetime": "2026-08-01T00:00Z"},
        "endDateTime": {"datetime": "2026-08-01T00:00Z"},
        "dateOfLastUpdate": {"datetime": "2026-08-01T00:00Z"},
    }
    if parent is not None:
        task["parent"] = {"id": parent, "name": "Родитель"}
    return task


def make_comment(comment_id: int, text: str) -> dict:
    return {
        "id": comment_id,
        "dateTime": {"datetime": "2026-08-01T00:00Z"},
        "owner": {"id": "user:1", "name": "Alex"},
        "description": text,
        "isDeleted": False,
    }


async def test_export_tasks_paginates_and_writes_files(tmp_path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content or b"{}")
        if request.url.path.endswith("/task/list"):
            if body.get("filters"):
                return httpx.Response(200, json={"tasks": []})
            offset = body.get("offset", 0)
            tasks = [make_task(i) for i in range(1, 101)]
            page = tasks if offset == 0 else []
            return httpx.Response(200, json={"tasks": page})
        if request.url.path.endswith("/comments/list"):
            return httpx.Response(200, json={"comments": [make_comment(1, "Коммент")]})
        return httpx.Response(404, json={})

    client = make_client(handler)
    export_tasks, _, settings = make_tools(client, export_dir=str(tmp_path))
    result = await export_tasks()

    assert result["exported"] == 100
    assert len(result["files"]) == 100
    assert result["files"][0]["commentCount"] == 1
    assert result["files"][0]["files"] == ["Задача-1.md"]
    md_path = tmp_path / "Проект" / "Задача" / "Задача-1.md"
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "Коммент" in text
    assert "?comment=1" in text
    # два запроса списка: offset 0 (100 шт) и offset 100 (0 шт) + фильтры подзадач
    list_requests = [r for r in requests if r.url.path.endswith("/task/list") and not json.loads(r.content or b"{}").get("filters")]
    assert len(list_requests) == 2


async def test_export_tasks_json_format(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/task/list"):
            if json.loads(request.content or b"{}").get("filters"):
                return httpx.Response(200, json={"tasks": []})
            return httpx.Response(200, json={"tasks": [make_task(7)]})
        return httpx.Response(200, json={"comments": []})

    client = make_client(handler)
    export_tasks, _, settings = make_tools(client, export_dir=str(tmp_path))
    result = await export_tasks(format="json", include_comments=False)

    assert result["files"][0]["files"] == ["task-7.json"]
    payload = json.loads((tmp_path / "Проект" / "Задача" / "task-7.json").read_text(encoding="utf-8"))
    assert payload["task"]["name"] == "Задача"
    assert payload["comments"] == []


async def test_export_tasks_subdir(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content or b"{}").get("filters"):
            return httpx.Response(200, json={"tasks": []})
        return httpx.Response(200, json={"tasks": [make_task(1)]})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client, export_dir=str(tmp_path))
    await export_tasks(output_dir="nested/deep")
    assert (tmp_path / "nested" / "deep" / "Проект" / "Задача" / "Задача-1.md").exists()


async def test_export_tasks_chunks_comments(tmp_path) -> None:
    all_comments = [make_comment(i, f"Коммент {i}") for i in range(1, 121)]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        if request.url.path.endswith("/task/list"):
            if body.get("filters"):
                return httpx.Response(200, json={"tasks": []})
            return httpx.Response(200, json={"tasks": [make_task(1)]})
        if request.url.path.endswith("/comments/list"):
            offset = body.get("offset", 0)
            page = all_comments[offset : offset + 100]
            return httpx.Response(200, json={"comments": page})
        return httpx.Response(404, json={})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client, export_dir=str(tmp_path), comments_per_file=100)
    result = await export_tasks()

    entry = result["files"][0]
    assert entry["commentCount"] == 120
    assert entry["files"] == ["Задача-1.md", "Задача-2.md"]

    first = (tmp_path / "Проект" / "Задача" / "Задача-1.md").read_text(encoding="utf-8")
    second = (tmp_path / "Проект" / "Задача" / "Задача-2.md").read_text(encoding="utf-8")
    assert "Описание Задача" in first
    assert "Описание Задача" not in second
    assert "Коммент 100" in first
    assert "Коммент 101" in second
    assert "chunk: 1" in first
    assert "chunk: 2" in second


async def test_export_tasks_tree_with_subtasks(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        if request.url.path.endswith("/task/list"):
            filters = body.get("filters") or []
            parent_filter = next((f for f in filters if f.get("type") == 73), None)
            if parent_filter:
                parent_id = parent_filter["value"]
                subtasks = {
                    1: [make_task(11, "Подзадача", parent=1)],
                    11: [],
                }
                return httpx.Response(200, json={"tasks": subtasks.get(parent_id, [])})
            return httpx.Response(200, json={"tasks": [make_task(1, "Задача")]})
        return httpx.Response(200, json={"comments": []})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client, export_dir=str(tmp_path))
    result = await export_tasks(include_comments=False)

    assert result["exported"] == 2
    assert (tmp_path / "Проект" / "Задача" / "Подзадача" / "Подзадача-1.md").exists()


async def test_export_tasks_no_project(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content or b"{}").get("filters"):
            return httpx.Response(200, json={"tasks": []})
        task = make_task(1, "Без проекта задача")
        task["project"] = None
        return httpx.Response(200, json={"tasks": [task]})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client, export_dir=str(tmp_path))
    result = await export_tasks(include_comments=False)

    assert result["files"][0]["project"] == "Без проекта"
    assert (tmp_path / "Без проекта" / "Без проекта задача" / "Без проекта задача-1.md").exists()


async def test_export_tasks_same_name_appends_id(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content or b"{}").get("filters"):
            return httpx.Response(200, json={"tasks": []})
        return httpx.Response(200, json={"tasks": [make_task(1, "Одинаковая"), make_task(2, "Одинаковая")]})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client, export_dir=str(tmp_path))
    result = await export_tasks(include_comments=False)

    assert (tmp_path / "Проект" / "Одинаковая").exists()
    assert (tmp_path / "Проект" / "Одинаковая (2)").exists()


async def test_end_date_before_compiles_to_filter() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return httpx.Response(200, json={"tasks": []})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client)
    await export_tasks(end_date_before="2026-08-01")

    filters = captured["body"]["filters"]
    assert filters[0]["type"] == 14
    assert filters[0]["operator"] == "lt"
    assert filters[0]["value"] == {"dateType": "otherDate", "dateValue": "01-08-2026"}


async def test_person_and_project_shortcuts_compile() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return httpx.Response(200, json={"tasks": []})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client)
    await export_tasks(
        assigner="user:1",
        assignee="contact:5",
        auditor="group:3",
        counterparty=42,
        project=17,
    )

    filters = captured["body"]["filters"]
    by_type = {f["type"]: f for f in filters}
    assert by_type[1]["value"] == "user:1"
    assert by_type[2]["value"] == "contact:5"
    assert by_type[3]["value"] == "group:3"
    assert by_type[7]["value"] == 42
    assert by_type[5]["value"] == 17


async def test_filter_id_passthrough() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content or b"{}")
        return httpx.Response(200, json={"tasks": []})

    client = make_client(handler)
    export_tasks, _, _ = make_tools(client)
    await export_tasks(filter_id="123")

    assert captured["body"]["filterId"] == "123"


def test_resolve_output_dir_rejects_traversal(tmp_path) -> None:
    settings = Settings(_env_file=None, api_token="mock", export_dir=str(tmp_path))
    with pytest.raises(ValueError):
        _resolve_output_dir(settings.export_root, "../outside")
    with pytest.raises(ValueError):
        _resolve_output_dir(settings.export_root, "C:/Windows")
    with pytest.raises(ValueError):
        _resolve_output_dir(settings.export_root, "a/../../b")


def test_resolve_output_dir_ok(tmp_path) -> None:
    settings = Settings(_env_file=None, api_token="mock", export_dir=str(tmp_path))
    target = _resolve_output_dir(settings.export_root, "sub/dir")
    assert target.is_relative_to(settings.export_root)


async def test_task_summary_with_counts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/task/list"):
            return httpx.Response(200, json={"tasks": [make_task(5), make_task(6, "Другая")]})
        return httpx.Response(200, json={"comments": [make_comment(1, "x") for _ in range(3)]})

    client = make_client(handler)
    _, task_summary, _ = make_tools(client)
    result = await task_summary()

    assert len(result) == 2
    assert result[0]["taskId"] == 5
    assert result[0]["commentCount"] == 3
    assert result[0]["status"] == "В работе"


async def test_task_summary_skips_counts_when_disabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/task/list"):
            return httpx.Response(200, json={"tasks": [make_task(5)]})
        return httpx.Response(200, json={"comments": []})

    client = make_client(handler)
    _, task_summary, _ = make_tools(client)
    result = await task_summary(include_comment_counts=False)
    assert result[0]["commentCount"] is None


def test_compile_filters_merges_shortcuts_and_custom() -> None:
    filters = _compile_filters(
        [{"type": 8, "operator": "equal", "value": "поиск"}],
        end_date_before="2026-08-01",
        project=3,
    )
    assert len(filters) == 3
    assert filters[0]["type"] == 8
    assert any(f["type"] == 14 for f in filters)
    assert any(f["type"] == 5 for f in filters)


def test_strip_html_removes_tags_and_entities() -> None:
    text = "<p>Привет <b>мир</b></p><br/>Текст &amp; символы<br><ul><li>пункт</li></ul>"
    out = _strip_html(text)
    assert "<" not in out
    assert "Привет мир" in out
    assert "Текст & символы" in out
    assert "пункт" in out


def test_strip_html_empty_and_plain() -> None:
    assert _strip_html("") == ""
    assert _strip_html(None) == ""
    assert _strip_html("просто текст") == "просто текст"


def test_safe_filename_sanitizes_and_truncates() -> None:
    assert _safe_filename('a/b\\c:*?"<>|') == "a-b-c-------"
    assert _safe_filename("   имя   задачи   ") == "имя задачи"
    assert len(_safe_filename("x" * 500)) <= 100
    assert _safe_filename("  ") == ""


def test_comment_url_format() -> None:
    url = _comment_url("mock.planfix.ru", 21197, 912082)
    assert url == "https://mock.planfix.ru/task/21197/?comment=912082"


def test_account_name_from_base_url() -> None:
    settings = Settings(_env_file=None, api_token="mock", base_url="https://acme.planfix.ru/rest")
    assert settings.account_name == "acme"


def test_account_name_overridden_by_env() -> None:
    settings = Settings(
        _env_file=None,
        api_token="mock",
        base_url="https://acme.planfix.ru/rest",
        export_account="myaccount",
    )
    assert settings.account_name == "myaccount"


def test_export_dir_default_is_export(tmp_path) -> None:
    settings = Settings(_env_file=None, api_token="mock", export_dir="export")
    assert settings.export_root.name == "export"


def test_export_root_relative_resolves_from_cwd(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, api_token="mock", export_dir="raw/planfix_tasks")
    assert settings.export_root == tmp_path / "raw" / "planfix_tasks"


def test_export_root_absolute_kept_as_is(tmp_path) -> None:
    settings = Settings(_env_file=None, api_token="mock", export_dir=str(tmp_path))
    assert settings.export_root == tmp_path


def test_render_markdown_frontmatter_and_comment_link() -> None:
    task = make_task(21197, "Тестовая")
    comments = [make_comment(912082, "<p>Текст <b>комментария</b></p>")]
    md = _render_markdown(task, comments, "acme", "acme.planfix.ru", total_comments=1)

    assert md.startswith("---")
    assert "account: acme" in md
    assert "taskId: 21197" in md
    assert "project: Проект" in md
    assert "# Тестовая" in md
    assert "https://acme.planfix.ru/task/21197/?comment=912082" in md
    assert "<p>" not in md
    assert "<b>" not in md
    assert "## Комментарии (1)" in md
    assert "chunk: 1" in md


async def test_build_tree_recurses_subtasks() -> None:
    calls: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        filters = body.get("filters") or []
        parent_filter = next((f for f in filters if f.get("type") == 73), None)
        if parent_filter:
            calls.append(parent_filter["value"])
            subtasks = {
                1: [make_task(11, "Подзадача", parent=1)],
                11: [make_task(111, "Внучка", parent=11)],
                111: [],
            }
            return httpx.Response(200, json={"tasks": subtasks.get(parent_filter["value"], [])})
        return httpx.Response(200, json={"tasks": [make_task(1)]})

    client = make_client(handler)
    tree = await _build_tree(client, [make_task(1)], DEFAULT_TASK_FIELDS, set())

    assert len(tree) == 1
    assert tree[0]["task"]["id"] == 1
    assert tree[0]["children"][0]["task"]["id"] == 11
    assert tree[0]["children"][0]["children"][0]["task"]["id"] == 111
    assert calls == [1, 11, 111]