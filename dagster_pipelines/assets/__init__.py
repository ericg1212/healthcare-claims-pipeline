import os
import subprocess
import sys
from pathlib import Path

from dagster import AssetExecutionContext, AssetKey, AssetOut, Config, Output, multi_asset
from dagster_dbt import DbtCliResource, dbt_assets

DBT_MANIFEST = Path(__file__).parent.parent.parent / "dbt_project" / "target" / "manifest.json"
_REPO_ROOT = Path(__file__).parent.parent.parent

RAW_TABLES = [
    "raw_person",
    "raw_claim_header",
    "raw_claim_line",
    "raw_visit_occurrence",
    "raw_condition_occurrence",
    "raw_drug_exposure",
    "raw_payer_plan_period",
]


class FhirLoadConfig(Config):
    fhir_dir: str = str(_REPO_ROOT / "data" / "synthea_output")


@multi_asset(
    outs={t: AssetOut(key=AssetKey(["raw", t])) for t in RAW_TABLES},
    group_name="ingestion",
    compute_kind="python",
)
def raw_claims_load(context: AssetExecutionContext, config: FhirLoadConfig):
    """Parse Synthea FHIR bundles from fhir_dir and load all 7 RAW tables to Snowflake."""
    fhir_path = Path(config.fhir_dir)
    if not fhir_path.exists() or not any(fhir_path.glob("*.json")):
        raise FileNotFoundError(f"No FHIR JSON files found in {fhir_path}")

    context.log.info("Loading FHIR bundles from %s", fhir_path)
    result = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "scripts" / "load_to_snowflake.py"),
         "--fhir-dir", str(fhir_path)],
        cwd=str(_REPO_ROOT),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        context.log.info(line)
    if result.returncode != 0:
        context.log.error(result.stderr)
        raise RuntimeError("FHIR load failed — see logs above")

    for table in RAW_TABLES:
        yield Output(value=None, output_name=table)


@dbt_assets(manifest=DBT_MANIFEST)
def healthcare_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
