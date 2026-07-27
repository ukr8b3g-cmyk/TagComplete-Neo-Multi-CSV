"""Public API for the persistent server-side Multi-CSV search engine."""

from __future__ import annotations

try:
    from scripts.tacjp_fast_search_files import FastSearchFilesMixin
    from scripts.tacjp_fast_search_index import FastSearchIndexMixin
    from scripts.tacjp_fast_search_common import DataStore, SearchRequest
    from scripts.tacjp_fast_search_query import FastSearchQueryMixin
except (ImportError, ModuleNotFoundError):
    from tacjp_fast_search_files import FastSearchFilesMixin  # type: ignore
    from tacjp_fast_search_index import FastSearchIndexMixin  # type: ignore
    from tacjp_fast_search_common import DataStore, SearchRequest  # type: ignore
    from tacjp_fast_search_query import FastSearchQueryMixin  # type: ignore


class FastSearchStore(
    FastSearchQueryMixin,
    FastSearchIndexMixin,
    FastSearchFilesMixin,
):
    """Compiled, persistent, single-flight indexes for CSV combinations."""

    def __init__(self, data_store: DataStore):
        FastSearchFilesMixin.__init__(self, data_store)


__all__ = ["FastSearchStore", "SearchRequest"]
