from pathlib import Path

from dagster import AssetSelection, Definitions, EnvVar, define_asset_job
from dagster_dbt import DbtCliResource

from dagster_pipelines.assets import healthcare_dbt_assets, raw_claims_load
from dagster_pipelines.resources import SnowflakeResource

DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt_project"

# Full pipeline: ingestion → dbt (topological order enforced by asset graph)
healthcare_pipeline = define_asset_job(
    name="healthcare_pipeline",
    selection=AssetSelection.all(),
    description="FHIR parse + Snowflake load → dbt staging → dbt mart",
)

defs = Definitions(
    assets=[raw_claims_load, healthcare_dbt_assets],
    jobs=[healthcare_pipeline],
    resources={
        "dbt": DbtCliResource(
            project_dir=str(DBT_PROJECT_DIR),
            profiles_dir=str(DBT_PROJECT_DIR / "profiles"),
            target="prod",
        ),
        "snowflake": SnowflakeResource(
            account=EnvVar("SNOWFLAKE_ACCOUNT"),
            user=EnvVar("SNOWFLAKE_USER"),
            password=EnvVar("SNOWFLAKE_PASSWORD"),
        ),
    },
)
