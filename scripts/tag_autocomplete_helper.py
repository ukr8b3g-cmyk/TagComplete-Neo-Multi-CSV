# This helper script scans folders for wildcards and embeddings and writes them
# to a temporary file to expose it to the javascript side

import glob
import importlib
import json
import sqlite3
import sys
import urllib.parse
import asyncio
from asyncio import sleep
from pathlib import Path

import requests

import gradio as gr
import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from modules import hashes, script_callbacks, sd_models, shared
from pydantic import BaseModel, Field

try:
    from scripts.jp_assist_core import (
        DEFAULT_REMOTE_URL,
        DEFAULT_UNDERSCORE_EXCLUSIONS,
        DataStore,
        PresetStore,
        RemoteUpdater,
        migrate_legacy_files,
    )
    from scripts.model_keyword_support import (
        get_lora_simple_hash,
        load_hash_cache,
        update_hash_cache,
        write_model_keyword_path,
    )
    from scripts.shared_paths import *
except (ModuleNotFoundError, ImportError):
    # Some Forge builds load extension scripts as standalone modules and resolve
    # ``scripts`` to the WebUI package. Add this extension's sibling directory.
    _HERE = Path(__file__).resolve().parent
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
    from jp_assist_core import (
        DEFAULT_REMOTE_URL,
        DEFAULT_UNDERSCORE_EXCLUSIONS,
        DataStore,
        PresetStore,
        RemoteUpdater,
        migrate_legacy_files,
    )
    from model_keyword_support import (
        get_lora_simple_hash,
        load_hash_cache,
        update_hash_cache,
        write_model_keyword_path,
    )
    from shared_paths import *


if not hasattr(gr.Dropdown, "get_component_class_id"):
    class MultiCSVDropdown(gr.Dropdown):
        """Keep Multi-CSV refresh compatible with older Gradio Dropdown.update."""

        def get_block_name(self):
            return "dropdown"

        @staticmethod
        def update(*args, **kwargs):
            kwargs.pop("multiselect", None)
            return gr.Dropdown.update(*args, **kwargs)
else:
    MultiCSVDropdown = gr.Dropdown


# Migrate older root-level data once, then keep all file types separated.
migrate_legacy_files(TAGS_PATH)
JP_DATA = DataStore(TAGS_PATH)
JP_PRESETS = PresetStore(JP_DATA)
JP_UPDATER = RemoteUpdater(JP_DATA)


try:
    try:
        from scripts import tag_frequency_db as tdb
    except ModuleNotFoundError:
        from inspect import currentframe, getframeinfo
        filename = getframeinfo(currentframe()).filename
        parent = Path(filename).resolve().parent
        sys.path.append(str(parent))
        import tag_frequency_db as tdb

    # Ensure the db dependency is reloaded on script reload
    importlib.reload(tdb)

    db = tdb.TagFrequencyDb()
    if int(db.version) != int(tdb.db_ver):
        raise ValueError("Database version mismatch")
except (ImportError, ValueError, sqlite3.Error) as e:
    print(f"[Tag Autocomplete Neo] Tag frequency database error: {e}")
    db = None

def get_embed_db(sd_model=None):
    """Return the active embedding database on Forge Neo or classic Forge."""
    try:
        forge_model = sd_model
        if forge_model is None:
            model_data = getattr(sd_models, "model_data", None)
            getter = getattr(model_data, "get_sd_model", None)
            forge_model = getter() if callable(getter) else getattr(shared, "sd_model", None)
        if forge_model is not None:
            engine = getattr(
                forge_model,
                "text_processing_engine",
                getattr(forge_model, "text_processing_engine_l", None),
            )
            database = getattr(engine, "embeddings", None) if engine is not None else None
            if database is not None:
                return database
    except Exception:
        pass

    # Forge classic / A1111 compatibility path. sd_hijack is intentionally
    # imported lazily because Forge Neo removed the module entirely.
    try:
        from modules import sd_hijack
        return getattr(getattr(sd_hijack, "model_hijack", None), "embedding_db", None)
    except Exception:
        return None

# Attempt to get embedding load function, using the same call as api.
try:
    embed_db = get_embed_db()
    if embed_db is not None:
        load_textual_inversion_embeddings = embed_db.load_textual_inversion_embeddings
    else:
        load_textual_inversion_embeddings = lambda *args, **kwargs: None
except Exception as e: # Not supported.
    load_textual_inversion_embeddings = lambda *args, **kwargs: None
    print("[Tag Autocomplete Neo] Cannot reload embeddings instantly:", e)

# Sorting functions for extra networks / embeddings stuff
sort_criteria = {
    "Name": lambda path, name, subpath: name.lower() if subpath else path.stem.lower(),
    "Date Modified (newest first)": lambda path, name, subpath: path.stat().st_mtime if path.exists() else name.lower(),
    "Date Modified (oldest first)": lambda path, name, subpath: path.stat().st_mtime if path.exists() else name.lower()
}

def sort_models(model_list, sort_method = None, name_has_subpath = False):
    """Sorts models according to the setting.
    
    Input: list of (full_path, display_name, {hash}) models. 
    Returns models in the format of name, sort key, meta.
    Meta is optional and can be a hash, version string or other required info.
    """
    if len(model_list) == 0:
        return model_list

    if sort_method is None:
        sort_method = getattr(shared.opts, "tac_modelSortOrder", "Name")

    # Get sorting method from dictionary
    sorter = sort_criteria.get(sort_method, sort_criteria["Name"])

    # During merging on the JS side we need to re-sort anyway, so here only the sort criteria are calculated.
    # The list itself doesn't need to get sorted at this point.
    if len(model_list[0]) > 2:
        results = [f'"{name}","{sorter(path, name, name_has_subpath)}",{meta}' for path, name, meta in model_list]
    else:
        results = [f'"{name}","{sorter(path, name, name_has_subpath)}"' for path, name in model_list]
    return results


def get_wildcards():
    """Returns a list of all wildcards. Works on nested folders."""
    wildcard_files = list(WILDCARD_PATH.rglob("*.txt"))
    resolved = [(w, w.relative_to(WILDCARD_PATH).as_posix())
                for w in wildcard_files
                if w.name != "put wildcards here.txt"
                and w.is_file()]
    return sort_models(resolved, name_has_subpath=True)


def get_ext_wildcards():
    """Returns a list of all extension wildcards. Works on nested folders."""
    wildcard_files = []
    excluded_folder_names = [
        value.strip()
        for value in (getattr(shared.opts, "tac_wildcardExclusionList", "") or "").split(",")
        if value.strip()
    ]
    for path in WILDCARD_EXT_PATHS:
        wildcard_files.append(path.as_posix())
        resolved = [(w, w.relative_to(path).as_posix())
                    for w in path.rglob("*.txt")
                    if w.name != "put wildcards here.txt"
                    and not any(excluded in w.parts for excluded in excluded_folder_names)
                    and w.is_file()]
        wildcard_files.extend(sort_models(resolved, name_has_subpath=True))
        wildcard_files.append("-----")

    return wildcard_files

def is_umi_format(data):
    """Returns True if the YAML file is in UMI format."""
    issue_found = False
    for item in data:
        try:
            if not (data[item] and 'Tags' in data[item] and isinstance(data[item]['Tags'], list)):
                issue_found = True
                break
        except:
            issue_found = True
            break
    return not issue_found

count = 0
def parse_umi_format(umi_tags, data):
    global count
    for item in data:
        umi_tags[count] = ','.join(data[item]['Tags'])
        count += 1


def parse_dynamic_prompt_format(yaml_wildcards, data, path):
    # Recurse subkeys, delete those without string lists as values
    def recurse_dict(d: dict):
        for key, value in d.copy().items():
            if isinstance(value, dict):
                recurse_dict(value)
            elif not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
                del d[key]

    try:
        recurse_dict(data)
        # Add to yaml_wildcards
        yaml_wildcards[path.name] = data
    except:
        return


