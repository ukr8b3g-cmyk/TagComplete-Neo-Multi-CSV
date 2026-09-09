import importlib.util
import sys
import types
from pathlib import Path


class _OptionInfo:
    def __init__(
        self,
        default=None,
        label="",
        component=None,
        component_args=None,
        section=None,
        refresh=None,
        **_kwargs,
    ):
        self.default = default
        self.label = label
        self.component = component
        self.component_args = component_args
        self.section = section
        self.refresh = refresh
        self.do_not_save = False

    def info(self, _text):
        return self


class _Options:
    def __init__(self):
        self.data_labels = {}
        self.data = {"tacjp_cleaningStatus": "Not installed"}

    def add_option(self, key, option):
        self.data_labels[key] = option
        if key not in self.data and not option.do_not_save:
            self.data[key] = option.default
        setattr(self, key, self.data.get(key, option.default))


class _FakeApp:
    def __init__(self):
        self.routes = {}

    def _register(self, method, path):
        def decorator(function):
            self.routes[(method, path)] = function
            return function

        return decorator

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)


class _BaseModel:
    pass


def _field(default=None, *, default_factory=None, **_kwargs):
    return default_factory() if default_factory is not None else default


def test_forge_loader_keeps_lookup_model_and_status_refresh_working(
    tmp_path: Path,
    monkeypatch,
):
    ui_callbacks = []
    app_callbacks = []
    script_callbacks = types.SimpleNamespace(
        on_ui_settings=ui_callbacks.append,
        on_app_started=app_callbacks.append,
    )
    opts = _Options()
    modules = types.ModuleType("modules")
    modules.script_callbacks = script_callbacks
    modules.shared = types.SimpleNamespace(OptionInfo=_OptionInfo, opts=opts)

    gradio = types.ModuleType("gradio")
    gradio.Blocks = type("Blocks", (), {})
    gradio.Dropdown = type("Dropdown", (), {})
    gradio.HTML = type("HTML", (), {})

    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = _FakeApp
    responses = types.ModuleType("fastapi.responses")
    responses.JSONResponse = lambda content: content

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

    path = Path(__file__).resolve().parents[1] / "scripts" / "zzzz_tag_cleaning.py"
    name = "_test_tag_cleaning_unregistered"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    assert name not in sys.modules
    spec.loader.exec_module(module)

    app = _FakeApp()
    app_callbacks[0](gradio.Blocks(), app)
    lookup = app.routes[("POST", "/tacjp/v1/cleaning/lookup")]
    assert lookup.__annotations__["body"] is module.CleaningLookupBody

    monkeypatch.setattr(
        module.CLEANING,
        "status",
        lambda: {
            "ready": True,
            "tag_count": 1,
            "pair_count": 1,
            "size_bytes": 1024,
            "metadata": {"built_at": "test"},
        },
    )
    ui_callbacks[0]()
    status = opts.data_labels["tacjp_cleaningStatus"]
    assert status.do_not_save is True
    assert "tacjp_cleaningStatus" not in opts.data
    assert status.component_args() == {}
    refreshed = status.refresh()
    assert refreshed.startswith("Ready")
    assert status.component_args() == {"value": refreshed}
    assert status.component_args() == {}
