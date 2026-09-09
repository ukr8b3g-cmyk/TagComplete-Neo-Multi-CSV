"""Forge/Forge Neo integration for the optional Danbooru Tag Cleaning Assist."""

import asyncio
import sys
from pathlib import Path

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from modules import script_callbacks, shared
from pydantic import BaseModel, Field

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from scripts.shared_paths import TAGS_PATH
    from scripts.tag_cleaning_db import SENSITIVITY_PRESETS, TagCleaningStore
except (ImportError, ModuleNotFoundError):
    from shared_paths import TAGS_PATH  # type: ignore
    from tag_cleaning_db import SENSITIVITY_PRESETS, TagCleaningStore  # type: ignore

CLEANING_ROOT = Path(TAGS_PATH) / "cleaning"
CLEANING = TagCleaningStore(CLEANING_ROOT)
_STATUS_REFRESH_VALUE: str | None = None


class CleaningLookupItem(BaseModel):
    tag: str = Field(default="", max_length=256)
    category: int | None = None


class CleaningLookupBody(BaseModel):
    items: list[CleaningLookupItem] = Field(default_factory=list, max_items=250)


def _database_status_text() -> str:
    status = CLEANING.status()
    if not status.get("ready"):
        error = status.get("error")
        return "Not installed" + (f" — {error}" if error else "")
    metadata = status.get("metadata", {})
    built_at = metadata.get("built_at", "unknown")
    size_mib = float(status.get("size_bytes", 0)) / (1024 * 1024)
    return (
        f"Ready — {status.get('tag_count', 0):,} tag records, "
        f"{status.get('pair_count', 0):,} related-pair records, "
        f"{size_mib:.1f} MiB, built {built_at}"
    )


def update_cleaning_database():
    print("[TagComplete Neo Multi-CSV] Updating Danbooru Tag Cleaning database...")
    try:
        status = CLEANING.update_from_remote()
        text = (
            _database_status_text()
            if status.get("ready")
            else str(status.get("error") or "Update failed")
        )
        print(f"[TagComplete Neo Multi-CSV] Tag Cleaning database: {text}")
        return text
    except Exception as exc:
        print(f"[TagComplete Neo Multi-CSV] Tag Cleaning update failed: {exc}")
        return f"Update failed — {exc}"


def refresh_cleaning_status():
    global _STATUS_REFRESH_VALUE
    _STATUS_REFRESH_VALUE = _database_status_text()
    return _STATUS_REFRESH_VALUE


def cleaning_status_component_args():
    """Pass the refreshed value through Forge Neo's component-args callback."""
    global _STATUS_REFRESH_VALUE
    if _STATUS_REFRESH_VALUE is None:
        return {}
    value = _STATUS_REFRESH_VALUE
    _STATUS_REFRESH_VALUE = None
    return {"value": value}


def on_ui_settings():
    section = ("tac", "Tag Autocomplete / Multi-CSV")
    options = {
        "tacjp_cleaningEnabled": shared.OptionInfo(
            False,
            "Forge Neo — Enable Danbooru Tag Cleaning Assist",
        ).info(
            "Default OFF. Adds correction-data indicators after normal TagComplete results; "
            "it does not replace tags automatically."
        ),
        "tacjp_cleaningShowWarnings": shared.OptionInfo(
            True,
            "Tag Cleaning — Show remove-heavy warnings",
        ).info(
            "Means the tag is frequently removed by this correction dataset. "
            "It does NOT mean the Danbooru tag is deprecated."
        ),
        "tacjp_cleaningShowSuggestions": shared.OptionInfo(
            True,
            "Tag Cleaning — Show strong related add suggestions",
        ).info(
            "Shows tags that were frequently added in the same correction rows. "
            "These are hints, not automatic replacements."
        ),
        "tacjp_cleaningSensitivity": shared.OptionInfo(
            "Balanced",
            "Tag Cleaning — Sensitivity",
            gr.Dropdown,
            lambda: {"choices": list(SENSITIVITY_PRESETS.keys())},
        ).info("Conservative reduces indicators; Broad shows weaker correction signals."),
    }
    for option in options.values():
        option.section = section
    for key, option in options.items():
        shared.opts.add_option(key, option)

    status_option = shared.OptionInfo(
        _database_status_text(),
        "Tag Cleaning database status",
        gr.HTML,
        cleaning_status_component_args,
        refresh=refresh_cleaning_status,
        section=section,
    )
    status_option.do_not_save = True
    shared.opts.data.pop("tacjp_cleaningStatus", None)
    shared.opts.add_option("tacjp_cleaningStatus", status_option)
    shared.opts.add_option(
        "tacjp_cleaningUpdate",
        shared.OptionInfo(
            "Download / build Tag Cleaning database",
            "Tag Cleaning database update",
            gr.HTML,
            {},
            refresh=update_cleaning_database,
            section=section,
        ).info(
            "Explicit action only. Downloads the Hugging Face Parquet source, installs "
            "DuckDB into tags/cleaning/_vendor if needed, builds SQLite, then deletes "
            "the temporary Parquet file."
        ),
    )


def api_tag_cleaning(_: gr.Blocks, app: FastAPI):
    @app.get("/tacjp/v1/cleaning/status")
    async def tag_cleaning_status():
        return JSONResponse(
            {
                "enabled": bool(getattr(shared.opts, "tacjp_cleaningEnabled", False)),
                **CLEANING.status(),
            }
        )

    @app.post("/tacjp/v1/cleaning/lookup")
    async def tag_cleaning_lookup(body: CleaningLookupBody):
        if not getattr(shared.opts, "tacjp_cleaningEnabled", False):
            return JSONResponse(
                {"enabled": False, "ready": False, "database_id": "", "results": []}
            )
        sensitivity = str(
            getattr(shared.opts, "tacjp_cleaningSensitivity", "Balanced") or "Balanced"
        )
        payload = [item.dict() for item in body.items]
        result = await asyncio.to_thread(
            CLEANING.lookup,
            payload,
            show_warnings=bool(
                getattr(shared.opts, "tacjp_cleaningShowWarnings", True)
            ),
            show_suggestions=bool(
                getattr(shared.opts, "tacjp_cleaningShowSuggestions", True)
            ),
            sensitivity=sensitivity,
        )
        return JSONResponse({"enabled": True, **result})


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_app_started(api_tag_cleaning)
