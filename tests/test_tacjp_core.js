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
assert.equal(core.matchScore("long_hair", "long hair"), 0);
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

console.log("tacjp_core.js tests passed");
