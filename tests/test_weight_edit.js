"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = process.env.TAGCOMPLETE_TEST_ROOT || path.join(__dirname, "..");
const source = fs.readFileSync(path.join(root, "javascript/tagAutocomplete.js"), "utf8");
const core = require(path.join(root, "javascript/tacjp_core.js"));
function fixture(value, start, end = start) {
    const edits = [], area = {value, selectionStart: start, selectionEnd: end, scrollTop: 91, scrollLeft: 7,
        setSelectionRange(a, b) {this.selectionStart = a;this.selectionEnd = b;}};
    const doc = {activeElement: area, execCommand(command, _ui, text) {
        edits.push({command, text, start: area.selectionStart, end: area.selectionEnd});
        area.value = area.value.slice(0, area.selectionStart) + text + area.value.slice(area.selectionEnd);
        area.scrollTop = 0;area.scrollLeft = 0;return true;
    }};
    area.ownerDocument = doc;
    const context = {TACJPCore: core, document: doc, isEnabled: () => true, hideResults() {},
        updateInput() {throw new Error("native input must not be dispatched twice");}};
    vm.createContext(context);
    vm.runInContext(source.slice(source.indexOf("const tagWeightWheelLast ="), source.indexOf("function navigateInList(")), context);
    return {area, doc, edits, context, apply() {return context.applyTagWeightShortcut(area, core.adjustTagWeight(area.value, area.selectionStart, area.selectionEnd, 1));}};
}
{
    const f = fixture("😀,\n  red hair, blue eyes", 9);assert.equal(f.apply(), true);
    assert.equal(f.area.value, "😀,\n  (red hair:1.05), blue eyes");
    assert.deepEqual(f.edits, [{command: "insertText", text: "(red hair:1.05)", start: 6, end: 14}]);
    assert.equal(f.area.scrollTop, 91);assert.equal(f.area.scrollLeft, 7);
    assert.equal(f.doc.activeElement, f.area);
}
for (const failure of ["missing", "throws", "no edit", "readonly", "disabled", "blurred"]) {
    const f = fixture("red hair", 2, 4);
    if (failure === "missing") delete f.doc.execCommand;
    if (failure === "throws") f.doc.execCommand = () => {throw new Error("unsupported");};
    if (failure === "no edit") f.doc.execCommand = () => false;
    if (failure === "readonly") f.area.readOnly = true;
    if (failure === "disabled") f.area.disabled = true;
    if (failure === "blurred") f.doc.activeElement = {};
    assert.equal(f.apply(), false, failure);assert.equal(f.area.value, "red hair", failure);
    assert.equal(f.area.selectionStart, 2);assert.equal(f.area.selectionEnd, 4);
}
console.log("weight edit: native range edit, owner document, scroll, focus and unavailable-edit guards passed");
