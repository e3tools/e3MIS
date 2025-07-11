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
            const type = fieldSchema.type || 'string';
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
    }
  };

  window.SchemaForm = SchemaForm;
  SchemaForm.init();
});