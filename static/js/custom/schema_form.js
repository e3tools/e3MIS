document.addEventListener("DOMContentLoaded", function () {
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
      this.pageContainer = document.getElementById("pages-container");
      this.configTextarea = document.getElementById("config_schema");

      // Load existing schema if available
      this.loadExistingSchema();

      // Initial render
      this.renderAllPages();

      // Handle + Add Page
      document.getElementById("add-page-btn").addEventListener("click", () => {
        this.addPage();
      });

      // Handle + Add Field
      document.getElementById("add-text-field").addEventListener("click", () => {
        this.resetFieldModal();
        $('#addFieldModal').modal('show');
      });

      // Show/hide enum input based on type
      document.getElementById("field-type-input").addEventListener("change", () => {
        this.toggleFieldTypeOptions();
      });

      // Handle Save Field
      document.getElementById("save-field-btn").addEventListener("click", () => {
        this.saveField();
      });

      // Optional debug
      const form = document.querySelector("form");
      if (form) {
        form.addEventListener("submit", () => {
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

      $("#btn-required-yes").addClass("active");
      $("#btn-required-no").removeClass("active");

      this.toggleFieldTypeOptions();
    },

    toggleFieldTypeOptions() {
      const fieldType = document.getElementById("field-type-input").value;

      const enum_options_group = $("#enum-options-group");
      const text_restrictions_group = $("#text-restrictions-group");
      const number_restrictions_group = $("#number-restrictions-group");
      const date_restrictions_group = $("#date-restrictions-group");

      // Hide all restriction groups first
      enum_options_group.hide();
      text_restrictions_group.hide();
      number_restrictions_group.hide();
      date_restrictions_group.hide();

      // Show relevant restriction group based on field type
      switch (fieldType) {
        case "enum":
        case "multi":
          enum_options_group.show();
          break;
        case "string":
          text_restrictions_group.show();
          break;
        case "number":
        case "integer":
          number_restrictions_group.show();
          break;
        case "date":
          date_restrictions_group.show();
          break;
      }
    },

    saveField() {
      const fieldName = document.getElementById("field-name-input").value.trim();
      const fieldType = document.getElementById("field-type-input").value;
      const isRequired = document.getElementById("btn-required-yes").classList.contains("active");

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
      const existingSchemaValue = this.configTextarea.value.trim();

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

    updateSchemaTextarea() {
      this.configTextarea.value = JSON.stringify(this.formSchema);
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
        const rawOptions = document.getElementById("enum-options-input").value.trim();
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
        const rawOptions = document.getElementById("enum-options-input").value.trim();
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
        const minDate = document.getElementById("min-date-input").value.trim();
        const maxDate = document.getElementById("max-date-input").value.trim();

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
        const minLength = document.getElementById("min-length-input").value.trim();
        const maxLength = document.getElementById("max-length-input").value.trim();

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
        const minNumber = document.getElementById("min-number-input").value.trim();
        const maxNumber = document.getElementById("max-number-input").value.trim();

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
      page.options.fields[fieldName] = {
        label: document.getElementById("field-label-input").value.trim() || fieldName,
        help: document.getElementById("field-help-input").value.trim()
      };

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
      this.pageContainer.innerHTML = "";

      this.formSchema.form.forEach((page, index) => {
        // Create page card
        const card = document.createElement("div");
        card.className = "card card-secondary";

        // Header with page switch
        const cardHeader = document.createElement("div");
        cardHeader.className = "card-header d-flex justify-content-between align-items-center";
        cardHeader.innerHTML = `
          <h3 class="card-title mb-0" style="cursor:pointer">
            Page ${index + 1}${index === this.currentPageIndex ? " <small>(active)</small>" : ""}
          </h3>
        `;
        cardHeader.onclick = () => this.switchToPage(index);
        card.appendChild(cardHeader);

        // Only render body for active page
        if (index === this.currentPageIndex) {
          const cardBody = document.createElement("div");
          cardBody.className = "card-body";

          const ul = document.createElement("ul");
          ul.className = "list-group";

          const properties = page.page.properties || {};
          let counter = 0;

          for (const [fieldName, fieldSchema] of Object.entries(properties)) {
            counter += 1;
            const isRequired = page.page.required.includes(fieldName);
            const type = this.getFieldTypeDisplay(fieldSchema);
            const enumValues = fieldSchema.enum ? ` [${fieldSchema.enum.join(", ")}]` : '';
            const multiValues = fieldSchema.multi ? ` [${fieldSchema.multi.join(", ")}]` : '';
            const restrictionsText = this.getFieldRestrictionsText(fieldSchema);
            const label = page.options.fields[fieldName]?.label || fieldName;
            const help = page.options.fields[fieldName]?.help || "";

            let is_identifier_html = ''

            const li = document.createElement("li");
            li.className = "list-group-item";

            if (type === 'string' && enumValues === '' && multiValues === '') {
              is_identifier_html = `
              <div class="custom-control custom-radio">
                <input type="radio" id="identifierRadio${counter}" name="identifier_field" class="custom-control-input" value="${fieldName}">
                <label class="custom-control-label" for="identifierRadio${counter}">Use as identifier</label>
              </div>`
            }

            li.innerHTML = `
              <div class="d-flex justify-content-between align-items-center">
                <div>
                  <strong>${label}</strong>
                  <small class="text-muted d-block">
                    (${type})${enumValues}${multiValues}${restrictionsText} ${isRequired ? '[required]' : ''}
                  </small>
                  ${help ? `<small class="text-muted d-block">${help}</small>` : ""}
                </div>
                ${is_identifier_html ? `${is_identifier_html}` : ""}
                <button type="button" class="btn btn-sm btn-danger" onclick="SchemaForm.removeField('${fieldName}')">
                  <i class="fas fa-trash-alt"></i> Remove
                </button>
              </div>
            `;

            ul.appendChild(li);
          }

          cardBody.appendChild(ul);
          card.appendChild(cardBody);
        }

        this.pageContainer.appendChild(card);
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
      if (fieldSchema.validators.min_length !== undefined || fieldSchema.validators.max_length !== undefined) {
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
      if (fieldSchema.validators.minimum !== undefined || fieldSchema.validators.maximum !== undefined) {
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
    }
  };

  window.SchemaForm = SchemaForm;
  SchemaForm.init();
});