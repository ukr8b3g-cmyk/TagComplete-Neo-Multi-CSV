"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "..", "javascript", "zzzzz_tag_cleaning.js"),
    "utf8",
);

function loadHook(cleaningEnabled, {failAt = 0, deferred = false, renderStep = Infinity} = {}) {
    let fetchCount = 0;
    const requests = [];
    const pending = [];
    const signals = [];
    const errors = [];
    let applyClick = null;
    let enabledChange = null;
    const checkbox = {checked: cleaningEnabled};
    let nodes = [];
    const context = {
        console: {info() {}, debug(...args) {errors.push(args);}},
        document: {
            documentElement: {dataset: {}},
            addEventListener(type, handler) {
                if (type === "click") applyClick = handler;
                if (type === "change") enabledChange = handler;
            },
            getElementById() { return {}; },
        },
        AbortController,
        fetch: async (_url, options) => {
            fetchCount += 1;
            const items = JSON.parse(options.body).items;
            requests.push(items);
            signals.push(options.signal);
            const response = items.length > 250 || fetchCount === failAt
                ? {ok: false, status: items.length > 250 ? 422 : 503, statusText: "test failure"}
                : {ok: true, json: async () => ({
                    enabled: true, ready: true, database_id: "test-database",
                    results: items.map(item => ({requested_tag: item.tag, match: null})),
                })};
            if (deferred) return new Promise(resolve => pending.push(() => resolve(response)));
            return response;
        },
        getTextAreaIdentifier: () => "",
        gradioApp: () => ({
            querySelector(selector) {
                if (selector.includes("tacjp_cleaningEnabled")) return checkbox;
                return selector.startsWith(".autocompleteResults") ? {querySelectorAll: () => nodes} : null;
            },
            querySelectorAll() { return []; },
        }),
        setTimeout(callback) { callback(); },
        addResultsToList(_area, results, _word, reset) {
            if (reset) {
                nodes.forEach(node => {node.isConnected = false;});
                nodes = [];
            }
            const end = Math.min(results.length, nodes.length + renderStep);
            while (nodes.length < end) nodes.push({isConnected: true,
                querySelectorAll: () => [], querySelector: () => null});
            return "original-output";
        },
    };
    vm.runInNewContext(
        `const opts = {tacjp_cleaningEnabled: ${cleaningEnabled}}; `
        + "const ResultType = {tag: 1};\n" + source,
        context,
    );
    return {
        requests,
        signals,
        reply(index = 0) {pending[index]();},
        errors,
        call(results = [{
                text: "pink_hair",
                type: 1,
                category: 0,
                categoryScheme: "danbooru",
            }], reset = true) {
            const output = context.addResultsToList({}, results, "", reset);
            return {output, fetchCount};
        },
        settle() {return new Promise(resolve => setImmediate(resolve));},
        apply(value) {
            checkbox.checked = value;
            enabledChange({
                target: {
                    checked: value,
                    matches: selector => selector.includes("tacjp_cleaningEnabled"),
                },
            });
            applyClick({target: {closest: selector => selector === "#settings_submit"}});
        },
    };
}

const disabled = loadHook(false).call();
assert.equal(disabled.output, "original-output");
assert.equal(disabled.fetchCount, 0);

const enabled = loadHook(true).call();
assert.equal(enabled.output, "original-output");
assert.equal(enabled.fetchCount, 1);

const disabledAfterApply = loadHook(true);
disabledAfterApply.apply(false);
assert.equal(disabledAfterApply.call().fetchCount, 0);

const enabledAfterApply = loadHook(false);
enabledAfterApply.apply(true);
assert.equal(enabledAfterApply.call().fetchCount, 1);

function candidate(index) {
    return {text: `synthetic_${index}`, type: 1, category: index % 5, categoryScheme: "danbooru"};
}

