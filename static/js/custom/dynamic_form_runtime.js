/**
 * Dynamic form runtime.
 *
 * Powers the schema-driven forms (mobile registration screens and the detail-page
 * "Form Preview" panels) with two behaviours:
 *   1. Cascading administrative-level selects (AJAX driven).
 *   2. Conditional field display (show/hide + toggle `required`) based on the
 *      `data-conditional` / `data-conditions` attributes emitted by the form parser.
 *
 * Django-provided values are read from `window.DynamicFormConfig`:
 *   {
 *     adminLevels:          [{ order, name }, ...],
 *     rootUrl:              "...",   // administrative-unit-root
 *     childrenUrlTemplate:  "...",   // administrative-level-children, pk=9999 placeholder
 *     ancestorsUrlTemplate: "...",   // administrative-unit-ancestors, pk=9999 placeholder
 *     parentFormData:       { field_name: value, ... }   // optional, for cross-form conditionals
 *   }
 */
$(document).ready(function () {

    const cfg = window.DynamicFormConfig || {};
    const adminLevels = cfg.adminLevels || [];
    const rootUrl = cfg.rootUrl;
    const childrenUrlTemplate = cfg.childrenUrlTemplate;
    const ancestorsUrlTemplate = cfg.ancestorsUrlTemplate;
    let parentFormData = cfg.parentFormData || {};

    // The custom file-input plugin is only loaded on the mobile screens; guard the call
    // so the desktop preview (which doesn't load it) doesn't error.
    if (window.bsCustomFileInput) {
        bsCustomFileInput.init();
    }

    function getChildrenUrl(parentId) {
        return childrenUrlTemplate.replace('9999', parentId);
    }
    function getAncestorsUrl(unitId) {
        return ancestorsUrlTemplate.replace('9999', unitId);
    }

    // ── Cascading Administrative Level Selects ──────────────────────────────
    if (rootUrl) {
        $('select[data-field-type="administrative_level"]').each(function () {
            const $originalSelect = $(this);
            const initialValue = $originalSelect.val();
            const maxLevelOrder = parseInt($originalSelect.data('max-level-order')) || 0;

            // When the field is restricted to the user's assigned administrative units, the
            // server has already filtered the <select> options to those units (+ descendants).
            // Keep that native select (just make it searchable) instead of building the cascade,
            // which loads the full tree from the API and would ignore the restriction.
            const restrictToAssigned = String($originalSelect.data('admin-level-restriction')) === 'true';
            if (restrictToAssigned) {
                if ($originalSelect.data('select2')) {
                    $originalSelect.select2('destroy');
                }
                $originalSelect.select2({ width: '100%' });
                return;
            }

            // Filter admin levels by max order if set
            const effectiveLevels = maxLevelOrder
                ? adminLevels.filter(function (l) { return l.order <= maxLevelOrder; })
                : adminLevels;

            // Destroy select2 on the original select if applied
            if ($originalSelect.data('select2')) {
                $originalSelect.select2('destroy');
            }
            // Hide original select, keep it as hidden input carrier
            $originalSelect.hide();

            // Build cascading selects container
            const $container = $('<div class="cascading-admin-selects"></div>');
            $originalSelect.after($container);

            effectiveLevels.forEach(function (level) {
                const $wrapper = $('<div class="au-select-wrapper mb-2" data-level-order="' + level.order + '" style="display:none;"></div>');
                const $sel = $('<select class="form-control au-cascade-select" data-level-order="' + level.order + '" data-level-name="' + level.name + '">' +
                    '<option value="">-- ' + level.name + ' --</option></select>');
                $wrapper.append($sel);
                $container.append($wrapper);
            });

            function showSelect(order) {
                const $wrapper = $container.find('.au-select-wrapper[data-level-order="' + order + '"]');
                $wrapper.show();
                const $sel = $wrapper.find('.au-cascade-select');
                if ($sel.data('select2')) $sel.select2('destroy');
                $sel.select2({ width: '100%' });
            }

            function hideAfterOrder(order) {
                $container.find('.au-select-wrapper').each(function () {
                    if ($(this).data('level-order') > order) {
                        const $sel = $(this).find('.au-cascade-select');
                        if ($sel.data('select2')) $sel.select2('destroy');
                        const levelName = $sel.data('level-name');
                        $sel.html('<option value="">-- ' + levelName + ' --</option>');
                        $(this).hide();
                    }
                });
            }

            function loadRootUnits(callback) {
                $.ajax({
                    url: rootUrl,
                    success: function (data) {
                        const $sel = $container.find('.au-cascade-select[data-level-order="1"]');
                        const levelName = $sel.data('level-name');
                        $sel.html('<option value="">-- ' + levelName + ' --</option>');
                        $.each(data, function () {
                            $sel.append($('<option>').val(this.id).text(this.name));
                        });
                        showSelect(1);
                        if (callback) callback();
                    }
                });
            }

            function loadChildren(parentId, targetOrder, callback) {
                $.ajax({
                    url: getChildrenUrl(parentId),
                    success: function (data) {
                        if (data.length > 0) {
                            const $sel = $container.find('.au-cascade-select[data-level-order="' + targetOrder + '"]');
                            const levelName = $sel.data('level-name');
                            $sel.html('<option value="">-- ' + levelName + ' --</option>');
                            $.each(data, function () {
                                $sel.append($('<option>').val(this.id).text(this.name));
                            });
                            showSelect(targetOrder);
                        }
                        if (callback) callback();
                    }
                });
            }

            // Update the original hidden select when cascading changes
            function syncOriginal() {
                let lastVal = '';
                $container.find('.au-select-wrapper:visible .au-cascade-select').each(function () {
                    if ($(this).val()) lastVal = $(this).val();
                });
                $originalSelect.val(lastVal);
            }

            $container.on('change', '.au-cascade-select', function () {
                const currentOrder = $(this).data('level-order');
                const selectedValue = $(this).val();
                hideAfterOrder(currentOrder);
                const nextOrder = currentOrder + 1;
                if (selectedValue && (!maxLevelOrder || nextOrder <= maxLevelOrder)) {
                    loadChildren(selectedValue, nextOrder);
                }
                syncOriginal();
            });

            // Initialize: load root, then restore initial value if editing
            loadRootUnits(function () {
                if (initialValue) {
                    $.ajax({
                        url: getAncestorsUrl(initialValue),
                        success: function (resp) {
                            const chain = resp.chain || [];
                            let i = 0;
                            function selectNext() {
                                if (i >= chain.length) return;
                                const node = chain[i];
                                // Skip levels beyond max order
                                if (maxLevelOrder && node.level_order > maxLevelOrder) return;
                                const $sel = $container.find('.au-cascade-select[data-level-order="' + node.level_order + '"]');
                                $sel.val(String(node.id));
                                if ($sel.data('select2')) {
                                    $sel.trigger('change.select2');
                                }
                                i++;
                                if (i < chain.length && (!maxLevelOrder || chain[i].level_order <= maxLevelOrder)) {
                                    loadChildren(node.id, chain[i].level_order, selectNext);
                                } else {
                                    syncOriginal();
                                }
                            }
                            selectNext();
                        }
                    });
                }
            });
        });
    }

    // ── Conditional Field Display ───────────────────────────────────────────

    // Initialize conditional display on page load
    initConditionalDisplay();

    // Re-evaluate whenever any form field changes
    $('form').on('change keyup', 'input, select, textarea', function () {
        evaluateAllConditionalFields();
    });

    function initConditionalDisplay() {
        // Evaluate all conditions on load
        evaluateAllConditionalFields();
    }

    function evaluateAllConditionalFields() {
        $('[data-conditional="true"]').each(function () {
            const $field = $(this);
            const $formGroup = $field.closest('.form-group, .custom-file');

            // Check if field has multiple conditions (new format)
            const conditionsData = $field.data('conditions');

            if (conditionsData) {
                // Multiple conditions
                const shouldShow = evaluateMultipleConditions(conditionsData);

                if (shouldShow) {
                    $formGroup.slideDown(200);
                    if ($field.data('originally-required')) {
                        $field.prop('required', true);
                    }
                } else {
                    $formGroup.slideUp(200);
                    if ($field.prop('required')) {
                        $field.data('originally-required', true);
                        $field.prop('required', false);
                    }
                    clearFieldValue($field);
                }
            } else {
                // Single condition (legacy format)
                const dependsOn = $field.data('depends-on');
                const operator = $field.data('depends-operator');
                const expectedValue = String($field.data('depends-value'));
                const isParentForm = $field.data('is-parent-form') === 'true' || $field.data('is-parent-form') === true;

                if (!dependsOn) {
                    return;
                }

                let actualValue;

                if (isParentForm) {
                    actualValue = parentFormData[dependsOn];

                    if (actualValue === undefined || actualValue === null) {
                        $formGroup.hide();
                        return;
                    }
                } else {
                    const $dependentField = $(`[name="${dependsOn}"]`);

                    if ($dependentField.length === 0) {
                        $formGroup.hide();
                        return;
                    }

                    actualValue = getFieldValue($dependentField);
                }

                const shouldShow = evaluateCondition(String(actualValue), operator, expectedValue);

                if (shouldShow) {
                    $formGroup.slideDown(200);
                    if ($field.data('originally-required')) {
                        $field.prop('required', true);
                    }
                } else {
                    $formGroup.slideUp(200);
                    if ($field.prop('required')) {
                        $field.data('originally-required', true);
                        $field.prop('required', false);
                    }
                    clearFieldValue($field);
                }
            }
        });
    }

    /**
     * Evaluate multiple conditions with AND/OR logic.
     */
    function evaluateMultipleConditions(conditions) {
        if (!conditions || conditions.length === 0) {
            return true;
        }

        const results = [];

        for (let i = 0; i < conditions.length; i++) {
            const condition = conditions[i];
            const field = condition.field;
            const operator = condition.operator;
            const expectedValue = String(condition.value);
            const isParentForm = condition.is_parent_form === true;

            let actualValue;

            if (isParentForm) {
                actualValue = parentFormData[field];

                if (actualValue === undefined || actualValue === null) {
                    return false;
                }
            } else {
                const $dependentField = $(`[name="${field}"]`);

                if ($dependentField.length === 0) {
                    return false;
                }

                actualValue = getFieldValue($dependentField);
            }

            const result = evaluateCondition(String(actualValue), operator, expectedValue);
            results.push(result);
        }

        // Apply AND/OR logic
        let finalResult = results[0];

        for (let i = 0; i < conditions.length - 1; i++) {
            const logic = conditions[i].logic || 'AND';
            const nextResult = results[i + 1];

            if (logic === 'AND') {
                finalResult = finalResult && nextResult;
            } else if (logic === 'OR') {
                finalResult = finalResult || nextResult;
            }
        }

        return finalResult;
    }

    /**
     * Get the value of a field (handles different input types).
     */
    function getFieldValue($field) {
        if ($field.is(':checkbox')) {
            return $field.is(':checked') ? 'true' : 'false';
        } else if ($field.is(':radio')) {
            return $field.filter(':checked').val() || '';
        } else if ($field.is('select[multiple]')) {
            return $field.val() || [];
        } else {
            return $field.val() || '';
        }
    }

    /**
     * Evaluate a conditional expression.
     */
    function evaluateCondition(actualValue, operator, expectedValue) {
        if (actualValue === 'undefined' || actualValue === 'null' || actualValue === '') {
            return false;
        }

        switch (operator) {
            case 'equals':
                return actualValue === expectedValue;

            case 'not_equals':
                return actualValue !== expectedValue;

            case 'contains':
                return actualValue.toLowerCase().includes(expectedValue.toLowerCase());

            case 'greater_than':
                try {
                    return parseFloat(actualValue) > parseFloat(expectedValue);
                } catch (e) {
                    return false;
                }

            case 'less_than':
                try {
                    return parseFloat(actualValue) < parseFloat(expectedValue);
                } catch (e) {
                    return false;
                }

            case 'greater_or_equal':
                try {
                    return parseFloat(actualValue) >= parseFloat(expectedValue);
                } catch (e) {
                    return false;
                }

            case 'less_or_equal':
                try {
                    return parseFloat(actualValue) <= parseFloat(expectedValue);
                } catch (e) {
                    return false;
                }

            case 'between':
                try {
                    const [minVal, maxVal] = expectedValue.split(',').map(v => parseFloat(v.trim()));
                    const fieldVal = parseFloat(actualValue);
                    return fieldVal >= minVal && fieldVal <= maxVal;
                } catch (e) {
                    return false;
                }

            default:
                console.warn(`Unknown operator: ${operator}`);
                return false;
        }
    }

    /**
     * Clear the value of a field.
     */
    function clearFieldValue($field) {
        const fieldType = $field.attr('type');

        if (fieldType === 'checkbox' || fieldType === 'radio') {
            $field.prop('checked', false);
        } else if ($field.is('select')) {
            $field.val('').trigger('change');
        } else {
            $field.val('');
        }
    }

    // Expose for debugging / external triggers
    window.FormConditionalDisplay = {
        evaluateAllConditionalFields: evaluateAllConditionalFields,
        evaluateCondition: evaluateCondition,
        setParentFormData: function (data) {
            parentFormData = data;
            evaluateAllConditionalFields();
        }
    };

});
