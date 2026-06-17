# healthcare-claims-pipeline (P2)

## Project
RCM + RWE pipeline. Synthea FHIR R4 → Python parser → S3 → Snowflake RAW → dbt → Dagster.

## Key Numbers
- 257K denied / 495K total claims | 51.9% denial rate | $1.2M+ recoverable
- 104 T2D+CKD patients | 54.8% metformin utilization
- 40 pytest + 83 dbt tests | CI green

## Stack
| Layer | Tool |
|---|---|
| Data gen | Synthea `-p 2000` (FHIR R4, Massachusetts) |
| Parser | `synthea_parser/` → S3 → Snowflake RAW (7 tables) |
| Transform | dbt — 7 staging views + 5 mart tables (no intermediate layer) |
| Orchestration | Dagster |
| Warehouse | Snowflake xmtxels-dic71728 — **TRIAL EXPIRED Jun 9 2026, add billing** |

## dbt Models
Staging: stg_claim_header, stg_claim_line, stg_person, stg_visit_occurrence, stg_condition_occurrence, stg_drug_exposure, stg_payer_plan_period
Mart: fct_denials, fct_rwe_cohort, dim_patient, dim_provider, dim_date

CARC attribution: denial_rules seed (procedure+payer→CARC) — NOT from real 835 files.
fct_rwe_cohort metformin: RxNorm codes 860975/861004/861007/1807894 — NOT LIKE '%metformin%'.

## Key Commands
```
make generate          # Synthea 2000 patients
make parse             # FHIR → Snowflake RAW
pytest tests/ -v       # 40 unit tests
dbt run                # all models
dbt test               # 83 tests
dagster dev            # Dagster UI at localhost:3000
dbt docs serve         # live at ericg1212.github.io/healthcare-claims-pipeline
```

## Python
Full path: `C:/Users/ericg/AppData/Local/Programs/Python/Python313/python.exe`
No bare `python` in bash hooks.

## Repo
Public: github.com/ericg1212/healthcare-claims-pipeline | Branch protected | Secret scanning on
