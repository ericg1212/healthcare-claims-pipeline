# Copyright (c) 2026 Eric Grynspan. All rights reserved.
"""
Parser for FHIR R4 Patient resources → OMOP PERSON table.

De-identification boundary: exact birth dates are reduced to birth_year only.
In production with real PHI (Protected Health Information), name, SSN, and
other direct identifiers would be hashed or dropped here before any storage.
"""

from __future__ import annotations
from synthea_parser.models import Person


def parse_patient(resource: dict) -> Person:
    """Parse a FHIR Patient resource into an OMOP Person record."""
    person_id = resource.get("id", "")

    # Birth date — de-identified to year only at this boundary
    birth_str = resource.get("birthDate", "")
    birth_year, birth_month, birth_day = None, None, None
    if birth_str:
        parts = birth_str.split("-")
        birth_year = int(parts[0]) if parts else None
        birth_month = int(parts[1]) if len(parts) > 1 else None
        birth_day = int(parts[2]) if len(parts) > 2 else None

    gender = resource.get("gender", "unknown")

    # Race and ethnicity from FHIR extensions
    race, ethnicity = _extract_race_ethnicity(resource)

    # State from address
    addresses = resource.get("address", [])
    state = addresses[0].get("state") if addresses else None

    return Person(
        person_id=person_id,
        birth_year=birth_year or 1900,
        birth_month=birth_month,
        birth_day=birth_day,
        gender_source_value=gender,
        race_source_value=race,
        ethnicity_source_value=ethnicity,
        location_state=state,
    )


def _extract_race_ethnicity(resource: dict) -> tuple[str | None, str | None]:
    """
    Extract race and ethnicity from FHIR US Core extensions.
    These are stored as extensions rather than top-level fields in FHIR R4.
    """
    race, ethnicity = None, None
    for ext in resource.get("extension", []):
        url = ext.get("url", "")
        if "us-core-race" in url:
            for sub in ext.get("extension", []):
                if sub.get("url") == "text":
                    race = sub.get("valueString")
        elif "us-core-ethnicity" in url:
            for sub in ext.get("extension", []):
                if sub.get("url") == "text":
                    ethnicity = sub.get("valueString")
    return race, ethnicity
