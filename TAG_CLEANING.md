# Danbooru Tag Cleaning Assist — v1.2.0

Tag Cleaning Assist is an **optional Forge / Forge Neo feature** for `TagComplete Neo Multi-CSV`.
It uses the public Hugging Face dataset `Grio43/Tag_cleaning` as a correction signal after normal autocomplete results have already been found.

## Safety and semantics

The source dataset is an **image-level correction manifest**. `remove` means a tag was removed from an image during that cleaning process; it does **not** mean the Danbooru tag itself is deprecated. Likewise, a tag in `add` is not automatically a replacement.

For that reason v1.2.0:

- never rewrites prompt text automatically;
- never marks a tag as "deprecated" from this dataset alone;
- shows a warning only when the correction data is strongly remove-heavy;
- labels high-confidence remove/add co-occurrence as **Related adds**, not replacements.

## Settings

Open **Settings > Tag Autocomplete / Multi-CSV**.

- **Forge Neo — Enable Danbooru Tag Cleaning Assist** — default `OFF`.
- **Tag Cleaning — Show remove-heavy warnings** — default `ON`.
- **Tag Cleaning — Show strong related add suggestions** — default `ON`.
- **Tag Cleaning — Sensitivity** — `Conservative / Balanced / Broad`, default `Balanced`.
- **Tag Cleaning database status** — shows local index state.
- **Tag Cleaning database update** — explicit download/build action.

When the feature is OFF, the SQLite database is not queried and the existing autocomplete path is unchanged.

## Database and performance

Normal lookup uses Python's built-in `sqlite3` only. The 1.74M-row Parquet source is **not read during autocomplete**.

The explicit update action:

1. downloads `merged_2026.parquet` from `Grio43/Tag_cleaning`;
2. installs DuckDB 1.4.1 into `tags/cleaning/_vendor` only if DuckDB is unavailable;
3. aggregates tag-level add/remove counts and strong remove/add co-occurrence into `tags/cleaning/tag_cleaning.sqlite3`;
4. deletes the temporary Parquet file.

Autocomplete sends only the currently displayed Danbooru candidates to the local lookup endpoint, and results are cached in both the Python lookup layer and browser session.

## Data source

- Dataset: `Grio43/Tag_cleaning`
- Format: Parquet
- License reported by the dataset: Apache-2.0
- Published schema: `image_id`, `add`, `remove`, `updated_at`
- Dataset card states that corrections were normalized against a Danbooru metadata snapshot dated 2026-08-30.
