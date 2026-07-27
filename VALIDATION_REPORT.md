# TagComplete Neo Multi-CSV Validation Report

**Document status:** Publication candidate<br>
**Implementation under test:** `da4a361`<br>
**Validation date:** 2026-07-28<br>
**Verified environment:** Forge Neo `neo 2.27` / Python 3.13.12 / Gradio 4.40.0

[日本語版](VALIDATION_REPORT_JP.md)

## 1. Purpose

This document records the final, publishable validation results for
TagComplete Neo Multi-CSV.

Early startup failures, temporary implementations, and rejected experimental
values are excluded. The report covers only the confirmed results from the
later validation phase:

- Multi-CSV search and suggestion display
- Persistent disk cache and memory cache
- Input response and client rendering
- Version 6 cache-format performance
- Japanese and English UI
- Advanced-setting accordions and refresh buttons
- Automated tests and offline package verification

## 2. Evidence classification

| Classification | Meaning |
|---|---|
| Measured | Timing values collected in a live Forge Neo environment |
| Runtime verified | Display, interaction, or DOM state checked in Forge Neo |
| Automated | Reproducible with Python or JavaScript tests |
| Unverified | Compatibility is not currently guaranteed |

Performance values are reference measurements from one environment. They are
not hardware-independent guarantees and can vary with CPU, storage, browser,
other extensions, and the selected CSV set.

## 3. Runtime test conditions

### 3.1 Forge Neo software environment

The following software values were displayed by the current Forge Neo runtime:

| Component | Version or configuration |
|---|---|
| Forge Neo version | `neo 2.27` |
| Host | Windows 64-bit (`AMD64`) |
| Python | `3.13.12` |
| Python compiler | `MSC v.1944 64 bit (AMD64)` |
| PyTorch | `2.11.0+cu130` |
| CUDA allocator | `cudaMallocAsync` |
| Async weight offloading | Enabled, `2` streams |
| Flash Attention | Enabled (`2.8.3+cu130torch2.11`) |
| Gradio | `4.40.0` |

Performance-related launch flags:

```text
--pin-shared-memory --cuda-malloc --cuda-stream --disable-sage
```

Local model paths and unrelated extension errors are excluded because they are
not required to reproduce the Multi-CSV validation.

### 3.2 Performance-test hardware

The measured timing values in this report were collected on:

| Component | Hardware |
|---|---|
| CPU | AMD Ryzen 9 3900X |
| GPU | NVIDIA GeForce RTX 5060 Ti 16 GB |
| System memory | 64 GB |

This hardware record is the basis for the reference performance values.

### 3.3 Selected data

![English Multi-CSV file selection and prompt-mode controls](assets/validation/en-multicsv-controls.png)

*Multi-CSV file selection, translation selection, prompt mode, and suggestion display controls.*

Tag CSVs:

- `danbooru_2025.csv`
- `natural_language_tags.csv`

Translation CSVs:

- `merged_translations_dedup.csv`
- `natural_language_ja.csv`

`anima_artists.csv`, `anima_characters.csv`, and `e621.csv` are bundled, but
were not selected for this performance comparison.

### 3.4 Input conditions

- Normal query: `school`
- High-result query: `bag`
- Suggestion recovery after deletion: Backspace
- Cache states: `build`, `disk`, and `memory`
- Rendering comparison: 20, 50, and 100 suggestions

### 3.5 Adopted settings

![English server search and cache settings](assets/validation/en-search-settings.png)

*The CSV+ advanced accordion contains server search, candidate-pool, cache, and timing controls.*

| Setting | Adopted value |
|---|---|
| Multi-CSV search engine | `Server index — recommended` |
| Server search candidate pool | `250` |
| Persist compiled Multi-CSV search indexes | Enabled |
| Compiled search configurations kept in memory | `4` |
| Compiled search configurations kept on disk | `8` |
| Log Multi-CSV search timings | Normally disabled |
| Normal-input debounce | `50 ms` |

## 4. Performance results

### 4.1 Version 6 cache format

The `prefix_index` and `unicode_gram_index` structures were changed to
contiguous `keys + offsets + values` arrays.

| Test ID | Item | Before | v6 | Result |
|---|---|---:|---:|---|
| PERF-01 | Disk-cache restore | 873.55 ms | 380.54 ms | 56.4% faster |
| PERF-02 | First suggestion UI after restart | 1.052 s | 609 ms | Pass |
| PERF-03 | Memory-cache API | — | 9.03 ms | Pass |
| PERF-04 | Memory-cache suggestion UI | — | 176.4 ms | Practical pass |
| PERF-05 | Search-only time | — | About 7–10 ms | Not the bottleneck |
| PERF-06 | Cache size | Baseline | About 9.3% smaller | Pass |
| PERF-07 | First index build | — | About 10.24 s | Conditional pass |

PERF-07 occurs only on the first use of a selected CSV configuration. The
persistent disk cache is reused afterward, so startup preloading of all CSV
files was not adopted.

### 4.2 Client response

- A memory-cached API request took about 9 ms; search execution was not the
  primary source of UI latency.
- Normal input keeps the 50 ms debounce.
- Forge Neo main-thread contention sometimes delayed timer execution by about
  30–40 ms.
- A 25 ms debounce was rejected because it increased aborted requests without
  enough latency improvement.
- Comparisons with 20, 50, and 100 suggestions showed that TagComplete
  suggestion DOM creation was not the main source of delay.
- Backspace keeps immediate search behavior to restore suggestions quickly.

