"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../javascript/tagAutocomplete.js"), "utf8");
const utils = fs.readFileSync(path.join(__dirname, "../javascript/_utils.js"), "utf8");
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const event = (name, props = {}) => Object.assign(new Event(name, {cancelable: true}), props);
function fixture() {
    const classes = new Set();
    const area = Object.assign(new EventTarget(), {value: "blue", parentNode: {insertBefore() {}},
        classList: {contains: name => classes.has(name), add: name => classes.add(name)},
        focus() {}, setSelectionRange() {}});
    const calls = [], inserts = [];
    let visible = false;
    const context = {area, document: {activeElement: area}, isEnabled: () => true, isVisible: () => visible,
        performance: {now: () => 0}, setTimeout, clearTimeout, queueMicrotask,
        getTextAreaIdentifier: () => ".txt2img.p",
        TAC_CFG: {activeIn: {img2img: true, txt2img: true, negativePrompts: true, thirdParty: true}, delayTime: 20, keymap: {ChooseSelected: "Enter", ChooseFirstOrSelected: "Tab", MoveUp: "ArrowUp", MoveDown: "ArrowDown"}},
        selectedTag: 0, resultCount: 1, results: [{text: "blue_hair"}], tagword: "blue", tacSelfTrigger: false,
        createResultsDiv: () => ({}), hideResults: () => {visible = false; context.selectedTag = null;},
        updateRuby() {}, checkKeywordInsertionUndo() {}, updateSelectionStyle() {}, addResultsToList() {},
        insertTextAtCursor: (_area, result) => inserts.push(result.text),
        autocomplete: (_area, text, _fixed, generation) => {calls.push({text, generation}); visible = true; context.selectedTag = 0;},
    };
    vm.createContext(context);
    vm.runInContext(utils.slice(utils.indexOf("const debounce ="), utils.indexOf("// Difference function")), context);
    vm.runInContext(source.slice(source.indexOf("const autocompleteGenerations ="), source.indexOf("async function buildTagIndex(")), context);
    vm.runInContext(source.slice(source.indexOf("const tagWeightWheelLast ="), source.indexOf("async function refreshTacTempFiles(")), context);
    vm.runInContext(source.slice(source.indexOf("function addAutocompleteToArea("), source.indexOf("// One-time setup, triggered from onUiUpdate")), context);
    context.addAutocompleteToArea(area);
    return {area, context, calls, inserts, show() {visible = true; context.selectedTag = 0;}, visible: () => visible,
        key(key, props = {}) {const e = event("keydown", {key, ...props}); area.dispatchEvent(e); return e;}};
}
(async () => {
    for (const props of [{isComposing: true}, {keyCode: 229}]) {
        const f = fixture();
        for (const key of ["Enter", "Tab", "ArrowUp", "ArrowDown"]) {
            f.show(); const e = f.key(key, props);
            assert.equal(e.defaultPrevented, false); assert.equal(f.inserts.length, 0);
        }
    }
    {
        const f = fixture();f.show();
        f.area.dispatchEvent(event("input", {inputType: "insertText"}));
        const previous = f.context.nextAutocompleteGeneration(f.area);
        f.area.dispatchEvent(event("compositionstart"));
        assert.equal(f.visible(), false);
        assert.equal(f.context.isAutocompleteGenerationCurrent(f.area, previous), false);
        for (const key of ["Enter", "Tab", "ArrowUp", "ArrowDown"]) {
            f.show();assert.equal(f.key(key).defaultPrevented, false);
        }
        f.area.dispatchEvent(event("input", {inputType: "insertCompositionText", isComposing: true}));
        await wait(35);assert.equal(f.calls.length, 0);assert.equal(f.inserts.length, 0);
        f.area.value = "長髪";f.area.dispatchEvent(event("compositionend"));
        await wait(30);assert.equal(f.calls.length, 1);assert.equal(f.calls[0].text, "長髪");
        assert.equal(f.key("Enter").defaultPrevented, false);
        assert.equal(f.key("Tab").defaultPrevented, false);assert.equal(f.inserts.length, 0);
        f.area.dispatchEvent(event("keyup", {key: "Enter"}));
        assert.equal(f.key("Enter").defaultPrevented, true);assert.deepEqual(f.inserts, ["blue_hair"]);
    }
    {
        const f = fixture();f.area.dispatchEvent(event("compositionstart"));f.area.dispatchEvent(event("compositionend"));
        await wait(30);assert.equal(f.key("ArrowDown").defaultPrevented, true);
        assert.equal(f.key("Tab").defaultPrevented, true);assert.equal(f.inserts.length, 1);
    }
    {
        const f = fixture();f.area.dispatchEvent(event("compositionstart"));
        f.area.dispatchEvent(event("input", {inputType: "insertCompositionText", isComposing: false}));
        await wait(30);assert.equal(f.calls.length, 0);
        f.area.value = "長髪";f.area.dispatchEvent(event("compositionend"));
        f.area.dispatchEvent(event("input", {inputType: "insertText", isComposing: false}));
        await wait(35);assert.equal(f.calls.length, 1);assert.equal(f.calls[0].text, "長髪");
    }
    {
        // A mouse-confirmed composition has no confirmation keyup: do not block future Enter indefinitely.
        const f = fixture();f.area.dispatchEvent(event("compositionstart"));f.area.dispatchEvent(event("compositionend"));
        await wait(120);assert.equal(f.key("Enter").defaultPrevented, true);assert.equal(f.inserts.length, 1);
    }
    console.log("autocomplete IME: composition state, isComposing, 229, cancellation, confirmation key and independent navigation passed");
})().catch(error => {console.error(error); process.exitCode = 1;});
