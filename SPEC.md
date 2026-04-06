# Project 2 Spec — Healthcare Claims Intelligence Pipeline

**Status:** Pre-build  
**Target completion:** Apr 27, 2026  
**Portfolio role:** Demonstrates end-to-end healthcare data engineering — FHIR ingestion, OMOP CDM mapping, claims analytics, dual-pitch output (RCM + RWE)

---

## 1. Project Narrative

### The Problem
Claims data in healthcare is messy, multi-source, and compliance-sensitive. Most organizations can tell you their denial rate; few can tell you *why* denials are happening systematically and which are fixable at submission. On the RWE side, the same underlying claims + clinical data can answer questions about real-world drug utilization that controlled trials can't.

### The Build
A production-grade claims intelligence pipeline that ingests synthetic FHIR R4 data from Synthea, maps it to OMOP CDM, loads it into Snowflake, transforms it through dbt, and orchestrates everything with Dagster — with full observability from day one.

### Dual-Pitch Framing
| Audience | Finding | Angle |
|----------|---------|-------|
| RCM (Adonis, Candid Health, Nym Health) | Denial rate by payer + denial reason attribution — systematic vs random | "I built the pipeline that tells you which denials are fixable before you even file the appeal" |
| RWE / Pharma (Formation Bio, Roche, Truveta) | Cohort-level drug utilization finding — e.g., metformin underprescription in T2D+CKD | "Same pipeline, same OMOP model — flipped to answer drug utilization questions clinical trials can't" |

Both findings are derived from Synthea output — numbers are authentic, not pre-specified.

### The HIPAA Frame
Implements HIPAA technical safeguard patterns: de-identification boundary at ingestion, role-based access controls in Snowflake, append-only audit log. Synthetic data (Synthea) used so the pipeline can be demonstrated publicly without PHI constraints. Frame: "In production with real PHI, this boundary is where the BAA starts."

---

## 2. Architecture

```
Synthea (FHIR R4 JSON)
        │
        ▼
[Python FHIR Parser]
  ├── Patient → PERSON
  ├── Encounter → VISIT_OCCURRENCE
  ├── Condition → CONDITION_OCCURRENCE
  ├── MedicationRequest → DRUG_EXPOSURE
  ├── ExplanationOfBenefit → CLAIM_HEADER + CLAIM_LINE
  └── Coverage → PAYER_PLAN_PERIOD
        │
        ▼
Snowflake RAW schema
  (FHIR resources loaded as-is, typed but unmodeled)
        │
        ▼
dbt STAGING (stg_*) — OMOP CDM mapping
  stg_person, stg_visit_occurrence, stg_condition_occurrence,
  stg_drug_exposure, stg_claim_header, stg_claim_line,
  stg_payer_plan_period
        │
        ▼
dbt MART (fct_*, dim_*)
  ├── fct_claims          — claim-line level fact table
  ├── fct_denials         — denial events with CARC/RARC codes
  ├── dim_patient         — patient-level attributes + cohort flags
  ├── dim_payer           — payer reference
  ├── mart_denial_attribution — RCM finding: systematic vs random, by payer + procedure
  └── mart_rwe_cohort     — RWE finding: T2D+CKD cohort, drug utilization rates
        │
        ▼
[Dagster orchestrates full graph]
  Asset: synthea_generate → fhir_parse → snowflake_raw_load
       → dbt_staging → dbt_mart → observability_checks
        │
        ▼
README findings (two headline numbers)
```

---

## 3. Synthea Configuration

**Population:** ~2,000 patients  
**Condition focus:** Type 2 Diabetes (T2D) + Chronic Kidney Disease (CKD) — high claim volume, realistic payer adjudication failures, dense procedure codes  
**Payer mix:** Configure 2–3 synthetic payers with different adjudication rules to generate meaningful denial rate variance  
**Output format:** FHIR R4 JSON (Synthea default)  
**PHI:** None — Synthea is PHI-free by design

**Synthea config flags:**
```
--exporter.fhir.export=true
--exporter.fhir.version=R4
--generate.demographics.default_file=<targeted_demographics>
-p 2000
```

---

## 4. OMOP CDM Scope

### Tables to Build (MVP)