def get_yaml_wildcards():
    """Returns a list of all tags found in extension YAML files found under a Tags: key."""
    global count
    count = 0
    yaml_files = []
    for path in WILDCARD_EXT_PATHS:
        yaml_files.extend(p for p in path.rglob("*.yml") if p.is_file())
        yaml_files.extend(p for p in path.rglob("*.yaml") if p.is_file())

    yaml_wildcards = {}

    umi_tags = {} # { tag: count }

    for path in yaml_files:
        try:
            with open(path, encoding="utf8") as file:
                data = yaml.safe_load(file)
                if (data):
                    if (is_umi_format(data)):
                        parse_umi_format(umi_tags, data)
                    else:
                        parse_dynamic_prompt_format(yaml_wildcards, data, path)
                else:
                    print('[Tag Autocomplete Neo] No data found in ' + path.name)
        except (yaml.YAMLError, UnicodeDecodeError, AttributeError, TypeError) as e:
            # YAML file not in wildcard format or couldn't be read
            print(f'[Tag Autocomplete Neo] Issue in parsing YAML file {path.name}: {e}')
            continue
        except Exception as e:
            # Something else went wrong, just skip
            continue

    # Sort by count
    umi_sorted = sorted(umi_tags.items(), key=lambda item: item[1], reverse=True)
    umi_output = []
    for tag, count in umi_sorted:
        umi_output.append(f"{tag},{count}")

    if (len(umi_output) > 0):
        write_to_temp_file('umi_tags.txt', umi_output)

    with open(TEMP_PATH.joinpath("wc_yaml.json"), "w", encoding="utf-8") as file:
        json.dump(yaml_wildcards, file, ensure_ascii=False)


def get_embeddings(sd_model):
    """Write a list of all embeddings with their version"""

    # Version constants
    V1_SHAPE = 768
    V2_SHAPE = 1024
    VXL_SHAPE = 2048
    emb_v1 = []
    emb_v2 = []
    emb_vXL = []
    emb_unknown = []
    results = []

    try:
        embed_db = get_embed_db(sd_model)
        # Re-register callback if needed
        global load_textual_inversion_embeddings
        if embed_db is not None and load_textual_inversion_embeddings != embed_db.load_textual_inversion_embeddings:
            load_textual_inversion_embeddings = embed_db.load_textual_inversion_embeddings
        
        loaded = embed_db.word_embeddings
        skipped = embed_db.skipped_embeddings

        # Add embeddings to the correct list
        for key, emb in (skipped | loaded).items():
            filename = getattr(emb, "filename", None)
            
            if filename is None:
                if emb.shape is None:
                    emb_unknown.append((Path(key), key, ""))
                elif emb.shape == V1_SHAPE:
                    emb_v1.append((Path(key), key, "v1"))
                elif emb.shape == V2_SHAPE:
                    emb_v2.append((Path(key), key, "v2"))
                elif emb.shape == VXL_SHAPE:
                    emb_vXL.append((Path(key), key, "vXL"))
                else:
                    emb_unknown.append((Path(key), key, ""))
            
            else:
                if emb.filename is None:
                    continue

                # Resolve symlinks and make the path absolute before calling
                # relative_to() — guards against #291 (relative/symlinked paths
                # that don't appear to be under EMB_PATH until resolved).
                emb_resolved = Path(emb.filename).resolve()
                emb_base = EMB_PATH.resolve()
                try:
                    rel = emb_resolved.relative_to(emb_base).as_posix()
                except ValueError:
                    # Path is genuinely outside EMB_PATH (e.g. symlink to
                    # another drive). Use just the filename as the display key.
                    rel = emb_resolved.name

                if emb.shape is None:
                    emb_unknown.append((emb_resolved, rel, ""))
                elif emb.shape == V1_SHAPE:
                    emb_v1.append((emb_resolved, rel, "v1"))
                elif emb.shape == V2_SHAPE:
                    emb_v2.append((emb_resolved, rel, "v2"))
                elif emb.shape == VXL_SHAPE:
                    emb_vXL.append((emb_resolved, rel, "vXL"))
                else:
                    emb_unknown.append((emb_resolved, rel, ""))

        results = sort_models(emb_v1) + sort_models(emb_v2) + sort_models(emb_vXL) + sort_models(emb_unknown)
    except AttributeError:
        print("[Tag Autocomplete Neo] Old webui version or unrecognized model shape, using fallback for embedding completion.")
        # Get a list of all embeddings in the folder
        all_embeds = [str(e.relative_to(EMB_PATH)) for e in EMB_PATH.rglob("*") if e.suffix in {".bin", ".pt", ".png",'.webp', '.jxl', '.avif'} and e.is_file()]
        # Remove files with a size of 0
        all_embeds = [e for e in all_embeds if EMB_PATH.joinpath(e).stat().st_size > 0]
        # Remove file extensions
        all_embeds = [e[:e.rfind('.')] for e in all_embeds]
        results = [e + "," for e in all_embeds]

    write_to_temp_file('emb.txt', results)

model_keyword_installed = write_model_keyword_path()


def _read_safetensors_alias(path: Path):
    """Read ss_output_name from a safetensors header without loading tensors.

    Returns the value as a string, or None if not present or on any error.
    Only reads the compact metadata header (first ~8 KB in practice), so it is fast.
    """
    try:
        import struct
        import json as _json
        with open(path, "rb") as f:
            raw = f.read(8)
            if len(raw) < 8:
                return None
            length = struct.unpack("<Q", raw)[0]
            header = _json.loads(f.read(length))
            value = header.get("__metadata__", {}).get("ss_output_name", None)
            return value if value else None
    except Exception:
        return None


# Try to import the built-in Lora module for alias resolution.
# When available, model.get_alias() respects the user's "lora_preferred_name"
# setting ("Alias from file" = ss_output_name, "Filename" = filename stem).
# We keep a reference to the module rather than overriding _get_lora/_get_lyco
# so that filesystem scanning always runs — lora.available_loras is empty until
# a model is first loaded (Forge Neo loads on demand), which would cause lora.txt
# to be written as empty on startup.
_lora_module = None
try:
    import sys
    from modules import extensions
    sys.path.append(Path(extensions.extensions_builtin_dir).joinpath("Lora").as_posix())
    import lora as _lora_module  # pyright: ignore [reportMissingImports]
except Exception:
    pass


def _build_alias_map(base_path: Path | None) -> dict:
    """Build an {absolute_path: alias} map from lora.available_loras.
    Returns an empty dict when the module is unavailable or no model has been
    loaded yet (available_loras is still empty at startup)."""
    if _lora_module is None or base_path is None:
        return {}
    try:
        return {
            Path(model.filename).absolute(): model.get_alias()
            for model in _lora_module.available_loras.values()
            if Path(model.filename).absolute().is_relative_to(base_path)
        }
    except Exception:
        return {}


def _get_lora():
    """Returns a list of (path, alias_or_None) tuples for all LoRA files.
    Always uses a filesystem scan so files appear even before a model is loaded.
    When lora.available_loras is populated the alias already respects the user's
    'lora_preferred_name' setting; otherwise None is returned and get_lora()
    resolves via safetensors header or filename stem."""
    if LORA_PATH is None or not LORA_PATH.exists():
        return []
    alias_map = _build_alias_map(LORA_PATH)
    lora_paths = [
        Path(l)
        for l in glob.glob(LORA_PATH.joinpath("**/*").as_posix(), recursive=True)
    ]
    valid_loras = [
        lf
        for lf in lora_paths
        if lf.suffix in {".safetensors", ".ckpt", ".pt"} and lf.is_file()
    ]
    return [(lf, alias_map.get(lf.absolute())) for lf in valid_loras]


