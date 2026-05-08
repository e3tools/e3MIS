$(document).ready(function () {

    // =========================================================================
    // Constants
    // =========================================================================

    const OPERATOR_DISPLAY = {
        'equals': '=',
        'not_equals': '\u2260',
        'contains': 'contains',
        'greater_than': '>',
        'less_than': '<',
        'between': 'between'
    };

    const OPERATOR_OPTIONS = [
        { value: 'equals', label: 'Equals (=)' },
        { value: 'not_equals', label: 'Not Equals (\u2260)' },
        { value: 'contains', label: 'Contains' },
        { value: 'greater_than', label: 'Greater Than (>)' },
        { value: 'less_than', label: 'Less Than (<)' },
        { value: 'between', label: 'Between' }
    ];

    function createEmptyPage() {
        return {
            page: { type: "object", required: [], properties: {} },
            options: { fields: {} }
        };
    }

    // =========================================================================
    // SchemaForm
    // =========================================================================

    const SchemaForm = {

        // -- State ------------------------------------------------------------
        formSchema: { form: [createEmptyPage()] },
        currentPageIndex: 0,
        editingFieldName: null,
        identifierField: null,
        parentFormFields: [],
        currentConditions: [],
        allFollowUpEventSchemas: {},
        allTrackableObjectSchemas: {},

        // =====================================================================
        // Initialization
        // =====================================================================

        init() {
            this.pageContainer = $("#pages-container");
            this.configTextarea = $("#config_schema");
            this.identifierField = this.configTextarea.data("identifier");

            this.loadAllAvailableSchemas();
            this.loadParentFormFields();
            this.loadExistingSchema();
            this.renderAllPages();
            this.watchDependenciesField();
            this.watchTrackableObjectsField();
            this.bindEvents();
        },

        bindEvents() {
            $("#add-page-btn").on("click", () => this.addPage());

            $("#add-text-field").on("click", () => {
                this.editingFieldName = null;
                this.resetFieldModal();
                this.populateConditionalFieldOptions();
                $('#addFieldModal').modal('show');
            });

            $("#field-type-input").on("change", () => this.toggleFieldTypeOptions());

            $("#enable-conditional").on("change", (e) => {
                $("#conditional-display-group").toggle(e.target.checked);
            });

            $("#conditional-field-select").on("change", () => {
                $("#conditional-operator-group-form").show();
                this.populateConditionalValues();
            });

            $("#field-label-input").on("input", () => {
                $("#field-name-input").val(this.slugify($("#field-label-input").val()));
            });

            $("#field-name-input").on("input", (e) => {
                const input = $(e.target);
                const slugified = this.slugify(input.val());
                if (input.val() !== slugified) input.val(slugified);
            });

            $("#save-field-btn").on("click", () => this.saveField());
            $("#add-condition-btn").on("click", () => this.addNewCondition());

            const form = $("form");
            if (form.length) {
                form.on("submit", () => {
                    console.log("Submitting schema:", this.formSchema);
                    this.updateSchemaTextarea();
                });
            }
        },

        // =====================================================================
        // Schema Loading & Validation
        // =====================================================================

        loadExistingSchema() {
            const raw = this.configTextarea.val().trim();
            if (raw) {
                try {
                    const parsed = JSON.parse(raw);
                    if (this.isValidSchema(parsed)) {
                        this.formSchema = parsed;
                        this.sortFieldsByOrder();
                    }
                } catch (e) {
                    console.error("Error parsing existing schema:", e);
                }
            }

            if (typeof window.existingSchema !== 'undefined' && window.existingSchema) {
                try {
                    if (this.isValidSchema(window.existingSchema)) {
                        this.formSchema = window.existingSchema;
                        this.sortFieldsByOrder();
                    }
                } catch (e) {
                    console.error("Error loading schema from window.existingSchema:", e);
                }
            }
        },

        loadAllAvailableSchemas() {
            if (typeof window.allFollowUpEventSchemas !== 'undefined') {
                this.allFollowUpEventSchemas = window.allFollowUpEventSchemas;
            }
            if (typeof window.allTrackableObjectSchemas !== 'undefined') {
                this.allTrackableObjectSchemas = window.allTrackableObjectSchemas;
            }
        },

        isValidSchema(schema) {
            if (!schema || typeof schema !== 'object') return false;
            if (!Array.isArray(schema.form) || schema.form.length === 0) return false;

            for (const page of schema.form) {
                if (!page.page || typeof page.page !== 'object') return false;
                if (!page.options || typeof page.options !== 'object') return false;
                if (!page.page.properties || typeof page.page.properties !== 'object') return false;
                if (!Array.isArray(page.page.required)) return false;
                if (!page.options.fields || typeof page.options.fields !== 'object') return false;
            }
            return true;
        },

        setSchema(schema) {
            if (this.isValidSchema(schema)) {
                this.formSchema = schema;
                this.currentPageIndex = 0;
                this.renderAllPages();
            } else {
                console.error("Invalid schema provided to setSchema");
            }
        },

        updateSchemaTextarea() {
            this.configTextarea.val(JSON.stringify(this.formSchema));
        },

        // =====================================================================
        // Parent Form & Dependencies
        // =====================================================================

        loadParentFormFields() {
            if (typeof window.parentFormSchema === 'undefined' || !window.parentFormSchema) return;

            try {
                const parentSchema = window.parentFormSchema;
                if (parentSchema.form && parentSchema.form.length > 0) {
                    parentSchema.form.forEach((page, pageIndex) => {
                        this.extractFieldsFromPage(page, pageIndex, null);
                    });
                }
            } catch (e) {
                console.error("Error loading parent form fields:", e);
            }
        },

        watchDependenciesField() {
            const $field = $('select[name="dependencies"]');
            if ($field.length === 0) return;

            $field.on('change', () => this.updateParentFormFields());
            this.updateParentFormFields();
        },

        watchTrackableObjectsField() {
            const $field = $('select[name="trackable_objects"]');
            if ($field.length === 0) return;

            $field.on('change', () => this.updateParentFormFields());
            setTimeout(() => this.updateParentFormFields(), 500);
        },

        updateParentFormFields() {
            this.parentFormFields = [];

            const selectedDeps = $('select[name="dependencies"]').val() || [];
            selectedDeps.forEach(depId => {
                const schema = this.allFollowUpEventSchemas[depId];
                if (schema) this.extractFieldsFromSchema(schema, `FollowUpEvent: ${schema.name}`);
            });

            const selectedObjs = $('select[name="trackable_objects"]').val() || [];
            selectedObjs.forEach(objId => {
                const schema = this.allTrackableObjectSchemas[objId];
                if (schema) this.extractFieldsFromSchema(schema, `TrackableObject: ${schema.name}`);
            });
        },

        extractFieldsFromSchema(schemaData, sourceName) {
            try {
                const schema = schemaData.schema;
                if (!schema || !schema.form || schema.form.length === 0) return;

                schema.form.forEach((page, pageIndex) => {
                    this.extractFieldsFromPage(page, pageIndex, sourceName);
                });
            } catch (e) {
                console.error(`Error extracting fields from ${sourceName}:`, e);
            }
        },

        extractFieldsFromPage(page, pageIndex, sourceName) {
            const properties = page.page.properties || {};
            const options = page.options.fields || {};

            Object.keys(properties).forEach(fieldName => {
                const fieldSchema = properties[fieldName];
                const fieldOptions = options[fieldName] || {};

                this.parentFormFields.push({
                    name: fieldName,
                    label: fieldOptions.label || fieldName,
                    type: fieldSchema.type,
                    enum: fieldSchema.enum,
                    multi: fieldSchema.multi,
                    format: fieldSchema.format,
                    pageIndex: pageIndex,
                    source: sourceName
                });
            });
        },

        // =====================================================================
        // Page Management
        // =====================================================================

        addPage() {
            this.formSchema.form.push(createEmptyPage());
            this.currentPageIndex = this.formSchema.form.length - 1;
            this.renderAllPages();
        },

        switchToPage(index) {
            this.currentPageIndex = index;
            this.renderAllPages();
        },

        // =====================================================================
        // Field CRUD
        // =====================================================================

        saveField() {
            const fieldName = $("#field-name-input").val().trim();
            const fieldType = $("#field-type-input").val();
            const isRequired = $("#btn-required-yes").hasClass("active");

            if (!fieldName) {
                alert("Field name cannot be empty.");
                return;
            }

            const currentPage = this.formSchema.form[this.currentPageIndex];

            if (fieldName in currentPage.page.properties && fieldName !== this.editingFieldName) {
                alert("Field name already exists in this page.");
                return;
            }

            let fieldPosition = null;
            if (this.editingFieldName) {
                const fieldNames = Object.keys(currentPage.page.properties);
                fieldPosition = fieldNames.indexOf(this.editingFieldName);
                this.removeFieldSilently(this.editingFieldName);
            }

            this.addField(fieldName, fieldType, isRequired, fieldPosition);

            $("#field-name-input").prop('disabled', false);
            this.editingFieldName = null;
            $('#addFieldModal').modal('hide');
        },

        addField(fieldName, fieldType, isRequired, insertAtPosition = null) {
            const page = this.formSchema.form[this.currentPageIndex];

            const newFieldSchema = this.buildFieldSchema(fieldType);
            if (!newFieldSchema) return;

            const newFieldOptions = this.buildFieldOptions(fieldName);

            if (insertAtPosition !== null && insertAtPosition >= 0) {
                const fieldNames = Object.keys(page.page.properties);
                const newProperties = {};
                const newFields = {};

                fieldNames.forEach((name, index) => {
                    if (index === insertAtPosition) {
                        newProperties[fieldName] = newFieldSchema;
                        newFields[fieldName] = newFieldOptions;
                    }
                    newProperties[name] = page.page.properties[name];
                    newFields[name] = page.options.fields[name];
                });

                if (insertAtPosition >= fieldNames.length) {
                    newProperties[fieldName] = newFieldSchema;
                    newFields[fieldName] = newFieldOptions;
                }

                page.page.properties = newProperties;
                page.options.fields = newFields;
            } else {
                page.page.properties[fieldName] = newFieldSchema;
                page.options.fields[fieldName] = newFieldOptions;
            }

            if (isRequired) {
                if (!page.page.required.includes(fieldName)) {
                    page.page.required.push(fieldName);
                }
            } else {
                page.page.required = page.page.required.filter(f => f !== fieldName);
            }

            this.updateFieldOrder();
            this.renderAllPages();
        },

        editField(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldSchema = page.page.properties[fieldName];
            const fieldOptions = page.options.fields[fieldName];

            this.editingFieldName = fieldName;

            $("#field-name-input").val(fieldName);
            $("#field-label-input").val(fieldOptions.label || "");
            $("#field-help-input").val(fieldOptions.help || "");
            $("#field-placeholder-input").val(fieldOptions.placeholder || "");

            // Determine and set field type
            let fieldType = fieldSchema.type;
            if (fieldSchema.enum) {
                fieldType = "enum";
                $("#enum-options-input").val(fieldSchema.enum.join(", "));
                this.setActiveButton("btn-enum", fieldSchema.display === "radio" ? "radio" : "select");
            } else if (fieldSchema.multi) {
                fieldType = "multi";
                $("#enum-options-input").val(fieldSchema.multi.join(", "));
                this.setActiveButton("btn-multi", fieldSchema.display === "checkboxes" ? "checkboxes" : "select");
            } else if (fieldSchema.format === "date") {
                fieldType = "date";
            } else if (fieldSchema.type === "integer" || fieldSchema.type === "number") {
                fieldType = "number";
                this.setActiveButton("btn-number", fieldSchema.type === "number" ? "decimal" : "integer");
            }
            $("#field-type-input").val(fieldType);

            // Text display option
            if (fieldSchema.type === "string" && !fieldSchema.enum && !fieldSchema.multi && fieldSchema.format !== "date") {
                this.setActiveButton("btn-text", fieldSchema.display === "textarea" ? "textarea" : "input");
            }

            // Required status
            const isRequired = page.page.required.includes(fieldName);
            this.setActiveButton("btn-required", isRequired ? "yes" : "no");

            // Populate validators
            if (fieldSchema.validators) {
                $("#min-length-input").val(fieldSchema.validators.min_length ?? "");
                $("#max-length-input").val(fieldSchema.validators.max_length ?? "");
                $("#min-number-input").val(fieldSchema.validators.min_value ?? "");
                $("#max-number-input").val(fieldSchema.validators.max_value ?? "");
                $("#min-date-input").val(fieldSchema.validators.min || "");
                $("#max-date-input").val(fieldSchema.validators.max || "");

                if (fieldSchema.validators.trackable_object_id) {
                    $("#trackable-object-restriction-input").val(fieldSchema.validators.trackable_object_id);
                }
                if (fieldSchema.validators.administrative_level_restriction) {
                    this.setActiveButton("btn-trackable-object-adm-lvl", "yes");
                } else {
                    this.setActiveButton("btn-trackable-object-adm-lvl", "no");
                }
            }

            // Administrative level restrictions
            if (fieldSchema.type === "administrative_level" && fieldSchema.validators) {
                this.setActiveButton(
                    "btn-admin-level-restriction",
                    fieldSchema.validators.administrative_level_restriction === "true" ? "yes" : "no"
                );
            }

            // Populate conditional field options before loading conditions
            this.populateConditionalFieldOptions();

            // Load conditions
            this.currentConditions = [];
            if (fieldOptions.dependencies && fieldOptions.dependencies.conditions) {
                fieldOptions.dependencies.conditions.forEach(cond => {
                    this.currentConditions.push({
                        field: cond.field,
                        field_label: this.getFieldLabelForCondition(cond.field, cond.is_parent_form),
                        operator: cond.operator,
                        value: cond.value,
                        is_parent_form: cond.is_parent_form,
                        logic: cond.logic
                    });
                });
                $("#enable-conditional").prop("checked", true);
                $("#conditional-display-group").show();
                this.renderConditionsList();
            } else if (fieldOptions.dependencies) {
                // Legacy single-condition format
                const depFieldName = Object.keys(fieldOptions.dependencies)[0];
                const depConfig = fieldOptions.dependencies[depFieldName];
                this.currentConditions = [{
                    field: depFieldName,
                    field_label: this.getFieldLabelForCondition(depFieldName, depConfig.is_parent_form),
                    operator: depConfig.operator,
                    value: depConfig.value,
                    is_parent_form: depConfig.is_parent_form,
                    logic: 'AND'
                }];
                $("#enable-conditional").prop("checked", true);
                $("#conditional-display-group").show();
                this.renderConditionsList();
            } else {
                $("#enable-conditional").prop("checked", false);
                $("#conditional-display-group").hide();
            }

            this.toggleFieldTypeOptions();

            $("#addFieldModalLabel").text("Edit Field");
            $("#save-field-btn").text("Update Field");
            $('#addFieldModal').modal('show');
        },

        removeField(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldLabel = page.options.fields[fieldName]?.label || fieldName;

            if (!confirm(`Are you sure you want to remove the field "${fieldLabel}"?`)) return;

            // Check for dependent fields
            const dependentFields = [];
            for (const [otherName, otherOpts] of Object.entries(page.options.fields)) {
                if (otherName !== fieldName && otherOpts.dependencies) {
                    if (Object.keys(otherOpts.dependencies).includes(fieldName)) {
                        dependentFields.push(otherOpts.label || otherName);
                    }
                }
            }

            if (dependentFields.length > 0) {
                const proceed = confirm(
                    `Warning: The following fields have conditional display rules that depend on "${fieldLabel}":\n\n` +
                    `${dependentFields.join(", ")}\n\n` +
                    `These conditional rules will be removed. Continue?`
                );
                if (!proceed) return;

                for (const [otherName, otherOpts] of Object.entries(page.options.fields)) {
                    if (otherName !== fieldName && otherOpts.dependencies) {
                        if (Object.keys(otherOpts.dependencies).includes(fieldName)) {
                            delete otherOpts.dependencies;
                        }
                    }
                }
            }

            delete page.page.properties[fieldName];
            delete page.options.fields[fieldName];
            page.page.required = page.page.required.filter(f => f !== fieldName);
            this.renderAllPages();
        },

        removeFieldSilently(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            delete page.page.properties[fieldName];
            delete page.options.fields[fieldName];
            page.page.required = page.page.required.filter(f => f !== fieldName);
        },

        duplicateField(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldSchema = page.page.properties[fieldName];
            const fieldOptions = page.options.fields[fieldName];
            const isRequired = page.page.required.includes(fieldName);
            const originalLabel = fieldOptions.label || fieldName;

            let newFieldName = `${fieldName}_copy`;
            let counter = 1;
            while (newFieldName in page.page.properties) {
                counter++;
                newFieldName = `${fieldName}_copy${counter}`;
            }

            if (!confirm(`Duplicate field "${originalLabel}"?\n\nThe new field will be named "${newFieldName}" and can be edited afterward.`)) {
                return;
            }

            page.page.properties[newFieldName] = JSON.parse(JSON.stringify(fieldSchema));
            page.options.fields[newFieldName] = JSON.parse(JSON.stringify(fieldOptions));
            page.options.fields[newFieldName].label = `${originalLabel} (Copy)`;

            if (isRequired) {
                page.page.required.push(newFieldName);
            }

            this.renderAllPages();
        },

        // =====================================================================
        // Field Schema Builders
        // =====================================================================

        buildFieldSchema(fieldType) {
            switch (fieldType) {
                case "enum": {
                    const options = this.parseCommaSeparated($("#enum-options-input").val());
                    if (options.length === 0) {
                        alert("You must provide at least one dropdown option.");
                        return null;
                    }
                    return {
                        type: "string",
                        enum: options,
                        display: $("#btn-enum-radio").hasClass("active") ? "radio" : "select"
                    };
                }
                case "multi": {
                    const options = this.parseCommaSeparated($("#enum-options-input").val());
                    if (options.length === 0) {
                        alert("You must provide at least one multiselect option.");
                        return null;
                    }
                    return {
                        type: "string",
                        multi: options,
                        display: $("#btn-multi-checkboxes").hasClass("active") ? "checkboxes" : "select"
                    };
                }
                case "date": {
                    const schema = { type: "string", format: "date", validators: {} };
                    const minDate = $("#min-date-input").val().trim();
                    const maxDate = $("#max-date-input").val().trim();
                    if (minDate) schema.validators.min = minDate;
                    if (maxDate) schema.validators.max = maxDate;
                    return schema;
                }
                case "string": {
                    const display = $("#btn-text-textarea").hasClass("active") ? "textarea" : "input";
                    const schema = { type: fieldType, display: display, validators: {} };
                    const minLen = $("#min-length-input").val().trim();
                    const maxLen = $("#max-length-input").val().trim();
                    if (minLen && !isNaN(minLen)) schema.validators.min_length = parseInt(minLen);
                    if (maxLen && !isNaN(maxLen)) schema.validators.max_length = parseInt(maxLen);
                    return schema;
                }
                case "number": {
                    const numType = $("#btn-number-decimal").hasClass("active") ? "number" : "integer";
                    const schema = { type: numType, validators: {} };
                    const minNum = $("#min-number-input").val().trim();
                    const maxNum = $("#max-number-input").val().trim();
                    if (minNum && !isNaN(minNum)) schema.validators.min_value = parseFloat(minNum);
                    if (maxNum && !isNaN(maxNum)) schema.validators.max_value = parseFloat(maxNum);
                    return schema;
                }
                case "trackable_object": {
                    const schema = { type: fieldType, validators: {} };
                    const admRestriction = $("#btn-trackable-object-adm-lvl-yes").hasClass("active");
                    const objType = $("#trackable-object-restriction-input").val().trim();
                    if (admRestriction && !isNaN(admRestriction)) {
                        schema.validators.administrative_level_restriction = admRestriction;
                    }
                    if (objType && !isNaN(objType)) {
                        schema.validators.trackable_object_id = objType;
                    }
                    return schema;
                }
                case "administrative_level": {
                    const schema = { type: fieldType, validators: {} };
                    if ($("#btn-admin-level-restriction-yes").hasClass("active")) {
                        schema.validators.administrative_level_restriction = "true";
                    }
                    return schema;
                }
                case "bool":
                    return { type: fieldType, display: "radio", validators: {} };
                default:
                    return { type: fieldType, validators: {} };
            }
        },

        buildFieldOptions(fieldName) {
            const options = {
                label: $("#field-label-input").val().trim() || fieldName,
                help: $("#field-help-input").val().trim(),
                placeholder: $("#field-placeholder-input").val().trim()
            };

            if ($("#enable-conditional").is(":checked") && this.currentConditions.length > 0) {
                options.dependencies = {
                    conditions: this.currentConditions.map(cond => ({
                        field: cond.field,
                        operator: cond.operator,
                        value: cond.value,
                        is_parent_form: cond.is_parent_form,
                        logic: cond.logic
                    }))
                };
            }

            return options;
        },

        // =====================================================================
        // Field Ordering
        // =====================================================================

        moveFieldUp(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const index = Object.keys(page.page.properties).indexOf(fieldName);
            if (index > 0) this.swapFields(index, index - 1);
        },

        moveFieldDown(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldNames = Object.keys(page.page.properties);
            const index = fieldNames.indexOf(fieldName);
            if (index < fieldNames.length - 1) this.swapFields(index, index + 1);
        },

        swapFields(index1, index2) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldNames = Object.keys(page.page.properties);

            [fieldNames[index1], fieldNames[index2]] = [fieldNames[index2], fieldNames[index1]];

            const newProperties = {};
            const newFields = {};
            fieldNames.forEach(name => {
                newProperties[name] = page.page.properties[name];
                newFields[name] = page.options.fields[name];
            });

            page.page.properties = newProperties;
            page.options.fields = newFields;

            this.updateFieldOrder();
            this.renderAllPages();
        },

        updateFieldOrder() {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldNames = Object.keys(page.page.properties);

            fieldNames.forEach((fieldName, index) => {
                if (!page.options.fields[fieldName]) {
                    page.options.fields[fieldName] = {};
                }
                page.options.fields[fieldName].order = index;
            });
        },

        sortFieldsByOrder() {
            this.formSchema.form.forEach(page => {
                const properties = page.page.properties || {};
                const fields = page.options.fields || {};
                const fieldNames = Object.keys(properties);

                fieldNames.sort((a, b) => {
                    const orderA = fields[a]?.order !== undefined ? fields[a].order : 999;
                    const orderB = fields[b]?.order !== undefined ? fields[b].order : 999;
                    return orderA - orderB;
                });

                const sortedProperties = {};
                const sortedFields = {};
                fieldNames.forEach(name => {
                    sortedProperties[name] = properties[name];
                    sortedFields[name] = fields[name];
                });

                page.page.properties = sortedProperties;
                page.options.fields = sortedFields;
            });
        },

        // =====================================================================
        // Conditions
        // =====================================================================

        addNewCondition() {
            const selectedOption = $("#conditional-field-select option:selected");
            const field = selectedOption.val();
            const fieldLabel = selectedOption.text();
            const formSource = selectedOption.data('form-source');
            const operator = $("#conditional-operator-select").val();

            const value = $("#conditional-value-select").is(":visible")
                ? $("#conditional-value-select").val()
                : $("#conditional-value-input").val().trim();

            if (!field) { alert("Please select a field."); return false; }
            if (!value) { alert("Please enter a value."); return false; }

            this.currentConditions.push({
                field: field,
                field_label: fieldLabel,
                operator: operator,
                value: value,
                is_parent_form: formSource === 'parent',
                logic: 'AND'
            });

            // Clear the condition form
            $("#conditional-field-select").val('');
            $("#conditional-operator-select").val('equals');
            $("#conditional-value-input").val('');
            $("#conditional-value-select").val('').hide();
            $("#conditional-value-input").show();

            this.renderConditionsList();
            return true;
        },

        editCondition(index) {
            const condition = this.currentConditions[index];

            $("#conditional-field-select").val(condition.field);
            this.populateConditionalValues();
            $("#conditional-operator-select").val(condition.operator);

            if ($("#conditional-value-select").is(":visible")) {
                $("#conditional-value-select").val(condition.value);
            } else {
                $("#conditional-value-input").val(condition.value);
            }

            this.currentConditions.splice(index, 1);
            this.renderConditionsList();
            $("#conditional-form-section")[0].scrollIntoView({ behavior: 'smooth' });
        },

        deleteCondition(index) {
            if (!confirm(`Are you sure you want to delete condition ${index + 1}?`)) return;
            this.currentConditions.splice(index, 1);
            this.renderConditionsList();
        },

        renderConditionsList() {
            const container = $("#conditions-list");
            container.empty();

            if (this.currentConditions.length === 0) {
                container.html('<p class="text-muted"><em>No conditions added yet. Click "Add Condition" below.</em></p>');
                return;
            }

            this.currentConditions.forEach((condition, index) => {
                container.append(this.createConditionCard(condition, index));

                if (index < this.currentConditions.length - 1) {
                    container.append(this.createLogicSelector(index));
                }
            });

            this.updateLogicPreview();
        },

        createConditionCard(condition, index) {
            const formSource = condition.is_parent_form ? "Parent Form" : "Current Form";
            const operatorSymbol = OPERATOR_DISPLAY[condition.operator] || condition.operator;

            const card = $('<div>', { class: 'condition-card card card-light mb-2', 'data-index': index });
            const cardBody = $('<div>', { class: 'card-body p-2' });

            cardBody.html(`
                <div class="d-flex justify-content-between align-items-center">
                  <div class="flex-grow-1">
                    <strong>${index + 1}.</strong>
                    <span class="badge badge-info">${formSource}</span>
                    <span class="ml-1">"${condition.field_label || condition.field}"</span>
                    <span class="badge badge-secondary ml-1">${operatorSymbol}</span>
                    <span class="ml-1">"${condition.value}"</span>
                  </div>
                  <div>
                    <button type="button" class="btn btn-sm btn-warning edit-condition-btn" data-index="${index}" title="Edit">
                      <i class="fas fa-edit"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-danger delete-condition-btn" data-index="${index}" title="Delete">
                      <i class="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
            `);

            card.append(cardBody);
            card.find('.edit-condition-btn').on('click', () => this.editCondition(index));
            card.find('.delete-condition-btn').on('click', () => this.deleteCondition(index));
            return card;
        },

        createLogicSelector(index) {
            const currentLogic = this.currentConditions[index].logic || 'AND';

            const selector = $('<div>', { class: 'logic-selector text-center mb-2' });
            selector.html(`
                <div class="btn-group btn-group-sm" role="group">
                  <button type="button" class="btn btn-outline-primary logic-btn ${currentLogic === 'AND' ? 'active' : ''}" data-index="${index}" data-logic="AND">AND</button>
                  <button type="button" class="btn btn-outline-success logic-btn ${currentLogic === 'OR' ? 'active' : ''}" data-index="${index}" data-logic="OR">OR</button>
                </div>
            `);

            selector.find('.logic-btn').on('click', (e) => {
                const $btn = $(e.currentTarget);
                this.currentConditions[$btn.data('index')].logic = $btn.data('logic');
                $btn.siblings().removeClass('active');
                $btn.addClass('active');
                this.updateLogicPreview();
            });

            return selector;
        },

        updateLogicPreview() {
            const preview = $("#logic-preview");

            if (this.currentConditions.length === 0) { preview.hide(); return; }
            if (this.currentConditions.length === 1) {
                preview.html('<small class="text-muted">Show field when condition 1 is true</small>').show();
                return;
            }

            const logicText = '(' + this.currentConditions.map((cond, i) => {
                const suffix = i < this.currentConditions.length - 1 ? ` ${cond.logic || 'AND'} ` : '';
                return `Condition${i + 1}${suffix}`;
            }).join('') + ')';

            preview.html(`<small class="text-info"><strong>Logic:</strong> ${logicText}</small>`).show();
        },

        populateConditionalFieldOptions() {
            const page = this.formSchema.form[this.currentPageIndex];
            const select = $("#conditional-field-select");

            select.empty().append('<option value="">Select a field...</option>');

            // Current form fields
            if (Object.keys(page.page.properties || {}).length > 0) {
                const group = $('<optgroup label="Current Form">');
                for (const [fieldName, _] of Object.entries(page.page.properties || {})) {
                    if (fieldName !== this.editingFieldName) {
                        const label = page.options.fields[fieldName]?.label || fieldName;
                        group.append($('<option>', {
                            value: fieldName,
                            'data-form-source': 'current',
                            text: `${label} (${fieldName})`
                        }));
                    }
                }
                select.append(group);
            }

            // Parent form fields
            if (this.parentFormFields.length > 0) {
                const group = $('<optgroup label="Parent Form">');
                this.parentFormFields.forEach(field => {
                    const displayLabel = field.source ? `${field.label} - ${field.source}` : field.label;
                    group.append($('<option>', {
                        value: field.name,
                        'data-form-source': 'parent',
                        'data-field-type': field.type,
                        'data-field-enum': JSON.stringify(field.enum || []),
                        'data-field-format': field.format || '',
                        text: `${displayLabel} (${field.name})`
                    }));
                });
                select.append(group);
            } else {
                const group = $('<optgroup label="Parent Form">');
                group.append($('<option>', { value: '', disabled: true, text: 'No parent forms selected in Dependencies' }));
                select.append(group);
            }
        },

        populateConditionalValues() {
            const selectedOption = $("#conditional-field-select option:selected");
            const selectedField = selectedOption.val();
            const formSource = selectedOption.data('form-source');
            const valueInput = $("#conditional-value-input");
            const valueSelect = $("#conditional-value-select");

            if (!selectedField) {
                valueInput.attr('type', 'text').show();
                valueSelect.hide();
                return;
            }

            // Resolve field schema
            let fieldSchema;
            if (formSource === 'parent') {
                fieldSchema = {
                    type: selectedOption.data('field-type'),
                    enum: selectedOption.data('field-enum'),
                    format: selectedOption.data('field-format')
                };
            } else {
                const page = this.formSchema.form[this.currentPageIndex];
                fieldSchema = page.page.properties[selectedField];
            }

            // Reset operator dropdown
            const operatorSelect = $("#conditional-operator-select");
            operatorSelect.empty();
            OPERATOR_OPTIONS.forEach(op => {
                operatorSelect.append(`<option value="${op.value}">${op.label}</option>`);
            });

            const hasEnum = fieldSchema.enum && Array.isArray(fieldSchema.enum) && fieldSchema.enum.length > 0;
            const hasMulti = fieldSchema.multi && Array.isArray(fieldSchema.multi) && fieldSchema.multi.length > 0;

            if (hasEnum || hasMulti) {
                const options = fieldSchema.enum || fieldSchema.multi;
                valueSelect.empty().append('<option value="">Select a value...</option>');
                options.forEach(opt => valueSelect.append($('<option>', { value: opt, text: opt })));
                valueInput.hide();
                valueSelect.show();
            } else if (fieldSchema.format === "date" || fieldSchema.type === "date") {
                valueInput.attr('type', 'date').val('').show();
                valueSelect.hide();
            } else if (fieldSchema.type === "number" || fieldSchema.type === "integer") {
                valueInput.attr('type', 'text').val('').attr('placeholder', 'Enter value or min,max for between').show();
                valueSelect.hide();
            } else if (fieldSchema.type === "bool") {
                valueSelect.empty()
                    .append('<option value="">Select...</option>')
                    .append('<option value="true">Yes</option>')
                    .append('<option value="false">No</option>');
                $("#conditional-operator-group-form").hide();
                valueInput.hide();
                valueSelect.show();
            } else {
                valueInput.attr('type', 'text').val('').show();
                valueSelect.hide();
            }
        },

        // =====================================================================
        // Modal & UI Helpers
        // =====================================================================

        resetFieldModal() {
            // Clear inputs
            $("#field-name-input").val("");
            $("#field-type-input").val("string");
            $("#enum-options-input").val("");
            $("#field-label-input").val("");
            $("#field-help-input").val("");
            $("#field-placeholder-input").val("");

            // Clear validators
            $("#min-length-input, #max-length-input, #min-number-input, #max-number-input, #min-date-input, #max-date-input").val("");
            $("#trackable-object-restriction-input").val("");

            // Reset button groups to defaults
            this.setActiveButton("btn-trackable-object-adm-lvl", "yes");
            this.setActiveButton("btn-admin-level-restriction", "yes");
            this.setActiveButton("btn-enum", "select");
            this.setActiveButton("btn-multi", "select");
            this.setActiveButton("btn-text", "input");
            this.setActiveButton("btn-number", "integer");
            this.setActiveButton("btn-required", "yes");

            // Reset conditions
            $("#enable-conditional").prop("checked", false);
            $("#conditional-display-group").hide();
            this.currentConditions = [];
            this.renderConditionsList();

            // Update modal title
            $("#addFieldModalLabel").text("Add New Field");
            $("#save-field-btn").text("Add Field");

            this.toggleFieldTypeOptions();
        },

        toggleFieldTypeOptions() {
            const fieldType = $("#field-type-input").val();

            const groups = [
                "#trackable-object-restrictions-group", "#enum-options-group",
                "#text-restrictions-group", "#number-restrictions-group",
                "#date-restrictions-group", "#admin-level-restrictions-group",
                "#enum-display-group", "#multi-display-group", "#text-display-group", "#number-display-group"
            ];
            groups.forEach(g => $(g).hide());

            const visibilityMap = {
                "enum":                 ["#enum-options-group", "#enum-display-group"],
                "multi":                ["#enum-options-group", "#multi-display-group"],
                "string":               ["#text-display-group", "#text-restrictions-group"],
                "number":               ["#number-display-group", "#number-restrictions-group"],
                "date":                 ["#date-restrictions-group"],
                "trackable_object":     ["#trackable-object-restrictions-group"],
                "administrative_level": ["#admin-level-restrictions-group"]
            };

            (visibilityMap[fieldType] || []).forEach(g => $(g).show());
        },

        /**
         * Activate one button in a yes/no or option button group.
         * prefix: e.g. "btn-required", suffix: e.g. "yes" or "no"
         */
        setActiveButton(prefix, suffix) {
            $(`#${prefix}-${suffix}`).addClass("active").siblings().removeClass("active");
        },

        // =====================================================================
        // Rendering
        // =====================================================================

        renderAllPages() {
            this.pageContainer.empty();

            this.formSchema.form.forEach((page, index) => {
                const card = $("<div>").addClass("card card-secondary");

                const cardHeader = $("<div>")
                    .addClass("card-header d-flex justify-content-between align-items-center")
                    .html(`
                        <h3 class="card-title mb-0" style="cursor:pointer">
                          Page ${index + 1}${index === this.currentPageIndex ? " <small>(active)</small>" : ""}
                        </h3>
                    `)
                    .on("click", () => this.switchToPage(index));

                card.append(cardHeader);

                if (index === this.currentPageIndex) {
                    const cardBody = $("<div>").addClass("card-body");
                    const ul = $("<ul>").addClass("list-group");

                    const fieldNames = Object.keys(page.page.properties || {});
                    fieldNames.forEach((fieldName, fieldIndex) => {
                        ul.append(this.renderFieldItem(page, fieldName, fieldIndex, fieldNames.length));
                    });

                    cardBody.append(ul);
                    card.append(cardBody);
                }

                this.pageContainer.append(card);
            });

            this.updateSchemaTextarea();
        },

        renderFieldItem(page, fieldName, fieldIndex, totalFields) {
            const fieldSchema = page.page.properties[fieldName];
            const isRequired = page.page.required.includes(fieldName);
            const typeDisplay = this.getFieldTypeDisplay(fieldSchema);
            const enumValues = fieldSchema.enum ? ` [${fieldSchema.enum.join(", ")}]` : '';
            const multiValues = fieldSchema.multi ? ` [${fieldSchema.multi.join(", ")}]` : '';
            const restrictionsText = this.getFieldRestrictionsText(fieldSchema);
            const conditionalText = this.getConditionalDisplayText(page, fieldName);
            const label = page.options.fields[fieldName]?.label || fieldName;
            const help = page.options.fields[fieldName]?.help || "";

            // Identifier radio (only for plain string fields)
            let identifierHtml = '';
            if (fieldSchema.type === 'string' && !fieldSchema.enum && !fieldSchema.multi) {
                const radioId = `identifierRadio_${fieldName}`;
                const checked = this.identifierField === fieldName ? 'checked' : '';
                identifierHtml = `
                    <div class="custom-control custom-radio">
                      <input type="radio" id="${radioId}" ${checked} name="identifier_field" class="custom-control-input" value="${fieldName}">
                      <label class="custom-control-label" for="${radioId}">Use as identifier</label>
                    </div>`;
            }

            // Move buttons
            const moveButtonsHtml = totalFields > 1 ? `
                <div class="btn-group btn-group-sm mr-1">
                  <button type="button" class="btn btn-secondary move-up-btn" data-field-name="${fieldName}"
                    ${fieldIndex === 0 ? 'disabled' : ''} title="Move Up">
                    <i class="fas fa-arrow-up"></i>
                  </button>
                  <button type="button" class="btn btn-secondary move-down-btn" data-field-name="${fieldName}"
                    ${fieldIndex === totalFields - 1 ? 'disabled' : ''} title="Move Down">
                    <i class="fas fa-arrow-down"></i>
                  </button>
                </div>` : '';

            const li = $("<li>").addClass("list-group-item");
            li.html(`
                <div class="d-flex justify-content-between align-items-center">
                  <div class="flex-grow-1">
                    <strong>${label}</strong>
                    <small class="text-muted d-block">
                      (${typeDisplay})${enumValues}${multiValues}${restrictionsText} ${isRequired ? '[required]' : ''}
                    </small>
                    ${conditionalText ? `<small class="text-info d-block"><i class="fas fa-eye"></i> ${conditionalText}</small>` : ""}
                    ${help ? `<small class="text-muted d-block">${help}</small>` : ""}
                  </div>
                  <div class="d-flex align-items-center">
                    ${identifierHtml ? `<div class="mr-2">${identifierHtml}</div>` : ""}
                    ${moveButtonsHtml}
                    <div class="btn-group btn-group-sm">
                      <button type="button" class="btn btn-secondary duplicate-field-btn" data-field-name="${fieldName}" title="Duplicate">
                        <i class="fas fa-copy"></i>
                      </button>
                      <button type="button" class="btn btn-info edit-field-btn" data-field-name="${fieldName}" title="Edit">
                        <i class="fas fa-edit"></i>
                      </button>
                      <button type="button" class="btn btn-danger remove-field-btn" data-field-name="${fieldName}" title="Remove">
                        <i class="fas fa-trash-alt"></i>
                      </button>
                    </div>
                  </div>
                </div>
            `);

            li.find(".edit-field-btn").on("click", () => this.editField(fieldName));
            li.find(".remove-field-btn").on("click", () => this.removeField(fieldName));
            li.find(".duplicate-field-btn").on("click", () => this.duplicateField(fieldName));
            li.find(".move-up-btn").on("click", () => this.moveFieldUp(fieldName));
            li.find(".move-down-btn").on("click", () => this.moveFieldDown(fieldName));

            return li;
        },

        // =====================================================================
        // Display Helpers
        // =====================================================================

        getFieldTypeDisplay(fieldSchema) {
            if (fieldSchema.enum) {
                return fieldSchema.display === "radio" ? "dropdown (radio)" : "dropdown (select)";
            } else if (fieldSchema.multi) {
                return fieldSchema.display === "checkboxes" ? "multiselect (checkboxes)" : "multiselect (select)";
            } else if (fieldSchema.format === "date") {
                return "date";
            } else if (fieldSchema.type === "integer") {
                return "number (integer)";
            } else if (fieldSchema.type === "number") {
                return "number (decimal)";
            } else if (fieldSchema.type === "bool") {
                return "boolean (Yes/No)";
            } else if (fieldSchema.type === "string") {
                return fieldSchema.display === "textarea" ? "text (textarea)" : "text (input)";
            }
            return fieldSchema.type || "string";
        },

        getFieldRestrictionsText(fieldSchema) {
            const restrictions = [];

            if (fieldSchema.validators?.min_length !== undefined || fieldSchema.validators?.max_length !== undefined) {
                const min = fieldSchema.validators.min_length;
                const max = fieldSchema.validators.max_length;
                if (min !== undefined && max !== undefined) {
                    restrictions.push(` length: ${min}-${max}`);
                } else if (min !== undefined) {
                    restrictions.push(` length: min ${min}`);
                } else {
                    restrictions.push(` length: max ${max}`);
                }
            }

            if (fieldSchema.validators?.minimum !== undefined || fieldSchema.validators?.maximum !== undefined) {
                const min = fieldSchema.validators.minimum;
                const max = fieldSchema.validators.maximum;
                if (min !== undefined && max !== undefined) {
                    restrictions.push(` range: ${min}-${max}`);
                } else if (min !== undefined) {
                    restrictions.push(` range: min ${min}`);
                } else {
                    restrictions.push(` range: max ${max}`);
                }
            }

            return restrictions.join("");
        },

        getConditionalDisplayText(page, fieldName) {
            const fieldOptions = page.options.fields[fieldName];
            if (!fieldOptions || !fieldOptions.dependencies) return "";

            const deps = fieldOptions.dependencies;

            // Multiple conditions format
            if (deps.conditions && Array.isArray(deps.conditions)) {
                return "Show when: " + deps.conditions.map((cond, i) => {
                    const src = cond.is_parent_form ? "Parent Form" : "Current Form";
                    const label = this.getFieldLabelForCondition(cond.field, cond.is_parent_form);
                    const op = OPERATOR_DISPLAY[cond.operator] || cond.operator;
                    const suffix = i < deps.conditions.length - 1 ? ` ${cond.logic} ` : '';
                    return `[${src}] "${label}" ${op} "${cond.value}"${suffix}`;
                }).join('');
            }

            // Legacy single-condition format
            const depFieldName = Object.keys(deps)[0];
            const depConfig = deps[depFieldName];
            const src = depConfig.is_parent_form ? "Parent Form" : "Current Form";
            const label = this.getFieldLabelForCondition(depFieldName, depConfig.is_parent_form);
            const op = OPERATOR_DISPLAY[depConfig.operator] || depConfig.operator;
            return `Show when [${src}] "${label}" ${op} "${depConfig.value}"`;
        },

        getFieldLabelForCondition(fieldName, isParentForm) {
            if (isParentForm) {
                const parentField = this.parentFormFields.find(f => f.name === fieldName);
                return parentField ? parentField.label : fieldName;
            }
            const page = this.formSchema.form[this.currentPageIndex];
            return page.options.fields[fieldName]?.label || fieldName;
        },

        // =====================================================================
        // Utilities
        // =====================================================================

        slugify(text) {
            return text.toString().toLowerCase().trim()
                .replace(/\s+/g, '_')
                .replace(/[^\w\-]+/g, '')
                .replace(/\_\_+/g, '_')
                .replace(/^-+/, '')
                .replace(/-+$/, '');
        },

        parseCommaSeparated(raw) {
            return (raw || '').trim()
                ? raw.split(",").map(opt => opt.trim()).filter(opt => opt)
                : [];
        }
    };

    window.SchemaForm = SchemaForm;
    SchemaForm.init();
});
