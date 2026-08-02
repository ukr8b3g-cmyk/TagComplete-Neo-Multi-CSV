const assert = require("assert");
require("../javascript/tacjp_fast_search_core.js");

global.opts = {
    tacjp_searchEngine: "Server index",
    tacjp_serverResultPool: 250,
    tacjp_searchDebug: false,
};
global.TAC_CFG = {
    tagFiles: ["danbooru.csv"],
    promptMode: "Tag",
    wcWrap: "__",
    useIndexedSearch: true,
    showSourceLabels: false,
    alias: {searchByAlias: true},
    translation: {
        translationFiles: ["ja.csv"],
        searchByTranslation: true,
        liveTranslation: false,
    },
    extra: {
        extraFile: "extra-quality-tags.csv",
        addMode: "Insert before",
    },
};
global.QUEUE_AFTER_CONFIG_CHANGE = [];
global.QUEUE_AFTER_SETUP = [];
global.tagword = "long";
global.allTags = [];
global.tagIndex = new Map();
global.translations = new Map();
global.tagsLoaded = false;
global.extras = [];
global.loadExtraTags = async () => {
    global.extras = [
        ["long_quality", 5, "Extra tag", "longquality", "追加品質"],
    ];
};
global.buildTagIndex = async () => {};
let legacyLoads = 0;
global.loadTags = async () => { legacyLoads += 1; };
global.BaseTagParser = class {
    constructor(triggerCondition) {
        this.triggerCondition = triggerCondition;
    }
};
global.PARSERS = [];
global.ResultType = {tag: 1, extra: 2};
global.AutocompleteResult = class {
    constructor(text, type) {
        this.text = text;
        this.type = type;
    }
};
let warmupCalls = 0;
const idleCallbacks = [];
global.requestIdleCallback = callback => {
    idleCallbacks.push(callback);
    return idleCallbacks.length;
};
global.cancelIdleCallback = () => {};
global.fetch = async (url, options) => {
    const body = JSON.parse(options.body);
    if (url === "tacjp/v1/search-warmup") {
        warmupCalls += 1;
        assert.deepStrictEqual(body, {
            tag_files: ["danbooru.csv"],
            translation_files: ["ja.csv"],
        });
        return {ok: true, json: async () => ({status: "ready", cache: "memory"})};
    }
    assert.strictEqual(url, "tacjp/v1/search");
    assert.strictEqual(body.query, "long");
    assert.deepStrictEqual(body.tag_files, ["danbooru.csv"]);
    return {
        ok: true,
        json: async () => ({
            results: [
                [
                    "long_low_count",
                    0,
                    10,
                    "",
                    "",
                    "tag",
                    "tag",
                    "danbooru",
                    [],
                    10,
                ],
                [
                    "long_hair",
                    0,
                    100,
                    "longhair",
                    "長髪",
                    "tag",
                    "tag",
                    "danbooru",
                    [],
                    10,
                ],
            ],
        }),
    };
};

require("../javascript/zzzz_tacjp_fast_search.js");