def _get_lyco():
    """Returns a list of (path, alias_or_None) tuples for all LyCORIS files.
    Same strategy as _get_lora()."""
    if LYCO_PATH is None or not LYCO_PATH.exists():
        return []
    alias_map = _build_alias_map(LYCO_PATH)
    lyco_paths = [
        Path(ly)
        for ly in glob.glob(LYCO_PATH.joinpath("**/*").as_posix(), recursive=True)
    ]
    valid_lycos = [
        lyf
        for lyf in lyco_paths
        if lyf.suffix in {".safetensors", ".ckpt", ".pt"} and lyf.is_file()
    ]
    return [(lyf, alias_map.get(lyf.absolute())) for lyf in valid_lycos]


def is_visible(p: Path) -> bool:
    if getattr(shared.opts, "extra_networks_hidden_models", "When searched") != "Never":
        return True
    for part in p.parts:
        if part.startswith('.'):
            return False
    return True

def get_lora():
    """Write a list of all lora.

    Output format (CSV rows): "rel/path/name.ext","sort_key",hash,"alias"
    The alias column is what the frontend inserts into <lora:ALIAS:weight>.
    It mirrors the behaviour of Forge Neo's get_alias(): prefers ss_output_name
    unless the user has chosen "Filename" in the Extra Networks settings.
    """
    valid_loras = _get_lora()
    sort_method = getattr(shared.opts, "tac_modelSortOrder", "Name")
    sorter = sort_criteria.get(sort_method, sort_criteria["Name"])

    results = []
    for l, provided_alias in valid_loras:
        if not l.exists() or not l.is_file() or not is_visible(l):
            continue
        name = l.relative_to(LORA_PATH).as_posix()
        hash_val = get_lora_simple_hash(l) if model_keyword_installed else ""

        # Determine the alias to use for prompt insertion.
        # Priority:
        #   1. Value from lora.available_loras.get_alias() — already respects
        #      the "lora_preferred_name" setting ("Alias from file" / "Filename").
        #   2. ss_output_name from the safetensors header (fallback when the
        #      built-in lora module is not importable).
        #   3. Filename stem (last-resort fallback).
        if provided_alias is not None:
            alias = provided_alias
        elif l.suffix == ".safetensors":
            alias = _read_safetensors_alias(l) or l.stem
        else:
            alias = l.stem

        sort_key = sorter(l, name, True)
        results.append(f'"{name}","{sort_key}",{hash_val},"{alias}"')

    return results


def get_lyco():
    """Write a list of all LyCORIS/LOHA.

    Output format (CSV rows): "rel/path/name.ext","sort_key",hash,"alias"
    Same alias logic as get_lora().
    """
    valid_lycos = _get_lyco()
    sort_method = getattr(shared.opts, "tac_modelSortOrder", "Name")
    sorter = sort_criteria.get(sort_method, sort_criteria["Name"])

    results = []
    for ly, provided_alias in valid_lycos:
        if not ly.exists() or not ly.is_file() or not is_visible(ly):
            continue
        name = ly.relative_to(LYCO_PATH).as_posix()
        hash_val = get_lora_simple_hash(ly) if model_keyword_installed else ""

        if provided_alias is not None:
            alias = provided_alias
        elif ly.suffix == ".safetensors":
            alias = _read_safetensors_alias(ly) or ly.stem
        else:
            alias = ly.stem

        sort_key = sorter(ly, name, True)
        results.append(f'"{name}","{sort_key}",{hash_val},"{alias}"')

    return results

def get_style_names():
    try:
        style_names: list[str] = shared.prompt_styles.styles.keys()
        style_names = sorted(style_names, key=len, reverse=True)
        return style_names
    except Exception:
        return None

def write_tag_base_path():
    """Writes the tag base path to a fixed location temporary file"""
    with open(STATIC_TEMP_PATH.joinpath('tagAutocompletePath.txt'), 'w', encoding="utf-8") as f:
        f.write(TAGS_PATH.as_posix())


def write_to_temp_file(name, data):
    """Writes the given data to a temporary file"""
    with open(TEMP_PATH.joinpath(name), 'w', encoding="utf-8") as f:
        f.write(('\n'.join(data)))


tag_files = []
tag_files_withnone = []
translation_files = []
translation_files_withnone = []
json_files = []
json_files_withnone = []


def update_tag_files(*args, **kwargs):
    """Refresh separated tag and translation file choices."""
    global tag_files, tag_files_withnone, translation_files, translation_files_withnone
    JP_DATA.clear_cache()
    tag_files = [item.name for item in JP_DATA.list_tag_files()]
    translation_files = [item.name for item in JP_DATA.list_translation_files()]
    tag_files_withnone = ["None"] + tag_files
    translation_files_withnone = ["None"] + translation_files
    return {
        "tag_files": tag_files,
        "translation_files": translation_files,
    }


def update_json_files(*args, **kwargs):
    """Refresh chant JSON choices."""
    global json_files, json_files_withnone
    json_files = JP_DATA.list_chant_files()
    json_files_withnone = ["None"] + json_files
    return json_files


def _default_tag_selection():
    names = [item.name for item in JP_DATA.list_tag_files()]
    preferred = [
        name for name in ("danbooru_2025.csv", "natural_language_tags.csv")
        if name in names
    ]
    if preferred:
        return preferred
    return names[:1]


def _default_translation_selection():
    names = [item.name for item in JP_DATA.list_translation_files()]
    preferred = [
        name for name in ("merged_translations_dedup.csv", "natural_language_ja.csv")
        if name in names
    ]
    if preferred:
        return preferred
    return names[:1]


def _migrate_legacy_danbooru_selection():
    """Replace the retired small Danbooru filename without changing other choices."""

    selected = shared.opts.data.get("tacjp_tagFiles")
    if not isinstance(selected, list) or "danbooru_tags.csv" not in selected:
        return
    if not (JP_DATA.tag_dir / "danbooru_2025.csv").is_file():
        return
    migrated = []
    for name in selected:
        replacement = "danbooru_2025.csv" if name == "danbooru_tags.csv" else name
        if replacement not in migrated:
            migrated.append(replacement)
    shared.opts.data["tacjp_tagFiles"] = migrated
    try:
        shared.opts.save(shared.config_filename)
    except Exception:
        pass

# Write the tag base path to a fixed location temporary file
# to enable the javascript side to find our files regardless of extension folder name
if not STATIC_TEMP_PATH.exists():
    STATIC_TEMP_PATH.mkdir(exist_ok=True)

write_tag_base_path()
update_tag_files()
update_json_files()

# Check if the temp path exists and create it if not
if not TEMP_PATH.exists():
    TEMP_PATH.mkdir(parents=True, exist_ok=True)

# Set up files to ensure the script doesn't fail to load them
# even if no wildcards or embeddings are found
write_to_temp_file('wc.txt', [])
write_to_temp_file('wce.txt', [])
write_to_temp_file('wc_yaml.json', [])
write_to_temp_file('umi_tags.txt', [])
write_to_temp_file('hyp.txt', [])
write_to_temp_file('lora.txt', [])
write_to_temp_file('lyco.txt', [])
write_to_temp_file('styles.txt', [])
# Only reload embeddings if the file doesn't exist, since they are already re-written on model load
if not TEMP_PATH.joinpath("emb.txt").exists():
    write_to_temp_file('emb.txt', [])

# Write embeddings to emb.txt if found
if EMB_PATH.exists():
    # Get embeddings after the model loaded callback
    script_callbacks.on_model_loaded(get_embeddings)

