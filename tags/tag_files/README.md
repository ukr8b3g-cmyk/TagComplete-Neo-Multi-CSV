# Tag files

Place tag or natural-language CSV files in this folder. Subfolders are supported.

Supported headers include:

```csv
tag,category,count,aliases,translation,source_type,insert_mode,category_scheme
```

Only `tag` is required. Headerless TagComplete-compatible rows such as
`tag,category,count,aliases` are also supported.

Bundled files:

- `danbooru_2025.csv` (selected by default)
- `anima_artists.csv`
- `anima_characters.csv`
- `natural_language_tags.csv`

The optional Anima and natural-language files are not selected by default.
