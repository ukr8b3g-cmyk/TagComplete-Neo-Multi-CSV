const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const core = require('../javascript/tacjp_fast_search_core.js');

async function fixture() {
    const pending = [], loads = {merged: 0, index: 0};
    const context = {
        TACJPFastSearchCore: core,
        opts: {tacjp_tagFiles: ['A.csv'], tacjp_translationFiles: ['A-ja.csv'],
            tacjp_searchEngine: 'Server index', tac_useIndexedSearch: true,
            'tac_translation.liveTranslation': false, 'tac_extra.extraFile': 'None'},
        TAC_CFG: null, QUEUE_AFTER_CONFIG_CHANGE: [], QUEUE_AFTER_SETUP: [],
        tagword: 'a', allTags: [], tagIndex: new Map(), translations: new Map(), extras: [], tagsLoaded: false,
        BaseTagParser: class {constructor(triggerCondition) {this.triggerCondition = triggerCondition;}},
        PARSERS: [], ResultType: {tag: 1, extra: 2},
        AutocompleteResult: class {constructor(text, type) {this.text = text; this.type = type;}},
        buildTagIndex: async () => {loads.index++;},
        postTacAPI: async () => {loads.merged++; return {rows: [['current', 0, 1, '', 'current translation']]};},
        gradioApp: () => ({querySelectorAll: () => [], querySelector: () => null}),
        refreshTacTempFiles: async () => {},
        processQueue: async queue => {for (const fn of queue) await fn();},
        requestIdleCallback: () => 1, cancelIdleCallback: () => {},
        AbortController, setTimeout, clearTimeout, console: {info() {}, warn() {}, error() {}, debug() {}},
        fetch: (url, options) => new Promise(resolve => pending.push({url, options, resolve})),
    };
    vm.createContext(context);
    const source = fs.readFileSync(path.join(root, 'javascript/tagAutocomplete.js'), 'utf8');
    vm.runInContext(source.slice(source.indexOf('async function loadTags(c)'), source.indexOf('// Create the result list div')), context);
    vm.runInContext(fs.readFileSync(path.join(root, 'javascript/zzzz_tacjp_fast_search.js'), 'utf8'), context);
    await context.syncOptions();
    return {context, pending, loads, parser: context.PARSERS[0]};
}
const success = {ok: true, json: async () => ({results: [['a_from_A', 0, 10, '', 'old A translation']]})};
const failure = {ok: false, status: 500, statusText: 'old error'};
(async () => {
    for (const [response, aba] of [[success, false], [failure, false], [success, true], [failure, true]]) {
        const f = await fixture(), c = f.context;
        const result = f.parser.parse({selectionStart: 1}, 'a');
        c.opts.tacjp_tagFiles = ['B.csv']; await c.syncOptions();
        if (aba) {c.opts.tacjp_tagFiles = ['A.csv']; await c.syncOptions();}
        assert.equal(f.pending[0].options.signal.aborted, true);
        f.pending[0].resolve(response); // Model a transport which ignores abort.
        assert.equal((await result).length, 0);
        assert.equal(c.translations.has('a_from_A'), false);
        assert.equal(f.loads.merged, 0);
        assert.equal(f.parser.triggerCondition(), true);
    }
    {
        const f = await fixture(), c = f.context;
        const result = f.parser.parse({selectionStart: 1}, 'a');
        c.TAC_CFG = {...c.TAC_CFG, tagFiles: ['B.csv']}; // Before asynchronous config hooks finish.
        f.pending[0].resolve(success);
        assert.equal((await result).length, 0); assert.equal(c.translations.size, 0);
    }
    {
        const f = await fixture(), c = f.context;
        c.opts.tacjp_tagFiles = ['B.csv']; c.opts.tacjp_searchEngine = 'Legacy browser';
        c.opts['tac_translation.liveTranslation'] = true;
        await c.syncOptions();
        assert.deepEqual(f.loads, {merged: 1, index: 1});
        assert.equal(f.parser.triggerCondition(), false);
        c.opts.tacjp_searchEngine = 'Server index'; c.opts['tac_translation.liveTranslation'] = false;
        await c.syncOptions();
        assert.deepEqual(f.loads, {merged: 1, index: 1});
        assert.equal(f.parser.triggerCondition(), true);
    }
    {
        const f = await fixture(); const result = f.parser.parse({selectionStart: 1}, 'a');
        f.pending[0].resolve(failure); await result;
        assert.equal(f.loads.merged, 1); assert.equal(f.parser.triggerCondition(), false);
    }
    {
        const f = await fixture(), c = f.context;
        c.opts.tacjp_searchEngine = 'Legacy browser'; await c.syncOptions();
        let resolveOld;
        c.postTacAPI = () => new Promise(resolve => {resolveOld = resolve;});
        c.allTags = [];
        const oldLoad = c.loadTags(c.TAC_CFG);
        c.opts.tacjp_searchEngine = 'Server index'; c.opts.tacjp_tagFiles = ['B.csv'];
        await c.syncOptions();
        resolveOld({rows: [['obsolete_legacy', 0, 1, '', 'obsolete translation']]});
        await oldLoad;
        assert.equal(c.translations.has('obsolete_legacy'), false);
        assert.equal(c.allTags.length, 0);
    }
    console.log('config search lifecycle: stale success/failure, ABA, pre-hook response, single reload and real fallback passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
