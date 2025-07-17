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
        document.getElementById("field-name-input").value = "";
        document.getElementById("field-type-input").value = "string";
        document.getElementById("enum-options-input").value = "";
        document.getElementById("enum-options-group").style.display = "none";
        document.getElementById("btn-required-yes").classList.add("active");
        document.getElementById("btn-required-no").classList.remove("active");
        document.getElementById("field-label-input").value = "";
        document.getElementById("field-help-input").value = "";
        $('#addFieldModal').modal('show');
      });

      // Show/hide enum input based on type
      document.getElementById("field-type-input").addEventListener("change", function () {
        const showEnum = this.value === "enum";
        document.getElementById("enum-options-group").style.display = showEnum ? "block" : "none";
      });

      // Handle Save Field
      document.getElementById("save-field-btn").addEventListener("click", () => {
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
      } else if (fieldType === "date") {
        page.page.properties[fieldName] = {
          type: "string",
          format: "date" // ✅ JSON Schema convention for date
        };
      } else {
        page.page.properties[fieldName] = { type: fieldType };
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

          for (const [fieldName, fieldSchema] of Object.entries(properties)) {
            const isRequired = page.page.required.includes(fieldName);
            const type = this.getFieldTypeDisplay(fieldSchema);
            const enumValues = fieldSchema.enum ? ` [${fieldSchema.enum.join(", ")}]` : '';
            const label = page.options.fields[fieldName]?.label || fieldName;
            const help = page.options.fields[fieldName]?.help || "";

            const li = document.createElement("li");
            li.className = "list-group-item";

            li.innerHTML = `
              <div class="d-flex justify-content-between align-items-center">
                <div>
                  <strong>${label}</strong>
                  <small class="text-muted d-block">
                    (${type})${enumValues} ${isRequired ? '[required]' : ''}
                  </small>
                  ${help ? `<small class="text-muted d-block">${help}</small>` : ""}
                </div>
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
    }
  };

  window.SchemaForm = SchemaForm;
  SchemaForm.init();
});