"""Инструменты выгрузки задач в файлы и сводок: серверная пагинация, компактный результат.

Тяжёлая работа (циклы по страницам `/task/list` и `/task/{id}/comments/list`,
запись файлов) выполняется на сервере. LLM получает только компактный манифест
или сводку — ничего из сырых данных не попадает в контекст разговора.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from planfix_mcp.config import Settings

PAGE_SIZE = 100

# Типы сложных фильтров задач Planfix (docs: REST API — Сложные фильтры задач).
TASK_FILTER_ASSIGNER = 1
TASK_FILTER_ASSIGNEE = 2
TASK_FILTER_AUDITOR = 3
TASK_FILTER_PROJECT = 5
TASK_FILTER_COUNTERPARTY = 7
TASK_FILTER_START_DATE = 13
TASK_FILTER_END_DATE = 14
TASK_FILTER_PARENT = 73

DEFAULT_TASK_FIELDS = "id,name,description,status,project,parent,dateTime,startDateTime,endDateTime,dateOfLastUpdate"

COMMENT_FIELDS = "id,dateTime,type,description,owner,isDeleted,isPinned,isHidden,changeStatus,changeTaskStartDate,changeTaskExpectDate"


def _url(base: str, path: str) -> str:
    """Склейка base_url и пути как в RequestDirector FastMCP (сохраняет /rest)."""
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _to_planfix_date(value: str) -> str:
    """ISO 2026-08-01 -> dd-MM-yyyy; уже в нужном формате — без изменений."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return value


def _compile_filters(
    filters: list[dict[str, object]] | None,
    end_date_before: str | None = None,
    end_date_after: str | None = None,
    start_date_before: str | None = None,
    start_date_after: str | None = None,
    assigner: str | None = None,
    assignee: str | None = None,
    auditor: str | None = None,
    counterparty: int | str | None = None,
    project: int | None = None,
) -> list[dict[str, object]]:
    """Собирает массив ComplexTaskFilter: шорткаты + пользовательские filters."""
    compiled: list[dict[str, object]] = list(filters or [])

    for attr, ftype, operator in (
        ("end_date_before", TASK_FILTER_END_DATE, "lt"),
        ("end_date_after", TASK_FILTER_END_DATE, "gt"),
        ("start_date_before", TASK_FILTER_START_DATE, "lt"),
        ("start_date_after", TASK_FILTER_START_DATE, "gt"),
    ):
        value = locals()[attr]
        if value:
            compiled.append(
                {
                    "type": ftype,
                    "operator": operator,
                    "value": {
                        "dateType": "otherDate",
                        "dateValue": _to_planfix_date(value),
                    },
                }
            )

    if assigner:
        compiled.append({"type": TASK_FILTER_ASSIGNER, "operator": "equal", "value": assigner})
    if assignee:
        compiled.append({"type": TASK_FILTER_ASSIGNEE, "operator": "equal", "value": assignee})
    if auditor:
        compiled.append({"type": TASK_FILTER_AUDITOR, "operator": "equal", "value": auditor})
    if counterparty is not None:
        compiled.append({"type": TASK_FILTER_COUNTERPARTY, "operator": "equal", "value": counterparty})
    if project is not None:
        compiled.append({"type": TASK_FILTER_PROJECT, "operator": "equal", "value": project})

    return compiled


async def _fetch_all(
    client: httpx.AsyncClient, path: str, key: str, base_body: dict[str, object]
) -> list[dict[str, object]]:
    """Пагинация POST-метода: собирает все страницы по ключу из ответа."""
    items: list[dict[str, object]] = []
    offset = 0
    while True:
        body = dict(base_body)
        body.update({"offset": offset, "pageSize": PAGE_SIZE})
        response = await client.post(_url(str(client.base_url), path), json=body)
        response.raise_for_status()
        page = response.json().get(key) or []
        items.extend(page)
        if len(page) < PAGE_SIZE:
            return items
        offset += PAGE_SIZE


def _is_technical_comment(comment: dict[str, object]) -> bool:
    return bool(
        comment.get("changeStatus")
        or comment.get("changeTaskStartDate")
        or comment.get("changeTaskExpectDate")
    )


