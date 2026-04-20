"""
Parser for FHIR R4 MedicationRequest resources → OMOP DRUG_EXPOSURE table.

A MedicationRequest is a prescription — what drug was ordered, for whom,
and when. Synthea codes medications using RxNorm (a standardized medication
code system maintained by the U.S. National Library of Medicine).

Metformin (RxNorm concept for the base ingredient) is the key drug we track
for the T2D + CKD RWE (Real-World Evidence) cohort analysis — its
underprescription in CKD patients is the headline finding.
"""

from __future__ import annotations
from synthea_parser.models import DrugExposure
from synthea_parser.utils import extract_uuid, parse_datetime, get_coding
import uuid as uuid_lib

MEDICATION_SYSTEMS = [
    "http://www.nlm.nih.gov/research/umls/rxnorm",
]


def parse_medication_request(resource: dict) -> DrugExposure:
    """Parse a FHIR MedicationRequest into an OMOP DrugExposure record."""
    drug_id = resource.get("id", str(uuid_lib.uuid4()))
    person_id = extract_uuid(
        resource.get("subject", {}).get("reference", "")
    )

    # Encounter link
    encounter_ref = resource.get("encounter", {}).get("reference", "")
    visit_occurrence_id = extract_uuid(encounter_ref) if encounter_ref else None

    # Drug code — RxNorm
    med_concept = resource.get("medicationCodeableConcept", {})
    codings = med_concept.get("coding", [])
    code, display, _ = get_coding(codings, preferred_systems=MEDICATION_SYSTEMS)

    # Prescription dates
    authored_on = parse_datetime(resource.get("authoredOn"))

    # Dosage — quantity and days supply if available
    quantity, days_supply = None, None
    dosage = resource.get("dispenseRequest", {})
    if dosage:
        qty = dosage.get("quantity", {})
        quantity = qty.get("value")
        duration = dosage.get("expectedSupplyDuration", {})
        days_supply = int(duration.get("value", 0)) or None

    return DrugExposure(
        drug_exposure_id=drug_id,
        person_id=person_id,
        visit_occurrence_id=visit_occurrence_id,
        drug_source_value=code,
        drug_source_vocabulary="RxNorm",
        drug_display=display or None,
        drug_exposure_start_datetime=authored_on,
        drug_exposure_end_datetime=None,
        quantity=quantity,
        days_supply=days_supply,
    )
