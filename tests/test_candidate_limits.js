"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = process.env.TAGCOMPLETE_TEST_ROOT || path.join(__dirname, "..");
const source = fs.readFileSync(path.join(root, "javascript/tagAutocomplete.js"), "utf8");
const core = require(path.join(root, "javascript/tacjp_core.js"));
const types = {tag: 1, extra: 2, embedding: 3, lora: 4, wildcardTag: 5, umiWildcard: 6};
const candidate = (i, type = types.tag) => ({text: `blue_${i}`, type, count: 100, matchScore: 0});
async function search({parser = [], legacy = [], config = {}} = {}) {
    const state = {}, context = {TACJPCore: core, TAC_CFG: {
        candidateSortMode: "Legacy", useIndexedSearch: false, promptMode: "Tag",
        includeEmbeddingsInNormalResults: false, frequencySort: false, showAllResults: false, maxResults: 20,
        alias: {searchByAlias: true}, translation: {searchByTranslation: true}, extra: {extraFile: "None"}, ...config},
        tagsLoaded: true, allTags: legacy, translations: new Map(), tagIndex: new Map(), extras: [],
        ResultType: types, AutocompleteResult: class {constructor(text, type) {this.text = text;this.type = type;}},
        isEnabled: () => true, isAutocompleteGenerationCurrent: () => true,
        processParsers: async () => parser.length ? [parser] : [], getSortFunction: () => () => 0,
        isSingleCharacterPunctuationQuery: () => false, requestAnimationFrame: fn => fn(),
        addResultsToList(_a, results, _q, _reset, _timing, summary) {state.results = Array.from(results);state.summary = summary;},
        showResults() {}, hideResults() {}, getTextAreaIdentifier: () => ".positive",
        getUseCounts: async () => [{name: "blue_249", type: types.tag, count: 99}],
        calculateUsageBias: (_result, _count, uses) => uses,
    };
    vm.createContext(context);
    vm.runInContext(source.slice(source.indexOf("async function autocomplete("), source.indexOf("const tagWeightWheelLast =")), context);
    await context.autocomplete({selectionStart: 4}, "blue", "blue", 1);
    state.beforeNormal = context.resultCountBeforeNormalTags;
    return state;
}
(async () => {
    const tags = Array.from({length: 250}, (_, i) => candidate(i));
    Object.defineProperty(tags, "_tacjpHitCount", {value: 3000});
    const shown = await search({parser: tags});assert.equal(shown.results.length, 20);
    assert.equal(shown.summary.total, 3000);assert.equal(shown.summary.exact, true);
    assert.equal((await search({parser: tags, config: {showAllResults: true}})).results.length, 250);
    assert.equal((await search({parser: Array.from({length: 1000}, (_, i) => candidate(i)), config: {showAllResults: true}})).results.length, 1000);
    assert.equal((await search({parser: tags.map(row => ({...row, sourceType: "natural_language"}))})).results.length, 20);
    assert.equal((await search({parser: tags, config: {maxResults: 37}})).results.length, 37);
    const legacy = tags.map(row => [row.text, 0, row.count, ""]);
    assert.equal((await search({legacy})).results.length, 20);
    assert.equal((await search({legacy, config: {showAllResults: true}})).results.length, 250);
    for (const mode of ["Legacy", "Count", "Match quality"]) {
        assert.equal((await search({parser: tags, config: {candidateSortMode: mode}})).results.length, 20);
    }
    for (const useLegacy of [false, true]) {
        const state = await search({[useLegacy ? "legacy" : "parser"]: useLegacy ? legacy : tags, config: {frequencySort: true}});
        assert.equal(state.results.length, 20);assert.equal(state.results[0].text, "blue_249", "rank before applying the cap");
    }
    const specials = [types.embedding, types.lora, types.wildcardTag].flatMap(type => Array.from({length: 5}, (_, i) => candidate(i, type)));
    for (const includeEmbeddingsInNormalResults of [false, true]) {
        const state = await search({parser: [...specials, ...tags], config: {includeEmbeddingsInNormalResults}});
        assert.equal(state.results.filter(row => row.type === types.tag).length, 20);
        assert.equal(state.results.filter(row => row.type !== types.tag).length, 15);
        if (includeEmbeddingsInNormalResults) assert.equal(state.beforeNormal, 15);
    }
    assert.equal((await search({parser: specials})).results.length, 15);
    const extra = Array.from({length: 10}, (_, i) => candidate(i, types.extra));
    const custom = await search({parser: [...extra, ...tags]});assert.equal(custom.results.length, 20);
    assert.equal(custom.results.filter(row => row.type === types.extra).length, 10);
    assert.equal((await search({parser: Array.from({length: 250}, (_, i) => candidate(i, types.extra))})).results.length, 20);
    const request = require(path.join(root, "javascript/tacjp_fast_search_core.js")).makeRequest({maxResults: 20}, "blue", "blue", 4);
    assert.equal(request.limit, 250, "the retrieval pool remains independent of the display cap");
    console.log("candidate limits: server/legacy, show all, usage ranking, total hits and dedicated parsers passed");
})().catch(error => {console.error(error);process.exitCode = 1;});