| Layer | Table | Source | Priority |
|-------|-------|--------|----------|
| Core clinical | PERSON | Synthea Patient | P0 |
| Core clinical | VISIT_OCCURRENCE | Synthea Encounter | P0 |
| Core clinical | CONDITION_OCCURRENCE | Synthea Condition | P0 |
| Core clinical | DRUG_EXPOSURE | Synthea MedicationRequest | P0 |
| Claims | CLAIM_HEADER | Synthea ExplanationOfBenefit | P0 |
| Claims | CLAIM_LINE | Synthea EOB.item[] | P0 |
| Claims | PAYER_PLAN_PERIOD | Synthea Coverage | P1 |
| Reference | CONCEPT (subset) | OHDSI Athena download | P0 |
| Reference | VOCABULARY | OHDSI Athena download | P0 |

### Tables Deferred (post-MVP)
MEASUREMENT, OBSERVATION, PROCEDURE_OCCURRENCE, SPECIMEN, NOTE  
*Add when building RWE expansion or if lab values needed for cohort definition*

### Vocabulary
Download OHDSI Athena vocabulary subset: ICD-10-CM, SNOMED, RxNorm, CPT4, HCPCS, CMS Place of Service  
Load into Snowflake REFERENCE schema as static reference tables  
*Do not build manually — download from athena.ohdsi.org*

---

## 5. FHIR Parser Design

**Language:** Python  
**Input:** Synthea FHIR R4 JSON bundle files (one per patient)  
**Output:** Typed Python dataclasses → Snowflake raw tables via Snowflake Python connector or `snowflake-sqlalchemy`

### FHIR Resource → OMOP Mapping

| FHIR Resource | Key Fields | OMOP Target |
|---------------|-----------|-------------|
| Patient | id, birthDate, gender, address | PERSON |
| Encounter | id, period, type, serviceProvider | VISIT_OCCURRENCE |
| Condition | code, onsetDateTime, encounter | CONDITION_OCCURRENCE |
| MedicationRequest | medication, authoredOn, encounter | DRUG_EXPOSURE |
| ExplanationOfBenefit | id, patient, insurer, outcome, item[] | CLAIM_HEADER + CLAIM_LINE |
| ExplanationOfBenefit.item | sequence, productOrService, adjudication | CLAIM_LINE |
| ExplanationOfBenefit.adjudication | reason (CARC), amount | Denial flag + code |
| Coverage | subscriber, payor, period | PAYER_PLAN_PERIOD |

### Parser Structure
```
synthea_parser/
├── __init__.py
├── models.py        # Pydantic models for each FHIR resource
├── parsers/
│   ├── patient.py
│   ├── encounter.py
│   ├── condition.py
│   ├── medication.py
│   ├── eob.py       # ExplanationOfBenefit — most complex
│   └── coverage.py
├── loader.py        # Snowflake bulk load (COPY INTO)
└── utils.py         # concept_id lookup, date normalization, de-id helpers
```

**De-identification boundary:** Strip or hash patient identifiers (name, SSN, exact DOB → birth_year only) at parser output before Snowflake load — even though Synthea data is synthetic, implement the pattern for interview credibility.

---

## 6. Snowflake Schema Design

### Database: `HEALTHCARE_CLAIMS`

| Schema | Purpose | dbt Layer |
|--------|---------|-----------|
| `RAW` | FHIR resources loaded as-is, typed, no business logic | Source |
| `STAGING` | OMOP CDM mapped tables (stg_ prefix) | dbt staging models |
| `MART` | Analytical outputs (fct_, dim_, mart_ prefix) | dbt mart models |
| `REFERENCE` | OHDSI vocabulary, CARC/RARC code tables | Static loads |