(async () => {
    assert.strictEqual(PARSERS.length, 1);
    assert.strictEqual(QUEUE_AFTER_SETUP.length, 1);
    await QUEUE_AFTER_SETUP[0]();
    assert.strictEqual(idleCallbacks.length, 1);
    idleCallbacks.shift()();
    await new Promise(resolve => setImmediate(resolve));
    assert.strictEqual(warmupCalls, 1);
    await loadTags(TAC_CFG);
    assert.strictEqual(legacyLoads, 0);
    const parser = PARSERS[0];
    assert.strictEqual(parser.triggerCondition(), true);
    const timingLogs = [];
    const originalInfo = console.info;
    console.info = (...args) => timingLogs.push(args.join(" "));
    opts.tacjp_searchDebug = true;
    TACJPFastSearchTiming.input();
    const registeredAt = performance.now();
    TACJPFastSearchTiming.debounceScheduled({
        wait: 50,
        registeredAt,
        dueAt: registeredAt + 50,
    });
    TACJPFastSearchTiming.debounceFired({firedAt: registeredAt + 55});
    TACJPFastSearchTiming.mark("debounce_end");
    TACJPFastSearchTiming.mark("search_start");
    TACJPFastSearchTiming.mark("input_event_end");
    TACJPFastSearchTiming.mark("main_thread_available");
    TACJPFastSearchTiming.recordLongTask({
        startTime: registeredAt + 49,
        duration: 6,
        name: "self",
        attribution: [],
    });
    await new Promise(resolve => setTimeout(resolve, 60));
    const results = await parser.parse({selectionStart: 4}, "long");
    TACJPFastSearchTiming.mark("sort_done");
    TACJPFastSearchTiming.mark("dom_done");
    TACJPFastSearchTiming.mark("raf_done");
    TACJPFastSearchTiming.mark("paint_done");
    TACJPFastSearchTiming.domMetrics({
        dom_items: 100,
        dom_clear_ms: 1,
        dom_build_ms: 10,
        dom_attribute_ms: 8,
        dom_event_ms: 2,
        dom_append_ms: 1,
        dom_layout_ms: 3,
        dom_per_item_ms: 0.1,
    });
    TACJPFastSearchTiming.finish();
    opts.tacjp_searchDebug = false;
    assert.strictEqual(results.length, 3);
    assert.strictEqual(timingLogs.length, 1);
    for (const name of [
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
    ]) {
        assert.ok(timingLogs[0].includes(`"${name}":`));
    }
    for (const name of [
        "debounce_configured_ms",
        "timer_registered",
        "timer_due",
        "timer_fired",
        "timer_lag_ms",
        "search_start",
    ]) {
        assert.ok(timingLogs[0].includes(`"${name}":`));
    }
    assert.ok(timingLogs[0].includes('"debounce_configured_ms":50'));
    assert.ok(timingLogs[0].includes('"timer_lag_ms":5'));
    assert.ok(timingLogs[0].includes('"api_call_count":1'));
    assert.ok(timingLogs[0].includes('"aborted_request_count":0'));
    assert.ok(timingLogs[0].includes('"dom_items":100'));
    assert.ok(timingLogs[0].includes('"dom_per_item_ms":0.1'));
    assert.ok(timingLogs[0].includes('"input_event_end":'));
    assert.ok(timingLogs[0].includes('"main_thread_available":'));
    assert.ok(timingLogs[0].includes('"long_task_count":1'));
    assert.ok(timingLogs[0].includes('"timer_overlap_long_task_count":1'));
    opts.tacjp_searchDebug = true;
    TACJPFastSearchTiming.input();
    TACJPFastSearchTiming.begin(100, "old");
    TACJPFastSearchTiming.input();
    TACJPFastSearchTiming.begin(101, "new");
    TACJPFastSearchTiming.finish(100);
    TACJPFastSearchTiming.cancel(101);
    opts.tacjp_searchDebug = false;
    assert.strictEqual(timingLogs.length, 1);
    console.info = originalInfo;

    const highCount = results.find(result => result.text === "long_hair");
    const lowCount = results.find(result => result.text === "long_low_count");
    const extra = results.find(result => result.text === "long_quality");
    assert.ok(highCount);
    assert.ok(lowCount);
    assert.ok(extra);
    assert.strictEqual(highCount.translation, "長髪");
    assert.strictEqual(translations.get("long_hair"), "長髪");
    assert.strictEqual(extra.type, ResultType.extra);
    assert.ok(extra.sortKey.startsWith("0:"));
    assert.ok(highCount.sortKey.startsWith("1:"));
    assert.ok(highCount.sortKey.localeCompare(lowCount.sortKey) < 0);

    // Server Count order is authoritative. The client must retain it while
    // keeping an Insert-before extra result ahead of normal tags.
    TAC_CFG.candidateSortMode = "Count";
    const countResults = await parser.parse({selectionStart: 4}, "long");
    const countTags = countResults.filter(result => result.type === ResultType.tag);
    assert.deepStrictEqual(
        countTags.map(result => result.text),
        ["long_low_count", "long_hair"],
    );
    const countExtra = countResults.find(result => result.type === ResultType.extra);
    assert.ok(countExtra);
    assert.ok(countExtra.sortKey.localeCompare(countTags[0].sortKey) < 0);
    assert.ok(countTags[0].sortKey.startsWith("1:count:"));
    assert.ok(countTags[0].sortKey.localeCompare(countTags[1].sortKey) < 0);
    TAC_CFG.candidateSortMode = "Relevance";

    // Experimental full-prompt live translation requires the complete local map,
    // so changing to that mode must load the legacy browser dataset automatically.
    TAC_CFG.translation.liveTranslation = true;
    await QUEUE_AFTER_CONFIG_CHANGE[0]();
    assert.strictEqual(legacyLoads, 1);
    assert.strictEqual(parser.triggerCondition(), false);
    console.log("tacjp fast search integration tests passed");
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
