# Copyright (c) 2026 Eric Grynspan. All rights reserved.
"""
Bundle processor — parses a complete Synthea FHIR patient bundle.

Synthea outputs one JSON file per patient. Each file is a FHIR Bundle
(a container) holding all resources for that patient: their demographic
info, all their encounters, conditions, medications, claims, and insurance
coverage over their simulated lifetime.

This module opens each bundle, routes each resource to the correct parser,
and returns all parsed records as a ParsedBundle — a single object containing
all the data needed to write one patient's worth of rows to the database.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from synthea_parser.models import (
    Person, VisitOccurrence, ConditionOccurrence,
    DrugExposure, ClaimHeader, ClaimLine, PayerPlanPeriod,
)
from synthea_parser.parsers.patient import parse_patient
from synthea_parser.parsers.encounter import parse_encounter
from synthea_parser.parsers.condition import parse_condition
from synthea_parser.parsers.medication import parse_medication_request
from synthea_parser.parsers.eob import parse_eob
from synthea_parser.parsers.coverage import parse_coverage

logger = logging.getLogger(__name__)


@dataclass
class ParsedBundle:
    """All parsed records extracted from one patient's FHIR bundle."""
    persons: list[Person] = field(default_factory=list)
    visits: list[VisitOccurrence] = field(default_factory=list)
    conditions: list[ConditionOccurrence] = field(default_factory=list)
    drugs: list[DrugExposure] = field(default_factory=list)
    claim_headers: list[ClaimHeader] = field(default_factory=list)
    claim_lines: list[ClaimLine] = field(default_factory=list)
    payer_periods: list[PayerPlanPeriod] = field(default_factory=list)

    def merge(self, other: ParsedBundle) -> None:
        """Append all records from another ParsedBundle into this one."""
        self.persons.extend(other.persons)
        self.visits.extend(other.visits)
        self.conditions.extend(other.conditions)
        self.drugs.extend(other.drugs)
        self.claim_headers.extend(other.claim_headers)
        self.claim_lines.extend(other.claim_lines)
        self.payer_periods.extend(other.payer_periods)


def process_bundle(path: Path) -> ParsedBundle | None:
    """
    Parse one Synthea FHIR patient bundle file into a ParsedBundle.

    Uses a per-symbol try/except + continue pattern so a single malformed
    resource does not abort parsing for the whole patient — same resilience
    pattern as the Project 1 stock pipeline.

    Args:
        path: Path to a Synthea-generated .json bundle file.

    Returns:
        ParsedBundle with all successfully parsed records, or None if the
        file itself cannot be read/parsed.
    """
    try:
        with open(path, encoding="utf-8") as f:
            bundle = json.load(f)
    except Exception as e:
        logger.error("Failed to open bundle %s: %s", path.name, e)
        return None

    result = ParsedBundle()

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType", "")

        try:
            if resource_type == "Patient":
                result.persons.append(parse_patient(resource))

            elif resource_type == "Encounter":
                result.visits.append(parse_encounter(resource))

            elif resource_type == "Condition":
                result.conditions.append(parse_condition(resource))

            elif resource_type == "MedicationRequest":
                result.drugs.append(parse_medication_request(resource))

            elif resource_type == "ExplanationOfBenefit":
                header, lines = parse_eob(resource)
                result.claim_headers.append(header)
                result.claim_lines.extend(lines)

            elif resource_type == "Coverage":
                result.payer_periods.append(parse_coverage(resource))

        except Exception as e:
            logger.warning(
                "Skipped %s resource in %s: %s",
                resource_type, path.name, e
            )
            continue

    return result


def process_all_bundles(fhir_dir: Path) -> ParsedBundle:
    """
    Process all patient bundle files in a directory.

    Returns a single merged ParsedBundle containing all records
    from all patients — ready to be loaded into the database.
    """
    merged = ParsedBundle()
    files = list(fhir_dir.glob("*.json"))

    if not files:
        logger.warning("No FHIR JSON files found in %s", fhir_dir)
        return merged

    logger.info("Processing %d patient bundles from %s", len(files), fhir_dir)

    for path in files:
        bundle = process_bundle(path)
        if bundle is None:
            continue
        merged.merge(bundle)

    logger.info(
        "Parsed: %d patients | %d visits | %d conditions | %d drugs | "
        "%d claims (%d lines) | %d coverage periods",
        len(merged.persons), len(merged.visits), len(merged.conditions),
        len(merged.drugs), len(merged.claim_headers), len(merged.claim_lines),
        len(merged.payer_periods),
    )

    return merged