def refresh_embeddings(force: bool, *args, **kwargs):
    try:
        embed_db = get_embed_db()
        if embed_db is None:
            return
        # Call directly through embed_db to avoid the stale global binding that is
        # set to a no-op lambda when no model is loaded at import time.
        # Also removed the "any embeddings loaded?" guard so newly-added embeddings
        # are discovered even when the folder was previously empty (#297).
        # Forge Neo removed the force_reload kwarg; older Forge accepts it.
        try:
            embed_db.load_textual_inversion_embeddings()
        except TypeError:
            embed_db.load_textual_inversion_embeddings(force_reload=force)
        get_embeddings(None)
    except Exception as e:
        print(f"[Tag Autocomplete Neo] Error refreshing embeddings: {e}")

def refresh_temp_files(*args, **kwargs):
    global WILDCARD_EXT_PATHS
    skip_wildcard_refresh = getattr(shared.opts, "tac_skipWildcardRefresh", False)
    if not skip_wildcard_refresh:
        WILDCARD_EXT_PATHS = find_ext_wildcard_paths()
    write_temp_files(skip_wildcard_refresh)
    force_embed_refresh = getattr(shared.opts, "tac_forceRefreshEmbeddings", False)
    refresh_embeddings(force=force_embed_refresh)

def write_style_names(*args, **kwargs):
    styles = get_style_names()
    if styles:
        write_to_temp_file('styles.txt', styles)

def write_temp_files(skip_wildcard_refresh = False):
    # Write wildcards to wc.txt if found
    if WILDCARD_PATH.exists() and not skip_wildcard_refresh:
        try:
            # Attempt to create a relative path, but fall back to an absolute path if not possible
            relative_wildcard_path = WILDCARD_PATH.relative_to(FILE_DIR).as_posix()
        except ValueError:
            # If the paths are not relative, use the absolute path
            relative_wildcard_path = WILDCARD_PATH.as_posix()

        wildcards = [relative_wildcard_path] + get_wildcards()
        if wildcards:
            write_to_temp_file('wc.txt', wildcards)

    # Write extension wildcards to wce.txt if found
    if WILDCARD_EXT_PATHS is not None and not skip_wildcard_refresh:
        wildcards_ext = get_ext_wildcards()
        if wildcards_ext:
            write_to_temp_file('wce.txt', wildcards_ext)
        # Write yaml extension wildcards to umi_tags.txt and wc_yaml.json if found
        get_yaml_wildcards()

    if model_keyword_installed:
        try:
            load_hash_cache()
        except Exception as e:
            print(f"[Tag Autocomplete Neo] Warning: could not load hash cache: {e}")

    lora_exists = LORA_PATH is not None and LORA_PATH.exists()
    if lora_exists:
        try:
            lora = get_lora()
            if lora:
                write_to_temp_file('lora.txt', lora)
        except Exception as e:
            print(f"[Tag Autocomplete Neo] Warning: could not write lora.txt: {e}")

    # Forge Neo unifies LyCORIS with LoRA. Classic Forge can expose a
    # dedicated directory, in which case keep the original lyco completion list.
    if (
        LYCO_PATH is not None
        and LYCO_PATH.exists()
        and (LORA_PATH is None or LYCO_PATH.resolve() != LORA_PATH.resolve())
    ):
        try:
            lyco = get_lyco()
            if lyco:
                write_to_temp_file('lyco.txt', lyco)
        except Exception as e:
            print(f"[TagComplete Neo Multi-CSV] Warning: could not write lyco.txt: {e}")

    if model_keyword_installed:
        try:
            update_hash_cache()
        except Exception as e:
            print(f"[Tag Autocomplete Neo] Warning: could not update hash cache: {e}")

    if shared.prompt_styles is not None:
        write_style_names()

write_temp_files()


def update_remote_from_settings(*args, **kwargs):
    url = getattr(shared.opts, "tacjp_remoteUrl", DEFAULT_REMOTE_URL)
    target = getattr(shared.opts, "tacjp_remoteTarget", "danbooru_tags.csv")
    result = JP_UPDATER.update(requests, url, target)
    update_tag_files()
    state = "updated" if result.get("updated") else "unchanged"
    if result.get("error"):
        state = f"failed: {result['error']}"
    print(f"[TagComplete Neo Multi-CSV] Remote CSV {state}")
    return result


