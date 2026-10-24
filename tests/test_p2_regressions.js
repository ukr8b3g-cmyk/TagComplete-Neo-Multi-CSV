"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = process.env.TAGCOMPLETE_TEST_ROOT || path.join(__dirname, "..");
const source = fs.readFileSync(path.join(root, "javascript/tagAutocomplete.js"), "utf8");
const utils = fs.readFileSync(path.join(root, "javascript/_utils.js"), "utf8");
const core = require(path.join(root, "javascript/tacjp_core.js"));

function func(text, name) {
    const start = text.search(new RegExp(`(?:async )?function ${name}\\(`));
    assert.ok(start >= 0, name);
    return text.slice(start, text.indexOf("\n}", start) + 2);
}

function contextForAutocomplete(rows = []) {
    const frames = [];
    const state = {visible: true, shown: [], frames};
    const context = {
        TACJPCore: core,
        TAC_CFG: {
            wcWrap: "__", promptMode: "Custom", candidateSortMode: "Legacy",
            useIndexedSearch: true, includeEmbeddingsInNormalResults: false,
            frequencySort: false, showAllResults: false, maxResults: 20,
            alias: {searchByAlias: true}, translation: {searchByTranslation: true},
            extra: {extraFile: "None"},
        },
        tagsLoaded: true, allTags: rows, tagIndex: new Map(), translations: new Map(),
        previousTags: [], tagword: "", results: [], resultCountBeforeNormalTags: 0,
        hideBlocked: false, extras: [],
        ResultType: {tag: 1, extra: 2, umiWildcard: 3},
        AutocompleteResult: class {constructor(text, type) {this.text = text; this.type = type;}},
        isEnabled: () => true, processParsers: async () => [],
        hideResults: () => {state.visible = false;},
        addResultsToList: (_area, results) => {state.shown = results.map(row => row.text);},
        showResults: () => {state.visible = true;},
        requestAnimationFrame: callback => frames.push(callback),
        getSortFunction: () => () => 0,
        getTextAreaIdentifier: () => ".positive",
        getUseCounts: async () => [], calculateUsageBias: () => 0,
        showLoadingResults() {}, createTacStatusDot() {}, updateTacStatusDot() {},
        ensureTagsLoaded: async () => {context.tagsLoaded = true;},
    };
    const regexStart = source.indexOf("const WEIGHT_REGEX =");
    const regexEnd = source.indexOf("\nfunction getUnderscoreExclusionPatterns", regexStart);
    const start = source.indexOf("async function autocomplete(");
    // Include any adjacent private state, without loading the WebUI setup code.
    const adjacentStart = source.lastIndexOf("\n}", start) + 2;
    const end = source.indexOf("\nconst tagWeightWheelLast", start);
    vm.runInNewContext([
        func(utils, "escapeRegExp"), func(utils, "difference"),
        source.slice(source.indexOf("const autocompleteGenerations ="),
            source.indexOf("async function buildTagIndex(")),
        source.slice(regexStart, regexEnd), source.slice(adjacentStart, end),
    ].join("\n"), context);
    state.flush = () => {while (frames.length) frames.shift()();};
    return {context, state};
}

async function browserSearch(payload) {
    const rows = payload.rows.map(row => Object.assign(row.slice(0, 4), {
        _translation: row[4], _sourceType: row[5], _insertMode: row[6],
        _categoryScheme: row[7],
    }));
    const {context, state} = contextForAutocomplete(rows);
    for (const row of rows) {
        for (const word of core.normalizeSearch(row[0]).split(/[_\s]+/)) {
            const key = word.slice(0, 3);
            if (!context.tagIndex.has(key)) context.tagIndex.set(key, []);
            context.tagIndex.get(key).push(row);
        }
        if (row._translation) context.translations.set(row[0], row._translation);
    }
    Object.assign(context.TAC_CFG, payload.config || {});
    const area = {value: payload.query, selectionStart: payload.query.length};
    await context.autocomplete(area, area.value);
    state.flush();
    return state.shown;
}

