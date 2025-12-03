$(document).ready(function () {
    const SchemaForm = {
        formSchema: {
            form: [
                {
                    page: {
                        type: "object",
                        required: [],
                        properties: {}
                    },
                    options: {
                        fields: {}
                    }
                }
            ]
        },
        currentPageIndex: 0,
        editingFieldName: null,
        identifierField: null,
        parentFormFields: [], // Store parent form fields for cross-form conditionals
        currentConditions: [], // Track conditions being edited for multiple conditions
        allFollowUpEventSchemas: {}, // Cache of all FollowUpEvent schemas
        allTrackableObjectSchemas: {}, // Cache of all TrackableObject schemas

        init() {
            this.pageContainer = $("#pages-container");
            this.configTextarea = $("#config_schema");
            this.identifierField = this.configTextarea.data("identifier");

            // Load all available schemas for dynamic loading
            this.loadAllAvailableSchemas();

            // Load parent form fields if already available
            this.loadParentFormFields();

            // Load existing schema if available
            this.loadExistingSchema();

            // Initial render
            this.renderAllPages();

            // Watch for changes in Dependencies field
            this.watchDependenciesField();

            // Watch for changes in Trackable Objects field
            this.watchTrackableObjectsField();

            // Handle + Add Page
            $("#add-page-btn").on("click", () => {
                this.addPage();
            });

            // Handle + Add Field
            $("#add-text-field").on("click", () => {
                this.editingFieldName = null;
                this.resetFieldModal();
                this.populateConditionalFieldOptions();
                $('#addFieldModal').modal('show');
            });

            // Show/hide enum input based on type
            $("#field-type-input").on("change", () => {
                this.toggleFieldTypeOptions();
            });

            // Handle conditional display toggle
            $("#enable-conditional").on("change", (e) => {
                const conditionalGroup = $("#conditional-display-group");
                conditionalGroup.toggle(e.target.checked);
            });

            // Handle conditional field selection to populate values
            $("#conditional-field-select").on("change", () => {
                $("#conditional-operator-group-form").show();
                this.populateConditionalValues();
            });

            // Auto-slugify field name based on field label
            $("#field-label-input").on("input", () => {
                const label = $("#field-label-input").val();
                const slugified = this.slugify(label);
                $("#field-name-input").val(slugified);
            });

            // Restrict field name to slug-type values only
            $("#field-name-input").on("input", (e) => {
                const input = $(e.target);
                const value = input.val();
                const slugified = this.slugify(value);
                if (value !== slugified) {
                    input.val(slugified);
                }
            });

            // Handle Save Field
            $("#save-field-btn").on("click", () => {
                this.saveField();
            });

            // Handle Add Condition button
            $("#add-condition-btn").on("click", () => {
                this.addNewCondition();
            });

            // Optional debug
            const form = $("form");
            if (form.length) {
                form.on("submit", () => {
                    console.log("Submitting schema:", this.formSchema);
                    this.updateSchemaTextarea();
                });
            }
        },

        loadAllAvailableSchemas() {
            /**
             * Load all FollowUpEvent and TrackableObject schemas that are available
             * These will be passed from the view
             */

            // Load FollowUpEvent schemas
            if (typeof window.allFollowUpEventSchemas !== 'undefined') {
                this.allFollowUpEventSchemas = window.allFollowUpEventSchemas;
                console.log("📋 Loaded all FollowUpEvent schemas:", Object.keys(this.allFollowUpEventSchemas).length);
            }

            // Load TrackableObject schemas
            if (typeof window.allTrackableObjectSchemas !== 'undefined') {
                this.allTrackableObjectSchemas = window.allTrackableObjectSchemas;
                console.log("📋 Loaded all TrackableObject schemas:", Object.keys(this.allTrackableObjectSchemas).length);
            }
        },

        watchDependenciesField() {
            /**
             * Watch the "Dependencies" multiselect field for changes
             * When admin selects parent FollowUpEvents, immediately load their schemas
             */
            const $dependenciesField = $('select[name="dependencies"]');

            if ($dependenciesField.length === 0) {
                console.log("⚠️ Dependencies field not found");
                return;
            }

            console.log("👀 Watching dependencies field");

            $dependenciesField.on('change', () => {
                console.log("🔄 Dependencies changed!");
                this.updateParentFormFields();
            });

            // Also trigger on page load to catch pre-selected values
            this.updateParentFormFields();
        },

        watchTrackableObjectsField() {
            /**
             * Watch the "Trackable Objects" multiselect field for changes
             * When admin selects TrackableObjects, immediately load their schemas
             */
            const $trackableObjectsField = $('select[name="trackable_objects"]');

            if ($trackableObjectsField.length === 0) {
                console.log("⚠️ Trackable Objects field not found");
                return;
            }

            console.log("👀 Watching trackable objects field");

            $trackableObjectsField.on('change', () => {
                console.log("🔄 Trackable Objects changed!");
                this.updateParentFormFields();
            });

            // Also trigger on page load to catch pre-selected values
            setTimeout(() => {
                this.updateParentFormFields();
            }, 500); // Small delay to ensure form is fully loaded
        },

        updateParentFormFields() {
            /**
             * Update parent form fields based on currently selected dependencies
             * and trackable objects
             */
            console.log("🔄 Updating parent form fields...");

            this.parentFormFields = [];

            // Get selected FollowUpEvent dependencies
            const $dependenciesField = $('select[name="dependencies"]');
            const selectedDependencies = $dependenciesField.val() || [];

            console.log("Selected dependencies:", selectedDependencies);

            selectedDependencies.forEach(depId => {
                const schema = this.allFollowUpEventSchemas[depId];
                if (schema) {
                    console.log(`📥 Loading schema for FollowUpEvent ${depId}`);
                    this.extractFieldsFromSchema(schema, `FollowUpEvent: ${schema.name}`);
                }
            });

            // Get selected TrackableObjects
            const $trackableObjectsField = $('select[name="trackable_objects"]');
            const selectedTrackableObjects = $trackableObjectsField.val() || [];

            console.log("Selected trackable objects:", selectedTrackableObjects);

            selectedTrackableObjects.forEach(objId => {
                const schema = this.allTrackableObjectSchemas[objId];
                if (schema) {
                    console.log(`📥 Loading schema for TrackableObject ${objId}`);
                    this.extractFieldsFromSchema(schema, `TrackableObject: ${schema.name}`);
                }
            });

            console.log("✅ Parent form fields updated:", this.parentFormFields.length, "fields");
        },

        extractFieldsFromSchema(schemaData, sourceName) {
            /**
             * Extract field definitions from a schema and add to parentFormFields
             */
            try {
                const schema = schemaData.schema;

                if (!schema || !schema.form || schema.form.length === 0) {
                    console.warn(`⚠️ No form data in schema from ${sourceName}`);
                    return;
                }

                schema.form.forEach((page, pageIndex) => {
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
                });

                console.log(`✅ Extracted fields from ${sourceName}:`, this.parentFormFields.length, "total fields");
            } catch (error) {
                console.error(`❌ Error extracting fields from ${sourceName}:`, error);
            }
        },

        loadParentFormFields() {
            /**
             * Load parent form fields from pre-loaded schema (for editing existing forms)
             */
            if (typeof window.parentFormSchema !== 'undefined' && window.parentFormSchema) {
                try {
                    const parentSchema = window.parentFormSchema;

                    if (parentSchema.form && parentSchema.form.length > 0) {
                        parentSchema.form.forEach((page, pageIndex) => {
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
                                    pageIndex: pageIndex
                                });
                            });
                        });

                        console.log("✅ Loaded parent form fields from pre-loaded schema:", this.parentFormFields);
                    }
                } catch (error) {
                    console.error("❌ Error loading parent form fields:", error);
                }
            }
        },

        resetFieldModal() {
            $("#field-name-input").val("");
            $("#field-type-input").val("string");
            $("#enum-options-input").val("");
            $("#field-label-input").val("");
            $("#field-help-input").val("");

            // Reset validation fields
            $("#min-length-input").val("");
            $("#max-length-input").val("");
            $("#min-number-input").val("");
            $("#max-number-input").val("");
            $("#min-date-input").val("");
            $("#max-date-input").val("");

            // Reset conditional fields
            $("#enable-conditional").prop("checked", false);
            $("#conditional-display-group").hide();
            this.currentConditions = [];
            this.renderConditionsList();

            $("#btn-required-yes").addClass("active");
            $("#btn-required-no").removeClass("active");

            // Update modal title
            $("#addFieldModalLabel").text("Add New Field");
            $("#save-field-btn").text("Add Field");

            this.toggleFieldTypeOptions();
        },

        renderConditionsList() {
            const container = $("#conditions-list");
            container.empty();

            if (this.currentConditions.length === 0) {
                container.html('<p class="text-muted"><em>No conditions added yet. Click "Add Condition" below.</em></p>');
                return;
            }

            this.currentConditions.forEach((condition, index) => {
                const conditionCard = this.createConditionCard(condition, index);
                container.append(conditionCard);

                // Add AND/OR selector if not the last condition
                if (index < this.currentConditions.length - 1) {
                    const logicSelector = this.createLogicSelector(index);
                    container.append(logicSelector);
                }
            });

            // Update the logic preview
            this.updateLogicPreview();
        },

        createConditionCard(condition, index) {
            const formSource = condition.is_parent_form ? "Parent Form" : "Current Form";
            const operatorDisplay = {
                'equals': '=',
                'not_equals': '≠',
                'contains': 'contains',
                'greater_than': '>',
                'less_than': '<',
                'between': 'between'
            }[condition.operator] || condition.operator;

            const card = $('<div>', {
                class: 'condition-card card card-light mb-2',
                'data-index': index
            });

            const cardBody = $('<div>', {
                class: 'card-body p-2'
            });

            cardBody.html(`
        <div class="d-flex justify-content-between align-items-center">
          <div class="flex-grow-1">
            <strong>${index + 1}.</strong>
            <span class="badge badge-info">${formSource}</span>
            <span class="ml-1">"${condition.field_label || condition.field}"</span>
            <span class="badge badge-secondary ml-1">${operatorDisplay}</span>
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

            // Attach event handlers
            card.find('.edit-condition-btn').on('click', () => this.editCondition(index));
            card.find('.delete-condition-btn').on('click', () => this.deleteCondition(index));

            return card;
        },

        createLogicSelector(index) {
            const currentLogic = this.currentConditions[index].logic || 'AND';

            const selector = $('<div>', {
                class: 'logic-selector text-center mb-2'
            });

            selector.html(`
        <div class="btn-group btn-group-sm" role="group">
          <button type="button" class="btn btn-outline-primary logic-btn ${currentLogic === 'AND' ? 'active' : ''}" data-index="${index}" data-logic="AND">
            AND
          </button>
          <button type="button" class="btn btn-outline-success logic-btn ${currentLogic === 'OR' ? 'active' : ''}" data-index="${index}" data-logic="OR">
            OR
          </button>
        </div>
      `);

            selector.find('.logic-btn').on('click', (e) => {
                const $btn = $(e.currentTarget);
                const idx = $btn.data('index');
                const logic = $btn.data('logic');

                this.currentConditions[idx].logic = logic;

                // Update button states
                $btn.siblings().removeClass('active');
                $btn.addClass('active');

                this.updateLogicPreview();
            });

            return selector;
        },

        updateLogicPreview() {
            const preview = $("#logic-preview");

            if (this.currentConditions.length === 0) {
                preview.hide();
                return;
            }

            if (this.currentConditions.length === 1) {
                preview.html('<small class="text-muted">Show field when condition 1 is true</small>').show();
                return;
            }

            let logicText = '(';
            this.currentConditions.forEach((condition, index) => {
                logicText += `Condition${index + 1}`;
                if (index < this.currentConditions.length - 1) {
                    logicText += ` ${condition.logic || 'AND'} `;
                }
            });
            logicText += ')';

            preview.html(`<small class="text-info"><strong>Logic:</strong> ${logicText}</small>`).show();
        },

        addNewCondition() {

            // Get values from the condition form
            const selectedOption = $("#conditional-field-select option:selected");
            const field = selectedOption.val();
            const fieldLabel = selectedOption.text();
            const formSource = selectedOption.data('form-source');
            const operator = $("#conditional-operator-select").val();

            let value;
            if ($("#conditional-value-select").is(":visible")) {
                value = $("#conditional-value-select").val();
            } else {
                value = $("#conditional-value-input").val().trim();
            }

            // Validate
            if (!field) {
                alert("Please select a field.");
                return false;
            }

            if (!value) {
                alert("Please enter a value.");
                return false;
            }

            // Create condition object
            const condition = {
                field: field,
                field_label: fieldLabel,
                operator: operator,
                value: value,
                is_parent_form: formSource === 'parent',
                logic: 'AND' // Default logic for connecting to next condition
            };

            // Add to conditions array
            this.currentConditions.push(condition);

            // Clear the condition form
            $("#conditional-field-select").val('');
            $("#conditional-operator-select").val('equals');
            $("#conditional-value-input").val('');
            $("#conditional-value-select").val('').hide();
            $("#conditional-value-input").show();

            // Re-render conditions list
            this.renderConditionsList();

            return true;
        },

        editCondition(index) {
            const condition = this.currentConditions[index];

            // Populate the condition form with existing values
            $("#conditional-field-select").val(condition.field);

            // Trigger change to populate values dropdown
            this.populateConditionalValues();

            $("#conditional-operator-select").val(condition.operator);

            if ($("#conditional-value-select").is(":visible")) {
                $("#conditional-value-select").val(condition.value);
            } else {
                $("#conditional-value-input").val(condition.value);
            }

            // Remove the condition (it will be re-added when user clicks Add)
            this.currentConditions.splice(index, 1);
            this.renderConditionsList();

            // Scroll to condition form
            $("#conditional-form-section")[0].scrollIntoView({behavior: 'smooth'});
        },

        deleteCondition(index) {
            if (!confirm(`Are you sure you want to delete condition ${index + 1}?`)) {
                return;
            }

            this.currentConditions.splice(index, 1);
            this.renderConditionsList();
        },

        populateConditionalFieldOptions() {
            const page = this.formSchema.form[this.currentPageIndex];
            const select = $("#conditional-field-select");

            // Clear existing options
            select.empty().append('<option value="">Select a field...</option>');

            // Add optgroup for current form fields
            if (Object.keys(page.page.properties || {}).length > 0) {
                const currentFormGroup = $('<optgroup label="Current Form">');
                const properties = page.page.properties || {};

                for (const [fieldName, fieldSchema] of Object.entries(properties)) {
                    if (fieldName !== this.editingFieldName) {
                        const label = page.options.fields[fieldName]?.label || fieldName;
                        currentFormGroup.append($('<option>', {
                            value: fieldName,
                            'data-form-source': 'current',
                            text: `${label} (${fieldName})`
                        }));
                    }
                }
                select.append(currentFormGroup);
            }

            // Add optgroup for parent form fields if available
            if (this.parentFormFields.length > 0) {
                const parentFormGroup = $('<optgroup label="Parent Form">');

                this.parentFormFields.forEach(field => {
                    const displayLabel = field.source
                        ? `${field.label} - ${field.source}`
                        : field.label;

                    parentFormGroup.append($('<option>', {
                        value: field.name,
                        'data-form-source': 'parent',
                        'data-field-type': field.type,
                        'data-field-enum': JSON.stringify(field.enum || []),
                        'data-field-format': field.format || '',
                        text: `${displayLabel} (${field.name})`
                    }));
                });

                select.append(parentFormGroup);
            } else {
                // Add a disabled option to explain why Parent Form is empty
                const emptyGroup = $('<optgroup label="Parent Form">');
                emptyGroup.append($('<option>', {
                    value: '',
                    disabled: true,
                    text: 'No parent forms selected in Dependencies'
                }));
                select.append(emptyGroup);
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

            let fieldSchema;

            // Get field schema based on source (current form or parent form)
            if (formSource === 'parent') {
                const fieldType = selectedOption.data('field-type');
                const fieldEnum = selectedOption.data('field-enum');
                const fieldFormat = selectedOption.data('field-format');

                fieldSchema = {
                    type: fieldType,
                    enum: fieldEnum,
                    format: fieldFormat
                };
            } else {
                const page = this.formSchema.form[this.currentPageIndex];
                fieldSchema = page.page.properties[selectedField];
            }

            // Reset operator dropdown to show all options
            const operatorSelect = $("#conditional-operator-select");
            operatorSelect.empty();
            operatorSelect.append('<option value="equals">Equals (=)</option>');
            operatorSelect.append('<option value="not_equals">Not Equals (≠)</option>');
            operatorSelect.append('<option value="contains">Contains</option>');
            operatorSelect.append('<option value="greater_than">Greater Than (>)</option>');
            operatorSelect.append('<option value="less_than">Less Than (<)</option>');
            operatorSelect.append('<option value="between">Between</option>');

            // If field has enum or multi values (and they're not empty), show dropdown
            const hasEnumValues = fieldSchema.enum && Array.isArray(fieldSchema.enum) && fieldSchema.enum.length > 0;
            const hasMultiValues = fieldSchema.multi && Array.isArray(fieldSchema.multi) && fieldSchema.multi.length > 0;

            if (hasEnumValues || hasMultiValues) {
                const options = fieldSchema.enum || fieldSchema.multi;
                valueSelect.empty().append('<option value="">Select a value...</option>');

                options.forEach(opt => {
                    valueSelect.append($('<option>', {
                        value: opt,
                        text: opt
                    }));
                });

                valueInput.hide();
                valueSelect.show();
            }
            // If field is a date, change input type to date
            else if (fieldSchema.format === "date" || fieldSchema.type === "date") {
                valueInput.attr('type', 'date').val('').show();
                valueSelect.hide();
            }
            // If field is a number or integer, change input type to number and show between option
            else if (fieldSchema.type === "number" || fieldSchema.type === "integer") {
                valueInput.attr('type', 'text').val('').show();
                valueInput.attr('placeholder', 'Enter value or min,max for between');
                valueSelect.hide();
            }
            // If field is a boolean, show yes/no dropdown
            else if (fieldSchema.type === "bool") {
                valueSelect.empty()
                    .append('<option value="">Select...</option>')
                    .append('<option value="true">Yes</option>')
                    .append('<option value="false">No</option>');

                $("#conditional-operator-group-form").hide();
                valueInput.hide();
                valueSelect.show();
            }
            // Default: text input
            else {
                valueInput.attr('type', 'text').val('').show();
                valueSelect.hide();
            }
        },

        editField(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldSchema = page.page.properties[fieldName];
            const fieldOptions = page.options.fields[fieldName];

            // Set editing state
            this.editingFieldName = fieldName;

            $("#field-name-input").val(fieldName);
            $("#field-label-input").val(fieldOptions.label || "");
            $("#field-help-input").val(fieldOptions.help || "");

            // Determine and set field type
            let fieldType = fieldSchema.type;
            if (fieldSchema.enum) {
                fieldType = "enum";
                $("#enum-options-input").val(fieldSchema.enum.join(", "));
            } else if (fieldSchema.multi) {
                fieldType = "multi";
                $("#enum-options-input").val(fieldSchema.multi.join(", "));
            } else if (fieldSchema.format === "date") {
                fieldType = "date";
            }
            $("#field-type-input").val(fieldType);

            // Set required status
            const isRequired = page.page.required.includes(fieldName);
            if (isRequired) {
                $("#btn-required-yes").addClass("active");
                $("#btn-required-no").removeClass("active");
            } else {
                $("#btn-required-no").addClass("active");
                $("#btn-required-yes").removeClass("active");
            }

            // Populate validation fields based on type
            if (fieldSchema.validators) {
                // String restrictions
                $("#min-length-input").val(fieldSchema.validators.min_length || "");
                $("#max-length-input").val(fieldSchema.validators.max_length || "");

                // Number restrictions
                $("#min-number-input").val(fieldSchema.validators.min_value || "");
                $("#max-number-input").val(fieldSchema.validators.max_value || "");

                // Date restrictions
                $("#min-date-input").val(fieldSchema.validators.min || "");
                $("#max-date-input").val(fieldSchema.validators.max || "");
            }

            // Load multiple conditions
            this.currentConditions = [];
            if (fieldOptions.dependencies && fieldOptions.dependencies.conditions) {
                // New format: multiple conditions
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
                // OLD format: single condition (for backward compatibility)
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

            // Show appropriate restriction groups
            this.toggleFieldTypeOptions();

            // Update modal title and button text
            $("#addFieldModalLabel").text("Edit Field");
            $("#save-field-btn").text("Update Field");

            // Show modal
            $('#addFieldModal').modal('show');
        },

        getFieldLabelForCondition(fieldName, isParentForm) {
            if (isParentForm) {
                const parentField = this.parentFormFields.find(f => f.name === fieldName);
                return parentField ? parentField.label : fieldName;
            } else {
                const page = this.formSchema.form[this.currentPageIndex];
                return page.options.fields[fieldName]?.label || fieldName;
            }
        },

        saveField() {
            let fieldName = $("#field-name-input").val().trim();
            const fieldType = $("#field-type-input").val();
            const isRequired = $("#btn-required-yes").hasClass("active");

            if (!fieldName) {
                alert("Field name cannot be empty.");
                return;
            }

            const currentPage = this.formSchema.form[this.currentPageIndex];

            // Check if field name already exists (but allow if we're editing that same field)
            if (fieldName in currentPage.page.properties && fieldName !== this.editingFieldName) {
                alert("Field name already exists in this page.");
                return;
            }

            // If editing, save the position and remove the old field
            let fieldPosition = null;
            if (this.editingFieldName) {
                const fieldNames = Object.keys(currentPage.page.properties);
                fieldPosition = fieldNames.indexOf(this.editingFieldName);
                this.removeFieldSilently(this.editingFieldName);
            }

            // Add/update the field
            this.addField(fieldName, fieldType, isRequired, fieldPosition);

            // Re-enable field name input and clear editing state
            $("#field-name-input").prop('disabled', false);
            this.editingFieldName = null;

            $('#addFieldModal').modal('hide');
        },

        removeFieldSilently(fieldName) {
            // Remove field without re-rendering (used during edit)
            const page = this.formSchema.form[this.currentPageIndex];
            delete page.page.properties[fieldName];
            delete page.options.fields[fieldName];
            page.page.required = page.page.required.filter(f => f !== fieldName);
        },

        loadExistingSchema() {
            // Check if there's existing schema data in the textarea
            const existingSchemaValue = this.configTextarea.val().trim();

            if (existingSchemaValue) {
                try {
                    const parsedSchema = JSON.parse(existingSchemaValue);

                    // Validate the schema structure
                    if (this.isValidSchema(parsedSchema)) {
                        this.formSchema = parsedSchema;
                        console.log("✅ Successfully loaded existing schema:", this.formSchema);
                        console.log("Number of pages:", this.formSchema.form.length);
                    } else {
                        console.warn("❌ Invalid schema structure, using default schema");
                        console.log("Schema validation failed for:", parsedSchema);
                    }
                } catch (error) {
                    console.error("❌ Error parsing existing schema:", error);
                    console.warn("Using default schema instead");
                }
            } else {
                console.log("No existing schema found in textarea");
            }

            // Also check for schema data in a global variable (useful for Django templates)
            if (typeof window.existingSchema !== 'undefined' && window.existingSchema) {
                try {
                    if (this.isValidSchema(window.existingSchema)) {
                        this.formSchema = window.existingSchema;
                        console.log("✅ Loaded schema from window.existingSchema:", this.formSchema);
                    }
                } catch (error) {
                    console.error("❌ Error loading schema from window.existingSchema:", error);
                }
            }
        },

        isValidSchema(schema) {
            // Basic validation to ensure the schema has the expected structure
            console.log("🔍 Validating schema:", schema);

            if (!schema || typeof schema !== 'object') {
                console.log("❌ Schema is not an object");
                return false;
            }

            if (!Array.isArray(schema.form)) {
                console.log("❌ schema.form is not an array");
                return false;
            }

            if (schema.form.length === 0) {
                console.log("❌ schema.form is empty");
                return false;
            }

            // Check each page in the form
            for (let i = 0; i < schema.form.length; i++) {
                const page = schema.form[i];
                console.log(`🔍 Validating page ${i}:`, page);

                if (!page.page || typeof page.page !== 'object') {
                    console.log(`❌ Page ${i} missing or invalid 'page' property`);
                    return false;
                }

                if (!page.options || typeof page.options !== 'object') {
                    console.log(`❌ Page ${i} missing or invalid 'options' property`);
                    return false;
                }

                if (!page.page.properties || typeof page.page.properties !== 'object') {
                    console.log(`❌ Page ${i} missing or invalid 'page.properties'`);
                    return false;
                }

                if (!Array.isArray(page.page.required)) {
                    console.log(`❌ Page ${i} missing or invalid 'page.required' array`);
                    return false;
                }

                if (!page.options.fields || typeof page.options.fields !== 'object') {
                    console.log(`❌ Page ${i} missing or invalid 'options.fields'`);
                    return false;
                }
            }

            console.log("✅ Schema validation passed");
            return true;
        },

        setSchema(schema) {
            // Method to programmatically set the schema
            if (this.isValidSchema(schema)) {
                this.formSchema = schema;
                this.currentPageIndex = 0;
                this.renderAllPages();
                console.log("Schema set successfully:", this.formSchema);
            } else {
                console.error("Invalid schema provided to setSchema");
            }
        },

        toggleFieldTypeOptions() {
            const fieldType = $("#field-type-input").val();
            const trackableObjectRestrictionsGroup = $("#trackable-object-restrictions-group");
            const enumOptionsGroup = $("#enum-options-group");
            const textRestrictionsGroup = $("#text-restrictions-group");
            const numberRestrictionsGroup = $("#number-restrictions-group");
            const dateRestrictionsGroup = $("#date-restrictions-group");

            // Hide all restriction groups first
            trackableObjectRestrictionsGroup.hide();
            enumOptionsGroup.hide();
            textRestrictionsGroup.hide();
            numberRestrictionsGroup.hide();
            dateRestrictionsGroup.hide();

            // Show relevant restriction group based on field type
            switch (fieldType) {
                case "enum":
                case "multi":
                    enumOptionsGroup.show();
                    break;
                case "string":
                    textRestrictionsGroup.show();
                    break;
                case "number":
                case "integer":
                    numberRestrictionsGroup.show();
                    break;
                case "date":
                    dateRestrictionsGroup.show();
                    break;
                case "trackable_object":
                    trackableObjectRestrictionsGroup.show();
                    break;
            }
        },

        updateSchemaTextarea() {
            this.configTextarea.val(JSON.stringify(this.formSchema));
        },

        addPage() {
            this.formSchema.form.push({
                page: {
                    type: "object",
                    required: [],
                    properties: {}
                },
                options: {
                    fields: {}
                }
            });
            this.currentPageIndex = this.formSchema.form.length - 1;
            this.renderAllPages();
        },

        switchToPage(index) {
            this.currentPageIndex = index;
            this.renderAllPages();
        },

        addField(fieldName, fieldType, isRequired, insertAtPosition = null) {
            const page = this.formSchema.form[this.currentPageIndex];

            let newFieldSchema;
            let newFieldOptions;

            if (fieldType === "enum") {
                const rawOptions = $("#enum-options-input").val().trim();
                const enumOptions = rawOptions
                    ? rawOptions.split(",").map(opt => opt.trim()).filter(opt => opt)
                    : [];

                if (enumOptions.length === 0) {
                    alert("You must provide at least one dropdown option.");
                    return;
                }

                newFieldSchema = {
                    type: "string",
                    enum: enumOptions
                };
            } else if (fieldType === "multi") {
                const rawOptions = $("#enum-options-input").val().trim();
                const enumOptions = rawOptions
                    ? rawOptions.split(",").map(opt => opt.trim()).filter(opt => opt)
                    : [];

                if (enumOptions.length === 0) {
                    alert("You must provide at least one multiselect option.");
                    return;
                }

                newFieldSchema = {
                    type: "string",
                    multi: enumOptions
                };
            } else if (fieldType === "date") {
                newFieldSchema = {
                    type: "string",
                    format: "date",
                    validators: {}
                };

                const minDate = $("#min-date-input").val().trim();
                const maxDate = $("#max-date-input").val().trim();

                if (minDate) {
                    newFieldSchema.validators.min = minDate;
                }
                if (maxDate) {
                    newFieldSchema.validators.max = maxDate;
                }
            } else if (fieldType === "string") {
                newFieldSchema = {type: fieldType, validators: {}};

                const minLength = $("#min-length-input").val().trim();
                const maxLength = $("#max-length-input").val().trim();

                if (minLength && !isNaN(minLength)) {
                    newFieldSchema.validators.min_length = parseInt(minLength);
                }
                if (maxLength && !isNaN(maxLength)) {
                    newFieldSchema.validators.max_length = parseInt(maxLength);
                }
            } else if (fieldType === "number" || fieldType === "integer") {
                newFieldSchema = {type: fieldType, validators: {}};

                const minNumber = $("#min-number-input").val().trim();
                const maxNumber = $("#max-number-input").val().trim();

                if (minNumber && !isNaN(minNumber)) {
                    newFieldSchema.validators.min_value = parseFloat(minNumber);
                }
                if (maxNumber && !isNaN(maxNumber)) {
                    newFieldSchema.validators.max_value = parseFloat(maxNumber);
                }
            } else if (fieldType === "trackable_object") {
                newFieldSchema = {type: fieldType, validators: {}};

                const administrative_level_restriction = $("#btn-trackable-object-adm-lvl-yes").hasClass("active");
                const trackable_object_type = $("#trackable-object-restriction-input").val().trim();

                if (administrative_level_restriction && !isNaN(administrative_level_restriction)) {
                    newFieldSchema.validators.administrative_level_restriction = administrative_level_restriction;
                }
                if (trackable_object_type && !isNaN(trackable_object_type)) {
                    newFieldSchema.validators.trackable_object_id = trackable_object_type;
                }
            } else {
                newFieldSchema = {type: fieldType, validators: {}};
            }

            newFieldOptions = {
                label: $("#field-label-input").val().trim() || fieldName,
                help: $("#field-help-input").val().trim()
            };

            // Handle multiple conditions
            const enableConditional = $("#enable-conditional").is(":checked");
            if (enableConditional && this.currentConditions.length > 0) {
                newFieldOptions.dependencies = {
                    conditions: this.currentConditions.map(cond => ({
                        field: cond.field,
                        operator: cond.operator,
                        value: cond.value,
                        is_parent_form: cond.is_parent_form,
                        logic: cond.logic
                    }))
                };
            }

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

        updateFieldOrder() {
            // Update the order property for all fields in the current page
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldNames = Object.keys(page.page.properties);

            fieldNames.forEach((fieldName, index) => {
                if (!page.options.fields[fieldName]) {
                    page.options.fields[fieldName] = {};
                }
                page.options.fields[fieldName].order = index;
            });
        },

        removeField(fieldName) {
            // Confirm before removing
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldLabel = page.options.fields[fieldName]?.label || fieldName;

            if (!confirm(`Are you sure you want to remove the field "${fieldLabel}"?`)) {
                return;
            }

            // Check if any other fields depend on this field
            const dependentFields = [];
            for (const [otherFieldName, otherFieldOptions] of Object.entries(page.options.fields)) {
                if (otherFieldName !== fieldName && otherFieldOptions.dependencies) {
                    if (Object.keys(otherFieldOptions.dependencies).includes(fieldName)) {
                        dependentFields.push(otherFieldOptions.label || otherFieldName);
                    }
                }
            }

            if (dependentFields.length > 0) {
                const proceed = confirm(
                    `Warning: The following fields have conditional display rules that depend on "${fieldLabel}":\n\n` +
                    `${dependentFields.join(", ")}\n\n` +
                    `These conditional rules will be removed. Continue?`
                );

                if (!proceed) {
                    return;
                }

                // Remove dependencies from other fields
                for (const [otherFieldName, otherFieldOptions] of Object.entries(page.options.fields)) {
                    if (otherFieldName !== fieldName && otherFieldOptions.dependencies) {
                        if (Object.keys(otherFieldOptions.dependencies).includes(fieldName)) {
                            delete otherFieldOptions.dependencies;
                        }
                    }
                }
            }

            delete page.page.properties[fieldName];
            delete page.options.fields[fieldName];
            page.page.required = page.page.required.filter(f => f !== fieldName);
            this.renderAllPages();
        },

        duplicateField(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldSchema = page.page.properties[fieldName];
            const fieldOptions = page.options.fields[fieldName];
            const isRequired = page.page.required.includes(fieldName);
            const originalLabel = fieldOptions.label || fieldName;

            // Generate a unique name for the duplicated field
            let newFieldName = `${fieldName}_copy`;
            let counter = 1;
            while (newFieldName in page.page.properties) {
                counter++;
                newFieldName = `${fieldName}_copy${counter}`;
            }

            // Ask for confirmation before duplicating
            if (!confirm(`Duplicate field "${originalLabel}"?\n\nThe new field will be named "${newFieldName}" and can be edited afterward.`)) {
                return;
            }

            // Deep clone the field schema and options
            page.page.properties[newFieldName] = JSON.parse(JSON.stringify(fieldSchema));
            page.options.fields[newFieldName] = JSON.parse(JSON.stringify(fieldOptions));

            // Update label to indicate it's a copy
            page.options.fields[newFieldName].label = `${originalLabel} (Copy)`;

            // Add to required array if original was required
            if (isRequired) {
                page.page.required.push(newFieldName);
            }

            this.renderAllPages();
        },

        moveFieldUp(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldNames = Object.keys(page.page.properties);
            const currentIndex = fieldNames.indexOf(fieldName);

            if (currentIndex > 0) {
                // Swap with previous field
                this.swapFields(currentIndex, currentIndex - 1);
            }
        },

        moveFieldDown(fieldName) {
            const page = this.formSchema.form[this.currentPageIndex];
            const fieldNames = Object.keys(page.page.properties);
            const currentIndex = fieldNames.indexOf(fieldName);

            if (currentIndex < fieldNames.length - 1) {
                // Swap with next field
                this.swapFields(currentIndex, currentIndex + 1);
            }
        },

        swapFields(index1, index2) {
            const page = this.formSchema.form[this.currentPageIndex];

            // Get all field names in current order
            const fieldNames = Object.keys(page.page.properties);

            // Swap positions in the array
            [fieldNames[index1], fieldNames[index2]] = [fieldNames[index2], fieldNames[index1]];

            // Rebuild the properties and fields objects in the new order
            const newProperties = {};
            const newFields = {};

            fieldNames.forEach(fieldName => {
                newProperties[fieldName] = page.page.properties[fieldName];
                newFields[fieldName] = page.options.fields[fieldName];
            });

            // Update the page with reordered fields
            page.page.properties = newProperties;
            page.options.fields = newFields;

            // Update order tracking after swap
            this.updateFieldOrder();

            this.renderAllPages();
        },

        renderAllPages() {
            this.pageContainer.empty();

            this.formSchema.form.forEach((page, index) => {
                // Create page card
                const card = $("<div>").addClass("card card-secondary");

                // Header with page switch
                const cardHeader = $("<div>")
                    .addClass("card-header d-flex justify-content-between align-items-center")
                    .html(`
            <h3 class="card-title mb-0" style="cursor:pointer">
              Page ${index + 1}${index === this.currentPageIndex ? " <small>(active)</small>" : ""}
            </h3>
          `)
                    .on("click", () => this.switchToPage(index));

                card.append(cardHeader);

                // Only render body for active page
                if (index === this.currentPageIndex) {
                    const cardBody = $("<div>").addClass("card-body");
                    const ul = $("<ul>").addClass("list-group");

                    const properties = page.page.properties || {};
                    const fieldNames = Object.keys(properties);
                    let counter = 0;

                    fieldNames.forEach((fieldName, fieldIndex) => {
                        const fieldSchema = properties[fieldName];
                        counter += 1;
                        const isRequired = page.page.required.includes(fieldName);
                        const type = this.getFieldTypeDisplay(fieldSchema);
                        const enumValues = fieldSchema.enum ? ` [${fieldSchema.enum.join(", ")}]` : '';
                        const multiValues = fieldSchema.multi ? ` [${fieldSchema.multi.join(", ")}]` : '';
                        const restrictionsText = this.getFieldRestrictionsText(fieldSchema);
                        const conditionalText = this.getConditionalDisplayText(page, fieldName);
                        const label = page.options.fields[fieldName]?.label || fieldName;
                        const help = page.options.fields[fieldName]?.help || "";

                        let is_identifier_html = ''
                        let is_identifier_field = ''

                        const li = $("<li>").addClass("list-group-item");

                        if (this.identifierField === fieldName) {
                            is_identifier_field = 'checked';
                        } else {
                            is_identifier_field = '';
                        }

                        if (type === 'string' && enumValues === '' && multiValues === '') {
                            is_identifier_html = `
              <div class="custom-control custom-radio">
                <input type="radio" id="identifierRadio${counter}" ${is_identifier_field} name="identifier_field" class="custom-control-input" value="${fieldName}">
                <label class="custom-control-label" for="identifierRadio${counter}">Use as identifier</label>
              </div>`
                        }

                        // Show move up/down buttons if there are multiple fields
                        const showMoveButtons = fieldNames.length > 1;
                        const moveButtonsHtml = showMoveButtons ? `
              <div class="btn-group btn-group-sm mr-1">
                <button type="button" class="btn btn-secondary move-up-btn" data-field-name="${fieldName}" 
                  ${fieldIndex === 0 ? 'disabled' : ''} title="Move Up">
                  <i class="fas fa-arrow-up"></i>
                </button>
                <button type="button" class="btn btn-secondary move-down-btn" data-field-name="${fieldName}"
                  ${fieldIndex === fieldNames.length - 1 ? 'disabled' : ''} title="Move Down">
                  <i class="fas fa-arrow-down"></i>
                </button>
              </div>
            ` : '';

                        li.html(`
              <div class="d-flex justify-content-between align-items-center">
                <div class="flex-grow-1">
                  <strong>${label}</strong>
                  <small class="text-muted d-block">
                    (${type})${enumValues}${multiValues}${restrictionsText} ${isRequired ? '[required]' : ''}
                  </small>
                  ${conditionalText ? `<small class="text-info d-block"><i class="fas fa-eye"></i> ${conditionalText}</small>` : ""}
                  ${help ? `<small class="text-muted d-block">${help}</small>` : ""}
                </div>
                <div class="d-flex align-items-center">
                  ${is_identifier_html ? `<div class="mr-2">${is_identifier_html}</div>` : ""}
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

                        // Attach event listeners
                        li.find(".edit-field-btn").on("click", () => this.editField(fieldName));
                        li.find(".remove-field-btn").on("click", () => this.removeField(fieldName));
                        li.find(".duplicate-field-btn").on("click", () => this.duplicateField(fieldName));
                        li.find(".move-up-btn").on("click", () => this.moveFieldUp(fieldName));
                        li.find(".move-down-btn").on("click", () => this.moveFieldDown(fieldName));

                        ul.append(li);
                    });

                    cardBody.append(ul);
                    card.append(cardBody);
                }

                this.pageContainer.append(card);
            });

            this.updateSchemaTextarea();
        },

        getFieldTypeDisplay(fieldSchema) {
            // Helper method to get display name for field type
            if (fieldSchema.enum) {
                return "dropdown";
            } else if (fieldSchema.format === "date") {
                return "date";
            } else {
                return fieldSchema.type || "string";
            }
        },

        getFieldRestrictionsText(fieldSchema) {
            const restrictions = [];

            // String length restrictions
            if (fieldSchema.validators?.min_length !== undefined || fieldSchema.validators?.max_length !== undefined) {
                let lengthText = " length: ";
                if (fieldSchema.validators.min_length !== undefined && fieldSchema.validators.max_length !== undefined) {
                    lengthText += `${fieldSchema.validators.min_length}-${fieldSchema.validators.max_length}`;
                } else if (fieldSchema.validators.min_length !== undefined) {
                    lengthText += `min ${fieldSchema.validators.min_length}`;
                } else {
                    lengthText += `max ${fieldSchema.validators.max_length}`;
                }
                restrictions.push(lengthText);
            }

            if (fieldSchema.validators?.minimum !== undefined || fieldSchema.validators?.maximum !== undefined) {
                let rangeText = " range: ";
                if (fieldSchema.validators.minimum !== undefined && fieldSchema.validators.maximum !== undefined) {
                    rangeText += `${fieldSchema.validators.minimum}-${fieldSchema.validators.maximum}`;
                } else if (fieldSchema.validators.minimum !== undefined) {
                    rangeText += `min ${fieldSchema.validators.minimum}`;
                } else {
                    rangeText += `max ${fieldSchema.validators.maximum}`;
                }
                restrictions.push(rangeText);
            }

            return restrictions.join("");
        },

        getConditionalDisplayText(page, fieldName) {
            const fieldOptions = page.options.fields[fieldName];
            if (!fieldOptions || !fieldOptions.dependencies) {
                return "";
            }

            const deps = fieldOptions.dependencies;

            // Handle multiple conditions
            if (deps.conditions && Array.isArray(deps.conditions)) {
                let text = "Show when: ";
                deps.conditions.forEach((cond, index) => {
                    const formSource = cond.is_parent_form ? "Parent Form" : "Current Form";
                    const fieldLabel = this.getFieldLabelForCondition(cond.field, cond.is_parent_form);

                    const operatorText = {
                        'equals': '=',
                        'not_equals': '≠',
                        'contains': 'contains',
                        'greater_than': '>',
                        'less_than': '<',
                        'between': 'between'
                    }[cond.operator] || cond.operator;

                    text += `[${formSource}] "${fieldLabel}" ${operatorText} "${cond.value}"`;

                    if (index < deps.conditions.length - 1) {
                        text += ` ${cond.logic} `;
                    }
                });
                return text;
            }

            // Handle single condition (backward compatibility)
            const depFieldName = Object.keys(deps)[0];
            const depConfig = deps[depFieldName];
            const isParentForm = depConfig.is_parent_form === true;
            const formSource = isParentForm ? "Parent Form" : "Current Form";
            const depLabel = this.getFieldLabelForCondition(depFieldName, isParentForm);

            const operatorText = {
                'equals': '=',
                'not_equals': '≠',
                'contains': 'contains',
                'greater_than': '>',
                'less_than': '<',
                'between': 'between'
            }[depConfig.operator] || depConfig.operator;

            return `Show when [${formSource}] "${depLabel}" ${operatorText} "${depConfig.value}"`;
        },

        slugify(text) {
            // Convert text to slug format (lowercase, replace spaces with underscores, remove special chars)
            return text
                .toString()
                .toLowerCase()
                .trim()
                .replace(/\s+/g, '_')           // Replace spaces with underscores
                .replace(/[^\w\-]+/g, '')       // Remove all non-word chars except hyphens
                .replace(/\_\_+/g, '_')         // Replace multiple underscores with single underscore
                .replace(/^-+/, '')             // Trim hyphens from start
                .replace(/-+$/, '');            // Trim hyphens from end
        }
    };

    window.SchemaForm = SchemaForm;
    SchemaForm.init();
});