# Register autocomplete options
def on_ui_settings():
    TAC_SECTION = ("tac", "Tag Autocomplete / Multi-CSV")
    _migrate_legacy_danbooru_selection()

    frequency_sort_functions = {
        "Logarithmic (weak)": "Will respect the base order and slightly prefer often used tags",
        "Logarithmic (strong)": "Same as Logarithmic (weak), but with a stronger bias",
        "Usage first": "Will list used tags by frequency before all others",
    }

    tac_options = {
        # JP Assist data sources. The legacy single-file keys remain hidden so
        # existing configurations can be migrated without breaking type checks.
        "tacjp_tagFiles": shared.OptionInfo(
            _default_tag_selection(),
            "Tag files (multiple selection)",
            MultiCSVDropdown,
            lambda: {"choices": tag_files, "multiselect": True},
            refresh=update_tag_files,
        ).info("Files under tags/tag_files. Selection order is source priority."),
        "tacjp_translationFiles": shared.OptionInfo(
            _default_translation_selection(),
            "Translation files (multiple selection)",
            MultiCSVDropdown,
            lambda: {"choices": translation_files, "multiselect": True},
            refresh=update_tag_files,
        ).info("Optional files under tags/translation_files. Leave empty when translations are not needed."),
        "tacjp_promptMode": shared.OptionInfo(
            "Tag", "Prompt mode", gr.Dropdown,
            lambda: {"choices": [
                ("Tag priority", "Tag"),
                ("Auto (Hybrid)", "Hybrid"),
                ("Natural language priority", "Natural Language"),
                ("Equal priority", "Custom"),
            ]},
        ),
        "tacjp_uiLanguage": shared.OptionInfo(
            "Auto", "Multi-CSV UI language", gr.Dropdown,
            lambda: {"choices": ["Auto", "English", "Japanese"], "visible": False},
        ),
        "tacjp_showTranslations": shared.OptionInfo(True, "Display translations in suggestions"),
        "tacjp_showSourceLabels": shared.OptionInfo(False, "Show source labels (TAG / NL / CUSTOM)"),
        "tacjp_colorNaturalLanguage": shared.OptionInfo(True, "Mark natural-language suggestions"),
        "tacjp_quickControls": shared.OptionInfo(
            False,
            "Show user preset controls near prompts",
            gr.Checkbox,
            lambda: {"visible": False},
        ).needs_restart(),
        "tacjp_activePreset": shared.OptionInfo("", "Active user preset", gr.Textbox, lambda: {"visible": False}),
        # Hidden compatibility values from the discontinued remote-update UI.
        "tacjp_autoUpdate": shared.OptionInfo(False, "Legacy remote update", gr.Checkbox, lambda: {"visible": False}),
        "tacjp_remoteUrl": shared.OptionInfo(DEFAULT_REMOTE_URL, "Legacy remote URL", gr.Textbox, lambda: {"visible": False}),
        "tacjp_remoteTarget": shared.OptionInfo("danbooru_2025.csv", "Legacy remote target", gr.Textbox, lambda: {"visible": False}),
        # Hidden legacy fallback values.
        "tac_tagFile": shared.OptionInfo("None", "Legacy single tag file", gr.Dropdown, lambda: {"choices": tag_files_withnone, "visible": False}),

        # Active in settings
        "tac_active": shared.OptionInfo(True, "Enable Tag Autocompletion"),
        "tac_activeIn.txt2img": shared.OptionInfo(True, "Active in txt2img").needs_restart(),
        "tac_activeIn.img2img": shared.OptionInfo(True, "Active in img2img").needs_restart(),
        "tac_activeIn.negativePrompts": shared.OptionInfo(True, "Active in negative prompts").needs_restart(),
        "tac_activeIn.thirdParty": shared.OptionInfo(True, "Active in third party textboxes").needs_restart(),
        "tac_activeIn.modelList": shared.OptionInfo("", "Black/Whitelist models").info("Model names [with file extension] or hashes, separated by commas"),
        "tac_activeIn.modelListMode": shared.OptionInfo("Blacklist", "Mode to use for model list", gr.Dropdown, lambda: {"choices": ["Blacklist", "Whitelist"]}),

        # Results
        "tac_slidingPopup": shared.OptionInfo(True, "Move completion popup together with text cursor"),
        "tac_maxResults": shared.OptionInfo(5, "Maximum results"),
        "tac_showAllResults": shared.OptionInfo(False, "Show all results"),
        "tac_resultStepLength": shared.OptionInfo(100, "How many results to load at once"),
        "tac_delayTime": shared.OptionInfo(100, "Time in ms to wait before triggering completion again").needs_restart(),
        "tac_useIndexedSearch": shared.OptionInfo(True, "Use indexed search (faster, recommended for slower PCs / mobile)"),
        "tac_useWildcards": shared.OptionInfo(True, "Search for wildcards"),
        "tac_sortWildcardResults": shared.OptionInfo(True, "Sort wildcard file contents alphabetically"),
        "tac_wildcardExclusionList": shared.OptionInfo("", "Wildcard folder exclusion list").needs_restart(),
        "tac_skipWildcardRefresh": shared.OptionInfo(False, "Don't re-scan wildcard files when refreshing extra networks"),
        "tac_useEmbeddings": shared.OptionInfo(True, "Search for embeddings"),
        "tac_forceRefreshEmbeddings": shared.OptionInfo(False, "Force refresh embeddings with extra networks refresh"),
        "tac_includeEmbeddingsInNormalResults": shared.OptionInfo(False, "Include embeddings in normal tag results"),
        "tac_useLoras": shared.OptionInfo(True, "Search for Loras"),
        "tac_useLycos": shared.OptionInfo(True, "Search for LyCORIS/LoHa"),
        "tac_useLoraPrefixForLycos": shared.OptionInfo(True, "Use the '<lora:' prefix instead of '<lyco:' for LyCORIS"),
        "tac_showWikiLinks": shared.OptionInfo(False, "Show '?' links to Danbooru/e621 wiki pages"),
        "tac_showExtraNetworkPreviews": shared.OptionInfo(True, "Show preview thumbnails for extra networks"),
        "tac_modelSortOrder": shared.OptionInfo("Name", "Model sort order", gr.Dropdown, lambda: {"choices": list(sort_criteria.keys())}),
        "tac_useStyleVars": shared.OptionInfo(False, "Search for WebUI style names"),

        # Frequency sorting
        "tac_frequencySort": shared.OptionInfo(True, "Locally record tag usage and sort frequent tags higher"),
        "tac_frequencyFunction": shared.OptionInfo("Logarithmic (weak)", "Frequency sorting function", gr.Dropdown, lambda: {"choices": list(frequency_sort_functions.keys())}),
        "tac_frequencyMinCount": shared.OptionInfo(3, "Minimum uses before frequency bias"),
        "tac_frequencyMaxAge": shared.OptionInfo(30, "Maximum age in days for frequency bias"),
        "tac_frequencyRecommendCap": shared.OptionInfo(10, "Maximum number of frequency recommendations"),
        "tac_frequencyIncludeAlias": shared.OptionInfo(False, "Frequency sorting matches aliases"),

        # Insertion
        "tac_replaceUnderscores": shared.OptionInfo(True, "Replace underscores with spaces on insertion"),
        "tac_undersocreReplacementExclusionList": shared.OptionInfo(
            ",".join(DEFAULT_UNDERSCORE_EXCLUSIONS),
            "Underscore replacement exclusion patterns",
            gr.Textbox,
            lambda: {"lines": 3},
        ).info("Comma/newline separated. Supports * and ?. Wildcard syntax such as __folder/name__ is always preserved."),
        "tac_escapeParentheses": shared.OptionInfo(True, "Escape parentheses on insertion"),
        "tac_appendComma": shared.OptionInfo(True, "Append comma on tag/phrase completion"),
        "tac_appendSpace": shared.OptionInfo(True, "Append space after separator"),
        "tac_alwaysSpaceAtEnd": shared.OptionInfo(True, "Always append space at the end of the prompt"),
        "tac_modelKeywordCompletion": shared.OptionInfo("Never", "Try to add known trigger words for LORA/LyCO models", gr.Dropdown, lambda: {"choices": ["Never", "Only user list", "Always"]}).needs_restart(),
        "tac_modelKeywordLocation": shared.OptionInfo("Start of prompt", "Where to insert LoRA/LyCO trigger words", gr.Dropdown, lambda: {"choices": ["Start of prompt", "End of prompt", "Before LORA/LyCO", "After LORA/LyCO"]}),
        "tac_modelKeywordCivitai": shared.OptionInfo(False, "Fetch trigger words from CivitAI when absent locally"),
        "tac_civitaiApiKey": shared.OptionInfo("", "CivitAI API key for trigger word lookups"),
        "tac_animaArtistPrefix": shared.OptionInfo(
            "Off",
            "Add '@' to artist tags",
            gr.Dropdown,
            lambda: {"choices": [
                ("Off — never add '@'", "Off"),
                ("On — always add '@'", "On"),
                ("Auto — only for detected ANIMA models", "Auto"),
            ]},
        ),
        "tac_wildcardCompletionMode": shared.OptionInfo("To next folder level", "How to complete nested wildcard paths", gr.Dropdown, lambda: {"choices": ["To next folder level", "To first difference", "Always fully"]}),

        # Aliases / translations
        "tac_alias.searchByAlias": shared.OptionInfo(True, "Search by alias"),
        "tac_alias.onlyShowAlias": shared.OptionInfo(False, "Only show alias"),
        "tac_translation.translationFile": shared.OptionInfo("None", "Legacy single translation file", gr.Dropdown, lambda: {"choices": translation_files_withnone, "visible": False}),
        "tac_translation.oldFormat": shared.OptionInfo(False, "Legacy translation file uses old 3-column format"),
        "tac_translation.searchByTranslation": shared.OptionInfo(True, "Search by translation"),
        "tac_translation.liveTranslation": shared.OptionInfo(False, "Show live translation below prompt").info("Experimental"),

        # Extra / chants
        "tac_extra.extraFile": shared.OptionInfo("extra-quality-tags.csv" if "extra-quality-tags.csv" in tag_files else "None", "Extra filename", gr.Dropdown, lambda: {"choices": tag_files_withnone}, refresh=update_tag_files),
        "tac_extra.addMode": shared.OptionInfo("Insert before", "Mode to add extra tags", gr.Dropdown, lambda: {"choices": ["Insert before", "Insert after"]}),
        "tac_chantFile": shared.OptionInfo("demo-chants.json" if "demo-chants.json" in json_files else "None", "Chant filename", gr.Dropdown, lambda: {"choices": json_files_withnone}, refresh=update_json_files),
    }

    # Add normal settings
    for key, opt in tac_options.items():
        opt.section = TAC_SECTION
        shared.opts.add_option(key, opt)

    # Settings that need special treatment
    # Custom mappings
    keymapDefault = """\
{
    "MoveUp": "ArrowUp",
    "MoveDown": "ArrowDown",
    "JumpUp": "PageUp",
    "JumpDown": "PageDown",
    "JumpToStart": "Home",
    "JumpToEnd": "End",
    "ChooseSelected": "Enter",
    "ChooseFirstOrSelected": "Tab",
    "Close": "Escape"
}\
"""
    colorDefault = """\
{
    "danbooru": {
        "-1": ["red", "maroon"],
        "0": ["lightblue", "dodgerblue"],
        "1": ["indianred", "firebrick"],
        "3": ["violet", "darkorchid"],
        "4": ["lightgreen", "darkgreen"],
        "5": ["orange", "darkorange"]
    },
    "e621": {
        "-1": ["red", "maroon"],
        "0": ["lightblue", "dodgerblue"],
        "1": ["gold", "goldenrod"],
        "3": ["violet", "darkorchid"],
        "4": ["lightgreen", "darkgreen"],
        "5": ["tomato", "darksalmon"],
        "6": ["red", "maroon"],
        "7": ["whitesmoke", "black"],
        "8": ["seagreen", "darkseagreen"]
    },
    "derpibooru": {
        "-1": ["red", "maroon"],
        "0": ["#60d160", "#3d9d3d"],
        "1": ["#fff956", "#918e2e"],
        "3": ["#fd9961", "#a14c2e"],
        "4": ["#cf5bbe", "#6c1e6c"],
        "5": ["#3c8ad9", "#1e5e93"],
        "6": ["#a6a6a6", "#555555"],
        "7": ["#47abc1", "#1f6c7c"],
        "8": ["#7871d0", "#392f7d"],
        "9": ["#df3647", "#8e1c2b"],
        "10": ["#c98f2b", "#7b470e"],
        "11": ["#e87ebe", "#a83583"]
    },
    "danbooru_e621_merged": {
        "-1": ["red", "maroon"],
        "0": ["lightblue", "dodgerblue"],
        "1": ["indianred", "firebrick"],
        "3": ["violet", "darkorchid"],
        "4": ["lightgreen", "darkgreen"],
        "5": ["orange", "darkorange"],
        "6": ["red", "maroon"],
        "7": ["lightblue", "dodgerblue"],
        "8": ["gold", "goldenrod"],
        "9": ["gold", "goldenrod"],
        "10": ["violet", "darkorchid"],
        "11": ["lightgreen", "darkgreen"],
        "12": ["tomato", "darksalmon"],
        "14": ["whitesmoke", "black"],
        "15": ["seagreen", "darkseagreen"]
    }
}\
"""
    keymapLabel = "Configure Hotkeys. For possible values, see https://www.w3.org/TR/uievents-key, or leave empty / set to 'None' to disable. Must be valid JSON."
    colorLabel = "Configure colors. See the Settings section in the README for more info. Must be valid JSON."

    try:
        shared.opts.add_option("tac_keymap", shared.OptionInfo(keymapDefault, keymapLabel, gr.Code, lambda: {"language": "json", "interactive": True}, section=TAC_SECTION))
        shared.opts.add_option("tac_colormap", shared.OptionInfo(colorDefault, colorLabel, gr.Code, lambda: {"language": "json", "interactive": True}, section=TAC_SECTION))
    except AttributeError:
        shared.opts.add_option("tac_keymap", shared.OptionInfo(keymapDefault, keymapLabel, gr.Textbox, section=TAC_SECTION))
        shared.opts.add_option("tac_colormap", shared.OptionInfo(colorDefault, colorLabel, gr.Textbox, section=TAC_SECTION))

    shared.opts.add_option("tac_refreshTempFiles", shared.OptionInfo("Refresh TAC temp files", "Refresh internal temp files", gr.HTML, {}, refresh=refresh_temp_files, section=TAC_SECTION))

