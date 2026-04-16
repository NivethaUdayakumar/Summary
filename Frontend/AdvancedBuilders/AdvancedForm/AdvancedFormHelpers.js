(function (global) {
    // Resolve either a CSS selector or a direct DOM node into one element reference.
    function resolveElement(target) {
        if (typeof target === "string") {
            return document.querySelector(target);
        }
        return target || null;
    }

    // Normalize one value or many values into a predictable array.
    function normalizeArray(values) {
        if (values == null) {
            return [];
        }
        return Array.isArray(values) ? values : [values];
    }

    // Convert incoming values into a string Set for simple membership checks.
    function normalizeStringSet(values) {
        return new Set(
            normalizeArray(values)
                .filter(value => value != null)
                .map(value => String(value))
        );
    }

    // Build dropdown-ready {label, value} objects from strings or objects.
    function buildOptionList(optionValues, options) {
        var labelField = options.labelField || "label";
        var valueField = options.valueField || "value";

        return normalizeArray(optionValues).map(function (item) {
            if (item && typeof item === "object") {
                return {
                    label: item[labelField] != null ? String(item[labelField]) : "",
                    value: item[valueField] != null ? String(item[valueField]) : ""
                };
            }

            return {
                label: String(item),
                value: String(item)
            };
        });
    }

    // Refresh Semantic UI dropdown state when available, then emit a change event.
    function refreshDropdown(selectElement) {
        if (!global.jQuery) {
            selectElement.dispatchEvent(new Event("change", { bubbles: true }));
            return;
        }

        var jq = global.jQuery(selectElement);
        if (typeof jq.dropdown === "function") {
            jq.dropdown("refresh");
        }
        selectElement.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Check matching checkbox values inside one container and optionally clear the rest.
    function autoPopulateCheckboxes(containerTarget, selectedValues, options) {
        var settings = options || {};
        var container = resolveElement(containerTarget);
        if (!container) {
            throw new Error("Checkbox container not found");
        }

        var checkboxSelector = settings.checkboxSelector || 'input[type="checkbox"]';
        var checkedValues = normalizeStringSet(selectedValues);
        var clearMissing = settings.clearMissing !== false;
        var valueAttribute = settings.valueAttribute || "value";
        var checkboxes = container.querySelectorAll(checkboxSelector);

        checkboxes.forEach(function (checkbox) {
            var checkboxValue = checkbox.getAttribute(valueAttribute);
            if (checkboxValue == null) {
                checkboxValue = checkbox.value;
            }

            var shouldCheck = checkedValues.has(String(checkboxValue));
            if (shouldCheck) {
                checkbox.checked = true;
            } else if (clearMissing) {
                checkbox.checked = false;
            }
        });

        return checkboxes;
    }

    // Rebuild a select element from values, then apply any selected entries.
    function autoPopulateDropdown(selectTarget, optionValues, options) {
        var settings = options || {};
        var selectElement = resolveElement(selectTarget);
        if (!selectElement) {
            throw new Error("Dropdown element not found");
        }

        var selectedValues = normalizeStringSet(settings.selectedValues);
        var shouldClearOptions = settings.clearOptions !== false;
        var shouldKeepBlank = settings.keepBlankOption === true;
        var optionList = buildOptionList(optionValues, settings);

        if (shouldClearOptions) {
            selectElement.innerHTML = "";
            if (shouldKeepBlank) {
                selectElement.appendChild(new Option("", ""));
            }
        }

        optionList.forEach(function (item) {
            var option = new Option(item.label, item.value);
            option.selected = selectedValues.has(item.value);
            selectElement.appendChild(option);
        });

        refreshDropdown(selectElement);
        return selectElement;
    }

    // Select one or more existing dropdown options without rebuilding the list.
    function setDropdownValue(selectTarget, selectedValues) {
        var selectElement = resolveElement(selectTarget);
        if (!selectElement) {
            throw new Error("Dropdown element not found");
        }

        var selectedSet = normalizeStringSet(selectedValues);
        Array.from(selectElement.options).forEach(function (option) {
            option.selected = selectedSet.has(String(option.value));
        });

        refreshDropdown(selectElement);
        return selectElement;
    }

    global.AdvancedFormHelpers = {
        autoPopulateCheckboxes: autoPopulateCheckboxes,
        autoPopulateDropdown: autoPopulateDropdown,
        setDropdownValue: setDropdownValue
    };
})(window);
