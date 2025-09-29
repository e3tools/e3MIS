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

      this.toggleFieldTypeOptions();
    },

    populateConditionalFieldOptions() {
      const page = this.formSchema.form[this.currentPageIndex];
      const select = $("#conditional-field-select");

      // Clear existing options
      select.empty().append('<option value="">Select a field...</option>');

      // Add all existing fields as options
      const properties = page.page.properties || {};
      for (const [fieldName, fieldSchema] of Object.entries(properties)) {
        const label = page.options.fields[fieldName]?.label || fieldName;
        select.append($('<option>', {
          value: fieldName,
          text: `${label} (${fieldName})`
        }));
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

    saveField() {
      const fieldName = $("#field-name-input").val().trim();
      const fieldType = $("#field-type-input").val();
      const isRequired = $("#btn-required-yes").hasClass("active");

      if (!fieldName) {
        alert("Field name cannot be empty.");
        return;
      }

      const currentPage = this.formSchema.form[this.currentPageIndex];
      if (fieldName in currentPage.page.properties) {
        alert("Field name already exists in this page.");
        return;
      }

      this.addField(fieldName, fieldType, isRequired);
      $('#addFieldModal').modal('hide');
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
      const enumOptionsGroup = $("#enum-options-group");
      const textRestrictionsGroup = $("#text-restrictions-group");
      const numberRestrictionsGroup = $("#number-restrictions-group");
      const dateRestrictionsGroup = $("#date-restrictions-group");

      // Hide all restriction groups first
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

    addField(fieldName, fieldType, isRequired) {
      const page = this.formSchema.form[this.currentPageIndex];

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

        page.page.properties[fieldName] = {
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

        page.page.properties[fieldName] = {
          type: "string",
          multi: enumOptions
        };
      } else if (fieldType === "date") {
        const fieldSchema = {
          type: "string",
          format: "date",
          validators: {}
        };

        // Add date restrictions
        const minDate = $("#min-date-input").val().trim();
        const maxDate = $("#max-date-input").val().trim();

        if (minDate) {
          fieldSchema.validators.min = minDate;
        }
        if (maxDate) {
          fieldSchema.validators.max = maxDate;
        }

        page.page.properties[fieldName] = fieldSchema;
      } else if (fieldType === "string") {
        const fieldSchema = { type: fieldType, validators: {} };

        // Add string length restrictions
        const minLength = $("#min-length-input").val().trim();
        const maxLength = $("#max-length-input").val().trim();

        if (minLength && !isNaN(minLength)) {
          fieldSchema.validators.min_length = parseInt(minLength);
        }
        if (maxLength && !isNaN(maxLength)) {
          fieldSchema.validators.max_length = parseInt(maxLength);
        }

        page.page.properties[fieldName] = fieldSchema;
      } else if (fieldType === "number" || fieldType === "integer") {
        const fieldSchema = { type: fieldType, validators: {} };

        // Add number restrictions
        const minNumber = $("#min-number-input").val().trim();
        const maxNumber = $("#max-number-input").val().trim();

        if (minNumber && !isNaN(minNumber)) {
          fieldSchema.validators.min_value = parseFloat(minNumber);
        }
        if (maxNumber && !isNaN(maxNumber)) {
          fieldSchema.validators.max_value = parseFloat(maxNumber);
        }

        page.page.properties[fieldName] = fieldSchema;
      } else {
        page.page.properties[fieldName] = {type: fieldType, validators: {} };
      }

      // Add to options
      const fieldOptions = {
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

        fieldOptions.dependencies = {
          [conditionalField]: {
            operator: conditionalOperator,
            value: conditionalValue
          }
        };
      }

      page.options.fields[fieldName] = fieldOptions;

      // Add to required
      if (isRequired) {
        page.page.required.push(fieldName);
      }

      this.renderAllPages();
    },

    removeField(fieldName) {
      const page = this.formSchema.form[this.currentPageIndex];
      delete page.page.properties[fieldName];
      delete page.options.fields[fieldName];
      page.page.required = page.page.required.filter(f => f !== fieldName);
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
          let counter = 0;

          for (const [fieldName, fieldSchema] of Object.entries(properties)) {
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

            li.html(`
              <div class="d-flex justify-content-between align-items-center">
                <div>
                  <strong>${label}</strong>
                  <small class="text-muted d-block">
                    (${type})${enumValues}${multiValues}${restrictionsText} ${isRequired ? '[required]' : ''}
                  </small>
                  ${conditionalText ? `<small class="text-info d-block"><i class="fas fa-eye"></i> ${conditionalText}</small>` : ""}
                  ${help ? `<small class="text-muted d-block">${help}</small>` : ""}
                </div>
                ${is_identifier_html ? `${is_identifier_html}` : ""}
                <button type="button" class="btn btn-sm btn-danger" data-field-name="${fieldName}">
                  <i class="fas fa-trash-alt"></i> Remove
                </button>
              </div>
            `);

            // Attach event listener for remove button
            li.find("button").on("click", () => this.removeField(fieldName));

            ul.append(li);
          }

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