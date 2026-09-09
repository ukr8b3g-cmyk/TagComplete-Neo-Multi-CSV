# Changelog

## 1.2.0

- Added optional **Danbooru Tag Cleaning Assist** for Forge / Forge Neo; default is OFF.
- Added a separate SQLite correction index so normal autocomplete never scans the 1.74M-row source Parquet.
- Added Settings controls for enable/disable, remove-heavy warnings, strong related-add hints, and sensitivity.
- Added an explicit database download/build action. It downloads `Grio43/Tag_cleaning`, uses extension-local DuckDB 1.4.1 only for index construction, then deletes the temporary Parquet source.
- Added batched local lookup and browser/Python caches so only currently displayed Danbooru candidates are checked.
- Added correction badges and related-add hints without changing prompt insertion text or the existing Fast Search result set.
- Kept correction semantics conservative: `remove` is not treated as a deprecated-tag signal, and co-occurring `add` tags are hints rather than automatic replacements.
- Added category-aware lookup to avoid general/artist/copyright/character/meta name collisions.
- Added unit coverage for normalization, sensitivity fallback, warning thresholds, related-add confidence, and category separation.

## 1.1.0

- Repaired stale package-layout expectations for the current default CSVs and split Python and JavaScript CI jobs.
- Hardened the opt-in Remote Update API with a default-disabled hidden option, public-destination checks, manual redirect validation, and a 256 MiB download limit.
- Aligned README and validation reports with cache v8, current automated results, hidden preset controls, and pending reForge revalidation.
- Reduced Fast Search v8 full index-build peak RAM from 763.04 MiB to 729.16 MiB (-33.88 MiB / -4.4%) by classifying counted and non-counted rows in one pass, removing the temporary Python set, and using a stable count-only sort.
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
- Maintained Forge Neo compatibility across the v1.1.0 changes.

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
