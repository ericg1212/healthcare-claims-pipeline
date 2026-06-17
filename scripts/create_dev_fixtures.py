# Copyright (c) 2026 Eric Grynspan. All rights reserved.
"""
Create DuckDB dev fixture database with raw schema tables and sample data.

Run from project root:
    python scripts/create_dev_fixtures.py

Creates:  data/dev.duckdb
Purpose:  Enables dbt run/test against local DuckDB without Snowflake credentials.
          Data mirrors what the FHIR parser will load into Snowflake RAW.
          Includes paid + denied claims and self-pay cases for denial logic testing.
"""
import duckdb
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dev.duckdb"


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    # ── raw_person ────────────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_person (
            person_id              VARCHAR,
            birth_year             INTEGER,
            birth_month            INTEGER,
            birth_day              INTEGER,
            gender_source_value    VARCHAR,
            race_source_value      VARCHAR,
            ethnicity_source_value VARCHAR,
            location_state         VARCHAR,
            loaded_at              TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_person VALUES
        ('pt-001', 1965,  3, 15, 'M', 'White',                    'Non-Hispanic', 'MA', NOW()),
        ('pt-002', 1978,  7, 22, 'F', 'Black or African American', 'Non-Hispanic', 'MA', NOW()),
        ('pt-003', 1952, 11,  8, 'M', 'White',                    'Non-Hispanic', 'MA', NOW()),
        ('pt-004', 1983,  2, 14, 'F', 'Asian',                    'Non-Hispanic', 'MA', NOW()),
        ('pt-005', 1970,  9, 30, 'M', 'White',                    'Hispanic',     'MA', NOW())
    """)

    # ── raw_claim_header ──────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_claim_header (
            claim_id          VARCHAR,
            patient_id        VARCHAR,
            payer_id          VARCHAR,
            payer_name        VARCHAR,
            claim_type        VARCHAR,   -- professional | pharmacy | institutional
            submitted_amount  DECIMAL(10,2),
            payment_amount    DECIMAL(10,2),
            claim_date        DATE,
            procedure_display VARCHAR,
            loaded_at         TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_claim_header VALUES
        -- Paid claims
        ('clm-001','pt-001','pyr-med', 'Medicare',               'professional', 350.00,   280.00,'2024-01-15','Office visit',       NOW()),
        ('clm-002','pt-002','pyr-bcbs','Blue Cross Blue Shield',  'professional', 200.00,   160.00,'2024-01-20','Annual wellness visit',NOW()),
        ('clm-003','pt-003','pyr-med', 'Medicare',               'institutional',15000.00,12000.00,'2024-02-01','Inpatient stay',      NOW()),
        -- Denied: high-cost procedure → CARC 197 (prior auth)
        ('clm-004','pt-001','pyr-med', 'Medicare',               'professional', 8500.00,    0.00,'2024-02-10','Renal dialysis',      NOW()),
        -- Denied: Medicaid pharmacy → CARC 96 (non-covered)
        ('clm-005','pt-004','pyr-mcd', 'Medicaid',               'pharmacy',      120.00,    0.00,'2024-03-01','Metformin 500mg',     NOW()),
        -- Denied: general insured → CARC 16 (missing info)
        ('clm-006','pt-005','pyr-bcbs','Blue Cross Blue Shield',  'professional',  450.00,    0.00,'2024-03-15','Follow-up visit',    NOW()),
        -- Self-pay: NO_INSURANCE — NOT a denial, excluded from denial analysis
        ('clm-007','pt-003','NO_INSURANCE','NO_INSURANCE',        'professional',  200.00,  200.00,'2024-04-01','Office visit',        NOW()),
        ('clm-008','pt-002','NO_INSURANCE','NO_INSURANCE',        'professional',  150.00,  150.00,'2024-04-10','Lab draw',            NOW())
    """)

    # ── raw_claim_line ────────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_claim_line (
            claim_line_id     VARCHAR,
            claim_id          VARCHAR,
            sequence          INTEGER,
            procedure_code    VARCHAR,
            procedure_display VARCHAR,
            quantity          DECIMAL(10,2),
            submitted_amount  DECIMAL(10,2),
            payment_amount    DECIMAL(10,2),
            loaded_at         TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_claim_line VALUES
        ('cll-001','clm-001',1,'99213','Office or other outpatient visit',        1.0,  350.00, 280.00,NOW()),
        ('cll-002','clm-002',1,'99395','Periodic preventive medicine reevaluation',1.0, 200.00, 160.00,NOW()),
        ('cll-003','clm-003',1,'99223','Initial hospital care',                   1.0,15000.00,12000.00,NOW()),
        ('cll-004','clm-004',1,'90945','Renal dialysis',                          1.0, 8500.00,   0.00,NOW()),
        ('cll-005','clm-005',1,'72500','Metformin 500 MG Oral Tablet',           30.0,  120.00,   0.00,NOW()),
        ('cll-006','clm-006',1,'99214','Office or other outpatient visit',        1.0,  450.00,   0.00,NOW())
    """)

    # ── raw_visit_occurrence ──────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_visit_occurrence (
            visit_occurrence_id    VARCHAR,
            person_id              VARCHAR,
            visit_start_datetime   TIMESTAMP,
            visit_end_datetime     TIMESTAMP,
            visit_type_source_value VARCHAR,
            provider_id            VARCHAR,
            care_site_id           VARCHAR,
            loaded_at              TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_visit_occurrence VALUES
        ('vis-001','pt-001','2024-01-15 09:00:00','2024-01-15 09:30:00','ambulatory',NULL,NULL,NOW()),
        ('vis-002','pt-002','2024-01-20 10:00:00','2024-01-20 10:30:00','ambulatory',NULL,NULL,NOW()),
        ('vis-003','pt-003','2024-02-01 08:00:00','2024-02-05 14:00:00','inpatient', NULL,NULL,NOW()),
        ('vis-004','pt-004','2024-03-01 11:00:00','2024-03-01 11:15:00','ambulatory',NULL,NULL,NOW()),
        ('vis-005','pt-005','2024-03-15 14:00:00','2024-03-15 14:20:00','ambulatory',NULL,NULL,NOW())
    """)

    # ── raw_condition_occurrence ──────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_condition_occurrence (
            condition_occurrence_id    VARCHAR,
            person_id                  VARCHAR,
            visit_occurrence_id        VARCHAR,
            condition_source_value     VARCHAR,
            condition_source_vocabulary VARCHAR,
            condition_start_datetime   TIMESTAMP,
            condition_end_datetime     TIMESTAMP,
            condition_display          VARCHAR,
            loaded_at                  TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_condition_occurrence VALUES
        -- T2D + CKD cohort for RWE pitch
        ('cnd-001','pt-001','vis-001','E11.9', 'ICD10CM','2024-01-15 09:00:00',NULL,'Type 2 diabetes mellitus without complications',NOW()),
        ('cnd-002','pt-003','vis-003','E11.9', 'ICD10CM','2024-02-01 08:00:00',NULL,'Type 2 diabetes mellitus without complications',NOW()),
        ('cnd-003','pt-003','vis-003','N18.3', 'ICD10CM','2024-02-01 08:00:00',NULL,'Chronic kidney disease, stage 3',              NOW()),
        ('cnd-004','pt-004','vis-004','E11.9', 'ICD10CM','2024-03-01 11:00:00',NULL,'Type 2 diabetes mellitus without complications',NOW()),
        ('cnd-005','pt-005','vis-005','N18.3', 'ICD10CM','2024-03-15 14:00:00',NULL,'Chronic kidney disease, stage 3',              NOW())
    """)

    # ── raw_drug_exposure ─────────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_drug_exposure (
            drug_exposure_id              VARCHAR,
            person_id                     VARCHAR,
            visit_occurrence_id           VARCHAR,
            drug_source_value             VARCHAR,
            drug_source_vocabulary        VARCHAR,
            drug_display                  VARCHAR,
            drug_exposure_start_datetime  TIMESTAMP,
            drug_exposure_end_datetime    TIMESTAMP,
            quantity                      DECIMAL(10,2),
            days_supply                   INTEGER,
            loaded_at                     TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_drug_exposure VALUES
        -- Metformin prescriptions for T2D patients
        ('drg-001','pt-001','vis-001','860975','RxNorm','Metformin 500 MG Oral Tablet','2024-01-15 09:30:00',NULL, 60.0,30,NOW()),
        ('drg-002','pt-003','vis-003','860975','RxNorm','Metformin 500 MG Oral Tablet','2024-02-01 09:00:00',NULL, 60.0,30,NOW()),
        ('drg-003','pt-004','vis-004','860975','RxNorm','Metformin 500 MG Oral Tablet','2024-03-01 11:15:00',NULL,120.0,30,NOW())
    """)

    # ── raw_payer_plan_period ─────────────────────────────────────
    con.execute("""
        CREATE OR REPLACE TABLE raw.raw_payer_plan_period (
            payer_plan_period_id        VARCHAR,
            person_id                   VARCHAR,
            payer_source_value          VARCHAR,
            plan_source_value           VARCHAR,
            payer_plan_period_start_date DATE,
            payer_plan_period_end_date   DATE,
            loaded_at                   TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO raw.raw_payer_plan_period VALUES
        ('ppp-001','pt-001','Medicare',             'Medicare Part B','2023-01-01','2024-12-31',NOW()),
        ('ppp-002','pt-002','Blue Cross Blue Shield','PPO Plan',      '2023-01-01','2024-12-31',NOW()),
        ('ppp-003','pt-003','Medicare',             'Medicare Part B','2023-01-01','2024-12-31',NOW()),
        ('ppp-004','pt-004','Medicaid',             'MassHealth',     '2023-01-01','2024-12-31',NOW()),
        ('ppp-005','pt-005','Blue Cross Blue Shield','PPO Plan',      '2023-01-01','2024-12-31',NOW())
    """)

    # ── Summary ───────────────────────────────────────────────────
    print(f"Dev fixture created: {DB_PATH}")
    for tbl in ("raw_person", "raw_claim_header", "raw_claim_line",
                "raw_visit_occurrence", "raw_condition_occurrence",
                "raw_drug_exposure", "raw_payer_plan_period"):
        count = con.execute(f"SELECT COUNT(*) FROM raw.{tbl}").fetchone()[0]
        print(f"  raw.{tbl}: {count} rows")

    con.close()


if __name__ == "__main__":
    main()
