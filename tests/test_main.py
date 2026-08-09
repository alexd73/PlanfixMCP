"""Юнит-тесты CLI: парсер и выбор транспорта в planfix_mcp.__main__."""

from __future__ import annotations

from planfix_mcp.__main__ import build_parser, main


def test_parser_defaults() -> None:
    args = build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.validate_output is None


def test_parser_http_args() -> None:
    args = build_parser().parse_args(["--transport", "http", "--host", "0.0.0.0", "--port", "9000"])
    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


class _StubServer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def _patch_server(monkeypatch) -> _StubServer:
    stub = _StubServer()
    monkeypatch.setattr("planfix_mcp.__main__.build_server", lambda **kw: stub)
    return stub


def test_main_stdio_default(monkeypatch) -> None:
    stub = _patch_server(monkeypatch)
    main([])
    assert len(stub.calls) == 1
    assert stub.calls[0] == {"transport": "stdio"}


def test_main_http_transport(monkeypatch) -> None:
    stub = _patch_server(monkeypatch)
    main(["--transport", "http", "--host", "127.0.0.1", "--port", "9876"])
    assert len(stub.calls) == 1
    assert stub.calls[0] == {"transport": "http", "host": "127.0.0.1", "port": 9876}


def test_main_passes_settings_overrides(monkeypatch) -> None:
    overrides: list[dict[str, object]] = []

    def fake_build(**kw: object) -> _StubServer:
        overrides.append(kw.get("settings_overrides", {}))
        return _StubServer()

    monkeypatch.setattr("planfix_mcp.__main__.build_server", fake_build)
    main(["--base-url", "https://e.example/rest", "--tags", "project", "--api-token", "x"])
    assert overrides[0]["base_url"] == "https://e.example/rest"
    assert overrides[0]["tags"] == "project"
    assert overrides[0]["api_token"] == "x"


def test_main_validate_output_flag(monkeypatch) -> None:
    overrides: list[dict[str, object]] = []

    def fake_build(**kw: object) -> _StubServer:
        overrides.append(kw.get("settings_overrides", {}))
        return _StubServer()

    monkeypatch.setattr("planfix_mcp.__main__.build_server", fake_build)
    main(["--no-validate-output"])
    assert overrides[0]["validate_output"] is False


def test_main_validate_output_absent_by_default(monkeypatch) -> None:
    overrides: list[dict[str, object]] = []

    def fake_build(**kw: object) -> _StubServer:
        overrides.append(kw.get("settings_overrides", {}))
        return _StubServer()

    monkeypatch.setattr("planfix_mcp.__main__.build_server", fake_build)
    main([])
    assert "validate_output" not in overrides[0]