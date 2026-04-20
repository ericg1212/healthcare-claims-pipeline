"""
Load dev fixture data into Snowflake RAW schema.

Mirrors create_dev_fixtures.py — same rows, same schema — but targets
Snowflake instead of DuckDB. Run this once to populate the RAW layer
before running `make dbt-snowflake`.

Prerequisites:
    Set env vars: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD
    Or create a .env file at project root and run: source .env

Run from project root:
    python scripts/create_snowflake_fixtures.py
"""
import os
import snowflake.connector


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="HEALTHCARE_CLAIMS",
        warehouse="HEALTHCARE_WH",
        role="ACCOUNTADMIN",
        schema="RAW",
    )


DDL = """
CREATE OR REPLACE TABLE RAW.RAW_PERSON (
    person_id              VARCHAR,
    birth_year             INTEGER,
    birth_month            INTEGER,
    birth_day              INTEGER,
    gender_source_value    VARCHAR,
    race_source_value      VARCHAR,
    ethnicity_source_value VARCHAR,
    location_state         VARCHAR,
    loaded_at              TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE RAW.RAW_CLAIM_HEADER (
    claim_id          VARCHAR,
    patient_id        VARCHAR,
    payer_id          VARCHAR,
    payer_name        VARCHAR,
    claim_type        VARCHAR,
    submitted_amount  NUMBER(10,2),
    payment_amount    NUMBER(10,2),
    claim_date        DATE,
    procedure_display VARCHAR,
    loaded_at         TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE RAW.RAW_CLAIM_LINE (
    claim_line_id     VARCHAR,
    claim_id          VARCHAR,
    sequence          INTEGER,
    procedure_code    VARCHAR,
    procedure_display VARCHAR,
    quantity          NUMBER(10,2),
    submitted_amount  NUMBER(10,2),
    payment_amount    NUMBER(10,2),
    loaded_at         TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE RAW.RAW_VISIT_OCCURRENCE (
    visit_occurrence_id     VARCHAR,
    person_id               VARCHAR,
    visit_start_datetime    TIMESTAMP_NTZ,
    visit_end_datetime      TIMESTAMP_NTZ,
    visit_type_source_value VARCHAR,
    provider_id             VARCHAR,
    care_site_id            VARCHAR,
    loaded_at               TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE RAW.RAW_CONDITION_OCCURRENCE (
    condition_occurrence_id     VARCHAR,
    person_id                   VARCHAR,
    visit_occurrence_id         VARCHAR,
    condition_source_value      VARCHAR,
    condition_source_vocabulary VARCHAR,
    condition_start_datetime    TIMESTAMP_NTZ,
    condition_end_datetime      TIMESTAMP_NTZ,
    condition_display           VARCHAR,
    loaded_at                   TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE RAW.RAW_DRUG_EXPOSURE (
    drug_exposure_id             VARCHAR,
    person_id                    VARCHAR,
    visit_occurrence_id          VARCHAR,
    drug_source_value            VARCHAR,
    drug_source_vocabulary       VARCHAR,
    drug_display                 VARCHAR,
    drug_exposure_start_datetime TIMESTAMP_NTZ,
    drug_exposure_end_datetime   TIMESTAMP_NTZ,
    quantity                     NUMBER(10,2),
    days_supply                  INTEGER,
    loaded_at                    TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE RAW.RAW_PAYER_PLAN_PERIOD (
    payer_plan_period_id         VARCHAR,
    person_id                    VARCHAR,
    payer_source_value           VARCHAR,
    plan_source_value            VARCHAR,
    payer_plan_period_start_date DATE,
    payer_plan_period_end_date   DATE,
    loaded_at                    TIMESTAMP_NTZ
);
"""

