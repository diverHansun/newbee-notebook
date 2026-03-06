DOCUMENTS_DIR := data/documents

.PHONY: clean-doc clean-orphans help-clean

clean-doc: ## Delete one document directory by ID. Usage: make clean-doc ID=<uuid>
ifndef ID
	@echo "Error: missing ID. Usage: make clean-doc ID=<uuid>"
	@exit 1
endif
	@python -m newbee_notebook.scripts.clean_document --id "$(ID)" --yes

clean-orphans: ## Detect and interactively clean orphan directories
	@python -m newbee_notebook.scripts.clean_orphan_documents --documents-dir $(DOCUMENTS_DIR)

help-clean: ## Show clean command help
	@echo "clean-doc: make clean-doc ID=<uuid>"
	@echo "clean-orphans: make clean-orphans"
	@echo "PowerShell alternative: .\\scripts\\clean-doc.ps1 -Id <uuid>"

