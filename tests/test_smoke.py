from synthea_parser.utils import extract_uuid, parse_datetime, hash_id


def test_extract_uuid_urn():
    assert extract_uuid("urn:uuid:abc-123") == "abc-123"


def test_extract_uuid_reference():
    assert extract_uuid("Patient/abc-123") == "abc-123"


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


def test_hash_id_deterministic():
    assert hash_id("patient-1") == hash_id("patient-1")
    assert hash_id("patient-1") != hash_id("patient-2")
