// Utility functions to select text areas the script should work on,
// including third party options.
// Supported third party options so far:
// - Dataset Tag Editor

// Core text area selectors.
// Use descendant selectors (no '>') so they work with Gradio 4.39+ which inserts
// intermediate wrapper divs between the component root and the <label>/<textarea>.
const core = [
    "#txt2img_prompt textarea",
    "#img2img_prompt textarea",
    "#txt2img_neg_prompt textarea",
    "#img2img_neg_prompt textarea",
    "#txt2img_edit_style_prompt textarea",
    "#txt2img_edit_style_neg_prompt textarea",
    "#img2img_edit_style_prompt textarea",
    "#img2img_edit_style_neg_prompt textarea"
];

// Third party text area selectors
const thirdParty = {
    "dataset-tag-editor": {
        "base": "#tab_dataset_tag_editor_interface",
        "hasIds": false,
        "selectors": [
            "Caption of Selected Image",
            "Interrogate Result",
            "Edit Caption",
            "Edit Tags"
        ]
    },
    "image browser": {
        "base": "#tab_image_browser",
        "hasIds": false,
        "selectors": [
            "Filename keyword search",
            "EXIF keyword search"
        ]
    },
    "tab_tagger": {
        "base": "#tab_tagger",
        "hasIds": false,
        "selectors": [
            "Additional tags (split by comma)",
            "Exclude tags (split by comma)"
        ]
    },
    "tiled-diffusion-t2i": {
        "base": "#txt2img_script_container",
        "hasIds": true,
        "onDemand": true,
        "selectors": [
            "[id^=MD-t2i][id$=prompt] textarea",
            "[id^=MD-t2i][id$=prompt] input[type='text']"
        ]
    },
    "tiled-diffusion-i2i": {
        "base": "#img2img_script_container",
        "hasIds": true,
        "onDemand": true,
        "selectors": [
            "[id^=MD-i2i][id$=prompt] textarea",
            "[id^=MD-i2i][id$=prompt] input[type='text']"
        ]
    },
    "adetailer-t2i": {
        "base": "#txt2img_script_container",
        "hasIds": true,
        "onDemand": true,
        "selectors": [
            "[id^=script_txt2img_adetailer_ad_prompt] textarea",
            "[id^=script_txt2img_adetailer_ad_negative_prompt] textarea"
        ]
    },
    "adetailer-i2i": {
        "base": "#img2img_script_container",
        "hasIds": true,
        "onDemand": true,
        "selectors": [
            "[id^=script_img2img_adetailer_ad_prompt] textarea",
            "[id^=script_img2img_adetailer_ad_negative_prompt] textarea"
        ]
    },
    "deepdanbooru-object-recognition": {
        "base": "#tab_deepdanboru_object_recg_tab",
        "hasIds": false,
        "selectors": [
            "Found tags",
        ]
    },
    "TIPO": {
        "base": "#tab_txt2img",
        "hasIds": false,
        "selectors": [
            "Tag Prompt"
        ]
    }
}

function getTextAreas() {
    // First get all core text areas
    let textAreas = [...gradioApp().querySelectorAll(core.join(", "))];

    for (const [key, entry] of Object.entries(thirdParty)) {
        if (entry.hasIds) { // If the entry has proper ids, we can just select them
            textAreas = textAreas.concat([...gradioApp().querySelectorAll(entry.selectors.join(", "))]);
        } else { // Otherwise, we have to find the text areas by their adjacent labels
            let base = gradioApp().querySelector(entry.base);

            // Safety check
            if (!base) continue;

            let allTextAreas = [...base.querySelectorAll("textarea, input[type='text']")];

            // Filter the text areas where the adjacent label matches one of the selectors
            let matchingTextAreas = allTextAreas.filter(ta => [...ta.parentElement.childNodes].some(x => entry.selectors.includes(x.innerText)));
            textAreas = textAreas.concat(matchingTextAreas);
        }
    };

    return textAreas;
}

const onDemandObservers = new WeakMap();
function addOnDemandObservers(setupFunction) {
    function observeAccordion(acc, entry) {
        const existing = onDemandObservers.get(acc);
        if (existing) {
            existing.entries.add(entry);
            existing.setup = setupFunction;
            return;
        }
        const record = {entries: new Set([entry]), setup: setupFunction};
        const observer = new MutationObserver(mutations => {
            let addedElements = false;
            for (const mutation of mutations) {
                if (mutation.type !== "childList") continue;
                for (const child of mutation.removedNodes) {
                    if (child.nodeType !== 1) continue;
                    for (const node of [child, ...child.querySelectorAll(".gradio-accordion")]) {
                        const removed = onDemandObservers.get(node);
                        if (removed && !node.isConnected) {
                            removed.observer.disconnect();
                            onDemandObservers.delete(node);
                        }
                    }
                }
                for (const child of mutation.addedNodes) {
                    if (child.nodeType !== 1) continue;
                    addedElements = true;
                    const accordions = [...child.querySelectorAll(".gradio-accordion")];
                    if (child.classList.contains("gradio-accordion")) accordions.unshift(child);
                    for (const accordion of accordions) {
                        for (const owner of record.entries) observeAccordion(accordion, owner);
                    }
                }
            }
            if (!acc.isConnected) {
                observer.disconnect();
                onDemandObservers.delete(acc);
                return;
            }
            if (!addedElements) return;
            const areas = new Set();
            for (const owner of record.entries) {
                if (owner.hasIds) {
                    gradioApp().querySelectorAll(owner.selectors.join(", ")).forEach(area => areas.add(area));
                } else {
                    const base = gradioApp().querySelector(owner.base);
                    if (!base) continue;
                    base.querySelectorAll("textarea, input[type='text']").forEach(area => {
                        if ([...area.parentElement.childNodes].some(label => owner.selectors.includes(label.innerText))) {
                            areas.add(area);
                        }
                    });
                }
            }
            areas.forEach(area => record.setup(area));
        });
        record.observer = observer;
        onDemandObservers.set(acc, record);
        observer.observe(acc, {childList: true});
    }
    for (const [key, entry] of Object.entries(thirdParty)) {
        if (!entry.onDemand) continue;

        let base = gradioApp().querySelector(entry.base);
        if (!base) continue;

        base.querySelectorAll(".gradio-accordion").forEach(acc => observeAccordion(acc, entry));
    };
}

const thirdPartyIdSet = new Set();
// Get the identifier for the text area to differentiate between positive and negative
function getTextAreaIdentifier(textArea) {
    // Use descendant selectors to match Gradio 4.39+ DOM structure.
    let txt2img_p = gradioApp().querySelector('#txt2img_prompt textarea');
    let txt2img_n = gradioApp().querySelector('#txt2img_neg_prompt textarea');
    let img2img_p = gradioApp().querySelector('#img2img_prompt textarea');
    let img2img_n = gradioApp().querySelector('#img2img_neg_prompt textarea');

    let modifier = "";
    switch (textArea) {
        case txt2img_p:
            modifier = ".txt2img.p";
            break;
        case txt2img_n:
            modifier = ".txt2img.n";
            break;
        case img2img_p:
            modifier = ".img2img.p";
            break;
        case img2img_n:
            modifier = ".img2img.n";
            break;
        default:
            // If the text area is not a core text area, it must be a third party text area
            // Add it to the set of third party text areas and get its index as a unique identifier
            if (!thirdPartyIdSet.has(textArea))
                thirdPartyIdSet.add(textArea);

            modifier = `.thirdParty.ta${[...thirdPartyIdSet].indexOf(textArea)}`;
            break;
    }
    return modifier;
}
