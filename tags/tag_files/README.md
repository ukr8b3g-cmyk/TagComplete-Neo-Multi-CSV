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
- `natural_language_tags.csv` (selected by default)
- `e621.csv`
- `anima_artists.csv`
- `anima_characters.csv`

The e621 and Anima files are bundled but not selected by default.
`danbooru_2025.csv` and `e621.csv` are sourced from sd-webui-tagcomplete-neo.
