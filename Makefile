# Tizita Studio — SPEC §13. Targets that call unimplemented commands exit 2 until their milestone.
.PHONY: help film radio-cut plan test lint format costs smoke models clean-clone-test serve frontend deploy

UV ?= uv
TIZITA = $(UV) run tizita

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

film: ## validate -> run all stages -> qa (both exports)
	$(TIZITA) validate
	$(TIZITA) run
	$(TIZITA) run --stage qa

radio-cut: ## narration + pad + subtitles on black
	$(TIZITA) radio-cut

plan: ## dry run: what would regenerate
	$(TIZITA) plan

test: ## pytest (CPU only)
	$(UV) run pytest

lint: ## ruff check + format check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## apply ruff fixes and formatting
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

costs: ## regenerate COSTS.md generated section
	$(TIZITA) costs

smoke: ## one call per configured provider
	$(TIZITA) smoke

models: ## default downloads (SPEC §19); optional: tizita models download --only <name>
	$(TIZITA) models download

clean-clone-test: ## clone HEAD, make film with no .env: 0 model calls + QA pass
	bash scripts/clean_clone_test.sh

serve: ## showcase API
	$(TIZITA) serve

frontend: ## frontend dev server
	cd frontend && npm run dev

deploy: ## showcase deploy (M8)
	@echo "deploy lands in M8 (see deploy/README.md)"; exit 2
