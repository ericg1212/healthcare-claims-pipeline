PROJ_DIR := $(shell pwd)
JAVA     := java
SYNTHEA  := C:/Tools/synthea-with-dependencies.jar
DATA_DIR := $(PROJ_DIR)/data/synthea_output

# ── Synthea ───────────────────────────────────────────────────────
.PHONY: generate
generate:
	@echo "Generating Synthea FHIR R4 population..."
	$(JAVA) -jar $(SYNTHEA) \
		-p 2000 \
		--exporter.fhir.export=true \
		--exporter.baseDirectory=$(DATA_DIR) \
		Massachusetts

.PHONY: generate-test
generate-test:
	@echo "Generating small test population (50 patients)..."
	$(JAVA) -jar $(SYNTHEA) \
		-p 50 \
		--exporter.fhir.export=true \
		--exporter.baseDirectory=$(DATA_DIR)/test \
		Massachusetts

# ── Python FHIR parser ────────────────────────────────────────────
.PHONY: parse
parse:
	@echo "Parsing FHIR JSON → Snowflake RAW..."
	python -m synthea_parser.loader --env snowflake

.PHONY: parse-dev
parse-dev:
	@echo "Parsing FHIR JSON → DuckDB (dev)..."
	python -m synthea_parser.loader --env duckdb

# ── dbt ──────────────────────────────────────────────────────────
.PHONY: dbt-dev
dbt-dev:
	@echo "Running dbt against DuckDB (dev)..."
	cd dbt_project && dbt build --profiles-dir profiles --target dev

.PHONY: dbt-snowflake
dbt-snowflake:
	@echo "Running dbt against Snowflake (prod)..."
	cd dbt_project && dbt build --profiles-dir profiles --target prod

.PHONY: dbt-test
dbt-test:
	cd dbt_project && dbt test --profiles-dir profiles --target dev

.PHONY: dbt-test-prod
dbt-test-prod:
	cd dbt_project && dbt test --profiles-dir profiles --target prod

.PHONY: dbt-freshness
dbt-freshness:
	cd dbt_project && dbt source freshness --profiles-dir profiles --target dev

# ── Dagster ──────────────────────────────────────────────────────
.PHONY: dagster
dagster:
	@echo "Starting Dagster UI at localhost:3000..."
	dagster dev -m dagster_pipelines

# ── Full pipeline ────────────────────────────────────────────────
.PHONY: run
run: generate parse-dev dbt-dev
	@echo "Full pipeline run complete (DuckDB dev mode)."

.PHONY: load-snowflake
load-snowflake:
	@echo "Loading fixture data into Snowflake RAW..."
	python scripts/create_snowflake_fixtures.py

.PHONY: run-snowflake
run-snowflake: load-snowflake dbt-snowflake
	@echo "Full pipeline run complete (Snowflake)."

# ── Vocab load ───────────────────────────────────────────────────
.PHONY: vocab
vocab:
	@echo "Loading OHDSI vocabulary into Snowflake REFERENCE schema..."
	python scripts/load_vocabulary.py

# ── Tests + CI ───────────────────────────────────────────────────
.PHONY: test
test:
	pytest tests/ -v --cov=synthea_parser --cov=dagster_pipelines

.PHONY: lint
lint:
	flake8 synthea_parser/ dagster_pipelines/ scripts/ tests/
	bandit -r synthea_parser/ dagster_pipelines/ -ll
	pip-audit

.PHONY: ci
ci: lint test dbt-test
	@echo "CI checks passed."

# ── Utilities ────────────────────────────────────────────────────
.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: clean
clean:
	rm -rf $(DATA_DIR)/fhir/*.json
	@echo "Cleared generated FHIR files."

.PHONY: java-version
java-version:
	$(JAVA) -version
