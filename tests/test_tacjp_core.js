"use strict";

const assert = require("node:assert/strict");
const core = require("../javascript/tacjp_core.js");

assert.deepEqual(core.optionList(["a.csv", "None", "a.csv"]), ["a.csv"]);
assert.deepEqual(core.optionList([], ["legacy.csv"]), ["legacy.csv"]);
assert.deepEqual(core.optionList('["a.csv","b.csv"]'), ["a.csv", "b.csv"]);

const patterns = "score_*, ^_^, >_<, @_@";
assert.equal(core.isUnderscoreProtected("score_8_up", patterns), true);
assert.equal(core.isUnderscoreProtected("^_^", patterns), true);
assert.equal(core.isUnderscoreProtected("long_hair", patterns), false);
assert.equal(core.isUnderscoreProtected("__wildcards/eye-color__", [], "__"), true);

assert.equal(core.normalizeSearch("ＬＯＮＧ＿ＨＡＩＲ"), "long hair");
assert.equal(core.normalizeSearch("v_", true), "v ");
assert.equal(core.matchScore("long_hair", "long hair"), 0);
assert.equal(core.matchScore("v_shaped_elbow", "v_"), 10);
assert.equal(core.matchScore("very_long_hair", "v_"), 99);
assert.equal(core.matchScore("long_hair", "long_"), 10);
assert.equal(core.matchScore("walking_towards_viewer", "towards"), 20);
assert.equal(core.matchScore("soft natural lighting", "natural light"), 30);
assert.equal(core.matchScore("soft natural lighting", "natural", true), 30);
assert.equal(core.matchScore("soft natural lighting", "soft", true), 30);

assert.equal(core.sourcePenalty("Tag", "natural_language", false), 40);
assert.equal(core.sourcePenalty("Natural Language", "tag", true), 40);
assert.equal(core.sourcePenalty("Hybrid", "natural_language", true), 0);
assert.equal(core.sourcePenalty("Hybrid", "natural_language", false), 12);

const config = {appendComma: true, appendSpace: true, alwaysSpaceAtEnd: true};
assert.equal(core.separatorForInsertMode("tag", config, {beforeSeparator: false, atEnd: true}), ", ");
assert.equal(core.separatorForInsertMode("phrase", config, {beforeSeparator: false, atEnd: true}), ", ");
assert.equal(core.separatorForInsertMode("word", config, {beforeSeparator: false, atEnd: true}), " ");
assert.equal(core.separatorForInsertMode("word", config, {beforeSeparator: true, atEnd: false}), "");
assert.equal(core.separatorForInsertMode("raw", config, {}), "");
assert.equal(core.separatorForInsertMode("wildcard", config, {}), "");

assert.deepEqual(
    core.phraseReplacementRange("a girl with soft nat", 20, "soft natural lighting"),
    {start: 12, end: 20},
);
assert.deepEqual(
    core.phraseReplacementRange("soft nat", 8, "soft natural lighting"),
    {start: 0, end: 8},
);
assert.equal(core.phraseReplacementRange("natural", 7, "soft natural lighting"), null);
assert.equal(core.phraseReplacementRange("soft nat", 8, "with"), null);

assert.deepEqual(
    core.resolveTagWeightTarget("1girl, blue hair, smile", 11, 11),
    {
        start: 7,
        end: 16,
        raw: "blue hair",
        baseText: "blue hair",
        weight: 1,
        open: "(",
        close: ")",
    },
);
assert.equal(
    core.adjustTagWeight("blue hair", 4, 4, 1).value,
    "(blue hair:1.05)",
);
assert.equal(
    core.adjustTagWeight("(blue hair:1.05)", 4, 4, -1).value,
    "blue hair",
);
assert.equal(
    core.adjustTagWeight("blue hair", 4, 4, -1).value,
    "(blue hair:0.95)",
);
assert.equal(
    core.adjustTagWeight("(long black hair:1.10)", 5, 5, 1).value,
    "(long black hair:1.15)",
);
assert.equal(
    core.adjustTagWeight("1girl, long black hair, smile", 7, 22, 1).replacement,
    "(long black hair:1.05)",
);
assert.equal(
    core.adjustTagWeight("(blue hair:0.05)", 4, 4, -1).value,
    "(blue hair:0.00)",
);
assert.equal(
    core.adjustTagWeight("(blue hair:0.00)", 4, 4, -1).value,
    "(blue hair:-0.05)",
);
assert.equal(
    core.adjustTagWeight("(blue hair:-19.95)", 4, 4, -1).value,
    "(blue hair:-20.00)",
);
assert.equal(core.adjustTagWeight("(blue hair:-20.00)", 4, 4, -1), null);
assert.equal(
    core.adjustTagWeight("(blue hair:9.95)", 4, 4, 1).value,
    "(blue hair:10.00)",
);
assert.equal(core.adjustTagWeight("(blue hair:10.00)", 4, 4, 1), null);
assert.equal(
    core.adjustTagWeight("blue hair", 4, 4, 1, 0.1).value,
    "(blue hair:1.10)",
);
assert.equal(
    core.adjustTagWeight("(blue hair:1.10)", 4, 4, -1, 0.1).value,
    "blue hair",
);