(async () => {
    for (const size of [0, 1, 249, 250, 251, 500, 501]) {
        const hook = loadHook(true);
        const results = Array.from({length: size}, (_, index) => candidate(index));
        assert.equal(hook.call(results).output, "original-output");
        await hook.settle();
        assert.equal(hook.errors.length, 0, `lookup errors for ${size} items`);
        assert.ok(hook.requests.every(items => items.length <= 250));
        assert.deepEqual(hook.requests.flat().map(item => item.tag), results.map(item => item.text));
        assert.equal(hook.requests.length, Math.ceil(size / 250));
        hook.call(results);
        await hook.settle();
        assert.equal(hook.requests.length, Math.ceil(size / 250), "cached misses must not be re-requested");
    }

    const deduped = loadHook(true);
    const results = Array.from({length: 251}, (_, index) => candidate(index));
    deduped.call([...results, results[0], {...results[0], categoryScheme: "e621"}]);
    await deduped.settle();
    assert.deepEqual(deduped.requests.map(items => items.length), [250, 1]);
    const sameTagDifferentCategory = {...results[0], category: 4};
    deduped.call([results[0], sameTagDifferentCategory]);
    await deduped.settle();
    assert.deepEqual(deduped.requests.at(-1), [{tag: results[0].text, category: 4}]);

    const failed = loadHook(true, {failAt: 2});
    failed.call(results);
    await failed.settle();
    assert.equal(failed.errors.length, 1, "HTTP failures must remain visible to the caller");
    failed.call(results);
    await failed.settle();
    assert.deepEqual(failed.requests.map(items => items.length), [250, 1, 1], "only the failed batch needs retrying");

    // A transport may ignore abort: success and failure still need a generation check.
    for (const failAt of [0, 1]) {
        const hook = loadHook(true, {deferred: true, failAt});
        hook.call(); hook.apply(false);
        assert.equal(hook.signals[0].aborted, true);
        hook.reply(); await hook.settle();
        assert.equal(hook.errors.length, 0);
        hook.apply(true); hook.call();
        assert.equal(hook.requests.length, 2, "stale completion must not seed the new cache");
        hook.reply(1); await hook.settle();
    }
    {
        const hook = loadHook(true, {deferred: true});
        hook.call(); hook.apply(false); hook.apply(true);
        hook.reply(); await hook.settle(); hook.call();
        assert.equal(hook.requests.length, 2, "OFF to ON must not revive the first ON generation");
        hook.reply(1); await hook.settle(); hook.call();
        assert.equal(hook.requests.length, 2, "current responses still populate the cache");
    }
    {
        const hook = loadHook(true, {deferred: true});
        hook.call(Array.from({length: 501}, (_, index) => candidate(index)));
        hook.apply(false); hook.reply(); await hook.settle();
        assert.equal(hook.requests.length, 1, "disabling stops later batches");
    }

    const off = loadHook(false);
    off.call(results);
    await off.settle();
    assert.equal(off.requests.length, 0);
    {
        const hook = loadHook(true, {deferred: true});
        const first = Array.from({length: 20}, (_, i) => candidate(i));
        hook.call(first); hook.call(first);
        assert.equal(hook.requests.length, 1, "pending requests are shared across redraws");
        hook.call(Array.from({length: 20}, (_, i) => candidate(i + 10)));
        assert.deepEqual(hook.requests.map(items => items.length), [20, 10]);
        hook.reply(0);hook.reply(1);await hook.settle();
        hook.call(first);assert.equal(hook.requests.length, 2);
    }
    {
        const hook = loadHook(true, {deferred: true, failAt: 1});
        hook.call();hook.call();assert.equal(hook.requests.length, 1);
        hook.reply();await hook.settle();hook.call();
        assert.equal(hook.requests.length, 2, "a failed shared lookup can be retried");
        hook.reply(1);await hook.settle();
    }
    {
        const hook = loadHook(true, {renderStep: 50});
        const results = Array.from({length: 1000}, (_, i) => candidate(i));
        hook.call(results);await hook.settle();
        assert.deepEqual(hook.requests.map(items => items.length), [50]);
        hook.call(results, false);await hook.settle();
        assert.deepEqual(hook.requests[1].map(item => item.tag), results.slice(50, 100).map(item => item.text));
        hook.call(results);await hook.settle();
        assert.equal(hook.requests.length, 2, "reset draws use cached visible rows");
    }
    {
        const hook = loadHook(true, {deferred: true});
        hook.call();hook.apply(false);hook.apply(true);hook.call();
        hook.reply(0);await hook.settle();hook.call();
        assert.equal(hook.requests.length, 2, "old completion cannot release a new generation's shared lookup");
        hook.reply(1);await hook.settle();
    }
    console.log("tag cleaning UI tests passed (OFF, batches, cache, deduplication, failure retry)");
})().catch(error => {console.error(error); process.exitCode = 1;});