script_callbacks.on_ui_settings(on_ui_settings)

def get_style_mtime():
    try:
        style_file = getattr(shared, "styles_filename", "styles.csv")
        # Check in case a list is returned
        if isinstance(style_file, list):
            style_file = style_file[0]
        
        style_file = Path(FILE_DIR).joinpath(style_file)
        if Path.exists(style_file):
            return style_file.stat().st_mtime
    except Exception:
        return None

last_style_mtime = get_style_mtime()


class JpMergeRequest(BaseModel):
    tag_files: list[str] = Field(default_factory=list)
    translation_files: list[str] = Field(default_factory=list)
    prompt_mode: str = "Tag"


class JpPresetSaveRequest(BaseModel):
    name: str
    settings: dict
    builtin_override: bool = False


class JpPresetApplyRequest(BaseModel):
    name: str


class JpOptionsApplyRequest(BaseModel):
    settings: dict
    active_preset: str = ""


class JpPresetImportRequest(BaseModel):
    data: dict
    replace: bool = False


class JpRemoteUpdateRequest(BaseModel):
    url: str | None = None
    target: str | None = None


class JpUiLanguageRequest(BaseModel):
    language: str = "Auto"


PRESET_OPTION_MAP = {
    "tag_files": "tacjp_tagFiles",
    "translation_files": "tacjp_translationFiles",
    "prompt_mode": "tacjp_promptMode",
    "search_translations": "tac_translation.searchByTranslation",
    "show_translations": "tacjp_showTranslations",
    "show_source_labels": "tacjp_showSourceLabels",
    "color_natural_language": "tacjp_colorNaturalLanguage",
    "replace_underscores": "tac_replaceUnderscores",
    "append_comma": "tac_appendComma",
    "append_space": "tac_appendSpace",
    "always_space_at_end": "tac_alwaysSpaceAtEnd",
    "underscore_exclusions": "tac_undersocreReplacementExclusionList",
    "anima_artist_prefix": "tac_animaArtistPrefix",
}


def _current_preset_settings():
    return {
        key: getattr(shared.opts, option, None)
        for key, option in PRESET_OPTION_MAP.items()
    }


def _runtime_safe_preset_settings(settings):
    """Validate preset values and drop file references absent on this machine."""

    validated = JP_PRESETS.validate_settings(settings)
    available_tags = {item.name for item in JP_DATA.list_tag_files()}
    available_translations = {item.name for item in JP_DATA.list_translation_files()}
    validated["tag_files"] = [name for name in validated["tag_files"] if name in available_tags]
    validated["translation_files"] = [
        name for name in validated["translation_files"] if name in available_translations
    ]
    return validated


def _apply_preset_settings(settings):
    applied = {}
    for key, option in PRESET_OPTION_MAP.items():
        if key not in settings:
            continue
        value = settings[key]
        try:
            if option in shared.opts.data_labels:
                try:
                    shared.opts.set(option, value, run_callbacks=False)
                except TypeError:
                    shared.opts.set(option, value)
            else:
                setattr(shared.opts, option, value)
            applied[option] = value
        except Exception as exc:
            print(f"[TagComplete Neo Multi-CSV] Could not set {option}: {exc}")
    try:
        shared.opts.save(shared.config_filename)
    except Exception as exc:
        print(f"[TagComplete Neo Multi-CSV] Could not save applied preset: {exc}")
    JP_DATA.clear_cache()
    return applied


