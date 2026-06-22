# Copyright (c) 2026 Eric Grynspan. All rights reserved.
"""
Parser for FHIR R4 Coverage resources → OMOP PAYER_PLAN_PERIOD table.

Coverage represents a patient's insurance enrollment period — which payer
covered them and when. This is critical for the denial analysis: we use it
to confirm a claim is insured before flagging it as denied. A zero-payment
claim with NO_INSURANCE payer is self-pay, not a denial.
"""

from __future__ import annotations
from synthea_parser.models import PayerPlanPeriod
from synthea_parser.utils import extract_uuid, parse_date
import uuid as uuid_lib


def parse_coverage(resource: dict) -> PayerPlanPeriod:
    """Parse a FHIR Coverage resource into an OMOP PayerPlanPeriod record."""
    coverage_id = resource.get("id", str(uuid_lib.uuid4()))
    person_id = extract_uuid(
        resource.get("beneficiary", {}).get("reference", "")
    )

    # Payer name
    payors = resource.get("payor", [{}])
    payer_display = payors[0].get("display") if payors else None

    # Plan name
    plan_display = resource.get("class", [{}])[0].get("value") if resource.get("class") else None

    # Coverage period
    period = resource.get("period", {})
    start = parse_date(period.get("start"))
    end = parse_date(period.get("end"))

    return PayerPlanPeriod(
        payer_plan_period_id=coverage_id,
        person_id=person_id,
        payer_source_value=payer_display,
        plan_source_value=plan_display,
        payer_plan_period_start_date=start,
        payer_plan_period_end_date=end,
    )
