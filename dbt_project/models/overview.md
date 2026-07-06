{% docs __overview__ %}
# Healthcare Claims Intelligence Pipeline

Synthea FHIR R4 → OMOP CDM → Snowflake → dbt → Dagster. Two outputs from one infrastructure:

- **RCM** — `fct_denials`: CARC-level attribution across 257K denied claims, separating systematic denials (single upstream fix) from documentation failures
- **RWE** — `fct_rwe_cohort`: T2D+CKD metformin utilization cohort, defined entirely by seed rows

**Structure:** 7 staging views (OMOP mapping, denial-flag derivation) → 5 mart tables · 2 externalized seeds (`denial_rules`, `condition_codes`) · 83 tests.

Start with `fct_denials` and `fct_rwe_cohort` in the mart layer — the lineage graph shows how every mart column traces back to a FHIR resource.

[Repository](https://github.com/ericg1212/healthcare-claims-pipeline) · by [Eric Grynspan](https://www.linkedin.com/in/ericgrynspan/)
{% enddocs %}
