.DEFAULT_GOAL := help

.PHONY: help dev-web dev-api lint typecheck

help:
	@echo "FlowDesk — make targets"
	@echo "  dev-web    Run the Next.js web app   (http://localhost:3000)"
	@echo "  dev-api    Run the FastAPI service   (http://localhost:8000)"
	@echo "  lint       Lint TS (next lint) + Python (ruff)"
	@echo "  typecheck  Type-check TS (tsc) + Python (mypy)"

dev-web:
	pnpm --filter @flowdesk/web dev

dev-api:
	cd services/api && uvicorn api.main:app --reload --port 8000 --app-dir src

lint:
	pnpm -r --if-present lint
	cd services/engine && ruff check .
	cd services/api && ruff check .

typecheck:
	pnpm -r --if-present typecheck
	cd services/engine && mypy
	cd services/api && mypy
