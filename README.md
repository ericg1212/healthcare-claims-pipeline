# Denied: Healthcare Claims Intelligence Pipeline

[![CI](https://github.com/ericg1212/healthcare-claims-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ericg1212/healthcare-claims-pipeline/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=flat-square&logo=snowflake&logoColor=white)
![dbt](https://img.shields.io/badge/dbt-1.10-FF694B?style=flat-square&logo=dbt&logoColor=white)
![Dagster](https://img.shields.io/badge/Dagster-1.13-4F4FE6?style=flat-square&logo=dagster&logoColor=white)
![HIPAA](https://img.shields.io/badge/HIPAA-pattern-lightgrey?style=flat-square)

A production-grade healthcare data pipeline that ingests synthetic FHIR R4 claims data, maps it to OMOP CDM, and classifies every denied claim by root cause. The output is two distinct work queues — systematic denials with a defined upstream fix, and documentation quality failures that require a different intervention entirely — because treating them the same is where denial management budgets get wasted.

---

## Systematic or Random?

Healthcare organizations report a denial rate. What they rarely know is *why* — and more importantly, which denials are worth the cost of chasing.

At a **51.9% denial rate** across 495,412 claims, the financial exposure is substantial. Industry benchmarks put the average cost to rework a single denied claim at $25–118. Applied to 257,000 denials, the question is not whether to act — it is where to allocate the effort. Systematic denials have a fixed, upstream remediation with measurable ROI. Documentation failures are a process problem; reworking them claim-by-claim is a losing strategy.

**The classification matters because the remediation path is fundamentally different:**

| CARC | Type | Root Cause | Remediation |
|------|------|------------|-------------|
| 197 | Systematic | Renal dialysis and telehealth claims submitted without a prior authorization reference number — the service is covered, the submission is incomplete | Enforce PA reference number as a required field before claim submission; block filing if absent for PA-required procedure codes |
| 96 | Systematic | Drug not on Medicaid formulary — first-line therapies flagged post-prescribing when the conflict could have been detected at the point of care | Move the formulary check upstream to prescribing; a conflict identified at adjudication is too late to prevent the denial |
| 16 | Random | Claim lacks information to adjudicate — a catch-all code covering documentation gaps, coding errors, and credentialing failures across the clinical and billing workflow | Submission quality audit to identify the dominant subtype; root-cause-specific checklists at encounter close, not a blanket rework queue |

**CARC 197 and 96 are process failures, not coverage failures.** The services are covered. The denials exist because the right information was not attached to the claim at the right time. Both have a single, addressable fix point upstream of submission — prior-auth workflow enforcement for 197, formulary check at prescribing for 96. Together they represent ~27,600 denials with a deterministic remediation path.

**CARC 16 is a different problem at a different scale.** At 89.3% of denials, it cannot be addressed as a rework queue. The operational question is: which documentation failure is dominant in this population, and where in the clinical workflow does it originate? The five root causes identified in this cohort, and their mitigation paths:

| Root Cause | Mitigation |
|------------|------------|
| Missing prior authorization reference number on claims for services that *were* authorized | PA reference validation at claim creation; block submission if PA number is absent for codes that require prior auth |
| Absent medical necessity documentation — no clinical notes attached to support the procedure code | Enforce documentation completeness at encounter close; prevent billing until the relevant clinical note is finalized in the EHR |
| Missing or incorrect CPT modifiers — e.g., telehealth modifier -95 absent on video visit claims | Automated modifier scrubbing against payer-specific rules at claim creation; flag -95 requirement for all telehealth service codes |
| Incomplete referral documentation or missing referring provider NPI | Require referral ID as a mandatory field in the visit record; link referral tracking to appointment scheduling so the record is complete before the encounter |
| Rendering provider credentialing mismatch at the payer | Real-time credentialing status check against payer rosters at time of claim; automated re-credentialing alerts at 90/60/30 days before expiration |

**This pipeline produces two outputs:** a systematic queue (~27,600 claims, each with a specific upstream fix) and a documentation quality queue (229,400 claims requiring process intervention at the clinical workflow level). Knowing which queue a denial belongs to is prerequisite to any effective remediation strategy.

---

## Findings: 495,412 Claims, 51.9% Denial Rate

These denial patterns reflect the population's clinical mix — renal dialysis and Medicaid formulary conflicts in a complex comorbid patient population drive CARC 197 and 96; CARC 16 is a submission quality failure independent of diagnosis.

| Queue | CARC | Denial Reason | Claim Count | Share of Denials |
|-------|------|---------------|-------------|-----------------|
| Telehealth prior-auth | 197 | Non-covered charge — renal dialysis / telehealth not under plan | 3,700 | 1.4% |
| Medicaid pharmacy formulary | 96 | Non-covered charge — drug not on Medicaid formulary | 23,900 | 9.3% |
| Documentation gaps | 16 | Claim lacks information to adjudicate | 229,400 | 89.3% |
| **Total denied** | | | **257,000** | **51.9% denial rate** |

**Insight:** CARC 197 and 96 together represent ~27,600 systematic denials — claims where the denial pattern is deterministic and the fix is upstream of submission, not in the claim itself. CARC 16 at 89% signals a documentation and submission quality problem. The pipeline classifies every denial into one of these two work queues at the CARC level.

---

## Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Data generation | Synthea 3.x (Java) | Synthetic FHIR R4 population — PHI-free by design |
| Ingestion | Python 3.13 + Pydantic v2 | FHIR parser, OMOP mapping, de-identification |
| Storage | Snowflake | RAW, STAGING, MART schemas; TRANSFORMER role |
| Transformation | dbt 1.10 + dbt-snowflake | 12 models, 2 seeds, 83 tests |
| Orchestration | Dagster 1.13 | Multi-asset pipeline, full dependency graph |
| CI | GitHub Actions (SHA-pinned) | lint (flake8 + bandit + pip-audit), pytest, dbt compile |
| Dev adapter | dbt-duckdb | Zero-cost local dev and CI — no Snowflake credits in CI |
| Security | TRANSFORMER role, SECURITY.md, Dependabot | Least-privilege, supply chain protection |

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

## What the OMOP Layer Also Enables

The same OMOP CDM layer that drives denial attribution can answer a second analytical question without rebuilding any part of the ingestion pipeline: are the right patients getting the right drugs?

Real-world evidence (RWE) studies differ from randomized controlled trials in one key way: they measure what actually happens in clinical practice, not under controlled conditions. The pipeline identifies patients with comorbid Type 2 Diabetes (T2D, SNOMED 44054006) and Chronic Kidney Disease (CKD, stages 1–4) from OMOP condition records — a clinically significant cohort because ADA guidelines name metformin as first-line therapy for T2D, but CKD complicates dosing at eGFR thresholds (dose reduction required at eGFR <45, contraindicated at eGFR <30). This creates a zone where clinician judgment varies and underprescription is common.

**T2D + CKD Metformin Utilization (104-patient cohort)**

| Metric | Value |
|--------|-------|
| Cohort size (T2D + CKD) | 104 patients |
| On metformin | 57 patients (54.8%) |
| Not on metformin | 47 patients (45.2%) |

A 45.2% gap in first-line therapy utilization is a meaningful signal — but not a concluded finding. In a production RWE study, it is the starting point for stratification by CKD stage, eGFR band, payer, and age to distinguish appropriate clinical decision-making (eGFR-based contraindication) from underprescription or access barriers. The pipeline produces the cohort-level data required to run that analysis. Adding a new cohort definition requires one row in `seeds/condition_codes.csv` — no SQL changes.

---

## HIPAA Note

This pipeline uses **Synthea synthetic data** — 100% generated, zero real PHI. The de-identification boundary is enforced at the FHIR parser layer (`synthea_parser/utils.py::hash_id`) before any data reaches storage. In a production deployment with real patient data, this is where the BAA starts: identifiers are hashed at ingestion, day-level birth precision is stripped to year, and all downstream storage operates on de-identified OMOP fields. Snowflake access uses a least-privilege `TRANSFORMER` role — no `ACCOUNTADMIN` in the transformation path.
