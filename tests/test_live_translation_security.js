"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const source = fs.readFileSync(path.join(root, "javascript", "tagAutocomplete.js"), "utf8");
const utils = fs.readFileSync(path.join(root, "javascript", "_utils.js"), "utf8");
function utility(name) {
    const start = utils.indexOf(`function ${name}(`);
    assert.ok(start >= 0, name);
    return utils.slice(start, utils.indexOf("\n}", start) + 2);
}
const rubySource = source.slice(source.indexOf("function updateRuby("),
    source.indexOf("// Check if the last edit was the keyword insertion"));
const regexSource = source.match(/^const RUBY_TAG_REGEX = .*;$/m)[0];

function render(prompt, entries, enabled = true) {
    const ruby = {innerText: "", innerHTML: "", childNodes: [], children: []};
    const context = {
        TAC_CFG: {translation: {liveTranslation: enabled, translationFile: "fixture.csv"}},
        translations: new Map(entries),
        gradioApp: () => ({querySelector: () => ruby}),
        getTextAreaIdentifier: () => ".fixture",
    };
    vm.runInNewContext([utility("escapeRegExp"), utility("escapeHTML"),
        utility("toNgrams"), regexSource, rubySource].join("\n"), context);
    context.updateRuby({}, prompt);
    return ruby;
}

assert.equal(render("long_hair", [["long_hair", "長髪"]]).innerHTML,
    "<ruby>long_hair<rt>長髪</rt></ruby>");
assert.equal(render("long hair", [["long_hair", "長髪"]]).innerHTML,
    "<ruby>long hair<rt>長髪</rt></ruby>");

const attack = '<img src=x onerror="marker()">&\' $& $` $\'';
const escaped = "&lt;img src=x onerror=&quot;marker()&quot;&gt;&amp;&#039; $&amp; $` $&#039;";
assert.equal(render("long_hair", [["long_hair", attack]]).innerHTML,
    `<ruby>long_hair<rt>${escaped}</rt></ruby>`);
assert.equal(render("very long hair", [["long hair", attack]]).innerHTML,
    `very <ruby>long hair<rt>${escaped}</rt></ruby>`);

assert.equal(render("artist's", [["artist's", "作者"]]).innerHTML,
    "<ruby>artist&#039;s<rt>作者</rt></ruby>");
assert.equal(render("<img>", [["<img>", "画像"]]).innerHTML,
    "&lt;img&gt;");
assert.equal(render("<img>", []).innerHTML, "&lt;img&gt;");
assert.equal(render("<very long hair>", [["long hair", "長髪"]]).innerHTML,
    "&lt;very long hair&gt;");
assert.equal(render("long_hair", [["long_hair", attack]], false).innerHTML, "");
assert.equal(render(",", []).innerText, ",");
console.log("live translation security tests passed (10 cases)");
