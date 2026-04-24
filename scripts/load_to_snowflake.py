import argparse
import logging
from pathlib import Path
try:
    from scripts.snowflake_utils import get_connection
except ImportError:
    from snowflake_utils import get_connection
from synthea_parser.bundle_processor import process_bundle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 200  # bundles per Snowflake flush


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


def flush(cur, buf):
    if buf["persons"]:
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_PERSON VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["persons"])

    if buf["visits"]:
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_VISIT_OCCURRENCE VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["visits"])

    if buf["conditions"]:
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_CONDITION_OCCURRENCE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["conditions"])

    if buf["drugs"]:
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_DRUG_EXPOSURE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["drugs"])

    if buf["claim_headers"]:
        # RAW_CLAIM_HEADER: claim_id, patient_id, payer_id, payer_name,
        #   claim_type, submitted_amount, payment_amount, claim_date, procedure_display
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_CLAIM_HEADER VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["claim_headers"])

    if buf["claim_lines"]:
        # RAW_CLAIM_LINE: claim_line_id, claim_id, sequence, procedure_code,
        #   procedure_display, quantity, submitted_amount, payment_amount
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_CLAIM_LINE VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["claim_lines"])

    if buf["payer_periods"]:
        bulk_insert(cur,
            "INSERT INTO RAW.RAW_PAYER_PLAN_PERIOD VALUES (%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP())",
            buf["payer_periods"])

    for key in buf:
        buf[key].clear()


def make_buffer():
    return {k: [] for k in
            ["persons", "visits", "conditions", "drugs",
             "claim_headers", "claim_lines", "payer_periods"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fhir-dir", required=True)
    args = parser.parse_args()

    fhir_dir = Path(args.fhir_dir)
    files = sorted(fhir_dir.glob("*.json"))
    total = len(files)
    if not total:
        logger.error("No FHIR JSON files found in %s", fhir_dir)
        return

    logger.info("Found %d bundle files in %s", total, fhir_dir)

    conn = get_connection()
    cur = conn.cursor()
    truncate_raw(cur)
    conn.commit()

    buf = make_buffer()

    for i, path in enumerate(files, 1):
        bundle = process_bundle(path)
        if bundle is None:
            continue

        for p in bundle.persons:
            buf["persons"].append((
                p.person_id, p.birth_year, p.birth_month, p.birth_day,
                p.gender_source_value, p.race_source_value,
                p.ethnicity_source_value, p.location_state))

        for v in bundle.visits:
            buf["visits"].append((
                v.visit_occurrence_id, v.person_id,
                v.visit_start_datetime, v.visit_end_datetime,
                v.visit_type_source_value, v.provider_id, v.care_site_id))

        for c in bundle.conditions:
            buf["conditions"].append((
                c.condition_occurrence_id, c.person_id, c.visit_occurrence_id,
                c.condition_source_value, c.condition_source_vocabulary,
                c.condition_start_datetime, c.condition_end_datetime,
                c.condition_display))

        for d in bundle.drugs:
            buf["drugs"].append((
                d.drug_exposure_id, d.person_id, d.visit_occurrence_id,
                d.drug_source_value, d.drug_source_vocabulary, d.drug_display,
                d.drug_exposure_start_datetime, d.drug_exposure_end_datetime,
                d.quantity, d.days_supply))

        # Build claim_id → first procedure_display lookup from lines
        # procedure_display drives CARC 197 (Renal dialysis) in fct_denials
        first_proc = {}
        for l in bundle.claim_lines:
            if l.claim_id not in first_proc and l.procedure_display:
                first_proc[l.claim_id] = l.procedure_display

        for h in bundle.claim_headers:
            buf["claim_headers"].append((
                h.claim_id,
                h.person_id,           # stored as patient_id in raw table
                None,                  # payer_id — not available in FHIR EOB
                h.payer_display,       # stored as payer_name in raw table
                h.claim_type,
                h.submitted_amount,
                h.payment_amount,
                h.claim_start_date,    # stored as claim_date in raw table
                first_proc.get(h.claim_id)))  # procedure_display from first line

        for l in bundle.claim_lines:
            buf["claim_lines"].append((
                l.claim_line_id, l.claim_id,
                l.line_sequence,           # stored as sequence in raw table
                l.procedure_source_value,  # stored as procedure_code in raw table
                l.procedure_display,
                None,                      # quantity — not in ClaimLine model
                0.0,                       # submitted_amount — not in ClaimLine model
                0.0))                      # payment_amount — not in ClaimLine model

        for pp in bundle.payer_periods:
            buf["payer_periods"].append((
                pp.payer_plan_period_id, pp.person_id,
                pp.payer_source_value, pp.plan_source_value,
                pp.payer_plan_period_start_date, pp.payer_plan_period_end_date))

        if i % BATCH_SIZE == 0:
            flush(cur, buf)
            conn.commit()
            logger.info("Flushed batch %d/%d (%.0f%%)", i, total, i / total * 100)

    flush(cur, buf)
    conn.commit()

    logger.info("Done. Loaded %d bundles. Row counts:", total)
    raw_tables = [
        "RAW_PERSON", "RAW_VISIT_OCCURRENCE", "RAW_CONDITION_OCCURRENCE",
        "RAW_DRUG_EXPOSURE", "RAW_CLAIM_HEADER", "RAW_CLAIM_LINE",
        "RAW_PAYER_PLAN_PERIOD",
    ]
    for table in raw_tables:
        count = cur.execute(f"SELECT COUNT(*) FROM RAW.{table}").fetchone()[0]
        logger.info("  %-30s %d rows", table, count)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
