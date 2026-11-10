PY := .venv/bin/python
CASES := A-2048 B-3117 C-4420

.PHONY: setup demo web check gold clean-analysis

# One-time install: Python env for the pipeline, node modules for the web app.
setup:
	python3 -m venv .venv
	.venv/bin/pip install -q anthropic pymupdf jsonschema
	cd web && npm install

# Run the pipeline on all three cases. Each output is validated before it is written
# to data/cases/<id>/analysis.json, which is the file the web app loads.
demo:
	$(PY) -m pipeline.run --all

# Start the web app on http://localhost:5173
web:
	cd web && npx vite

# Verify the pipeline output and score it against the answer key.
check:
	@for c in $(CASES); do $(PY) tools/validate_analysis.py data/cases/$$c data/cases/$$c/analysis.json || exit 1; done

clean-analysis:
	rm -f data/cases/*/analysis.json