class _HTMLStripper(HTMLParser):
    """HTMLParser, собирающий текст без тегов; <br> и блочные теги -> перенос строки."""

    BLOCK_TAGS = {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def _strip_html(text: object) -> str:
    """Убирает HTML из текста: теги -> чистый текст, entities -> символы."""
    if not text:
        return ""
    stripper = _HTMLStripper()
    try:
        stripper.feed(str(text))
        return stripper.text()
    except Exception:
        return re.sub(r"<[^>]+>", "", html.unescape(str(text))).strip()


def _safe_filename(name: object, max_length: int = 100) -> str:
    """Очищает имя для имени файла: недопустимые символы -> '-', усечение."""
    cleaned = re.sub(r'[\\/:*?"<>|]', "-", str(name or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:max_length].rstrip(" .")


def _comment_url(host: str, task_id: object, comment_id: object) -> str:
    """Ссылка на комментарий Planfix: https://{host}/task/{id}/?comment={cid}."""
    return f"https://{host}/task/{task_id}/?comment={comment_id}"


def _comment_host(base_url: str) -> str:
    return urlparse(base_url).hostname or ""


def _resolve_output_dir(export_root: Path, output_dir: str) -> Path:
    """Возвращает целевой каталог, не допуская выход за пределы export_root."""
    if not output_dir:
        return export_root
    rel = Path(output_dir)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("output_dir должен быть относительным путём без '..'")
    root = export_root.resolve()
    target = (root / rel).resolve()
    if not target.is_relative_to(root):
        raise ValueError("output_dir выходит за пределы каталога выгрузки")
    return target


def _render_markdown(
    task: dict[str, object],
    comments: list[dict[str, object]],
    account: str,
    host: str,
    total_comments: int,
    chunk_index: int = 1,
    total_chunks: int = 1,
) -> str:
    """Obsidian-файл: frontmatter + чистый текст. Описание — только в первом чанке."""
    name = str(task.get("name", ""))
    project = _field_name(task.get("project"))
    status = _field_name(task.get("status"))
    created = _format_datetime(task.get("dateTime"))
    start = _format_datetime(task.get("startDateTime"))
    due = _format_datetime(task.get("endDateTime"))
    updated = _format_datetime(task.get("dateOfLastUpdate"))

    def val(v: str) -> str:
        return str(v) if v else ""

    frontmatter = {
        "account": account,
        "taskId": task.get("id", ""),
        "project": project,
        "status": status,
        "created": val(created),
        "start": val(start),
        "due": val(due),
        "updated": val(updated),
        "commentCount": total_comments,
        "chunk": chunk_index,
        "totalChunks": total_chunks,
    }
    fm_lines = ["---"]
    fm_lines += [f"{k}: {v}" for k, v in frontmatter.items()]
    fm_lines.append("---")

    lines = [*fm_lines, "", f"# {name}", ""]
    if chunk_index == 1 and task.get("description"):
        lines += [_strip_html(task["description"]), ""]
    lines.append(f"## Комментарии ({len(comments)})")
    lines.append("")
    for c in comments:
        dt = _format_datetime(c.get("dateTime"))
        cid = c.get("id")
        url = _comment_url(host, task.get("id"), cid)
        lines.append(f"- {dt} · [{cid}]({url})")
        lines.append("")
        lines.append(_strip_html(c.get("description")))
        lines.append("")
    return "\n".join(lines)


def _field_name(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("id") or "")
    return str(value or "")


def _format_datetime(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("datetime") or value.get("date") or "")
    return str(value or "")


def _entity_id(value: object) -> object:
    if isinstance(value, dict):
        return value.get("id")
    return value


def _unique_name(base: str, used: set[str], entity_id: object) -> str:
    """Имя папки/файла без коллизий: при совпадении добавляет id задачи/проекта."""
    if base not in used:
        used.add(base)
        return base
    candidate = f"{base} ({entity_id})"
    n = 2
    while candidate in used:
        n += 1
        candidate = f"{base} ({entity_id}) ({n})"
    used.add(candidate)
    return candidate


def _chunks(items: list, size: int) -> list[list]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _write_task_files(
    task_dir: Path,
    task: dict[str, object],
    comments: list[dict[str, object]],
    fmt: str,
    account: str,
    host: str,
    comments_per_file: int,
    used_files: set[str],
) -> list[str]:
    """Пишет файлы задачи: md-чанки (описание в -1) или один json."""
    task_id = task.get("id")
    base = _safe_filename(task.get("name"))
    if fmt == "json":
        name = f"task-{task_id}.json"
        path = task_dir / name
        payload = {"task": task, "comments": comments}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return [name]

    chunk_list = _chunks(comments, comments_per_file) or [[]]
    names: list[str] = []
    for i, chunk in enumerate(chunk_list, start=1):
        name = _unique_name(f"{base}-{i}", used_files, task_id)
        path = task_dir / f"{name}.md"
        path.write_text(
            _render_markdown(
                task,
                chunk,
                account,
                host,
                total_comments=len(comments),
                chunk_index=i,
                total_chunks=len(chunk_list),
            ),
            encoding="utf-8",
        )
        names.append(path.name)
    return names


def _project_folder_name(task: dict[str, object]) -> str:
    project = _field_name(task.get("project"))
    return _safe_filename(project) or "Без проекта"


async def _fetch_subtasks(
    client: httpx.AsyncClient, parent_id: object, fields: str
) -> list[dict[str, object]]:
    """Непосредственные подзадачи задачи (фильтр type 73)."""
    return await _fetch_all(
        client,
        "/task/list",
        "tasks",
        {
            "fields": fields,
            "filters": [{"type": TASK_FILTER_PARENT, "operator": "equal", "value": parent_id}],
        },
    )


async def _build_tree(
    client: httpx.AsyncClient,
    roots: list[dict[str, object]],
    fields: str,
    visited: set[object],
) -> list[dict[str, object]]:
    """Рекурсивно строит дерево задач: node = {task, children}."""
    tree: list[dict[str, object]] = []
    for root in roots:
        task_id = _entity_id(root.get("id"))
        if task_id in visited:
            continue
        visited.add(task_id)
        children = await _fetch_subtasks(client, task_id, fields)
        node: dict[str, object] = {
            "task": root,
            "children": await _build_tree(client, children, fields, visited),
        }
        tree.append(node)
    return tree


def build_export_tools(client: httpx.AsyncClient, settings: Settings):
    """Возвращает функции-инструменты export_tasks и task_summary (для server.add_tool)."""

    async def export_tasks(
        output_dir: str = "",
        format: str = "md",
        include_comments: bool = True,
        filter_id: str | None = None,
        run_as_user_id: str | None = None,
        filters: list[dict[str, object]] | None = None,
        fields: str | None = None,
        end_date_before: str | None = None,
        end_date_after: str | None = None,
        start_date_before: str | None = None,
        start_date_after: str | None = None,
        assigner: str | None = None,
        assignee: str | None = None,
        auditor: str | None = None,
        counterparty: int | str | None = None,
        project: int | None = None,
    ) -> dict[str, object]:
        """Выгрузить задачи (с комментариями) в файлы и вернуть компактный манифест.

        Сервер сам пагинирует `/task/list`, строит дерево задач (проект -> задача ->
        подзадачи), при необходимости тянет `/task/{id}/comments/list` и пишет файлы.
        Markdown: файл `<задача>-<N>.md` — описание в первом, комментарии чанками
        по `PLANFIX_EXPORT_COMMENTS_PER_FILE`. Возвращается только манифест.

        Параметры-шорткаты (endDateBefore, assigner и т.п.) сервер превращает в
        сложные фильтры Planfix. Фильтрация по сохранённому фильтру — через filterId,
        полный набор типов фильтров (включая пользовательские поля) — через filters.
        """
        target_dir = _resolve_output_dir(settings.export_root, output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        account = settings.account_name
        host = _comment_host(settings.base_url)
        task_fields = fields or DEFAULT_TASK_FIELDS

        task_filters = _compile_filters(
            filters,
            end_date_before=end_date_before,
            end_date_after=end_date_after,
            start_date_before=start_date_before,
            start_date_after=start_date_after,
            assigner=assigner,
            assignee=assignee,
            auditor=auditor,
            counterparty=counterparty,
            project=project,
        )
        base_body: dict[str, object] = {"fields": task_fields}
        if filter_id:
            base_body["filterId"] = filter_id
        if run_as_user_id:
            base_body["runAsUserId"] = run_as_user_id
        if task_filters:
            base_body["filters"] = task_filters

        seeds = await _fetch_all(client, "/task/list", "tasks", base_body)
        seed_ids = {_entity_id(t.get("id")) for t in seeds}
        roots = [t for t in seeds if _entity_id(t.get("parent")) not in seed_ids]
        tree = await _build_tree(client, roots, task_fields, set())

        async def fetch_comments(task_id: object) -> list[dict[str, object]]:
            comments = await _fetch_all(
                client,
                f"/task/{task_id}/comments/list",
                "comments",
                {"fields": COMMENT_FIELDS},
            )
            if settings.exclude_technical_comments:
                comments = [c for c in comments if not _is_technical_comment(c)]
            return comments

        async def write_node(
            node: dict[str, object], parent_dir: Path, used_dirs: set[str]
        ) -> list[dict[str, object]]:
            task = node["task"]
            task_id = task.get("id")
            folder = _unique_name(
                _safe_filename(task.get("name")) or f"task-{task_id}", used_dirs, task_id
            )
            task_dir = parent_dir / folder
            task_dir.mkdir(parents=True, exist_ok=True)

            comments: list[dict[str, object]] = []
            if include_comments:
                comments = await fetch_comments(task_id)

            used_files: set[str] = set()
            files = _write_task_files(
                task_dir,
                task,
                comments,
                format,
                account,
                host,
                settings.comments_per_file,
                used_files,
            )
            entry: dict[str, object] = {
                "taskId": task_id,
                "name": task.get("name"),
                "project": _field_name(task.get("project")) or "Без проекта",
                "files": files,
                "commentCount": len(comments),
            }
            entries: list[dict[str, object]] = [entry]
            child_used: set[str] = set()
            for child in node["children"]:
                entries.extend(await write_node(child, task_dir, child_used))
            return entries

        manifest: list[dict[str, object]] = []
        project_dirs: dict[tuple, Path] = {}
        project_used_dirs: dict[str, set[str]] = {}
        used_projects: set[str] = set()
        for root_node in tree:
            task = root_node["task"]
            project_key = (
                _entity_id(task.get("project")),
                _project_folder_name(task),
            )
            project_dir = project_dirs.get(project_key)
            if project_dir is None:
                project_folder = _unique_name(project_key[1], used_projects, project_key[0])
                project_dir = target_dir / project_folder
                project_dir.mkdir(parents=True, exist_ok=True)
                project_dirs[project_key] = project_dir
            used_dirs = project_used_dirs.setdefault(str(project_dir), set())
            manifest.extend(await write_node(root_node, project_dir, used_dirs))

        return {
            "exported": len(manifest),
            "outputDir": str(target_dir),
            "files": manifest,
        }

    async def task_summary(
        filter_id: str | None = None,
        run_as_user_id: str | None = None,
        filters: list[dict[str, object]] | None = None,
        fields: str | None = None,
        include_comment_counts: bool = True,
        end_date_before: str | None = None,
        end_date_after: str | None = None,
        start_date_before: str | None = None,
        start_date_after: str | None = None,
        assigner: str | None = None,
        assignee: str | None = None,
        auditor: str | None = None,
        counterparty: int | str | None = None,
        project: int | None = None,
    ) -> list[dict[str, object]]:
        """Компактная сводка по задачам без записи файлов.

        Возвращает список задач с id, названием, статусом, сроком и числом
        комментариев — для быстрого обзора и отбора, без выгрузки сырых данных.
        Принимает те же фильтры, что и export_tasks (шорткаты + filterId + filters).
        """
        task_filters = _compile_filters(
            filters,
            end_date_before=end_date_before,
            end_date_after=end_date_after,
            start_date_before=start_date_before,
            start_date_after=start_date_after,
            assigner=assigner,
            assignee=assignee,
            auditor=auditor,
            counterparty=counterparty,
            project=project,
        )
        base_body: dict[str, object] = {
            "fields": fields or "id,name,status,endDateTime,description,project,dateTime,startDateTime,dateOfLastUpdate"
        }
        if filter_id:
            base_body["filterId"] = filter_id
        if run_as_user_id:
            base_body["runAsUserId"] = run_as_user_id
        if task_filters:
            base_body["filters"] = task_filters

        tasks = await _fetch_all(client, "/task/list", "tasks", base_body)

        summary: list[dict[str, object]] = []
        for task in tasks:
            comment_count: int | None = None
            if include_comment_counts:
                comments = await _fetch_all(
                    client,
                    f"/task/{task.get('id')}/comments/list",
                    "comments",
                    {"fields": COMMENT_FIELDS},
                )
                if settings.exclude_technical_comments:
                    comments = [c for c in comments if not _is_technical_comment(c)]
                comment_count = len(comments)
            summary.append(
                {
                    "taskId": task.get("id"),
                    "name": task.get("name"),
                    "status": _field_name(task.get("status")),
                    "endDateTime": _format_datetime(task.get("endDateTime")),
                    "commentCount": comment_count,
                }
            )
        return summary

    return export_tasks, task_summary