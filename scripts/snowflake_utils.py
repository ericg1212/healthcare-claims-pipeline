# Copyright (c) 2026 Eric Grynspan. All rights reserved.
import os
import snowflake.connector


def get_connection(role: str = "TRANSFORMER") -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        database="HEALTHCARE_CLAIMS",
        warehouse="HEALTHCARE_WH",
        role=role,
        schema="RAW",
    )