DATA = {
    "RAW.RAW_PERSON": [
        ("pt-001", 1965,  3, 15, "M", "White",                     "Non-Hispanic", "MA"),
        ("pt-002", 1978,  7, 22, "F", "Black or African American",  "Non-Hispanic", "MA"),
        ("pt-003", 1952, 11,  8, "M", "White",                     "Non-Hispanic", "MA"),
        ("pt-004", 1983,  2, 14, "F", "Asian",                     "Non-Hispanic", "MA"),
        ("pt-005", 1970,  9, 30, "M", "White",                     "Hispanic",     "MA"),
    ],
    "RAW.RAW_CLAIM_HEADER": [
        ("clm-001","pt-001","pyr-med", "Medicare",              "professional", 350.00,   280.00,"2024-01-15","Office visit"),
        ("clm-002","pt-002","pyr-bcbs","Blue Cross Blue Shield", "professional", 200.00,   160.00,"2024-01-20","Annual wellness visit"),
        ("clm-003","pt-003","pyr-med", "Medicare",              "institutional",15000.00,12000.00,"2024-02-01","Inpatient stay"),
        ("clm-004","pt-001","pyr-med", "Medicare",              "professional", 8500.00,     0.00,"2024-02-10","Renal dialysis"),
        ("clm-005","pt-004","pyr-mcd", "Medicaid",              "pharmacy",      120.00,     0.00,"2024-03-01","Metformin 500mg"),
        ("clm-006","pt-005","pyr-bcbs","Blue Cross Blue Shield", "professional",  450.00,     0.00,"2024-03-15","Follow-up visit"),
        ("clm-007","pt-003","NO_INSURANCE","NO_INSURANCE",       "professional",  200.00,   200.00,"2024-04-01","Office visit"),
        ("clm-008","pt-002","NO_INSURANCE","NO_INSURANCE",       "professional",  150.00,   150.00,"2024-04-10","Lab draw"),
    ],
    "RAW.RAW_CLAIM_LINE": [
        ("cll-001","clm-001",1,"99213","Office or other outpatient visit",         1.0,  350.00, 280.00),
        ("cll-002","clm-002",1,"99395","Periodic preventive medicine reevaluation",1.0,  200.00, 160.00),
        ("cll-003","clm-003",1,"99223","Initial hospital care",                    1.0,15000.00,12000.00),
        ("cll-004","clm-004",1,"90945","Renal dialysis",                           1.0, 8500.00,   0.00),
        ("cll-005","clm-005",1,"72500","Metformin 500 MG Oral Tablet",            30.0,  120.00,   0.00),
        ("cll-006","clm-006",1,"99214","Office or other outpatient visit",         1.0,  450.00,   0.00),
    ],
    "RAW.RAW_VISIT_OCCURRENCE": [
        ("vis-001","pt-001","2024-01-15 09:00:00","2024-01-15 09:30:00","ambulatory",None,None),
        ("vis-002","pt-002","2024-01-20 10:00:00","2024-01-20 10:30:00","ambulatory",None,None),
        ("vis-003","pt-003","2024-02-01 08:00:00","2024-02-05 14:00:00","inpatient", None,None),
        ("vis-004","pt-004","2024-03-01 11:00:00","2024-03-01 11:15:00","ambulatory",None,None),
        ("vis-005","pt-005","2024-03-15 14:00:00","2024-03-15 14:20:00","ambulatory",None,None),
    ],
    "RAW.RAW_CONDITION_OCCURRENCE": [
        ("cnd-001","pt-001","vis-001","E11.9","ICD10CM","2024-01-15 09:00:00",None,"Type 2 diabetes mellitus without complications"),
        ("cnd-002","pt-003","vis-003","E11.9","ICD10CM","2024-02-01 08:00:00",None,"Type 2 diabetes mellitus without complications"),
        ("cnd-003","pt-003","vis-003","N18.3","ICD10CM","2024-02-01 08:00:00",None,"Chronic kidney disease, stage 3"),
        ("cnd-004","pt-004","vis-004","E11.9","ICD10CM","2024-03-01 11:00:00",None,"Type 2 diabetes mellitus without complications"),
        ("cnd-005","pt-005","vis-005","N18.3","ICD10CM","2024-03-15 14:00:00",None,"Chronic kidney disease, stage 3"),
    ],
    "RAW.RAW_DRUG_EXPOSURE": [
        ("drg-001","pt-001","vis-001","860975","RxNorm","Metformin 500 MG Oral Tablet","2024-01-15 09:30:00",None, 60.0,30),
        ("drg-002","pt-003","vis-003","860975","RxNorm","Metformin 500 MG Oral Tablet","2024-02-01 09:00:00",None, 60.0,30),
        ("drg-003","pt-004","vis-004","860975","RxNorm","Metformin 500 MG Oral Tablet","2024-03-01 11:15:00",None,120.0,30),
    ],
    "RAW.RAW_PAYER_PLAN_PERIOD": [
        ("ppp-001","pt-001","Medicare",             "Medicare Part B","2023-01-01","2024-12-31"),
        ("ppp-002","pt-002","Blue Cross Blue Shield","PPO Plan",      "2023-01-01","2024-12-31"),
        ("ppp-003","pt-003","Medicare",             "Medicare Part B","2023-01-01","2024-12-31"),
        ("ppp-004","pt-004","Medicaid",             "MassHealth",     "2023-01-01","2024-12-31"),
        ("ppp-005","pt-005","Blue Cross Blue Shield","PPO Plan",      "2023-01-01","2024-12-31"),
    ],
}

INSERT_SQL = {
    "RAW.RAW_PERSON":
        "INSERT INTO RAW.RAW_PERSON VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
    "RAW.RAW_CLAIM_HEADER":
        "INSERT INTO RAW.RAW_CLAIM_HEADER VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
    "RAW.RAW_CLAIM_LINE":
        "INSERT INTO RAW.RAW_CLAIM_LINE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
    "RAW.RAW_VISIT_OCCURRENCE":
        "INSERT INTO RAW.RAW_VISIT_OCCURRENCE VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
    "RAW.RAW_CONDITION_OCCURRENCE":
        "INSERT INTO RAW.RAW_CONDITION_OCCURRENCE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
    "RAW.RAW_DRUG_EXPOSURE":
        "INSERT INTO RAW.RAW_DRUG_EXPOSURE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
    "RAW.RAW_PAYER_PLAN_PERIOD":
        "INSERT INTO RAW.RAW_PAYER_PLAN_PERIOD VALUES (%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
}


def main() -> None:
    print("Connecting to Snowflake...")
    con = get_connection()
    cur = con.cursor()

    cur.execute("USE DATABASE HEALTHCARE_CLAIMS")
    cur.execute("USE WAREHOUSE HEALTHCARE_WH")

    print("Creating RAW tables...")
    for stmt in DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)

    print("Loading fixture data...")
    for table, rows in DATA.items():
        sql = INSERT_SQL[table]
        cur.executemany(sql, rows)
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    cur.close()
    con.close()
    print("\nSnowflake RAW layer ready. Run: make dbt-snowflake")


if __name__ == "__main__":
    main()
