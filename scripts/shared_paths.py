"""Cross-compatible path discovery for Forge and Forge Neo."""

from __future__ import annotations

from pathlib import Path

from modules import scripts, shared

try:
    from modules.paths import extensions_dir, script_path
except ImportError:  # pragma: no cover - legacy fallback
    from modules.paths_internal import extensions_dir, script_path


FILE_DIR = Path(script_path).absolute()
EXT_PATH = Path(extensions_dir).absolute()
TAGS_PATH = Path(scripts.basedir()).joinpath("tags").absolute()
TAG_FILES_PATH = TAGS_PATH.joinpath("tag_files")
TRANSLATION_FILES_PATH = TAGS_PATH.joinpath("translation_files")
CHANTS_PATH = TAGS_PATH.joinpath("chants")
CONFIG_PATH = TAGS_PATH.joinpath("config")
CACHE_PATH = TAGS_PATH.joinpath("cache")


def _path_from_options(*names: str) -> Path | None:
    for owner in (getattr(shared, "cmd_opts", None), getattr(shared, "opts", None)):
        if owner is None:
            continue
        for name in names:
            try:
                value = getattr(owner, name, None)
            except Exception:
                value = None
            if value:
                return Path(value).expanduser().absolute()
    return None


def _models_fallback(folder: str) -> Path:
    try:
        from modules.paths import models_path
        return Path(models_path).joinpath(folder).absolute()
    except Exception:
        return FILE_DIR.joinpath("models", folder).absolute()


EMB_PATH = _path_from_options("embeddings_dir") or _models_fallback("embeddings")
LORA_PATH = _path_from_options("lora_dir") or _models_fallback("Lora")

# Forge Neo unifies LyCORIS with LoRA. Older Forge installations may expose a
# dedicated directory; use it when available without requiring the extension.
LYCO_PATH = _path_from_options("lyco_dir", "lycoris_dir") or LORA_PATH
HYP_PATH = _path_from_options("hypernetwork_dir", "hypernetworks_dir")

WILDCARD_PATH = _path_from_options("wildcard_dir") or FILE_DIR.joinpath("scripts", "wildcards").absolute()


def find_ext_wildcard_paths() -> list[Path]:
    """Return unique wildcard folders exposed by installed extensions."""

    found: list[Path] = []
    candidates = list(EXT_PATH.glob("*/wildcards/"))
    dynamic = _path_from_options("wildcard_dir")
    if dynamic is not None:
        candidates.append(dynamic)

    seen: set[str] = set()
    for candidate in candidates:
        path = Path(candidate).expanduser().absolute()
        key = str(path).casefold()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        found.append(path)
    return found


WILDCARD_EXT_PATHS = find_ext_wildcard_paths()

STATIC_TEMP_PATH = FILE_DIR.joinpath("tmp").absolute()
TEMP_PATH = TAGS_PATH.joinpath("temp").absolute()

for directory in (
    TAGS_PATH,
    TAG_FILES_PATH,
    TRANSLATION_FILES_PATH,
    CHANTS_PATH,
    CONFIG_PATH,
    CACHE_PATH,
    TEMP_PATH,
    STATIC_TEMP_PATH,
):
    directory.mkdir(parents=True, exist_ok=True)
