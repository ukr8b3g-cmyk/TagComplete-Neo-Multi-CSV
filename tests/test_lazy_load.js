"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../javascript/tagAutocomplete.js"), "utf8");
function fixture() {
    const pending = [], builds = [];
    const context = {tagsLoaded: false, TAC_CFG: {useIndexedSearch: true}, allTags: [],
        loadTags: config => new Promise((resolve, reject) => pending.push({config, reject,
            resolve(rows = ["tag"]) {if (config === context.TAC_CFG) context.allTags = rows;resolve();}})),
        buildTagIndex: async () => {builds.push(context.TAC_CFG);},
    };
    vm.createContext(context);
    const start = source.indexOf("let pendingTagLoad =");
    vm.runInContext(source.slice(start < 0 ? source.indexOf("async function ensureTagsLoaded()") : start, source.indexOf("async function autocomplete(")), context);
    return {context, pending, builds};
}
(async () => {
    {
        const f = fixture(), a = f.context.ensureTagsLoaded(), b = f.context.ensureTagsLoaded();
        assert.equal(f.pending.length, 1);f.pending[0].resolve();await Promise.all([a, b]);
        assert.equal(f.builds.length, 1);assert.equal(f.context.tagsLoaded, true);
        await f.context.ensureTagsLoaded();assert.equal(f.pending.length, 1);
    }
    {
        const f = fixture(), a = f.context.ensureTagsLoaded(), b = f.context.ensureTagsLoaded();
        f.pending[0].reject(new Error("offline"));
        assert.ok((await Promise.allSettled([a, b])).every(item => item.status === "rejected"));
        const retry = f.context.ensureTagsLoaded();assert.equal(f.pending.length, 2);
        f.pending[1].resolve([]);await retry;
        assert.equal(f.context.tagsLoaded, true);assert.equal(f.builds.length, 0);
    }
    for (const oldFirst of [true, false]) {
        const f = fixture(), a = f.context.ensureTagsLoaded();
        f.context.TAC_CFG = {useIndexedSearch: true};
        const b = f.context.ensureTagsLoaded();assert.equal(f.pending.length, 2);
        if (oldFirst) {
            f.pending[0].resolve();await a;assert.equal(f.context.tagsLoaded, false);
            const shared = f.context.ensureTagsLoaded();assert.equal(f.pending.length, 2);
            f.pending[1].resolve();await Promise.all([b, shared]);
        } else {
            f.pending[1].resolve();await b;f.pending[0].resolve();await a;
        }
        assert.equal(f.builds.length, 1);assert.equal(f.context.tagsLoaded, true);
    }
    {
        const f = fixture();let finishBuild;
        f.context.buildTagIndex = () => new Promise(resolve => {finishBuild = resolve;});
        const a = f.context.ensureTagsLoaded();f.pending[0].resolve();
        await new Promise(resolve => setImmediate(resolve));f.context.TAC_CFG = {};finishBuild();await a;
        assert.equal(f.context.tagsLoaded, false, "an old index build cannot complete a new config");
    }
    console.log("lazy load: shared load/build, empty selection, retry and stale config completion passed");
})().catch(error => {console.error(error);process.exitCode = 1;});