Result: input response passed for practical use. The production debounce
remains 50 ms.

## 5. Functional validation

### 5.1 Insertion and exclusion controls

![English insertion and exclusion controls](assets/validation/en-insertion-controls.png)

*The restore-exclusions action is marked as CSV+, while the established
TagComplete insertion controls remain available.*

### 5.2 Artist-prefix control

![English artist-prefix control](assets/validation/en-artist-prefix.png)

*Artist tags can remain unchanged, always receive `@`, or receive it only for
detected Anima models.*

### 5.3 Functional results

| Test ID | Test | Expected result | Result |
|---|---|---|---|
| FUNC-01 | Select multiple tag CSVs | Merge sources using selection order as priority | Pass |
| FUNC-02 | Select multiple translation CSVs | Merge translations and aliases into tags | Pass |
| FUNC-03 | Duplicate tag merge | Display one suggestion for the same tag | Pass |
| FUNC-04 | `cache=build` | Build an index on the first search | Pass |
| FUNC-05 | `cache=memory` | Reuse the built index in the same session | Pass |
| FUNC-06 | `cache=disk` | Restore the persistent index after Forge Neo restart | Pass |
| FUNC-07 | CSV modification | Invalidate cache when the file signature changes | Pass |
| FUNC-08 | Concurrent first requests | Share one index build for the same configuration | Pass |
| FUNC-09 | `school` query | Display suggestions normally | Pass |
| FUNC-10 | `bag` query | Continue searching under a high-result condition | Pass |
| FUNC-11 | Backspace recovery | Refresh suggestions immediately after deletion | Pass |
| FUNC-12 | Legacy fallback | Enter compatibility mode when the Server API is unavailable | Pass |
| FUNC-13 | Extra providers | Preserve existing LoRA and related provider paths | Automated pass |
| FUNC-14 | Wildcard protection | Preserve `__folder/name__` syntax | Pass |
| FUNC-15 | Underscore exclusions | Apply glob-style exclusion patterns | Pass |

## 6. Runtime UI validation

| Test ID | Check | Result |
|---|---|---|
| UI-01 | Display Multi-CSV settings in Japanese when Japanese is selected | Pass |
| UI-02 | Display standard TagComplete Neo settings in Japanese | Pass |
| UI-03 | Restore standard labels and help text when English is selected | Pass |
| UI-04 | Switch the restore-exclusions button between Japanese and English | Pass |
| UI-05 | Place the CSV+ badge immediately after the setting name | Pass |
| UI-06 | Do not display the obsolete SHARED information banner | Pass |
| UI-07 | Place CORE advanced settings in a separate closed accordion | Pass |
| UI-08 | Place CSV+ search settings in a separate closed accordion | Pass |
| UI-09 | Keep only Hotkeys, Colors, and internal refresh in CORE | Pass |
| UI-10 | Keep search, pool, cache, and timing controls in CSV+ | Pass |
| UI-11 | Keep Extra and Chant refresh buttons beside their fields | Pass |
| UI-12 | Preserve advanced-accordion state across language changes | Pass |

## 7. Automated validation

Pre-publication validation on 2026-07-28:

| Check | Count or result |
|---|---|
| JavaScript Node test runner | 3 passed |
| Python pytest | 32 passed |
| Python syntax checks | Passed |
| JavaScript syntax checks | Passed |
| `tools/verify_extension.py` | PASS |
| `git diff --check` | No issues |

Example commands:

```powershell
node --check javascript/zz_jpAssistUI.js
node --check javascript/zzzz_tacjp_fast_search.js
node --test tests/*.js
pytest tests -q -p no:cacheprovider
python tools/verify_extension.py
git diff --check
```

Primary automated coverage:

- CSV parsing and duplicate merging
- Translation and alias merging
- Version 6 cache save and restore
- Empty indexes, missing keys, and large candidate sets
- Cache signatures and automatic invalidation
- Forge Neo loader compatibility
- Server API registration and Legacy fallback
- AbortController and latest-request priority
- Client timing logs
- Wildcard and underscore protection
- Distribution file layout

## 8. Adopted specification

The validation results define the following current behavior:

1. Large CSV files are not fully parsed at startup. Index construction begins
   on the first normal tag query.
2. The complete search index remains in Python; only the candidate pool is
   returned to the browser.
3. The persistent cache format is version 6. Older formats are ignored and
   invalidated automatically instead of being deleted.
4. Rebuilding occurs only when the selected CSV configuration or file
   signature changes.
5. Normal-input debounce remains 50 ms, while Backspace keeps immediate
   suggestion updates.
6. Timing logs are normally disabled and enabled only for diagnostics.
7. Existing TagComplete Neo providers retain their established processing
   paths.
8. Advanced settings are divided into CORE and CSV+ sections, both closed by
   default.
9. Japanese display mode translates both Multi-CSV and standard TagComplete
   Neo setting labels.
10. The unfinished user-preset UI is hidden in the current version.

## 9. Unverified and out of scope

| Item | Status |
|---|---|
| Forge Neo | Runtime verified |
| Stable Diffusion WebUI Forge | Unverified |
| reForge | Unverified |
| Comparison with every other extension disabled | Not performed |
| Hardware-by-hardware performance comparison | Not performed |
| User-preset UI | Planned for a later version |
| Generated-image quality | Outside this extension's validation scope |

A Pass in this report applies only to the documented environment and test
scope. It does not guarantee compatibility with unverified environments.
