.PHONY: install download prepare train evaluate release serve test smoke web
install:
	python -m pip install -r requirements.lock
	python -m pip install -e . --no-deps
	npm ci --prefix frontend
download:
	python -m feedrank.data download
prepare:
	python -m feedrank.data prepare
train:
	python -m feedrank.train
evaluate:
	python -m feedrank.evaluate
release:
	python -m feedrank.release
serve:
	python -m uvicorn feedrank.api:app --host 127.0.0.1 --port 8000
test:
	python -m pytest -q
	python -m ruff check feedrank tests scripts
	python -m ruff format --check feedrank tests scripts
smoke:
	python scripts/smoke.py
web:
	npm run build --prefix frontend
