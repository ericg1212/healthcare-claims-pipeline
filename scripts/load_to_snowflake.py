import os
import argparse
import logging
from pathlib import Path
import snowflake.connector
from synthea_parser.bundle_processor import process_all_bundles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="HEALTHCARE_CLAIMS",
        warehouse="HEALTHCARE_WH",
        role="transformer",
        schema="RAW",
    )


def truncate_raw(cur):
    tables = [
        "RAW_PERSON", "RAW_VISIT_OCCURRENCE", "RAW_CONDITION_OCCURRENCE",
        "RAW_DRUG_EXPOSURE", "RAW_CLAIM_HEADER", "RAW_CLAIM_LINE",
        "RAW_PAYER_PLAN_PERIOD",
    ]
    for t in tables:
        cur.execute(f"TRUNCATE TABLE RAW.{t}")
        logger.info("Truncated %s", t)


def bulk_insert(cur, sql, rows, chunk_size=5000):
    for i in range(0, len(rows), chunk_size):
        cur.executemany(sql, rows[i:i + chunk_size])


def load_persons(cur, persons):
    rows = [
        (p.person_id, p.birth_year, p.birth_month, p.birth_day,
         p.gender_source_value, p.race_source_value,
         p.ethnicity_source_value, p.location_state)
        for p in persons
    ]
    bulk_insert(cur, "INSERT INTO RAW.RAW_PERSON VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())", rows)
    logger.info("Loaded %d persons", len(rows))


def load_conditions(cur, conditions):
    rows = [
        (c.condition_occurrence_id, c.person_id, c.visit_occurrence_id,
         c.condition_source_value, c.condition_source_vocabulary,
         c.condition_start_datetime, c.condition_end_datetime,
         c.condition_display)
        for c in conditions
    ]
    bulk_insert(cur, "INSERT INTO RAW.RAW_CONDITION_OCCURRENCE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())", rows)
    logger.info("Loaded %d conditions", len(rows))


def load_drugs(cur, drugs):
    rows = [
        (d.drug_exposure_id, d.person_id, d.visit_occurrence_id,
         d.drug_source_value, d.drug_source_vocabulary, d.drug_display,
         d.drug_exposure_start_datetime, d.drug_exposure_end_datetime,
         d.quantity, d.days_supply)
        for d in drugs
    ]
    bulk_insert(cur, "INSERT INTO RAW.RAW_DRUG_EXPOSURE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())", rows)
    logger.info("Loaded %d drug exposures", len(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fhir-dir", required=True)
    args = parser.parse_args()

    fhir_dir = Path(args.fhir_dir)
    logger.info("Parsing FHIR bundles from %s", fhir_dir)
    bundle = process_all_bundles(fhir_dir)

    conn = get_connection()
    cur = conn.cursor()

    truncate_raw(cur)
    load_persons(cur, bundle.persons)
    load_conditions(cur, bundle.conditions)
    load_drugs(cur, bundle.drugs)

    conn.commit()
    cur.close()
    conn.close()
    logger.info("Done.")


if __name__ == "__main__":
    main()
