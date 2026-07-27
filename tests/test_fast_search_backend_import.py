from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


class _FieldValue:
    def __init__(self, default=None, default_factory=None):
        self.default = default
        self.default_factory = default_factory


class _BaseModel:
    def __init__(self, **values):
        for name in getattr(type(self), "__annotations__", {}):
            if name in values:
                value = values[name]
            else:
                declared = getattr(type(self), name, None)
                if isinstance(declared, _FieldValue):
                    value = (
                        declared.default_factory()
                        if declared.default_factory is not None
                        else declared.default
                    )
                else:
                    value = declared
            setattr(self, name, value)


def _field(default=None, *, default_factory=None, **_kwargs):
    return _FieldValue(default=default, default_factory=default_factory)


class _OptionInfo:
    def __init__(
        self,
        default=None,
        label="",
        component=None,
        component_args=None,
        onchange=None,
        section=None,
        refresh=None,
        **_kwargs,
    ):
        self.default = default
        self.label = label
        self.component = component
        self.component_args = component_args
        self.onchange = onchange
        self.section = section
        self.refresh = refresh

    def info(self, _text):
        return self


class _Options:
    def __init__(self):
        self.data_labels = {}

    def add_option(self, key, option):
        self.data_labels[key] = option
        setattr(self, key, option.default)


class _Response:
    def __init__(self, content=None, status_code=200, media_type=None, **_kwargs):
        self.content = content
        self.status_code = status_code
        self.media_type = media_type


class _JSONResponse(_Response):
    pass


class _FakeApp:
    def __init__(self):
        self.routes = {}

    def _register(self, method, path):
        def decorator(function):
            self.routes[(method, path)] = function
            return function

        return decorator

    def post(self, path):
        return self._register("POST", path)

    def get(self, path):
        return self._register("GET", path)


def test_fast_search_backend_registers_settings_and_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    ui_callbacks = []
    app_callbacks = []
    script_callbacks = types.SimpleNamespace(
        on_ui_settings=ui_callbacks.append,
        on_app_started=app_callbacks.append,
    )
    opts = _Options()
    shared = types.SimpleNamespace(OptionInfo=_OptionInfo, opts=opts)
    modules = types.ModuleType("modules")
    modules.script_callbacks = script_callbacks
    modules.shared = shared

    gradio = types.ModuleType("gradio")
    gradio.Blocks = type("Blocks", (), {})
    gradio.Dropdown = type("Dropdown", (), {})
    gradio.Slider = type("Slider", (), {})
    gradio.HTML = type("HTML", (), {})

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = _FakeApp
    responses = types.ModuleType("fastapi.responses")
    responses.JSONResponse = _JSONResponse
    responses.Response = _Response

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = _BaseModel
    pydantic.Field = _field

    shared_paths = types.ModuleType("scripts.shared_paths")
    shared_paths.TAGS_PATH = tmp_path / "tags"

    monkeypatch.setitem(sys.modules, "modules", modules)
    monkeypatch.setitem(sys.modules, "gradio", gradio)
    monkeypatch.setitem(sys.modules, "fastapi", fastapi)
    monkeypatch.setitem(sys.modules, "fastapi.responses", responses)
    monkeypatch.setitem(sys.modules, "pydantic", pydantic)
    monkeypatch.setitem(sys.modules, "scripts.shared_paths", shared_paths)

    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "zz_tacjp_fast_search.py"
    name = "_test_tacjp_fast_search_backend"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)

    assert len(ui_callbacks) == 1
    assert len(app_callbacks) == 1

    ui_callbacks[0]()
    for key in (
        "tacjp_searchEngine",
        "tacjp_serverResultPool",
        "tacjp_persistentSearchCache",
        "tacjp_searchMemoryEntries",
        "tacjp_searchDiskEntries",
        "tacjp_searchDebug",
        "tacjp_clearSearchCache",
    ):
        assert key in opts.data_labels

    app = _FakeApp()
    app_callbacks[0](gradio.Blocks(), app)
    assert ("POST", "/tacjp/v1/search") in app.routes
    assert ("POST", "/tacjp/v1/search-cache/clear") in app.routes
    assert ("GET", "/tacjp/v1/search-cache/status") in app.routes

    body = module.FastSearchBody(query="long", tag_files=[])
    response = asyncio.run(app.routes[("POST", "/tacjp/v1/search")](body))
    assert response.status_code == 200
