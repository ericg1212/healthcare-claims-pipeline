"""
Shared utilities for the FHIR parser.

De-identification (de-id): the process of removing or obscuring fields that
could identify a real patient — required under HIPAA (Health Insurance
Portability and Accountability Act) for any real PHI (Protected Health
Information). Synthea data is synthetic and PHI-free by design, but we
implement the pattern here so the pipeline is production-ready by construction.
"""

from __future__ import annotations
import hashlib
from datetime import datetime
from typing import Optional


def extract_uuid(reference: str) -> str:
    """
    Extract a bare UUID from a FHIR reference string.
    FHIR references look like: "urn:uuid:abc123..." or "Patient/abc123"
    We want just the UUID portion as our internal ID.
    """
    if reference.startswith("urn:uuid:"):
        return reference.replace("urn:uuid:", "")
    if "/" in reference:
        return reference.split("/")[-1]
    return reference


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    Parse FHIR datetime strings into Python datetime objects.
    FHIR uses ISO 8601 format: "2023-04-15T10:30:00-05:00"
    Handles date-only strings too: "2023-04-15"
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_date(value: Optional[str]):
    """Parse FHIR date string to Python date."""
    dt = parse_datetime(value)
    return dt.date() if dt else None


def hash_id(value: str) -> str:
    """
    One-way hash for de-identification of identifiers.
    In production with real PHI: patient names, SSNs, exact DOBs would be
    hashed here before touching any storage layer. With Synthea data this
    is a no-op pattern, but the boundary is explicit.
    """
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def get_coding(coding_list: list, preferred_systems: list[str]) -> tuple[str, str, str]:
    """
    Extract (code, display, system) from a FHIR coding array.
    FHIR often provides multiple codings for the same concept — one in SNOMED,
    one in ICD-10, etc. We prefer the system most useful for OMOP mapping.

    Returns ("", "", "") if nothing found.
    """
    system_priority = {s: i for i, s in enumerate(preferred_systems)}

    best = None
    best_priority = float("inf")

    for coding in coding_list:
        system = coding.get("system", "")
        priority = system_priority.get(system, float("inf"))
        if priority < best_priority:
            best = coding
            best_priority = priority

    if best:
        return (
            best.get("code", ""),
            best.get("display", ""),
            best.get("system", ""),
        )
    return ("", "", "")


def system_to_vocabulary_id(system_url: str) -> str:
    """
    Map a FHIR system URL to an OMOP vocabulary_id string.
    OMOP uses short IDs like "ICD10CM" or "SNOMED" rather than full URLs.
    """
    mapping = {
        "http://snomed.info/sct": "SNOMED",
        "http://hl7.org/fhir/sid/icd-10-cm": "ICD10CM",
        "http://www.nlm.nih.gov/research/umls/rxnorm": "RxNorm",
        "http://loinc.org": "LOINC",
    }
    return mapping.get(system_url, system_url)


def make_claim_line_id(claim_id: str, sequence: int) -> str:
    """Composite primary key for claim line items: claimId_sequence."""
    return f"{claim_id}_{sequence}"


def is_insured(payer_display: Optional[str]) -> bool:
    """
    Returns True if the claim has real insurance coverage.
    Synthea represents uninsured patients as payer "NO_INSURANCE".
    We exclude these from denial analysis — a zero payment for an uninsured
    patient is self-pay (patient responsibility), not a payer denial.
    """
    if not payer_display:
        return False
    return payer_display.upper() != "NO_INSURANCE"


def derive_denial_flag(
    payer_display: Optional[str],
    submitted_amount: float,
    payment_amount: float,
) -> bool:
    """
    Derive whether a claim was denied based on payment pattern.

    Logic:
    - Must be an insured claim (not NO_INSURANCE / self-pay)
    - Must have a submitted amount > 0 (a real claim was filed)
    - Must have payment = 0 (payer did not pay anything)

    Synthea does not generate CARC (Claim Adjustment Reason Codes) natively.
    The specific denial reason is assigned by the dbt attribution model on top.
    """
    if not is_insured(payer_display):
        return False
    return submitted_amount > 0 and payment_amount == 0.0
