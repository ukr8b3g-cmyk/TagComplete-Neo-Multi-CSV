# Changelog

## Unreleased

- Made `Count first` the default candidate sort mode and display valid `count=0` values.
- Added v8 compiled indexes with ASCII trigram and count-ranked lookup paths.
- Warm the selected Server index after startup and retain single-flight construction.
- Preserve a trailing underscore in tag searches, so `v_` does not match `very_...`.
- Changed new-install tag defaults to `tags_merged_dedup.csv` plus `natural_language_tags.csv`.
- Added a persistent server-side search engine for large Multi-CSV configurations.
- Replaced the full merged JSON transfer with small per-query candidate responses.
- Added per-file parsed caches and compiled combination caches that survive WebUI restarts.
- Added automatic cache invalidation when a selected CSV size or modification time changes.
- Added single-flight index construction so concurrent first queries share one build.
- Added compact ASCII prefix indexes and Unicode 1–3 gram indexes for translated search.
- Added settings for search engine selection, result pool size, memory/disk cache limits, timing logs, and cache clearing.
- Added automatic fallback to the legacy browser index if server search is unavailable.
- Kept the legacy browser index for compatibility and for experimental full-prompt live translation.

## 1.0.0

- Forked TagComplete Neo while preserving its autocomplete providers and UI.
- Added separated `tag_files`, `translation_files`, and `chants` directories.
- Added multiple tag/translation CSV selection and server-side deduplicated merge.
- Added translated search/display controls and natural-language source metadata.
- Added Tag, Hybrid, Natural Language, and Custom prompt modes.
- Added built-in and user presets with JSON export/import backup.
- Added optional collapsed quick controls near txt2img/img2img prompts.
- Added glob-style underscore exclusions and protected Dynamic Prompts syntax.
- Added conditional atomic remote CSV update with local fallback.
- Added Forge / Forge Neo path and embedding API compatibility fallbacks.
