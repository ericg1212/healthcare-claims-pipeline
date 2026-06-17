# Copyright (c) 2026 Eric Grynspan. All rights reserved.
import pytest
from synthea_parser.utils import (
    extract_uuid, parse_datetime, hash_id,
    get_coding, is_insured, derive_denial_flag,
)


# ── extract_uuid ────────────────────────────────────────────────────────────

def test_extract_uuid_urn():
    assert extract_uuid("urn:uuid:abc-123") == "abc-123"


def test_extract_uuid_reference():
    assert extract_uuid("Patient/abc-123") == "abc-123"


@pytest.mark.parametrize("ref,expected", [
    ("urn:uuid:abc-123",          "abc-123"),
    ("Patient/abc-123",           "abc-123"),
    ("Practitioner/dr-456",       "dr-456"),
    ("Organization/org-789",      "org-789"),
    ("bare-id",                   "bare-id"),
    ("urn:uuid:",                  ""),
    ("Patient/",                  ""),
])
def test_extract_uuid_parametrized(ref, expected):
    assert extract_uuid(ref) == expected


# ── parse_datetime ──────────────────────────────────────────────────────────

def test_parse_datetime_iso():
    dt = parse_datetime("2023-04-15T10:30:00")
    assert dt is not None
    assert dt.year == 2023


def test_parse_datetime_date_only():
    dt = parse_datetime("2023-04-15")
    assert dt is not None
    assert dt.month == 4


def test_parse_datetime_none():
    assert parse_datetime(None) is None


@pytest.mark.parametrize("value,expected_year", [
    ("2023-04-15T10:30:00",    2023),
    ("2023-04-15",             2023),
    ("1900-01-01",             1900),
    ("2099-12-31",             2099),
])
def test_parse_datetime_valid_formats(value, expected_year):
    dt = parse_datetime(value)
    assert dt is not None
    assert dt.year == expected_year


@pytest.mark.parametrize("value", [
    "",
    "not-a-date",
    "15-04-2023",
    "April 15 2023",
])
def test_parse_datetime_invalid_returns_none(value):
    assert parse_datetime(value) is None


# ── hash_id ─────────────────────────────────────────────────────────────────

def test_hash_id_deterministic():
    assert hash_id("patient-1") == hash_id("patient-1")
    assert hash_id("patient-1") != hash_id("patient-2")


@pytest.mark.parametrize("value", ["", "a", "x" * 1000])
def test_hash_id_always_returns_16_chars(value):
    assert len(hash_id(value)) == 16


# ── get_coding ──────────────────────────────────────────────────────────────

def test_get_coding_empty_list():
    assert get_coding([], ["http://snomed.info/sct"]) == ("", "", "")


def test_get_coding_prefers_priority_system():
    codings = [
        {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9", "display": "T2D ICD"},
        {"system": "http://snomed.info/sct",             "code": "44054006", "display": "T2D SNOMED"},
    ]
    code, display, system = get_coding(
        codings,
        ["http://snomed.info/sct", "http://hl7.org/fhir/sid/icd-10-cm"],
    )
    assert code == "44054006"
    assert system == "http://snomed.info/sct"


def test_get_coding_no_preferred_match_returns_empty():
    # get_coding is strict: only returns codings whose system is in preferred_systems
    codings = [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "N18.3", "display": "CKD3"}]
    assert get_coding(codings, ["http://snomed.info/sct"]) == ("", "", "")


# ── is_insured ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("payer,expected", [
    ("Medicare",              True),
    ("Medicaid",              True),
    ("Blue Cross Blue Shield", True),
    ("NO_INSURANCE",          False),
    ("no_insurance",          False),
    ("",                      False),
    (None,                    False),
])
def test_is_insured(payer, expected):
    assert is_insured(payer) == expected


# ── derive_denial_flag ───────────────────────────────────────────────────────

@pytest.mark.parametrize("payer,submitted,payment,expected", [
    ("Medicare",    350.0,   0.0,  True),   # insured, full denial
    ("Medicare",    350.0, 280.0,  False),  # insured, partial payment = not denied
    ("NO_INSURANCE", 350.0,   0.0,  False),  # self-pay excluded
    ("Medicaid",      0.0,   0.0,  False),  # zero submitted = no claim filed
    ("Medicaid",    120.0,   0.0,  True),   # pharmacy denial
    (None,          100.0,   0.0,  False),  # no payer
])
def test_derive_denial_flag(payer, submitted, payment, expected):
    assert derive_denial_flag(payer, submitted, payment) == expected
