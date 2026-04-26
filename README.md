# Denied: Healthcare Claims Intelligence Pipeline

[![CI](https://github.com/ericg1212/healthcare-claims-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ericg1212/healthcare-claims-pipeline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=flat-square&logo=snowflake&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-1.9-FF694B?style=flat-square&logo=dbt&logoColor=white)
![Dagster](https://img.shields.io/badge/Dagster-1.13-4F4FE6?style=flat-square&logo=dagster&logoColor=white)
![HIPAA](https://img.shields.io/badge/HIPAA-pattern-lightgrey?style=flat-square)

A production-grade healthcare data pipeline that ingests synthetic FHIR R4 claims data, maps it to OMOP CDM, and produces two independently valuable analytical outputs from the same pipeline: **RCM denial attribution** and **real-world evidence (RWE) drug utilization**.

---

## Not All Denials Are Equal

Healthcare organizations report a denial rate. What they rarely know is *why* — and whether the denials are fixable.

Systematic denials (CARC 197, 96) follow a pattern: the wrong claim type, the wrong formulary, a missing prior-auth. These are recoverable — fix the submission rule, stop the denial upstream. Random denials (CARC 16) are documentation gaps that will always exist at some rate. Treating them the same wastes resources on the unfixable.

The same OMOP layer that classifies denials can answer a second question without rebuilding anything: are the right patients getting the right drugs? Same data, different lens — RWE at no additional pipeline cost.

---

## Key Findings

### RCM — Denial Attribution (495,412 claims)

| Queue | CARC | Denial Reason | Claim Count | Share of Denials |
|-------|------|---------------|-------------|-----------------|
| Telehealth prior-auth | 197 | Non-covered charge — renal dialysis / telehealth not under plan | 3,700 | 1.4% |
| Medicaid pharmacy formulary | 96 | Non-covered charge — drug not on Medicaid formulary | 23,900 | 9.3% |
| Documentation gaps | 16 | Claim lacks information to adjudicate | 229,400 | 89.3% |
| **Total denied** | | | **257,000** | **51.9% denial rate** |

**Insight:** CARC 197 and 96 together represent ~27,600 systematic denials — claims where the denial pattern is deterministic and addressable upstream (prior-auth workflows, formulary check at prescribing). CARC 16 at 89% of denials signals a documentation and submission quality problem, not a coverage problem. The separation of these two classes is the core deliverable of the RCM pipeline.

### RWE — T2D + CKD Metformin Utilization (104-patient cohort)

Patients with comorbid Type 2 Diabetes (SNOMED 44054006) and Chronic Kidney Disease (stages 1–4) identified from OMOP condition records. Metformin is first-line therapy for T2D under ADA guidelines, but CKD complicates dosing at eGFR thresholds — a known source of underprescription.

| Metric | Value |
|--------|-------|
| Cohort size (T2D + CKD) | 104 patients |
| On metformin | 57 patients (54.8%) |
| Not on metformin | 47 patients (45.2%) |

**Insight:** A 45.2% gap in first-line therapy utilization in a comorbid population is a meaningful signal. In a production RWE study, this cohort would be the starting point for an adherence analysis — stratified by CKD stage, age band, and payer — to identify whether the gap reflects appropriate clinical decision-making (eGFR-based contraindication) or an access/adherence problem. The pipeline produces the cohort-level data required for that analysis.

---

## Architecture

```
Synthea FHIR R4 (2,000-patient synthetic population)
        │
        ▼
Python FHIR Parser  ←  6 resource types → OMOP CDM fields
  ├── Patient          →  PERSON
  ├── Encounter        →  VISIT_OCCURRENCE
  ├── Condition        →  CONDITION_OCCURRENCE (ICD-10 + SNOMED)
  ├── MedicationRequest → DRUG_EXPOSURE (RxNorm)
  ├── ExplanationOfBenefit → CLAIM_HEADER + CLAIM_LINE
  └── Coverage         →  PAYER_PLAN_PERIOD
        │  pydantic validation + de-identification boundary
        ▼
Snowflake RAW schema  (7 tables, append-only)
        │
        ▼
dbt STAGING (7 views)  ←  OMOP CDM mapping, type coercion, denial flag derivation
        │
        ▼
dbt MART (5 tables)
  ├── fct_denials           ← CARC attribution, systematic vs. random classification
  ├── fct_rwe_cohort        ← T2D+CKD cohort, metformin flag
  ├── dim_patient           ← demographics, age bands
  ├── dim_date              ← date spine 2020–2029
  └── dim_provider          ← provider reference
        │
        ▼
Dagster  ←  raw_claims_load → dbt build, full asset graph, healthcare_pipeline job
```

---

## Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Data generation | Synthea 3.x (Java) | Synthetic FHIR R4 population — PHI-free by design |
| Ingestion | Python 3.13 + Pydantic v2 | FHIR parser, OMOP mapping, de-identification |
| Storage | Snowflake | RAW, STAGING, MART schemas; TRANSFORMER role |
| Transformation | dbt 1.9 + dbt-snowflake | 12 models, 2 seeds, 83 tests |
| Orchestration | Dagster 1.13 | Multi-asset pipeline, full dependency graph |
| CI | GitHub Actions (SHA-pinned) | lint (flake8 + bandit + pip-audit), pytest, dbt compile |
| Dev adapter | dbt-duckdb | Zero-cost local dev and CI — no Snowflake credits in CI |
| Security | TRANSFORMER role, SECURITY.md, Dependabot | Least-privilege, supply chain protection |

---

## Project Structure

```
healthcare-claims-pipeline/
├── synthea_parser/          # FHIR → OMOP parser (6 resource types)
│   ├── parsers/             # One module per FHIR resource type
│   ├── bundle_processor.py  # Orchestrates parser chain per bundle
│   └── utils.py             # extract_uuid, parse_datetime, de-identification
├── scripts/
│   ├── load_to_snowflake.py # Bulk-loads parsed bundles → Snowflake RAW
│   ├── create_snowflake_fixtures.py  # Dev fixture data for Snowflake
│   └── snowflake_utils.py   # Shared connection factory
├── dbt_project/
│   ├── models/
│   │   ├── staging/         # 7 views — OMOP CDM mapping
│   │   └── mart/            # 5 tables — fct_denials, fct_rwe_cohort, dims
│   ├── seeds/
│   │   ├── denial_rules.csv     # CARC attribution rules (externalized)
│   │   └── condition_codes.csv  # SNOMED codes for RWE cohort (externalized)
│   └── profiles/profiles.yml    # dev (DuckDB) + prod (Snowflake)
├── dagster_pipelines/
│   ├── assets/__init__.py   # raw_claims_load multi_asset + dbt assets
│   ├── resources/__init__.py # SnowflakeResource (ConfigurableResource)
│   └── __init__.py          # Definitions + healthcare_pipeline job
├── tests/
│   └── test_smoke.py        # 40 pytest tests — parser utils, edge cases
├── .github/
│   ├── workflows/ci.yml     # SHA-pinned CI: lint + test + dbt-compile
│   └── dependabot.yml       # Weekly pip + actions dependency alerts
└── Makefile                 # generate, load-snowflake, dbt-snowflake, dagster, test
```

---

## Setup

### Prerequisites

- Python 3.13
- Java 17+ (for Synthea)
- Snowflake account with `HEALTHCARE_CLAIMS` database and `TRANSFORMER` / `SYSADMIN` roles
- Synthea JAR at `C:/Tools/synthea-with-dependencies.jar` (or update `SYNTHEA` in Makefile)

### Environment

```bash
cp .env.example .env
# Fill in: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD
```

### Install

```bash
pip install -r requirements.txt
```

### Run the full pipeline

```bash
# 1. Generate 2,000-patient FHIR population
make generate

# 2. Create Snowflake schema + load fixture data (first time only)
make load-snowflake

# 3. Bulk-load parsed FHIR bundles → Snowflake RAW
python scripts/load_to_snowflake.py --fhir-dir data/synthea_output

# 4. Run dbt transformations (Snowflake)
make dbt-snowflake

# 5. Launch Dagster UI to run the full pipeline as a single job
make dagster
# → navigate to localhost:3000 → Jobs → healthcare_pipeline → Launch run
```

### Dev mode (no Snowflake, no credits)

```bash
make dbt-dev    # runs dbt against local DuckDB
make test       # pytest + dbt compile
```

---

## Data Model

### Staging layer (views — always fresh, zero storage)

Seven OMOP CDM staging views clean and type-coerce the RAW tables. The denial flag is derived at this layer: a claim is denied when `is_insured = true AND submitted_amount > 0 AND payment_amount = 0`. `NO_INSURANCE` (Synthea self-pay) is explicitly excluded — a zero payment on an uninsured claim is patient responsibility, not a payer denial.

### Mart layer (tables — pre-computed for BI queries)

`fct_denials` applies CARC attribution from `seeds/denial_rules.csv` — adding a new denial rule requires one CSV row, no SQL changes. `fct_rwe_cohort` identifies the T2D+CKD cohort by joining `seeds/condition_codes.csv` against OMOP condition records — adding a new cohort definition requires adding rows to the seed, not editing model SQL. Both seeds externalize clinical knowledge from transformation logic.

### dbt tests

83 tests across 12 models: `not_null`, `unique`, `accepted_values`, `relationships`. Every primary key, every foreign key, every categorical field is tested. The `accepted_values` test on `carc_code` (`'197'`, `'96'`, `'16'`) and `denial_type` (`'systematic'`, `'random'`) ensures CARC attribution logic never silently produces invalid output.

---

## Testing

```bash
make test
# pytest: 40 tests — parser utilities, edge cases, denial flag derivation
# dbt compile: validates all 12 models + 2 seeds resolve without errors
```

pytest covers `extract_uuid`, `parse_datetime`, `hash_id`, `get_coding`, `is_insured`, and `derive_denial_flag` with parametrized inputs including boundary values, null handling, and malformed FHIR references.

---

## HIPAA Note

This pipeline uses **Synthea synthetic data** — 100% generated, zero real PHI. The de-identification boundary is enforced at the FHIR parser layer (`synthea_parser/utils.py::hash_id`) before any data reaches storage. In a production deployment with real patient data, this is where the BAA starts: identifiers are hashed at ingestion, day-level birth precision is stripped to year, and all downstream storage operates on de-identified OMOP fields. Snowflake access uses a least-privilege `TRANSFORMER` role — no `ACCOUNTADMIN` in the transformation path.
