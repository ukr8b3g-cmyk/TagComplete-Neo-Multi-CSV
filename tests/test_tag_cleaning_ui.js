"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "..", "javascript", "zzzzz_tag_cleaning.js"),
    "utf8",
);

function loadHook(cleaningEnabled) {
    let fetchCount = 0;
    let applyClick = null;
    let enabledChange = null;
    const checkbox = {checked: cleaningEnabled};
    const context = {
        console: {info() {}, debug() {}},
        document: {
            documentElement: {dataset: {}},
            addEventListener(type, handler) {
                if (type === "click") applyClick = handler;
                if (type === "change") enabledChange = handler;
            },
            getElementById() { return {}; },
        },
        fetch: async () => {
            fetchCount += 1;
            return {ok: true, json: async () => ({enabled: true, ready: true, results: []})};
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
        call() {
            const output = context.addResultsToList({}, [{
                text: "pink_hair",
                type: 1,
                category: 0,
                categoryScheme: "danbooru",
            }]);
            return {output, fetchCount};
        },
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

console.log("tag cleaning UI tests passed");
