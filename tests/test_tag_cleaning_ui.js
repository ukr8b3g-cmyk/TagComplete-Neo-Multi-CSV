"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "..", "javascript", "zzzzz_tag_cleaning.js"),
    "utf8",
);

function loadHook(cleaningEnabled, {failAt = 0} = {}) {
    let fetchCount = 0;
    const requests = [];
    const errors = [];
    let applyClick = null;
    let enabledChange = null;
    const checkbox = {checked: cleaningEnabled};
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
        fetch: async (_url, options) => {
            fetchCount += 1;
            const items = JSON.parse(options.body).items;
            requests.push(items);
            if (items.length > 250 || fetchCount === failAt) {
                return {ok: false, status: items.length > 250 ? 422 : 503, statusText: "test failure"};
            }
            return {ok: true, json: async () => ({
                enabled: true, ready: true, database_id: "test-database",
                results: items.map(item => ({requested_tag: item.tag, match: null})),
            })};
        },
        getTextAreaIdentifier: () => "",
        gradioApp: () => ({
            querySelector(selector) {
                return selector.includes("tacjp_cleaningEnabled") ? checkbox : null;
            },
            querySelectorAll() { return []; },
        }),
        setTimeout(callback) { callback(); },
        addResultsToList: () => "original-output",
    };
    vm.runInNewContext(
        `const opts = {tacjp_cleaningEnabled: ${cleaningEnabled}}; `
        + "const ResultType = {tag: 1};\n" + source,
        context,
    );
    return {
        requests,
        errors,
        call(results = [{
                text: "pink_hair",
                type: 1,
                category: 0,
                categoryScheme: "danbooru",
            }]) {
            const output = context.addResultsToList({}, results);
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

    const off = loadHook(false);
    off.call(results);
    await off.settle();
    assert.equal(off.requests.length, 0);
    console.log("tag cleaning UI tests passed (OFF, batches, cache, deduplication, failure retry)");
})().catch(error => {console.error(error); process.exitCode = 1;});