for (const unsupported of [
    "[red:blue:0.5]",
    "[tag:1.20]",
    "(tag)",
    "<lora:test:1.0>",
    "<lyco:test:1.0>",
    "embedding:test",
    "emb:test",
    "__hair/color__",
    "{red|blue}",
    "$chant",
]) {
    const caret = Math.floor(unsupported.length / 2);
    assert.equal(core.resolveTagWeightTarget(unsupported, caret, caret), null);
}
assert.equal(core.resolveTagWeightTarget("blue hair, smile", 0, 16), null);

console.log("tacjp_core.js tests passed");

// Exercise the actual keyboard/wheel handlers with the production weight core.
{
    const fs = require("node:fs");
    const path = require("node:path");
    const vm = require("node:vm");
    const source = fs.readFileSync(path.join(__dirname, "../javascript/tagAutocomplete.js"), "utf8");
    const area = {value: "blue hair", selectionStart: 4, selectionEnd: 4,
        focus() {}, setSelectionRange(start, end) {this.selectionStart = start; this.selectionEnd = end;}};
    let clock = 100;
    const document = {activeElement: area, execCommand(command, _ui, text) {
        assert.equal(command, "insertText");
        area.value = area.value.slice(0, area.selectionStart) + text + area.value.slice(area.selectionEnd);
        return true;
    }};
    area.ownerDocument = document;
    const context = {TACJPCore: core, document, isEnabled: () => true,
        performance: {now: () => clock}, updateInput() {}, hideResults() {}};
    vm.runInNewContext(source.slice(source.indexOf("const tagWeightWheelLast ="),
        source.indexOf("function navigateInList(")), context);
    function event(extra) {
        return {ctrlKey: true, prevented: false, preventDefault() {this.prevented = true;},
            stopPropagation() {}, ...extra};
    }
    assert.equal(context.handleTagWeightKeydown(area, event({key: "ArrowUp"})), true);
    assert.equal(area.value, "(blue hair:1.05)");
    assert.equal(context.handleTagWeightWheel(area, event({deltaY: -1})), true);
    assert.equal(area.value, "(blue hair:1.15)");
    context.handleTagWeightWheel(area, event({deltaY: -1}));
    assert.equal(area.value, "(blue hair:1.15)"); // 70 ms throttle.
    clock += 71;
    context.handleTagWeightWheel(area, event({deltaY: 1}));
    assert.equal(area.value, "(blue hair:1.05)");
    for (const extra of [{isComposing: true}, {keyCode: 229}, {ctrlKey: false}, {altKey: true}]) {
        const e = event({key: "ArrowUp", ...extra});
        assert.equal(context.handleTagWeightKeydown(area, e), false);
        assert.equal(e.prevented, false);
    }
    for (const [value, deltaY] of [["(blue hair:10.00)", -1], ["(blue hair:-20.00)", 1],
        ["<lora:test:1>", -1]]) {
        area.value = value;
        const e = event({deltaY});
        assert.equal(context.handleTagWeightWheel(area, e), false);
        assert.equal(e.prevented, false);
        assert.equal(area.value, value);
    }
    console.log("weight keyboard/wheel handlers passed (steps, throttle, IME, bounds)");
}
