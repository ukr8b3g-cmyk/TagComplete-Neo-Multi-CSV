# TagComplete Neo Multi-CSV Validation Report

**Document status:** Current-main alignment; partial live runtime smoke completed<br>
**Current main baseline:** `dba853e40a86585018ade9388fda90611cef6873`<br>
**Working-tree scope:** Phase A-D changes based on that commit; not committed<br>
**Automated validation date:** 2026-09-02<br>
**Historical live environment:** Forge Neo `neo 2.27` / Python 3.13.12 / Gradio 4.40.0 (`da4a361`, 2026-07-28)

[日本語版](VALIDATION_REPORT_JP.md)

## 1. Purpose

This document aligns the current-main specification and automated results for
TagComplete Neo Multi-CSV. It also preserves earlier live Forge Neo evidence as
historical evidence, clearly separated from current-main validation.

Current-main validation covers cache format v8 and the Phase A-D working tree.
Live UI and performance results in sections 3–6 were collected on `da4a361`.
The current-baseline Phase D measurements and Final Release Gate smoke results
are recorded separately in section 7.

- Multi-CSV search and suggestion display
- Persistent disk cache and memory cache
- Input response and client rendering
- Historical version 6 cache-format performance
- Japanese and English UI
- Advanced-setting accordions and refresh buttons
- Automated tests and offline package verification

## 2. Evidence classification

| Classification | Meaning |
|---|---|
| Measured | Timing values collected in a live Forge Neo environment |
| Runtime verified | Display, interaction, or DOM state checked in Forge Neo |
| Automated | Reproducible with Python or JavaScript tests |
| Local measured | Peak memory collected locally with Python `tracemalloc` |
| Historical | Evidence collected on an earlier commit; not a current-main Pass |
| Unverified | Compatibility is not currently guaranteed |

Performance values are reference measurements from one environment. They are
not hardware-independent guarantees and can vary with CPU, storage, browser,
other extensions, and the selected CSV set.

## 3. Historical runtime test conditions

Sections 3–6 describe the 2026-07-28 Forge Neo run on `da4a361`. They are
retained for reference and must not be interpreted as current-main runtime or
cache-v8 measurements.

### 3.1 Forge Neo software environment

The following software values were displayed by the historical Forge Neo runtime:

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

## 4. Historical performance results

### 4.1 Historical version 6 cache format

All values in this section were measured on `da4a361` with cache format v6.
The current implementation uses cache format v8. Phase D peak-memory values
are reported separately in section 7.2, so the historical v6 values below are
not relabelled or reused as v8 results.

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

### 4.2 Historical client response

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

## 5. Historical functional validation

The Pass labels in this section record the historical `da4a361` Forge Neo run.
Current-main evidence is recorded separately in section 7.

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

## 6. Historical runtime UI validation

The Pass labels below are historical. The complete matrix was not repeated on
the current baseline; the current Final Release Gate smoke subset is in
section 7.4.

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

## 7. Current-main validation

### 7.1 Automated gate

Local current-main gate on 2026-09-02 (Python 3.13.12 / Node.js 25.2.1):

| Check | Count or result |
|---|---|
| JavaScript Node test runner | 3 passed |
| Python pytest | 58 passed |
| Python syntax checks | Passed |
| JavaScript syntax checks | 23 files passed |
| `tools/verify_extension.py` | PASS |
| `git diff --check` | No issues |
| GitHub Actions | Not run; no commit or push was performed |

Example commands:

```powershell
python -m pytest -q
python -m compileall -q scripts tests
for file in tests/test_*.js; do node "$file"; done
for file in javascript/*.js tests/*.js; do node --check "$file"; done
python tools/verify_extension.py
git diff --check
```

Primary automated coverage:

