"""
Parser for FHIR R4 Encounter resources → OMOP VISIT_OCCURRENCE table.

An Encounter represents one clinical interaction: an office visit, hospital
admission, emergency visit, etc. Every claim and condition links back to
an encounter, making this the central join key in the data model.
"""

from __future__ import annotations
from synthea_parser.models import VisitOccurrence
from synthea_parser.utils import extract_uuid, parse_datetime


def parse_encounter(resource: dict) -> VisitOccurrence:
    """Parse a FHIR Encounter resource into an OMOP VisitOccurrence record."""
    visit_id = resource.get("id", "")
    person_id = extract_uuid(
        resource.get("subject", {}).get("reference", "")
    )

    # Visit dates
    period = resource.get("period", {})
    start = parse_datetime(period.get("start"))
    end = parse_datetime(period.get("end"))

    # Visit type — inpatient, ambulatory, emergency, etc.
    visit_type = None
    for coding in resource.get("type", [{}])[0].get("coding", []):
        visit_type = coding.get("display") or coding.get("code")
        break

    # Provider — the practitioner responsible for the visit
    provider_id = None
    participants = resource.get("participant", [])
    if participants:
        individual = participants[0].get("individual", {})
        provider_id = extract_uuid(individual.get("reference", "")) or None

    # Care site — the facility where the visit occurred
    care_site_id = None
    location = resource.get("location", [])
    if location:
        loc_ref = location[0].get("location", {}).get("reference", "")
        care_site_id = extract_uuid(loc_ref) or None

    return VisitOccurrence(
        visit_occurrence_id=visit_id,
        person_id=person_id,
        visit_start_datetime=start,
        visit_end_datetime=end,
        visit_type_source_value=visit_type,
        provider_id=provider_id,
        care_site_id=care_site_id,
    )
