# Copyright (c) 2026 Eric Grynspan. All rights reserved.
"""
Parser for FHIR R4 Condition resources → OMOP CONDITION_OCCURRENCE table.

A Condition represents a diagnosis — T2D (Type 2 Diabetes), CKD (Chronic
Kidney Disease), hypertension, etc. Synthea codes conditions in either
SNOMED CT or ICD-10-CM depending on context.

This is the table we query to identify the T2D + CKD patient cohort for
the RWE (Real-World Evidence) analysis.
"""

from __future__ import annotations
from synthea_parser.models import ConditionOccurrence
from synthea_parser.utils import (
    extract_uuid,
    parse_datetime,
    get_coding,
    system_to_vocabulary_id,
)
import uuid as uuid_lib

# Preferred code systems in priority order for OMOP mapping
CONDITION_SYSTEMS = [
    "http://hl7.org/fhir/sid/icd-10-cm",   # ICD-10-CM preferred for OMOP
    "http://snomed.info/sct",               # SNOMED fallback
]


def parse_condition(resource: dict) -> ConditionOccurrence:
    """Parse a FHIR Condition resource into an OMOP ConditionOccurrence record."""
    condition_id = resource.get("id", str(uuid_lib.uuid4()))
    person_id = extract_uuid(
        resource.get("subject", {}).get("reference", "")
    )

    # Encounter link
    encounter_ref = resource.get("encounter", {}).get("reference", "")
    visit_occurrence_id = extract_uuid(encounter_ref) if encounter_ref else None

    # Condition code — ICD-10-CM or SNOMED
    codings = resource.get("code", {}).get("coding", [])
    code, display, system = get_coding(codings, preferred_systems=CONDITION_SYSTEMS)
    vocabulary_id = system_to_vocabulary_id(system) if system else "SNOMED"

    # Onset and resolution dates
    onset = parse_datetime(
        resource.get("onsetDateTime") or resource.get("onsetPeriod", {}).get("start")
    )
    abatement = parse_datetime(
        resource.get("abatementDateTime")
        or resource.get("abatementPeriod", {}).get("end")
    )

    return ConditionOccurrence(
        condition_occurrence_id=condition_id,
        person_id=person_id,
        visit_occurrence_id=visit_occurrence_id,
        condition_source_value=code,
        condition_source_vocabulary=vocabulary_id,
        condition_start_datetime=onset,
        condition_end_datetime=abatement,
        condition_display=display or None,
    )
