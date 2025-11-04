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
    editingFieldName: null, // Track which field is being edited

    init() {
      this.pageContainer = $("#pages-container");
      this.configTextarea = $("#config_schema");

      // Load existing schema if available
      this.loadExistingSchema();

      // Initial render
      this.renderAllPages();

      // Handle + Add Page
      $("#add-page-btn").on("click", () => {
        this.addPage();
      });

      // Handle + Add Field
      $("#add-text-field").on("click", () => {
        this.editingFieldName = null; // Clear editing state
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

      // Handle Save Field
      $("#save-field-btn").on("click", () => {
        this.saveField();
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
      $("#conditional-field-select").val("");
      $("#conditional-operator-select").val("equals");
      $("#conditional-value-input").val("").attr("type", "text");
      $("#conditional-value-select").val("").hide();

      $("#btn-required-yes").addClass("active");
      $("#btn-required-no").removeClass("active");

      // Update modal title
      $("#addFieldModalLabel").text("Add New Field");
      $("#save-field-btn").text("Add Field");

      this.toggleFieldTypeOptions();
    },

    populateConditionalFieldOptions() {
      const page = this.formSchema.form[this.currentPageIndex];
      const select = $("#conditional-field-select");

      // Clear existing options
      select.empty().append('<option value="">Select a field...</option>');

      // Add all existing fields as options (excluding the field being edited)
      const properties = page.page.properties || {};
      for (const [fieldName, fieldSchema] of Object.entries(properties)) {
        if (fieldName !== this.editingFieldName) {
          const label = page.options.fields[fieldName]?.label || fieldName;
          select.append($('<option>', {
            value: fieldName,
            text: `${label} (${fieldName})`
          }));
        }
      }
    },

    populateConditionalValues() {
      const page = this.formSchema.form[this.currentPageIndex];
      const selectedField = $("#conditional-field-select").val();
      const valueInput = $("#conditional-value-input");
      const valueSelect = $("#conditional-value-select");

      if (!selectedField) {
        valueInput.attr('type', 'text').show();
        valueSelect.hide();
        return;
      }

      const fieldSchema = page.page.properties[selectedField];

      // If field has enum or multi values, show dropdown
      if (fieldSchema.enum || fieldSchema.multi) {
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
      // If field is a number or integer, change input type to number
      else if (fieldSchema.type === "number" || fieldSchema.type === "integer") {
        valueInput.attr('type', 'number').val('').show();
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

      // Populate basic field info
      $("#field-name-input").val(fieldName).prop('disabled', true); // Disable field name when editing
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

      // Populate conditional display
      if (fieldOptions.dependencies) {
        $("#enable-conditional").prop("checked", true);
        $("#conditional-display-group").show();

        const depFieldName = Object.keys(fieldOptions.dependencies)[0];
        const depConfig = fieldOptions.dependencies[depFieldName];

        this.populateConditionalFieldOptions();
        $("#conditional-field-select").val(depFieldName);
        $("#conditional-operator-select").val(depConfig.operator);

        // Trigger change to populate values dropdown
        this.populateConditionalValues();

        // Set the conditional value
        if ($("#conditional-value-select").is(":visible")) {
          $("#conditional-value-select").val(depConfig.value);
        } else {
          $("#conditional-value-input").val(depConfig.value);
        }
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
        this.currentPageIndex = 0; // Reset to first page
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

      // Build the field schema
      let newFieldSchema;
      let newFieldOptions;

      // Handle dropdown (enum)
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

        // Add date restrictions
        const minDate = $("#min-date-input").val().trim();
        const maxDate = $("#max-date-input").val().trim();

        if (minDate) {
          newFieldSchema.validators.min = minDate;
        }
        if (maxDate) {
          newFieldSchema.validators.max = maxDate;
        }
      } else if (fieldType === "string") {
        newFieldSchema = { type: fieldType, validators: {} };

        // Add string length restrictions
        const minLength = $("#min-length-input").val().trim();
        const maxLength = $("#max-length-input").val().trim();

        if (minLength && !isNaN(minLength)) {
          newFieldSchema.validators.min_length = parseInt(minLength);
        }
        if (maxLength && !isNaN(maxLength)) {
          newFieldSchema.validators.max_length = parseInt(maxLength);
        }
      } else if (fieldType === "number" || fieldType === "integer") {
        newFieldSchema = { type: fieldType, validators: {} };

        // Add number restrictions
        const minNumber = $("#min-number-input").val().trim();
        const maxNumber = $("#max-number-input").val().trim();

        if (minNumber && !isNaN(minNumber)) {
          newFieldSchema.validators.min_value = parseFloat(minNumber);
        }
        if (maxNumber && !isNaN(maxNumber)) {
          newFieldSchema.validators.max_value = parseFloat(maxNumber);
        }
      } else if ( fieldType === "trackable_object" ){
        newFieldSchema = { type: fieldType, validators: {} };

        const administrative_level_restriction = $("#btn-trackable-object-adm-lvl-yes").hasClass("active");
        const trackable_object_type = $("#trackable-object-restriction-input").val().trim();

        if (administrative_level_restriction && !isNaN(administrative_level_restriction)) {
          newFieldSchema.validators.administrative_level_restriction = administrative_level_restriction;
        }
        if (trackable_object_type && !isNaN(trackable_object_type)) {
          newFieldSchema.validators.trackable_object_id = trackable_object_type;
        }
      } else {
        newFieldSchema = {type: fieldType, validators: {} };
      }

      // Build field options
      newFieldOptions = {
        label: $("#field-label-input").val().trim() || fieldName,
        help: $("#field-help-input").val().trim()
      };

      // Add conditional display logic
      const enableConditional = $("#enable-conditional").is(":checked");
      if (enableConditional) {
        const conditionalField = $("#conditional-field-select").val();
        const conditionalOperator = $("#conditional-operator-select").val();

        // Get value from either input or select
        let conditionalValue;
        if ($("#conditional-value-select").is(":visible")) {
          conditionalValue = $("#conditional-value-select").val();
        } else {
          conditionalValue = $("#conditional-value-input").val().trim();
        }

        if (!conditionalField) {
          alert("Please select a field for the conditional display.");
          return;
        }

        if (!conditionalValue) {
          alert("Please enter a value for the conditional display.");
          return;
        }

        newFieldOptions.dependencies = {
          [conditionalField]: {
            operator: conditionalOperator,
            value: conditionalValue
          }
        };
      }

      // If insertAtPosition is specified, insert at that position
      if (insertAtPosition !== null && insertAtPosition >= 0) {
        // Get all current field names
        const fieldNames = Object.keys(page.page.properties);

        // Create new objects with proper order
        const newProperties = {};
        const newFields = {};

        fieldNames.forEach((name, index) => {
          if (index === insertAtPosition) {
            // Insert the new/edited field at this position
            newProperties[fieldName] = newFieldSchema;
            newFields[fieldName] = newFieldOptions;
          }
          newProperties[name] = page.page.properties[name];
          newFields[name] = page.options.fields[name];
        });

        // If position is at the end, add it now
        if (insertAtPosition >= fieldNames.length) {
          newProperties[fieldName] = newFieldSchema;
          newFields[fieldName] = newFieldOptions;
        }

        page.page.properties = newProperties;
        page.options.fields = newFields;
      } else {
        // Add at the end (default behavior for new fields)
        page.page.properties[fieldName] = newFieldSchema;
        page.options.fields[fieldName] = newFieldOptions;
      }

      // Add to required
      if (isRequired) {
        if (!page.page.required.includes(fieldName)) {
          page.page.required.push(fieldName);
        }
      } else {
        // Remove from required if it was previously required
        page.page.required = page.page.required.filter(f => f !== fieldName);
      }

      // Add order tracking to field options
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

      // Generate a unique name for the duplicated field
      let newFieldName = `${fieldName}_copy`;
      let counter = 1;
      while (newFieldName in page.page.properties) {
        counter++;
        newFieldName = `${fieldName}_copy${counter}`;
      }

      // Deep clone the field schema and options
      page.page.properties[newFieldName] = JSON.parse(JSON.stringify(fieldSchema));
      page.options.fields[newFieldName] = JSON.parse(JSON.stringify(fieldOptions));

      // Update label to indicate it's a copy
      const originalLabel = fieldOptions.label || fieldName;
      page.options.fields[newFieldName].label = `${originalLabel} (Copy)`;

      // Add to required array if original was required
      if (isRequired) {
        page.page.required.push(newFieldName);
      }

      this.renderAllPages();

      // Show a notification
      alert(`Field duplicated as "${newFieldName}". You can edit it to customize.`);
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

            const li = $("<li>").addClass("list-group-item");

            if (type === 'string' && enumValues === '' && multiValues === '') {
              is_identifier_html = `
              <div class="custom-control custom-radio">
                <input type="radio" id="identifierRadio${counter}" name="identifier_field" class="custom-control-input" value="${fieldName}">
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

      // Number restrictions
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
      const depFieldName = Object.keys(deps)[0];
      const depConfig = deps[depFieldName];
      const depLabel = page.options.fields[depFieldName]?.label || depFieldName;

      const operatorText = {
        'equals': '=',
        'not_equals': '≠',
        'contains': 'contains',
        'greater_than': '>',
        'less_than': '<'
      };

      return `Show when "${depLabel}" ${operatorText[depConfig.operator]} "${depConfig.value}"`;
    }
  };

  window.SchemaForm = SchemaForm;
  SchemaForm.init();
});