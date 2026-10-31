"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../javascript/_textAreas.js"), "utf8");
const element = (accordion = false, children = []) => ({nodeType: 1, isConnected: true,
    classList: {contains: name => accordion && name === "gradio-accordion"},
    querySelectorAll: () => children,
});
const outer = element(true), observers = [], registrations = [];
const areaA = {}, areaB = {}, areaShared = {};
const byLabel = {parentElement: {childNodes: [{innerText: "Prompt"}]}};
const labeledBase = {querySelectorAll: selector => selector === ".gradio-accordion" ? [outer] : [byLabel]};
const entries = {a: {onDemand: true, base: "#base", hasIds: true, selectors: ["#a"]},
    b: {onDemand: true, base: "#base", hasIds: true, selectors: ["#b"]},
    labeled: {onDemand: true, base: "#labeled", hasIds: false, selectors: ["Prompt"]}};
const root = {querySelector: selector => selector === "#labeled" ? labeledBase : {querySelectorAll: () => [outer]},
    querySelectorAll: selector => selector === "#a" ? [areaA, areaShared] : [areaB, areaShared]};
const context = {thirdParty: entries, gradioApp: () => root,
    MutationObserver: class {
        constructor(callback) {this.callback = callback;this.disconnected = false;observers.push(this);}
        observe(node) {this.node = node;}
        disconnect() {this.disconnected = true;}
    },
};
vm.createContext(context);
const start = source.indexOf("const onDemandObservers =");
vm.runInContext(source.slice(start < 0 ? source.indexOf("function addOnDemandObservers(") : start, source.indexOf("const thirdPartyIdSet")), context);
const setup = area => registrations.push(area);
const change = (addedNodes = [], removedNodes = []) => ({type: "childList", addedNodes, removedNodes});
context.addOnDemandObservers(setup);context.addOnDemandObservers(setup);
assert.equal(observers.length, 1, "overlapping owners and repeat setup share the accordion observer");
observers[0].callback([change([{nodeType: 3}])]);assert.equal(registrations.length, 0);
observers[0].callback([change([{nodeType: 3}, element()])]);
assert.deepEqual(new Set(registrations), new Set([areaA, areaB, areaShared, byLabel]));
assert.equal(registrations.length, 4);
const nested = element(true), deeper = element(true), wrapper = element(false, [deeper]);
observers[0].callback([change([nested, wrapper])]);assert.equal(observers.length, 3);
observers[1].callback([change([element()])]);
assert.equal(registrations.length, 12, "nested observers retain every owner");
nested.isConnected = false;deeper.isConnected = false;
observers[0].callback([change([], [nested, wrapper])]);
assert.equal(observers[1].disconnected, true);assert.equal(observers[2].disconnected, true);
nested.isConnected = true;
observers[0].callback([change([nested])]);assert.equal(observers.length, 4, "reinserted accordions get a fresh observer");
observers[0].callback([change([], [nested])]);assert.equal(observers[3].disconnected, false, "connected moves keep their observer");
outer.isConnected = false;observers[0].callback([change()]);assert.equal(observers[0].disconnected, true);
console.log("on-demand observers: text nodes, shared owners, nested insertion, removal and reinsertion passed");
