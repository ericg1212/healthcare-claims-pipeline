"""
Parser for FHIR R4 ExplanationOfBenefit (EOB) resources.

EOB = Explanation of Benefits — the record produced when a payer (insurance
company) processes a claim. It shows what was billed, what was paid, and
in real data would include denial reason codes. Synthea generates EOBs
without denial codes, so denial attribution is handled downstream in dbt.

Each EOB maps to:
  - 1 ClaimHeader row
  - 1+ ClaimLine rows (one per service/procedure line item)
"""

from __future__ import annotations
from typing import Optional
from synthea_parser.models import ClaimHeader, ClaimLine
from synthea_parser.utils import (
    extract_uuid,
    parse_datetime,
    parse_date,
    get_coding,
    make_claim_line_id,
    derive_denial_flag,
)

# SNOMED CT is Synthea's preferred procedure coding system
PROCEDURE_SYSTEMS = [
    "http://snomed.info/sct",
    "http://www.ama-assn.org/go/cpt",  # CPT4 fallback (rarely used by Synthea)
]


def parse_eob(resource: dict) -> tuple[ClaimHeader, list[ClaimLine]]:
    """
    Parse a single FHIR ExplanationOfBenefit resource into a ClaimHeader
    and its associated ClaimLine records.

    Args:
        resource: A dict representing one FHIR EOB resource from a patient bundle.

    Returns:
        A tuple of (ClaimHeader, [ClaimLine, ...])
    """
    claim_id = resource.get("id", "")
    person_id = extract_uuid(
        resource.get("patient", {}).get("reference", "")
    )

    # Encounter (visit) reference — links the claim back to the clinical visit
    visit_ref = resource.get("encounter", [{}])
    visit_occurrence_id = None
    if visit_ref and isinstance(visit_ref, list):
        visit_occurrence_id = extract_uuid(
            visit_ref[0].get("reference", "")
        )

    # Payer — who the claim was submitted to
    payer_display = resource.get("insurer", {}).get("display")

    # Claim type: "professional", "pharmacy", or "institutional"
    claim_type = _extract_claim_type(resource)

    # Billing period — the date range the claim covers
    billable_period = resource.get("billablePeriod", {})
    claim_start_date = parse_date(billable_period.get("start"))
    claim_end_date = parse_date(billable_period.get("end"))

    # Payment — what the payer actually paid
    payment_amount = (
        resource.get("payment", {})
        .get("amount", {})
        .get("value", 0.0)
    ) or 0.0

    # Submitted amount — total billed to the payer
    submitted_amount = _extract_submitted_amount(resource)

    # Derive denial flag from payment pattern (see utils.py)
    denial_flag = derive_denial_flag(payer_display, submitted_amount, payment_amount)

    header = ClaimHeader(
        claim_id=claim_id,
        person_id=person_id,
        visit_occurrence_id=visit_occurrence_id,
        payer_display=payer_display,
        claim_type=claim_type,
        claim_start_date=claim_start_date,
        claim_end_date=claim_end_date,
        submitted_amount=submitted_amount,
        payment_amount=payment_amount,
        denial_flag=denial_flag,
    )

    lines = _parse_claim_lines(resource, claim_id, person_id)

    return header, lines


def _extract_claim_type(resource: dict) -> Optional[str]:
    """
    Extract claim type from the EOB type coding.
    Synthea uses: professional | pharmacy | institutional
    These map to CMS (Centers for Medicare & Medicaid Services) claim categories.
    """
    for coding in resource.get("type", {}).get("coding", []):
        code = coding.get("code", "").lower()
        if code in ("professional", "pharmacy", "institutional"):
            return code
    return None


def _extract_submitted_amount(resource: dict) -> float:
    """
    Extract the total submitted (billed) amount from EOB.total[].
    Synthea places this under category.coding[code="submitted"].
    """
    for total in resource.get("total", []):
        for coding in total.get("category", {}).get("coding", []):
            if coding.get("code") == "submitted":
                return total.get("amount", {}).get("value", 0.0) or 0.0
    return 0.0


def _parse_claim_lines(
    resource: dict,
    claim_id: str,
    person_id: str,
) -> list[ClaimLine]:
    """
    Parse EOB.item[] into ClaimLine records.
    Each item is one service or procedure billed on the claim.
    """
    lines = []

    for item in resource.get("item", []):
        sequence = item.get("sequence", 0)

        # Procedure code — what service was performed
        product = item.get("productOrService", {})
        proc_code, proc_display, _ = get_coding(
            product.get("coding", []),
            preferred_systems=PROCEDURE_SYSTEMS,
        )

        # Place of service — where the service was delivered
        place = item.get("locationCodeableConcept", {})
        place_code = ""
        for coding in place.get("coding", []):
            place_code = coding.get("code", "")
            break

        # Service dates
        serviced_period = item.get("servicedPeriod", {})
        service_start = parse_datetime(
            serviced_period.get("start") or item.get("servicedDate")
        )
        service_end = parse_datetime(serviced_period.get("end"))

        lines.append(
            ClaimLine(
                claim_line_id=make_claim_line_id(claim_id, sequence),
                claim_id=claim_id,
                person_id=person_id,
                line_sequence=sequence,
                procedure_source_value=proc_code or None,
                procedure_display=proc_display or None,
                service_place_code=place_code or None,
                service_start_datetime=service_start,
                service_end_datetime=service_end,
            )
        )

    return lines
