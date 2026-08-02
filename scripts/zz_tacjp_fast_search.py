"""Forge integration for the persistent server-side Multi-CSV search engine."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import gradio as gr
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from modules import script_callbacks, shared
from pydantic import BaseModel, Field

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    from scripts.jp_assist_core import DataStore
    from scripts.shared_paths import TAGS_PATH
    from scripts.tacjp_fast_search_common import CACHE_VERSION
    from scripts.tacjp_fast_search import FastSearchStore, SearchRequest
except (ImportError, ModuleNotFoundError):
    from jp_assist_core import DataStore  # type: ignore
    from shared_paths import TAGS_PATH  # type: ignore
    from tacjp_fast_search_common import CACHE_VERSION  # type: ignore
    from tacjp_fast_search import FastSearchStore, SearchRequest  # type: ignore

FAST_DATA = DataStore(TAGS_PATH)
FAST_SEARCH = FastSearchStore(FAST_DATA)

try:
    import orjson
except ImportError:  # Forge variants without orjson remain supported.
    orjson = None


class FastSearchBody(BaseModel):
    query: str = Field(default="", max_length=512)
    tag_files: list[str] = Field(default_factory=list, max_items=64)
    translation_files: list[str] = Field(default_factory=list, max_items=64)
    prompt_mode: str = "Tag"
    candidate_sort_mode: str = "Count"
    context_natural: bool = False
    search_aliases: bool = True
    search_translations: bool = True
    substring_only: bool = False
    limit: int = Field(default=250, ge=1, le=2000)
    include_sources: bool = False


class FastSearchWarmupBody(BaseModel):
    tag_files: list[str] = Field(default_factory=list, max_items=64)
    translation_files: list[str] = Field(
        default_factory=list,
        max_items=64,
    )


def _json_response(payload, status_code: int = 200):
    if orjson is not None:
        return Response(
            content=orjson.dumps(payload),
            status_code=status_code,
            media_type="application/json",
        )
    return JSONResponse(payload, status_code=status_code)


def clear_fast_search_cache(*_args, **_kwargs):
    result = FAST_SEARCH.clear(disk=True)
    print(
        "[TagComplete Neo Multi-CSV] Cleared fast-search cache: "
        f"{result['memory_entries']} memory entries, "
        f"{result['disk_files']} files"
    )
    return result


def on_ui_settings():
    section = ("tac", "Tag Autocomplete / Multi-CSV")
    options = {
        "tacjp_searchEngine": shared.OptionInfo(
            "Server index",
            "Multi-CSV search engine",
            gr.Dropdown,
            lambda: {
                "choices": [
                    ("Server index — recommended", "Server index"),
                    ("Legacy browser index — compatibility", "Legacy browser"),
                ]
            },
        ).info(
            "Server index keeps compiled CSV data on the server and transfers "
            "only matching candidates."
        ),
        "tacjp_serverResultPool": shared.OptionInfo(
            250,
            "Server search candidate pool",
            gr.Slider,
            lambda: {"minimum": 20, "maximum": 1000, "step": 10},
        ).info(
            "Candidates returned before local frequency sorting. "
            "200–300 is recommended."
        ),
        "tacjp_persistentSearchCache": shared.OptionInfo(
            True,
            "Persist compiled Multi-CSV search indexes",
        ).info(
            "Reuses indexes after WebUI restart and rebuilds only when a "
            "selected CSV changes."
        ),
        "tacjp_searchMemoryEntries": shared.OptionInfo(
            4,
            "Compiled search configurations kept in memory",
            gr.Slider,
            lambda: {"minimum": 1, "maximum": 8, "step": 1},
        ),
        "tacjp_searchDiskEntries": shared.OptionInfo(
            8,
            "Compiled search configurations kept on disk",
            gr.Slider,
            lambda: {"minimum": 1, "maximum": 20, "step": 1},
        ),
        "tacjp_searchDebug": shared.OptionInfo(
            False,
            "Log Multi-CSV search timings",
        ),
    }
    for option in options.values():
        option.section = section
    for key, option in options.items():
        shared.opts.add_option(key, option)

    clear_option = shared.OptionInfo(
        "Clear compiled search cache",
        "Clear compiled Multi-CSV search cache",
        gr.HTML,
        {},
        refresh=clear_fast_search_cache,
        section=section,
    )
    shared.opts.add_option("tacjp_clearSearchCache", clear_option)


def api_fast_search(_: gr.Blocks, app: FastAPI):
    @app.post("/tacjp/v1/search")
    async def tacjp_fast_search(body: FastSearchBody):
        try:
            request = SearchRequest(
                query=body.query,
                tag_files=body.tag_files,
                translation_files=body.translation_files,
                prompt_mode=body.prompt_mode,
                candidate_sort_mode=body.candidate_sort_mode,
                context_natural=body.context_natural,
                search_aliases=body.search_aliases,
                search_translations=body.search_translations,
                substring_only=body.substring_only,
                limit=body.limit,
                include_sources=body.include_sources,
                persistent_cache=bool(
                    getattr(shared.opts, "tacjp_persistentSearchCache", True)
                ),
                memory_entries=int(
                    getattr(shared.opts, "tacjp_searchMemoryEntries", 4) or 4
                ),
                disk_entries=int(
                    getattr(shared.opts, "tacjp_searchDiskEntries", 8) or 8
                ),
            )
            result = await asyncio.to_thread(FAST_SEARCH.search, request)
            if getattr(shared.opts, "tacjp_searchDebug", False):
                print(
                    "[TagComplete Neo Multi-CSV] search "
                    f"cache={result.get('cache')} total={result.get('total')} "
                    f"count={result.get('count')} "
                    f"build={result.get('build_ms')}ms "
                    f"original_build={result.get('original_build_ms')}ms "
                    f"restore={result.get('restore_ms')}ms "
                    f"search_only={result.get('search_only_ms')}ms "
                    f"request={result.get('search_ms')}ms"
                )
            return _json_response(result)
        except (ValueError, FileNotFoundError) as exc:
            return _json_response(
                {"results": [], "count": 0, "error": str(exc)},
                400,
            )
        except Exception as exc:
            print(f"[TagComplete Neo Multi-CSV] Fast search failed: {exc}")
            return _json_response(
                {"results": [], "count": 0, "error": str(exc)},
                500,
            )

    @app.post("/tacjp/v1/search-warmup")
    async def tacjp_fast_search_warmup(body: FastSearchWarmupBody):
        try:
            result = await asyncio.to_thread(
                FAST_SEARCH.warmup,
                body.tag_files,
                body.translation_files,
                persistent=bool(
                    getattr(shared.opts, "tacjp_persistentSearchCache", True)
                ),
                memory_entries=int(
                    getattr(shared.opts, "tacjp_searchMemoryEntries", 4) or 4
                ),
                disk_entries=int(
                    getattr(shared.opts, "tacjp_searchDiskEntries", 8) or 8
                ),
            )
            if getattr(shared.opts, "tacjp_searchDebug", False):
                print(
                    "[TagComplete Neo Multi-CSV] warmup "
                    f"cache={result.get('cache')} total={result.get('total')} "
                    f"build={result.get('build_ms')}ms "
                    f"restore={result.get('restore_ms')}ms "
                    f"request={result.get('warmup_ms')}ms"
                )
            return _json_response(result)
        except (ValueError, FileNotFoundError) as exc:
            return _json_response(
                {"status": "error", "error": str(exc)},
                400,
            )
        except Exception as exc:
            print(f"[TagComplete Neo Multi-CSV] Warmup failed: {exc}")
            return _json_response(
                {"status": "error", "error": str(exc)},
                500,
            )

    @app.post("/tacjp/v1/search-cache/clear")
    async def tacjp_clear_fast_search_cache():
        return _json_response(FAST_SEARCH.clear(disk=True))

    @app.get("/tacjp/v1/search-cache/status")
    async def tacjp_fast_search_status():
        return _json_response(
            {
                "version": CACHE_VERSION,
                "memory_entries": len(FAST_SEARCH._memory),
                "file_entries": len(FAST_SEARCH._file_memory),
                "build_count": FAST_SEARCH.build_count,
                "disk_cache_available": FAST_SEARCH._disk_cache_available,
            }
        )


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_app_started(api_fast_search)
