# Security Policy

## Reporting a Vulnerability

To report a security vulnerability, email **eric.grynspan@gmail.com** with:

- Description of the vulnerability
- Steps to reproduce
- Potential impact

Do not open a public GitHub issue for security findings. You will receive a response within 5 business days.

## Notes

This pipeline processes **synthetic data only** (Synthea FHIR R4). No real PHI is present in this repository. In a production deployment with real patient data, the de-identification boundary is enforced at the FHIR parser layer (`synthea_parser/utils.py`) before any data reaches storage.