def api_tac(_: gr.Blocks, app: FastAPI):
    def safe_lookup_name(filename: str | None) -> str:
        """Return a basename suitable for recursive model-sidecar lookup."""

        decoded = urllib.parse.unquote(str(filename or "")).replace("\\", "/")
        name = Path(decoded).name
        if not name or name in {".", ".."}:
            raise ValueError("Invalid file name")
        return name

    @app.get("/tacjp/v1/files")
    async def tacjp_files():
        update_tag_files()
        update_json_files()
        return JSONResponse({
            "tag_files": [item.to_dict() for item in JP_DATA.list_tag_files()],
            "translation_files": [item.to_dict() for item in JP_DATA.list_translation_files()],
            "chant_files": JP_DATA.list_chant_files(),
        })

    @app.post("/tacjp/v1/merged-tags")
    async def tacjp_merged_tags(body: JpMergeRequest):
        try:
            rows = await asyncio.to_thread(
                JP_DATA.merge,
                body.tag_files,
                body.translation_files,
                prompt_mode=body.prompt_mode,
            )
            return JSONResponse({"rows": rows, "count": len(rows)})
        except (ValueError, FileNotFoundError) as exc:
            return JSONResponse({"rows": [], "count": 0, "error": str(exc)}, status_code=400)
        except Exception as exc:
            print(f"[TagComplete Neo Multi-CSV] Merge failed: {exc}")
            return JSONResponse({"rows": [], "count": 0, "error": str(exc)}, status_code=500)

    @app.get("/tacjp/v1/presets")
    async def tacjp_presets():
        return JSONResponse({**JP_PRESETS.list(), "active": getattr(shared.opts, "tacjp_activePreset", "")})

    @app.post("/tacjp/v1/ui-language")
    async def tacjp_ui_language(body: JpUiLanguageRequest):
        language = body.language if body.language in {"Auto", "English", "Japanese"} else "Auto"
        try:
            shared.opts.set("tacjp_uiLanguage", language, run_callbacks=False)
        except TypeError:
            shared.opts.set("tacjp_uiLanguage", language)
        shared.opts.save(shared.config_filename)
        return JSONResponse({"language": language})

    @app.get("/tacjp/v1/presets/export")
    async def tacjp_export_presets():
        return JSONResponse(JP_PRESETS.export(), headers={"Content-Disposition": "attachment; filename=tagcomplete-jp-presets.json"})

    @app.post("/tacjp/v1/presets/save")
    async def tacjp_save_preset(body: JpPresetSaveRequest):
        try:
            saved = JP_PRESETS.save(body.name, body.settings, builtin_override=body.builtin_override)
            return JSONResponse({"name": body.name, "settings": saved, "presets": JP_PRESETS.list()})
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.delete("/tacjp/v1/presets/{name:path}")
    async def tacjp_delete_preset(name: str):
        deleted = JP_PRESETS.delete(name)
        if deleted and getattr(shared.opts, "tacjp_activePreset", "") == name:
            shared.opts.data["tacjp_activePreset"] = ""
            shared.opts.save(shared.config_filename)
        return JSONResponse({"deleted": deleted, "presets": JP_PRESETS.list()})

    @app.post("/tacjp/v1/presets/restore-builtins")
    async def tacjp_restore_builtins():
        JP_PRESETS.restore_builtins()
        return JSONResponse(JP_PRESETS.list())

    @app.post("/tacjp/v1/presets/import")
    async def tacjp_import_presets(body: JpPresetImportRequest):
        try:
            return JSONResponse(JP_PRESETS.import_data(body.data, replace=body.replace))
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @app.post("/tacjp/v1/presets/apply")
    async def tacjp_apply_preset(body: JpPresetApplyRequest):
        settings = JP_PRESETS.get(body.name)
        if settings is None:
            return JSONResponse({"error": f"Preset not found: {body.name}"}, status_code=404)
        runtime_settings = _runtime_safe_preset_settings(settings)
        applied = _apply_preset_settings(runtime_settings)
        try:
            shared.opts.data["tacjp_activePreset"] = body.name
            shared.opts.save(shared.config_filename)
        except Exception:
            pass
        return JSONResponse({"name": body.name, "settings": runtime_settings, "applied": applied})

    @app.post("/tacjp/v1/options/apply")
    async def tacjp_apply_options(body: JpOptionsApplyRequest):
        validated = _runtime_safe_preset_settings(body.settings)
        applied = _apply_preset_settings(validated)
        try:
            shared.opts.data["tacjp_activePreset"] = body.active_preset
            shared.opts.save(shared.config_filename)
        except Exception:
            pass
        return JSONResponse({"settings": validated, "applied": applied, "active": body.active_preset})

    @app.get("/tacjp/v1/current-settings")
    async def tacjp_current_settings():
        return JSONResponse(_current_preset_settings())

    @app.get("/tacjp/v1/update-status")
    async def tacjp_update_status():
        return JSONResponse(JP_UPDATER.load_meta())

    @app.post("/tacjp/v1/update")
    async def tacjp_update(body: JpRemoteUpdateRequest):
        url = body.url or getattr(shared.opts, "tacjp_remoteUrl", DEFAULT_REMOTE_URL)
        target = body.target or getattr(shared.opts, "tacjp_remoteTarget", "danbooru_tags.csv")
        try:
            result = await asyncio.to_thread(JP_UPDATER.update, requests, url, target)
            update_tag_files()
            return JSONResponse(result, status_code=200 if not result.get("error") else 502)
        except ValueError as exc:
            return JSONResponse({"updated": False, "error": str(exc)}, status_code=400)

    async def get_json_info(base_path: Path, filename: str = None):
        if base_path is None or (not base_path.exists()):
            return Response(status_code=404)

        try:
            lookup = safe_lookup_name(filename)
            json_candidates = glob.glob(base_path.as_posix() + f"/**/{glob.escape(lookup)}.json", recursive=True)
            if json_candidates is not None and len(json_candidates) > 0 and Path(json_candidates[0]).is_file():
                return FileResponse(json_candidates[0])
            return Response(status_code=404)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    async def get_preview_thumbnail(base_path: Path, filename: str = None, blob: bool = False):
        if base_path is None or (not base_path.exists()):
            return Response(status_code=404)

        try:
            lookup = safe_lookup_name(filename)
            img_glob = glob.glob(base_path.as_posix() + f"/**/{glob.escape(lookup)}.*", recursive=True)
            img_candidates = [img for img in img_glob if Path(img).suffix in [".png", ".jpg", ".jpeg", ".webp", ".gif"] and Path(img).is_file()]
            if img_candidates is not None and len(img_candidates) > 0:
                if blob:
                    return FileResponse(img_candidates[0])
                else:
                    return JSONResponse({"url": urllib.parse.quote(img_candidates[0])})
            return Response(status_code=404)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.post("/tacapi/v1/refresh-temp-files")
    async def api_refresh_temp_files():
        await sleep(0) # might help with refresh blocking gradio
        refresh_temp_files()

    @app.post("/tacapi/v1/refresh-embeddings")
    async def api_refresh_embeddings():
        refresh_embeddings(force=False)

    @app.get("/tacapi/v1/lora-info/{lora_name}")
    async def get_lora_info(lora_name):
        return await get_json_info(LORA_PATH, lora_name)

    @app.get("/tacapi/v1/lyco-info/{lyco_name}")
    async def get_lyco_info(lyco_name):
        return await get_json_info(LYCO_PATH, lyco_name)

    @app.get("/tacapi/v1/civitai-trigger-words/{lora_name}")
    async def get_civitai_trigger_words(lora_name: str):
        """Look up trigger words for a LoRA from CivitAI by-hash API.

        Priority:
          1. Return cached result from .json sidecar if sha256 matches.
          2. Call CivitAI GET /api/v1/model-versions/by-hash/{sha256}.
          3. Save trainedWords to .json sidecar for future cache hits.
        """
        if LORA_PATH is None or not LORA_PATH.exists():
            return Response(status_code=404)

        # Locate the LoRA file
        try:
            lookup = safe_lookup_name(lora_name)
        except ValueError:
            return Response(status_code=400)
        path_glob = glob.glob(
            LORA_PATH.as_posix() + f"/**/{glob.escape(lookup)}.*", recursive=True
        )
        paths = [
            p for p in path_glob
            if Path(p).suffix in {".safetensors", ".ckpt", ".pt"} and Path(p).is_file()
        ]
        if not paths:
            return Response(status_code=404)

        lora_path = Path(paths[0])
        json_path = lora_path.with_suffix(".json")

        # Compute SHA256 (uses Forge's cache, fast on repeat calls)
        sha256 = hashes.sha256_from_cache(
            str(lora_path), f"lora/{lora_name}", lora_path.suffix == ".safetensors"
        )
        if not sha256:
            return Response(status_code=404)

        sha256_upper = sha256.upper()

        # Check sidecar cache
        sidecar: dict = {}
        if json_path.is_file():
            try:
                sidecar = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                sidecar = {}

        if (
            sidecar.get("civitai_sha256", "").upper() == sha256_upper
            and "civitai_trained_words" in sidecar
        ):
            return JSONResponse({"trainedWords": sidecar["civitai_trained_words"]})

        # Fetch from CivitAI
        api_key = getattr(shared.opts, "tac_civitaiApiKey", "").strip()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.get(
                f"https://civitai.com/api/v1/model-versions/by-hash/{sha256_upper}",
                headers=headers,
                timeout=(10, 20),
            )
            if response.status_code != 200:
                return Response(status_code=response.status_code)
            data = response.json()
            if "error" in data:
                return Response(status_code=404)

            trained_words = data.get("trainedWords", [])
            trained_str = ", ".join(trained_words) if trained_words else ""

            # Persist to sidecar
            sidecar["civitai_sha256"] = sha256_upper
            sidecar["civitai_trained_words"] = trained_str
            try:
                json_path.write_text(
                    json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception as e:
                print(f"[Tag Autocomplete Neo] Could not save civitai trigger words to sidecar: {e}")

            return JSONResponse({"trainedWords": trained_str})
        except Exception as e:
            print(f"[Tag Autocomplete Neo] CivitAI trigger word lookup failed: {e}")
            return Response(status_code=500)

    checkpoint_basemodel_cache_path = TEMP_PATH.joinpath("known_checkpoint_basemodels.json")

    def load_checkpoint_basemodel_cache():
        if not checkpoint_basemodel_cache_path.is_file():
            return {}
        try:
            return json.loads(checkpoint_basemodel_cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_checkpoint_basemodel_cache(cache: dict):
        try:
            checkpoint_basemodel_cache_path.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            print(f"[Tag Autocomplete Neo] Could not save checkpoint base model cache: {e}")

    @app.get("/tacapi/v1/civitai-checkpoint-basemodel/{sha256}")
    async def get_civitai_checkpoint_basemodel(sha256: str):
        """Look up a checkpoint's CivitAI base model family by hash.

        Used to detect ANIMA-based checkpoints (and other base model families) so
        the frontend can adjust tag insertion behavior (e.g. '@' artist prefix).

        Priority:
          1. Return cached result from the local JSON cache if the hash is known.
          2. Call CivitAI GET /api/v1/model-versions/by-hash/{sha256}.
          3. Save the baseModel field to the cache for future cache hits.
        """
        sha256_upper = sha256.upper()
        cache = load_checkpoint_basemodel_cache()

        if sha256_upper in cache:
            return JSONResponse({"baseModel": cache[sha256_upper]})

        api_key = getattr(shared.opts, "tac_civitaiApiKey", "").strip()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.get(
                f"https://civitai.com/api/v1/model-versions/by-hash/{sha256_upper}",
                headers=headers,
                timeout=(10, 20),
            )
            if response.status_code != 200:
                return Response(status_code=response.status_code)
            data = response.json()
            if "error" in data:
                return Response(status_code=404)

            base_model = data.get("baseModel", "")

            cache[sha256_upper] = base_model
            save_checkpoint_basemodel_cache(cache)

            return JSONResponse({"baseModel": base_model})
        except Exception as e:
            print(f"[Tag Autocomplete Neo] CivitAI checkpoint base model lookup failed: {e}")
            return Response(status_code=500)

    @app.get("/tacapi/v1/lora-cached-hash/{lora_name}")
    async def get_lora_cached_hash(lora_name: str):
        if LORA_PATH is None or not LORA_PATH.exists():
            return Response(status_code=404)
        try:
            lookup = safe_lookup_name(lora_name)
        except ValueError:
            return Response(status_code=400)
        path_glob = glob.glob(LORA_PATH.as_posix() + f"/**/{glob.escape(lookup)}.*", recursive=True)
        paths = [lora for lora in path_glob if Path(lora).suffix in [".safetensors", ".ckpt", ".pt"] and Path(lora).is_file()]
        if paths is not None and len(paths) > 0:
            path = paths[0]
            hash = hashes.sha256_from_cache(path, f"lora/{lora_name}", path.endswith(".safetensors"))
            if hash is not None:
                return hash
        
        return None

    def get_path_for_type(type):
        if type == "lora":
            return LORA_PATH
        elif type == "lyco":
            return LYCO_PATH
        elif type == "embedding":
            return EMB_PATH
        else:
            return None

    @app.get("/tacapi/v1/thumb-preview/{filename}")
    async def get_thumb_preview(filename, type):
        return await get_preview_thumbnail(get_path_for_type(type), filename, False)

    @app.get("/tacapi/v1/thumb-preview-blob/{filename}")
    async def get_thumb_preview_blob(filename, type):
        return await get_preview_thumbnail(get_path_for_type(type), filename, True)

    @app.get("/tacapi/v1/wildcard-contents")
    async def get_wildcard_contents(basepath: str, filename: str):
        if not basepath or not filename:
            return Response(status_code=404)

        try:
            base = Path(basepath).expanduser().resolve()
            if not base.is_dir():
                return Response(status_code=404)
            wildcard_path = (base / filename).resolve()
            try:
                wildcard_path.relative_to(base)
            except ValueError:
                return Response(status_code=403)
            if wildcard_path.is_file():
                return FileResponse(wildcard_path)
            return Response(status_code=404)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.get("/tacapi/v1/refresh-styles-if-changed")
    async def refresh_styles_if_changed():
        global last_style_mtime
        
        mtime = get_style_mtime()
        if mtime is not None and mtime > last_style_mtime:
            last_style_mtime = mtime
            # Update temp file
            if shared.prompt_styles is not None:
                write_style_names()
            
            return Response(status_code=200) # Success
        else:
            return Response(status_code=304) # Not modified
    def db_request(func, get = False):
        if db is not None:
            try:
                if get:
                    ret = func()
                    if isinstance(ret, list):
                        ret = [{"name": t[0], "type": t[1], "count": t[2], "lastUseDate": t[3]} for t in ret]
                    return JSONResponse({"result": ret})
                else:
                    func()
            except sqlite3.Error as e:
                return JSONResponse({"error": e.__cause__}, status_code=500)
        else:
            return JSONResponse({"error": "Database not initialized"}, status_code=500)

    @app.post("/tacapi/v1/increase-use-count")
    async def increase_use_count(tagname: str, ttype: int, neg: bool):
        db_request(lambda: db.increase_tag_count(tagname, ttype, neg))

    @app.get("/tacapi/v1/get-use-count")
    async def get_use_count(tagname: str, ttype: int, neg: bool):
        return db_request(lambda: db.get_tag_count(tagname, ttype, neg), get=True)
    
    # Small dataholder class
    class UseCountListRequest(BaseModel):
        tagNames: list[str]
        tagTypes: list[int]
        neg: bool = False

    # Semantically weird to use post here, but it's required for the body on js side
    @app.post("/tacapi/v1/get-use-count-list")
    async def get_use_count_list(body: UseCountListRequest):
        # If a date limit is set > 0, pass it to the db
        date_limit = getattr(shared.opts, "tac_frequencyMaxAge", 30)
        date_limit = date_limit if date_limit > 0 else None

        if db:
            count_list = list(db.get_tag_counts(body.tagNames, body.tagTypes, body.neg, date_limit))
        else:
            count_list = None
    
        # If a limit is set, return at max the top n results by count
        if count_list and len(count_list):
            limit = int(min(getattr(shared.opts, "tac_frequencyRecommendCap", 10), len(count_list)))
            # Sort by count and return the top n
            if limit > 0:
                count_list = sorted(count_list, key=lambda x: x[2], reverse=True)[:limit]

        return db_request(lambda: count_list, get=True)

    @app.put("/tacapi/v1/reset-use-count")
    async def reset_use_count(tagname: str, ttype: int, pos: bool, neg: bool):
        db_request(lambda: db.reset_tag_count(tagname, ttype, pos, neg))

    @app.get("/tacapi/v1/get-all-use-counts")
    async def get_all_tag_counts():
        return db_request(lambda: db.get_all_tags(), get=True)

script_callbacks.on_app_started(api_tac)
