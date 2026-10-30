##@
##@ Frontend React
##@

.PHONY: dev build lint typecheck test check install

dev: ##@ Start Vite dev server
	npm run dev -- --port 5150

build: ##@ Build for production
	npm run build

lint: ##@ Run eslint
	npm run lint

typecheck: ##@ Run TypeScript type checker
	npm run typecheck

test: ##@ Run the unit and component tests (vitest)
	npm test

check: ##@ Run all checks (lint + typecheck + test)
check: lint typecheck test

install: ##@ Install dependencies
	npm install
	