- CSV parsing and duplicate merging
- Translation and alias merging
- Version 8 cache save and restore
- Empty indexes, missing keys, and large candidate sets
- Cache signatures and automatic invalidation
- Forge Neo loader compatibility
- Server API registration and Legacy fallback
- Remote Update API default-disable, URL/redirect rejection, size limits, and atomic replacement
- AbortController and latest-request priority
- Client timing logs
- Wildcard and underscore protection
- Distribution file layout

### 7.2 Phase D Fast Search v8 peak RAM

These current-baseline values were collected with Python `tracemalloc`. They
are local measurements, not the historical Forge Neo v6 measurements in
section 4.

| Measurement | Before | After | Reduction |
|---|---:|---:|---:|
| Full first index build: 2 selected tag CSVs, 2 selected translation CSVs, 474,008 total rows | 763.04 MiB | 729.16 MiB | 33.88 MiB (-4.4%) |
| Classification only: 750,000 rows, 3-run median | 57.29 MiB | 22.48 MiB | 34.81 MiB (-60.8%) |

Mechanical summary: `763.04 → 729.16 MiB`; `57.29 → 22.48 MiB`.

### 7.3 Phase D correctness

| Check | Result |
|---|---|
| Search parity | PASS |
| `count_order` parity | PASS |
| `non_count_ids` parity | PASS |
| Count / Legacy / Relevance behavior | Unchanged |
| `count=0` behavior | Preserved |
| cache v8 format | Unchanged |
| Disk restore test | PASS |
| Memory cache test | PASS |
| Single-flight test | PASS |
| CSV invalidation test | PASS |

### 7.4 Final Release Gate smoke test

The confirmation method is part of the result and must not be interpreted as
a broader Pass.

| Method | Check | Result |
|---|---|---|
| Forge Neo runtime | Startup/UI, TagComplete Ready, and Settings | PASS |
| Forge Neo runtime | Default 2 tag CSVs plus 2 translation CSVs | PASS |
| Forge Neo runtime | Server-index English autocomplete and Count first | PASS |
| Forge Neo runtime | Trailing-underscore `v_` search | PASS |
| Forge Neo runtime | Legacy browser → Server index switching | PASS |
| Forge Neo runtime | cache v8, memory hit, and disk cache available | PASS |
| Live API | Japanese search `女の子`: 13 results, first result `1girl` | PASS |
| Automated test only | `count=0` | PASS |
| Automated test only | Disk-restore functionality after WebUI restart | PASS |
| Unverified | Japanese IME-driven UI suggestion display | Not verified |
| Unverified | Disk-restore smoke after an actual WebUI restart | Not verified |
| Unverified | reForge current-main smoke test | Not verified |

One browser console error from `sd-dynamic-prompts-main` was observed. It was
not emitted by TagComplete Neo Multi-CSV; no TagComplete-specific console error
was observed.

## 8. Adopted specification

The validation results define the following current behavior:

1. Large CSV files are not fully parsed at startup. Index construction begins
   on the first normal tag query.
2. The complete search index remains in Python; only the candidate pool is
   returned to the browser.
3. The persistent cache format is version 8. Older formats are ignored and
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
10. The preset backend and stored data remain, while preset controls are
    intentionally hidden in the current version.

## 9. Unverified and out of scope

| Item | Status |
|---|---|
| Forge Neo | Current-main partial smoke completed; see section 7.4 |
| Stable Diffusion WebUI Forge | Unverified |
| reForge | Compatibility path retained; current-main revalidation pending |
| Japanese IME-driven UI suggestions | Unverified; live Japanese search API passed |
| Actual WebUI-restart disk-restore smoke | Not performed; automated functionality test passed |
| Comparison with every other extension disabled | Not performed |
| Hardware-by-hardware performance comparison | Not performed |
| User-preset UI | Intentionally hidden; backend and stored data retained |
| Generated-image quality | Outside this extension's validation scope |

A current Pass applies only to section 7 and its documented method and local
environment. Pass labels in sections 3–6 are historical evidence from
`da4a361`; they do not guarantee current-main compatibility with unverified
environments.