async function punctuationTests() {
    for (const prompt of ["", ",", ", ,", " ", "\n", "\t,\r\n"]) {
        const {context, state} = contextForAutocomplete();
        context.previousTags = ["long_hair"];
        context.tagword = "long_hair";
        await context.autocomplete({value: prompt}, prompt);
        state.flush();
        assert.equal(state.visible, false, JSON.stringify(prompt));
        assert.equal(context.tagword, "");
        assert.equal(context.previousTags.length, 0);
    }
    for (const pendingAt of ["parser", "frequency", "frame", "load"]) {
        const {context, state} = contextForAutocomplete();
        const area = {value: "long", selectionStart: 4};
        let release;
        const response = new Promise(resolve => {release = resolve;});
        const stale = {text: "long_hair", type: 1, sourceType: "tag", count: 1};
        context.processParsers = async () => [[stale]];
        if (pendingAt === "parser") context.processParsers = () => response;
        if (pendingAt === "frequency") {
            context.TAC_CFG.frequencySort = true;
            context.getUseCounts = () => response;
        }
        if (pendingAt === "load") {
            context.tagsLoaded = false;
            context.ensureTagsLoaded = () => response;
        }
        const pending = context.autocomplete(area, "long");
        await new Promise(resolve => setImmediate(resolve));
        if (pendingAt === "load") context.tagsLoaded = true;
        area.value = ",";
        await context.autocomplete(area, ",");
        release(pendingAt === "parser" ? [[stale]] : []);
        await pending;
        state.flush();
        assert.equal(state.visible, false, pendingAt);
        assert.equal(context.tagword, "", pendingAt);
        assert.deepEqual(state.shown, [], pendingAt);
    }
}

async function mainGenerationTests() {
    for (const prompt of ["/", "\\"]) {
        const {context, state} = contextForAutocomplete();
        await context.autocomplete({value: prompt, selectionStart: 1}, prompt);
        state.flush();
        assert.equal(state.visible, false, prompt);
        assert.deepEqual(state.shown, []);
    }
    const {context, state} = contextForAutocomplete();
    const area = {value: "long", selectionStart: 4};
    let release;
    context.processParsers = () => new Promise(resolve => {release = resolve;});
    const pending = context.autocomplete(area, "long");
    await new Promise(resolve => setImmediate(resolve));
    // Input/focusout invalidates the old response before the debounced call starts.
    const generation = context.nextAutocompleteGeneration(area);
    release([[{text: "long_hair", type: 1}]]);
    await pending;
    state.flush();
    assert.deepEqual(state.shown, []);
    const stale = context.autocomplete(area, "long", null, generation - 1);
    await stale;
    assert.deepEqual(state.shown, []);
}

async function wildcardTests() {
    const context = {
        TAC_CFG: {useWildcards: true, wcWrap: "__", sortWildcardResults: false},
        BaseTagParser: class {constructor(trigger) {this.trigger = trigger;}},
        PARSERS: [], QUEUE_FILE_LOAD: [], QUEUE_SANITIZE: [], QUEUE_AFTER_INSERT: [],
        wildcardFiles: [["root", "plain", "plain"]], wildcardExtFiles: [],
        yamlWildcards: {}, tagword: "__", URLSearchParams,
        ResultType: {wildcardTag: 1, wildcardFile: 2, yamlWildcard: 3},
        AutocompleteResult: class {constructor(text, type) {this.text = text; this.type = type;}},
        getSortFunction: () => () => 0,
    };
    let fetched = 0;
    context.fetchTacAPI = async () => {fetched++; return "# comment\nplain item\n";};
    vm.runInNewContext(func(utils, "escapeRegExp") + "\n" + fs.readFileSync(
        path.join(root, "javascript/ext_wildcards.js"), "utf8"), context);
    for (const ext of ["yml", "yaml", "YML", "YAML"]) {
        const file = `sample.${ext}`;
        context.wildcardExtFiles = [[file, "color/warm"]];
        context.yamlWildcards = {[file]: {color: {warm: ["red", "orange"]}}};
        context.tagword = "__";
        const listed = context.PARSERS[1].parse();
        assert.equal(listed.length, 2);
        assert.equal(listed[1].type, context.ResultType.yamlWildcard);
        context.tagword = "__color/warm__";
        const content = await context.PARSERS[0].parse();
        assert.deepEqual(Array.from(content, row => row.text), ["red", "orange"]);
        assert.equal(fetched, 0);
    }
    context.tagword = "__plain__";
    assert.deepEqual(Array.from(await context.PARSERS[0].parse(), row => row.text), ["plain item"]);
    assert.equal(fetched, 1);
}

(async () => {
    if (process.argv[2] === "--browser-search") {
        const payload = JSON.parse(fs.readFileSync(0, "utf8"));
        process.stdout.write(JSON.stringify(await browserSearch(payload)));
        return;
    }
    const failures = [];
    for (const [name, test] of [["punctuation and stale responses", punctuationTests],
        ["main input generations and punctuation", mainGenerationTests],
        ["YML/YAML and text wildcards", wildcardTests]]) {
        try {await test(); console.log(`${name}: passed`);}
        catch (error) {failures.push(name); console.error(`${name}:`, error);}
    }
    if (failures.length) process.exitCode = 1;
})().catch(error => {console.error(error); process.exitCode = 1;});
