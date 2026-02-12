DOCUMENTS_DIR := data/documents

.PHONY: clean-doc clean-orphans help-clean

clean-doc: ## Delete one document directory by ID. Usage: make clean-doc ID=<uuid>
ifndef ID
	@echo "Error: missing ID. Usage: make clean-doc ID=<uuid>"
	@exit 1
endif
	@if echo "$(ID)" | grep -qiE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$$'; then \
		if [ -d "$(DOCUMENTS_DIR)/$(ID)" ]; then \
			echo "Deleting $(DOCUMENTS_DIR)/$(ID)"; \
			rm -rf "$(DOCUMENTS_DIR)/$(ID)"; \
			echo "Done."; \
		else \
			echo "Directory not found: $(DOCUMENTS_DIR)/$(ID)"; \
		fi; \
	else \
		echo "Error: invalid UUID format"; \
		exit 1; \
	fi

clean-orphans: ## Detect and interactively clean orphan directories
	@python -m newbee_notebook.scripts.clean_orphan_documents --documents-dir $(DOCUMENTS_DIR)

help-clean: ## Show clean command help
	@echo "clean-doc: make clean-doc ID=<uuid>"
	@echo "clean-orphans: make clean-orphans"
	@echo "PowerShell alternative: .\\scripts\\clean-doc.ps1 -Id <uuid>"

