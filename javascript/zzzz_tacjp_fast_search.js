(function () {
    "use strict";

    let installed = false;
    let remoteDisabledForSession = false;
    let activeController = null;
    let requestSequence = 0;

    const timingState = {
        active: null,
        apiCallCount: 0,
        abortedRequestCount: 0,
        longTaskObserver: null,
        longTasks: [],
        enabled() {
            return !!opts?.["tacjp_searchDebug"];
        },
        ensureLongTaskObserver() {
            if (
                this.longTaskObserver
                || typeof PerformanceObserver === "undefined"
                || !PerformanceObserver.supportedEntryTypes?.includes("longtask")
            ) {
                return;
            }
            this.longTaskObserver = new PerformanceObserver(list => {
                for (const entry of list.getEntries()) {
                    this.recordLongTask(entry);
                }
            });
            this.longTaskObserver.observe({type: "longtask", buffered: true});
        },
        recordLongTask(entry) {
            const task = {
                start: Number(entry.startTime) || 0,
                duration: Number(entry.duration) || 0,
                name: String(entry.name || "unknown"),
                attribution: Array.from(entry.attribution || []).map(item => ({
                    name: String(item.name || ""),
                    containerType: String(item.containerType || ""),
                    containerName: String(item.containerName || ""),
                    containerId: String(item.containerId || ""),
                    containerSrc: String(item.containerSrc || ""),
                })),
            };
            this.longTasks.push(task);
            const cutoff = performance.now() - 20000;
            this.longTasks = this.longTasks
                .filter(item => item.start + item.duration >= cutoff)
                .slice(-100);
        },
        input() {
            if (!this.enabled()) {
                this.active = null;
                return;
            }
            this.ensureLongTaskObserver();
            const now = performance.now();
            this.active = {
                sequence: null,
                query: "",
                started: now,
                marks: {input: now},
            };
        },
        debounceScheduled({wait, registeredAt, dueAt}) {
            if (!this.enabled() || !this.active) return;
            this.active.debounce = {
                configuredMs: Number(wait) || 0,
                registeredAt,
                dueAt,
                firedAt: null,
            };
        },
        debounceFired({firedAt}) {
            if (!this.enabled() || !this.active?.debounce) return;
            this.active.debounce.firedAt = firedAt;
        },
        begin(sequence, query) {
            if (!this.enabled()) return;
            if (!this.active) this.input();
            if (!this.active) return;
            this.active.sequence = sequence;
            this.active.query = String(query || "");
        },
        mark(name, sequence = null) {
            const active = this.active;
            if (!this.enabled() || !active) return;
            if (sequence !== null && active.sequence !== sequence) return;
            active.marks[name] = performance.now();
        },
        cancel(sequence) {
            if (this.active?.sequence === sequence) this.active = null;
        },
        apiCall() {
            this.apiCallCount += 1;
        },
        abortedRequest() {
            this.abortedRequestCount += 1;
        },
        domMetrics(metrics, sequence = null) {
            const active = this.active;
            if (!this.enabled() || !active) return;
            if (sequence !== null && active.sequence !== sequence) return;
            active.domMetrics = {...metrics};
        },
        finish(sequence = null) {
            const active = this.active;
            if (!this.enabled() || !active) return;
            if (sequence !== null && active.sequence !== sequence) return;
            const names = [
                "input",
                "debounce_end",
                "fetch_start",
                "response_received",
                "json_done",
                "results_built",
                "sort_done",
                "dom_done",
                "raf_done",
                "paint_done",
            ];
            if (names.some(name => active.marks[name] === undefined)) return;
            const timings = {query: active.query};
            for (const name of names) {
                timings[name] = Number(
                    (active.marks[name] - active.started).toFixed(2),
                );
            }
            if (active.debounce && active.debounce.firedAt !== null) {
                timings.debounce_configured_ms = active.debounce.configuredMs;
                timings.timer_registered = Number(
                    (active.debounce.registeredAt - active.started).toFixed(2),
                );
                timings.timer_due = Number(
                    (active.debounce.dueAt - active.started).toFixed(2),
                );
                timings.timer_fired = Number(
                    (active.debounce.firedAt - active.started).toFixed(2),
                );
                timings.timer_lag_ms = Number(
                    (active.debounce.firedAt - active.debounce.dueAt).toFixed(2),
                );
            }
            if (active.marks.search_start !== undefined) {
                timings.search_start = Number(
                    (active.marks.search_start - active.started).toFixed(2),
                );
            }
            for (const name of ["input_event_end", "main_thread_available"]) {
                if (active.marks[name] !== undefined) {
                    timings[name] = Number(
                        (active.marks[name] - active.started).toFixed(2),
                    );
                }
            }
            timings.api_call_count = this.apiCallCount;
            timings.aborted_request_count = this.abortedRequestCount;
            if (active.domMetrics) {
                Object.assign(timings, active.domMetrics);
            }
            const paintDone = active.marks.paint_done;
            const relevantTasks = this.longTasks.filter(task => (
                task.start < paintDone
                && task.start + task.duration > active.started
            ));
            const timerDue = active.debounce?.dueAt;
            const timerFired = active.debounce?.firedAt;
            const timerTasks = timerDue === undefined || timerFired === null
                ? []
                : relevantTasks.filter(task => (
                    task.start < timerFired
                    && task.start + task.duration > timerDue
                ));
            timings.long_task_count = relevantTasks.length;
            timings.long_task_total_ms = Number(
                relevantTasks.reduce((sum, task) => sum + task.duration, 0).toFixed(2),
            );
            timings.long_task_max_ms = Number(
                Math.max(0, ...relevantTasks.map(task => task.duration)).toFixed(2),
            );
            timings.timer_overlap_long_task_count = timerTasks.length;
            timings.timer_overlap_long_task_ms = Number(
                timerTasks.reduce((sum, task) => {
                    const start = Math.max(task.start, timerDue);
                    const end = Math.min(task.start + task.duration, timerFired);
                    return sum + Math.max(0, end - start);
                }, 0).toFixed(2),
            );
            timings.long_tasks = relevantTasks.slice(-5).map(task => ({
                start: Number((task.start - active.started).toFixed(2)),
                duration: Number(task.duration.toFixed(2)),
                name: task.name,
                attribution: task.attribution,
            }));
            console.info(
                "[TagComplete Neo Multi-CSV] client timing "
                + JSON.stringify(timings),
            );
            this.active = null;
        },
    };
    globalThis.TACJPFastSearchTiming = timingState;

    function install() {
        if (installed) return;
        if (
            typeof loadTags !== "function"
            || typeof BaseTagParser === "undefined"
            || typeof PARSERS === "undefined"
            || typeof AutocompleteResult === "undefined"
            || typeof ResultType === "undefined"
            || typeof TACJPFastSearchCore === "undefined"
        ) {
            setTimeout(install, 50);
            return;
        }
        installed = true;

        const legacyLoadTags = loadTags;
        const normalizeSearch = value => globalThis.TACJPCore?.normalizeSearch
            ? globalThis.TACJPCore.normalizeSearch(value)
            : String(value || "").toLocaleLowerCase().replaceAll("_", " ").trim();
        const matchScore = (value, query, substringOnly) => globalThis.TACJPCore?.matchScore
            ? globalThis.TACJPCore.matchScore(value, query, substringOnly)
            : (() => {
                const candidate = normalizeSearch(value);
                const needle = normalizeSearch(query);
                if (!candidate || !needle) return 99;
                if (substringOnly) return candidate.includes(needle) ? 30 : 99;
                if (candidate === needle) return 0;
                if (candidate.startsWith(needle)) return 10;
                return candidate.includes(needle) ? 30 : 99;
            })();

        function stableSortKey(group, score, count, text) {
            const boundedCount = Math.max(0, Math.min(999999999999, Number(count) || 0));
            const inverseCount = String(999999999999 - boundedCount).padStart(12, "0");
            return `${group}:${String(Number(score) || 0).padStart(4, "0")}:${inverseCount}:${normalizeSearch(text)}`;
        }

        function serverSelected() {
            return !remoteDisabledForSession
                && !TAC_CFG?.translation?.liveTranslation
                && String(opts?.["tacjp_searchEngine"] || "Server index") !== "Legacy browser";
        }

        async function switchToLegacy(error) {
            if (remoteDisabledForSession) return;
            remoteDisabledForSession = true;
            console.warn(
                "[TagComplete Neo Multi-CSV] Server search unavailable; "
                + "falling back to the legacy browser index for this session.",
                error,
            );
            allTags = [];
            tagIndex?.clear?.();
            translations.clear();
            tagsLoaded = false;
            await legacyLoadTags(TAC_CFG);
            if (TAC_CFG?.useIndexedSearch && allTags.length > 0) await buildTagIndex();
            tagsLoaded = true;
        }

        // Keep lazy loading, but in server mode do not transfer the complete merged
        // dataset to the browser. The legacy extra-file list stays local because it
        // has separate Insert before/after semantics in upstream TagComplete.
        loadTags = async function fastLoadTags(config) {
            if (!serverSelected()) return legacyLoadTags(config);
            allTags = [];
            tagIndex?.clear?.();
            translations.clear();
            await loadExtraTags(config);
        };

        let previousServerMode = serverSelected();
        if (typeof QUEUE_AFTER_CONFIG_CHANGE !== "undefined") {
            QUEUE_AFTER_CONFIG_CHANGE.push(async () => {
                const nextServerMode = serverSelected();
                if (nextServerMode === previousServerMode) return;
                previousServerMode = nextServerMode;
                allTags = [];
                tagIndex?.clear?.();
                translations.clear();
                tagsLoaded = false;
                if (nextServerMode) {
                    await loadTags(TAC_CFG);
                } else {
                    await legacyLoadTags(TAC_CFG);
                    if (TAC_CFG?.useIndexedSearch && allTags.length > 0) {
                        await buildTagIndex();
                    }
                }
                tagsLoaded = true;
            });
        }

        function appendLocalExtraResults(output, body) {
            if (!Array.isArray(extras) || extras.length === 0) return output;
            if (!TAC_CFG?.extra?.extraFile || TAC_CFG.extra.extraFile === "None") return output;

            const existing = new Set(output.map(result => normalizeSearch(result.text)));
            const group = TAC_CFG.extra.addMode === "Insert before" ? "0" : "2";
            for (const row of extras) {
                const text = String(row?.[0] || "").trim();
                if (!text || existing.has(normalizeSearch(text))) continue;
                const fields = [text];
                if (body.search_aliases && row?.[3]) fields.push(...String(row[3]).split(","));
                if (body.search_translations && row?.[4]) fields.push(String(row[4]));
                const score = Math.min(...fields.map(value => matchScore(value, body.query, body.substring_only)));
                if (!Number.isFinite(score) || score >= 99) continue;

                const result = new AutocompleteResult(text, ResultType.extra);
                result.category = row?.[1] || 0;
                result.meta = row?.[2] || "Custom tag";
                result.aliases = String(row?.[3] || "");
                result.translation = String(row?.[4] || "");
                result.sourceType = "custom";
                result.sourceTypes = ["custom"];
                result.sourceFiles = [TAC_CFG.extra.extraFile];
                result.insertMode = "tag";
                result.categoryScheme = "custom";
                result.matchScore = score;
                result.sortKey = stableSortKey(group, score, 0, text);
                if (result.translation) translations.set(text, result.translation);
                output.push(result);
                existing.add(normalizeSearch(text));
            }
            return output;
        }

        class ServerTagParser extends BaseTagParser {
            constructor() {
                super(() => {
                    if (!serverSelected() || !TAC_CFG) return false;
                    return TACJPFastSearchCore.eligibleQuery(tagword, TAC_CFG.wcWrap || "__");
                });
            }

            async parse(textArea, prompt) {
                const sequence = ++requestSequence;
                if (activeController) activeController.abort();
                activeController = new AbortController();
                timingState.begin(sequence, tagword);

                if (typeof updateTacStatusDot === "function") updateTacStatusDot("loading");
                const body = TACJPFastSearchCore.makeRequest(
                    TAC_CFG,
                    tagword,
                    prompt,
                    textArea?.selectionStart ?? String(prompt || "").length,
                    {resultPool: opts?.["tacjp_serverResultPool"] || 250},
                );
                if (!body.query || body.tag_files.length === 0) {
                    if (typeof updateTacStatusDot === "function") updateTacStatusDot("ready");
                    return appendLocalExtraResults([], body);
                }

                try {
                    timingState.mark("fetch_start", sequence);
                    timingState.apiCall();
                    const response = await fetch("tacjp/v1/search", {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(body),
                        signal: activeController.signal,
                    });
                    timingState.mark("response_received", sequence);
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    const data = await response.json();
                    timingState.mark("json_done", sequence);
                    if (sequence !== requestSequence) return [];
                    if (!data || !Array.isArray(data.results)) {
                        throw new Error(data?.error || "Search API returned no results array");
                    }
                    const output = [];
                    for (const row of data.results) {
                        const text = String(row?.[0] || "").trim();
                        if (!text) continue;
                        const result = new AutocompleteResult(text, ResultType.tag);
                        result.category = row[1];
                        result.count = Number(row[2]) || 0;
                        result.aliases = String(row[3] || "");
                        result.translation = String(row[4] || "");
                        result.sourceType = String(row[5] || "tag");
                        result.insertMode = String(row[6] || "tag");
                        result.categoryScheme = String(row[7] || "danbooru");
                        result.sourceFiles = Array.isArray(row[8]) ? row[8] : [];
                        result.sourceTypes = [result.sourceType];
                        result.matchScore = Number(row[9]) || 0;
                        result.sortKey = TAC_CFG.candidateSortMode === "Legacy"
                            ? `1:legacy:${String(output.length).padStart(8, "0")}`
                            : stableSortKey(
                                "1",
                                result.matchScore,
                                result.count,
                                text,
                            );
                        if (result.translation) translations.set(text, result.translation);
                        output.push(result);
                    }
                    appendLocalExtraResults(output, body);
                    timingState.mark("results_built", sequence);
                    Object.defineProperty(output, "_tacjpTimingSequence", {
                        value: sequence,
                    });
                    if (typeof updateTacStatusDot === "function") updateTacStatusDot("ready");
                    if (opts?.["tacjp_searchDebug"]) {
                        console.debug("[TagComplete Neo Multi-CSV] server search", data);
                    }
                    return output;
                } catch (error) {
                    if (error?.name === "AbortError") {
                        timingState.abortedRequest();
                        return [];
                    }
                    if (sequence !== requestSequence) return [];
                    timingState.cancel(sequence);
                    if (typeof updateTacStatusDot === "function") updateTacStatusDot("error");
                    await switchToLegacy(error);
                    return [];
                }
            }
        }

        PARSERS.push(new ServerTagParser());
        console.info("[TagComplete Neo Multi-CSV] Persistent server search enabled.");
    }

    install();
})();