### ⚠️ FIRST THING TO DO AFTER CREATING SNOWFLAKE WAREHOUSE
```sql
ALTER WAREHOUSE healthcare_wh SET AUTO_SUSPEND = 60;
```
AUTO_SUSPEND = 60 means the warehouse (Snowflake's compute engine — the thing that costs credits) automatically shuts off after 60 seconds of inactivity. Without this, it idles and burns credits continuously. A warehouse left running overnight can consume the entire $400 trial credit balance. Set this before running anything else.

### Access Controls (HIPAA pattern, implemented on synthetic data)
```sql
-- Roles
ROLE raw_loader     -- parser service account: INSERT only on RAW
ROLE analyst        -- SELECT on STAGING + MART, no RAW access
ROLE admin          -- full access, audited

-- Audit log (append-only)
TABLE raw.pipeline_audit (
  event_ts        TIMESTAMP_NTZ,
  user_name       VARCHAR,
  action          VARCHAR,  -- LOAD, TRANSFORM, QUERY
  table_name      VARCHAR,
  row_count       INTEGER,
  pipeline_run_id VARCHAR
)
```

---

## 7. dbt Model Structure

```
dbt_project/
├── dbt_project.yml
├── profiles.yml
├── models/
│   ├── staging/
│   │   ├── stg_person.sql
│   │   ├── stg_visit_occurrence.sql
│   │   ├── stg_condition_occurrence.sql
│   │   ├── stg_drug_exposure.sql
│   │   ├── stg_claim_header.sql
│   │   ├── stg_claim_line.sql
│   │   └── stg_payer_plan_period.sql
│   └── mart/
│       ├── fct_claims.sql
│       ├── fct_denials.sql
│       ├── dim_patient.sql
│       ├── dim_payer.sql
│       ├── mart_denial_attribution.sql   ← RCM finding
│       └── mart_rwe_cohort.sql           ← RWE finding
├── tests/
│   ├── assert_no_future_claim_dates.sql
│   ├── assert_denial_amounts_positive.sql
│   └── assert_t2d_ckd_cohort_nonempty.sql
├── sources.yml       ← source freshness declarations (Project 1 gap closed)
└── schema.yml        ← column tests: not_null, unique, accepted_values
```

### dbt Test Strategy

| Layer | Tests |
|-------|-------|
| Staging | `not_null` on all PKs + FKs, `unique` on person_id, `accepted_values` on gender, `relationships` for FK integrity |
| Mart | Custom SQL tests: no future claim dates, denial amounts > 0, T2D+CKD cohort non-empty |
| Sources | `freshness` on RAW tables — warn after 24h, error after 48h |

### Source Freshness (closes Project 1 gap)
```yaml
sources:
  - name: raw
    database: HEALTHCARE_CLAIMS
    schema: RAW
    freshness:
      warn_after: {count: 24, period: hour}
      error_after: {count: 48, period: hour}
    loaded_at_field: _loaded_at
    tables:
      - name: raw_claim_header
      - name: raw_person
      ...
```

---

## 8. Dagster Asset Graph

```
synthea_generate          # runs Synthea CLI, outputs FHIR JSON to /data/fhir/
        │
fhir_parse                # Python parser → typed records
        │
snowflake_raw_load        # COPY INTO RAW schema
        │
        ├── dbt_staging   # dbt run --select staging.*
        │
        └── dbt_mart      # dbt run --select mart.*
                │
        ├── mart_denial_attribution   # RCM finding
        └── mart_rwe_cohort           # RWE finding
                │
        pipeline_audit_check          # asset check: audit log populated, row counts nonzero
```

### Dagster Configuration
- **Executor:** In-process (local dev), multiprocess for full runs  
- **Resources:** Snowflake resource (connection via env vars), dbt resource (dagster-dbt integration)  
- **Schedules:** Manual trigger for portfolio (no prod schedule needed)  
- **UI:** localhost:3000 — screenshot for README  
- **Asset checks:** Block downstream if upstream asset fails row count or freshness check

### Dagster-dbt Integration
Use `dagster-dbt` library — dbt models become Dagster assets automatically. Avoids building a custom Dagster→dbt bridge.

```python
from dagster_dbt import DbtCliResource, dbt_assets

@dbt_assets(manifest=dbt_manifest_path)
def healthcare_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

---

## 9. Denial Attribution Logic

### CARC Code Classification (rule-based, in dbt)

| Category | CARC Codes | Type | Fix |
|----------|-----------|------|-----|
| Prior auth missing | 197, 15 | Systematic | Submission fix |
| Wrong procedure code | 4, 5, 6 | Systematic | Coding fix |
| Payer coverage mismatch | 96, 97 | Systematic | Eligibility check |
| Timely filing | 29 | Systematic | Process fix |
| Missing documentation | 16, 18 | Random | Case-by-case |
| Coordination of benefits | 22 | Random | Case-by-case |

**mart_denial_attribution output columns:**
```
payer_id | procedure_code | denial_reason_category | denial_type (systematic/random)
claim_count | denial_count | denial_rate | avg_claim_amount
```

**RCM headline finding (example format):** "X% of denials are systematic — fixable at submission — with prior auth failures accounting for the largest share across [payer]."

---

## 10. RWE Cohort Logic

### Cohort: T2D + CKD Patients

**Inclusion criteria (dbt, OMOP condition_occurrence):**
- CONDITION_OCCURRENCE contains ICD-10 E11.* (T2D) AND N18.* (CKD)
- At least one VISIT_OCCURRENCE in the observation period

**mart_rwe_cohort output:**
```
patient_id | has_t2d | has_ckd | is_t2d_ckd_cohort
metformin_prescribed (bool) | metformin_prescription_count
observation_period_days | first_condition_date | last_visit_date
```

**RWE headline finding (example format):** "T2D+CKD patients received metformin at X% lower rates than T2D-only patients, consistent with guideline caution for eGFR<30 — detectable from claims + OMOP alone."

---

## 11. CI/CD

**Platform:** GitHub Actions (same as Project 1)

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]

jobs:
  lint:
    - flake8, bandit, pip-audit (same as Project 1)

  test:
    - pytest tests/ (FHIR parser unit tests, Dagster asset tests)
    - dbt test against DuckDB adapter (CI runs dbt against local DuckDB, not Snowflake — no credit spend)

  dbt-compile:
    - dbt compile --profiles-dir ci/ (validates SQL without executing)
```

**DuckDB in CI:** Use dbt-duckdb adapter for CI dbt runs — zero cost, no Snowflake credentials in CI, fast. Snowflake runs happen locally and on scheduled demo runs.

---

## 12. Observability (Day One)

| Layer | What | When |
|-------|------|------|
| dbt source freshness | Warn 24h, error 48h on RAW tables | Every dbt run |
| dbt schema tests | not_null, unique, accepted_values, relationships on all staging models | Every dbt run |
| dbt custom tests | No future dates, positive amounts, cohort non-empty | Every mart build |
| Dagster asset checks | Row count > 0, audit log populated | Post-materialization |
| Pipeline audit log | Every load event logged to `raw.pipeline_audit` | Every parser run |

---

## 13. Repo Structure

```
healthcare-claims-pipeline/
├── README.md
├── SPEC.md
├── .github/
│   └── workflows/ci.yml
├── synthea_parser/          # FHIR R4 → Snowflake RAW
│   ├── models.py
│   ├── parsers/
│   ├── loader.py
│   └── utils.py
├── dbt_project/             # dbt nested under repo root (dagster-dbt expects this)
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/
│   │   └── mart/
│   ├── tests/
│   ├── sources.yml
│   └── schema.yml
├── dagster_pipelines/       # Dagster asset definitions + resources
│   ├── assets/
│   ├── resources/
│   └── definitions.py
├── tests/                   # pytest — parser + Dagster unit tests
├── data/
│   └── synthea_output/      # gitignored — FHIR JSON generated locally
├── scripts/
│   └── load_vocabulary.py   # one-time OHDSI Athena vocab load
├── .env.example
├── Makefile                 # make generate, make parse, make load, make dbt, make dagster
└── requirements.txt
```

---

## 14. README Structure

```
# Healthcare Claims Intelligence Pipeline

## Findings
[RCM] X% of denials are systematic — prior auth failures largest driver across Payer A
[RWE] T2D+CKD cohort received metformin at X% lower rates than T2D-only

## Architecture
[diagram]

## Stack
Synthea | Python | OMOP CDM | Snowflake | dbt | Dagster | GitHub Actions

## HIPAA Pattern
Implements HIPAA technical safeguard patterns — de-identification boundary at ingestion,
role-based access, append-only audit log. Synthea synthetic data allows public demo
without PHI constraints.

## Pipeline Walkthrough
1. Generate (Synthea)
2. Parse (FHIR → OMOP)
3. Load (Snowflake RAW)
4. Transform (dbt staging → mart)
5. Orchestrate (Dagster)
6. Validate (dbt tests + asset checks)

## Observability
[dbt source freshness | dbt tests | Dagster asset checks]

## Quick Start
make generate && make parse && make load && make dbt && make dagster
```

---

## 15. Milestone Plan (3 weeks to Apr 27)

| Week | Focus | Deliverables |
|------|-------|-------------|
| Week 1 (Apr 7–13) | Foundation | Synthea configured + generating, FHIR parser built + tested, Snowflake RAW schema loaded, GitHub repo + CI skeleton |
| Week 2 (Apr 14–20) | dbt layer | All staging models, mart models, dbt tests + source freshness, DuckDB CI working |
| Week 3 (Apr 21–27) | Dagster + polish | Full Dagster asset graph wired, denial attribution + RWE findings derived, audit log, README with actual findings filled in |

---

## 16. Risks — All Resolved (Pre-inspected Apr 7 2026)

| Risk | Finding | Resolution | Status |
|------|---------|-----------|--------|
| Synthea CARC denial codes | Confirmed: zero CARC codes generated. All EOBs outcome="complete", adjudication=[]. 1,706/3,142 EOBs have payment=0 + submitted>0 on insured claims. NO_INSURANCE (1,037 claims) = self-pay, not denials. | Rule-based CARC attribution in dbt: high-cost procedures → CARC 197 (prior auth), Medicaid+pharmacy → CARC 96 (non-covered), general insured denial → CARC 16. Interview framing: "raw 837 data without 835 remittance — I built the attribution layer." | ✓ Resolved |
| Snowflake credit burn | Est. ~1 credit ($2) per full pipeline run. $400 trial = 200 full runs. | DuckDB for all dev/CI. Snowflake only for demo runs. `AUTO_SUSPEND = 60` on warehouse. | ✓ Resolved |
| OHDSI Athena vocab size / CPT4 license | Synthea uses SNOMED for procedures — CPT4 not generated. Free vocabs only needed: ICD10CM + SNOMED + RxNorm + LOINC ≈ 835K rows. | Download only those 4 from Athena. No UMLS license required. | ✓ Resolved |
| dagster-dbt versioning | dagster-dbt==0.28.22 requires dbt-core>=1.7,<1.12. dbt-core 1.11.x too new/risky. | Pin: dagster==1.12.22, dagster-dbt==0.28.22, dbt-core==1.9.10, dbt-duckdb==1.9.6, dbt-snowflake==1.9.4. All in requirements.txt. | ✓ Resolved |
| concept_id mapping | FHIR uses SNOMED/ICD10/RxNorm/LOINC — all map cleanly to OMOP via CONCEPT table. | concept_lookup utility: SELECT concept_id WHERE concept_code + vocabulary_id + standard_concept='S'. Return 0 (OMOP unmapped standard). dbt test: error if >5% unmapped. DuckDB vocab fixture for CI. | ✓ Resolved |
| Java version | Synthea 3.x requires Java 17+ (compiled at class version 61.0). System Java = 1.8. | Portable JDK 21 (Temurin) extracted to tools/jdk-21.0.7+6/. Makefile uses JAVA=tools/.../bin/java. No system install needed. | ✓ Resolved |

### Synthea Payer Distribution (from 20-patient test run)
| Payer | Claims | Notes |
|-------|--------|-------|
| NO_INSURANCE | 1,037 | Self-pay — exclude from denial analysis |
| Medicare | 960 | Primary denial analysis target |
| Medicaid | 640 | Coverage mismatch denials |
| Humana / BCBS / Aetna / United | 369 | Commercial — prior auth denials |

### Synthea Claim Type Distribution
- Professional: 1,573 | Pharmacy: 1,443 | Institutional: 126

### Denial Attribution Logic (dbt — mart_denial_attribution)
```sql
carc_code = CASE
  WHEN payer != 'NO_INSURANCE' AND payment_amount = 0 AND submitted_amount > 0
       AND procedure_display IN ('Renal dialysis', 'Cisplatin 50 MG Injection',
           'PACLitaxel 100 MG Injection', 'Combined chemotherapy and radiation therapy')
    THEN '197'  -- Prior auth required (systematic)
  WHEN payer = 'Medicaid' AND claim_type = 'pharmacy'
       AND payment_amount = 0 AND submitted_amount > 0
    THEN '96'   -- Non-covered service (systematic)
  WHEN payer != 'NO_INSURANCE' AND payment_amount = 0 AND submitted_amount > 0
    THEN '16'   -- Missing information (random)
  ELSE NULL     -- Paid or self-pay
END
