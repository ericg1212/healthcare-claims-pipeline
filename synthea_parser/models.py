"""
Pydantic models for FHIR R4 resources produced by Synthea.

Each model maps to one OMOP CDM (Observational Medical Outcomes Partnership
Common Data Model) target table. Fields are typed and validated at parse time
so bad data surfaces immediately rather than silently corrupting downstream tables.

FHIR R4 = the current standard format for exchanging healthcare data between systems.
Synthea generates patient bundles in this format — one JSON file per patient.
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


# ── PERSON (maps from FHIR Patient resource) ──────────────────────────────────

class Person(BaseModel):
    """One row per patient in OMOP PERSON table."""
    person_id: str                          # Synthea UUID
    birth_year: int
    birth_month: Optional[int] = None
    birth_day: Optional[int] = None
    gender_source_value: str               # "male" | "female" | "unknown"
    race_source_value: Optional[str] = None
    ethnicity_source_value: Optional[str] = None
    location_state: Optional[str] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── VISIT_OCCURRENCE (maps from FHIR Encounter resource) ─────────────────────

class VisitOccurrence(BaseModel):
    """One row per clinical encounter (office visit, hospital stay, etc.)."""
    visit_occurrence_id: str               # Synthea Encounter UUID
    person_id: str
    visit_start_datetime: Optional[datetime] = None
    visit_end_datetime: Optional[datetime] = None
    visit_type_source_value: Optional[str] = None   # e.g. "ambulatory", "inpatient"
    provider_id: Optional[str] = None
    care_site_id: Optional[str] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── CONDITION_OCCURRENCE (maps from FHIR Condition resource) ─────────────────

class ConditionOccurrence(BaseModel):
    """
    One row per diagnosed condition per encounter.
    Source codes are ICD-10-CM (International Classification of Diseases,
    10th Revision) or SNOMED CT (a clinical terminology standard).
    """
    condition_occurrence_id: str
    person_id: str
    visit_occurrence_id: Optional[str] = None
    condition_source_value: str            # raw ICD-10 or SNOMED code
    condition_source_vocabulary: str       # "ICD10CM" | "SNOMED"
    condition_start_datetime: Optional[datetime] = None
    condition_end_datetime: Optional[datetime] = None
    condition_display: Optional[str] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── DRUG_EXPOSURE (maps from FHIR MedicationRequest resource) ────────────────

class DrugExposure(BaseModel):
    """
    One row per medication prescribed.
    Source codes are RxNorm (a standardized medication code system
    maintained by the U.S. National Library of Medicine).
    """
    drug_exposure_id: str
    person_id: str
    visit_occurrence_id: Optional[str] = None
    drug_source_value: str                 # raw RxNorm code
    drug_source_vocabulary: str = "RxNorm"
    drug_display: Optional[str] = None
    drug_exposure_start_datetime: Optional[datetime] = None
    drug_exposure_end_datetime: Optional[datetime] = None
    quantity: Optional[float] = None
    days_supply: Optional[int] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── CLAIM_HEADER (maps from FHIR ExplanationOfBenefit resource) ──────────────

class ClaimHeader(BaseModel):
    """
    One row per claim submitted to a payer (insurance company).

    EOB = Explanation of Benefits — the record a payer sends after processing
    a claim, showing what was billed, what was paid, and any denial.

    denial_flag: True when an insured claim has submitted_amount > 0
    but payment_amount = 0. Synthea does not generate CARC (Claim Adjustment
    Reason Codes) natively — the denial attribution layer is built in dbt
    on top of this flag.
    """
    claim_id: str                          # Synthea EOB UUID
    person_id: str
    visit_occurrence_id: Optional[str] = None
    payer_display: Optional[str] = None    # e.g. "Medicare", "Humana"
    claim_type: Optional[str] = None       # "professional" | "pharmacy" | "institutional"
    claim_start_date: Optional[date] = None
    claim_end_date: Optional[date] = None
    submitted_amount: float = 0.0          # total billed to payer
    payment_amount: float = 0.0            # amount payer actually paid
    denial_flag: bool = False              # derived: insured + payment=0 + submitted>0
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── CLAIM_LINE (maps from FHIR ExplanationOfBenefit.item[]) ──────────────────

class ClaimLine(BaseModel):
    """
    One row per line item on a claim — each service or procedure billed separately.
    A single claim (ClaimHeader) can have multiple lines.

    procedure_source_value: SNOMED CT code for the procedure performed.
    service_place_code: CMS (Centers for Medicare & Medicaid Services) code
    indicating where the service was delivered (office, hospital, etc.).
    """
    claim_line_id: str                     # composite: claim_id + sequence
    claim_id: str
    person_id: str
    line_sequence: int
    procedure_source_value: Optional[str] = None   # SNOMED code
    procedure_display: Optional[str] = None
    service_place_code: Optional[str] = None
    service_start_datetime: Optional[datetime] = None
    service_end_datetime: Optional[datetime] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)


# ── PAYER_PLAN_PERIOD (maps from FHIR Coverage resource) ─────────────────────

class PayerPlanPeriod(BaseModel):
    """
    One row per insurance coverage period per patient.
    Tracks which payer covered the patient and when — needed to determine
    whether a zero-payment claim is a denial or simply self-pay (no insurance).
    """
    payer_plan_period_id: str
    person_id: str
    payer_source_value: Optional[str] = None
    plan_source_value: Optional[str] = None
    payer_plan_period_start_date: Optional[date] = None
    payer_plan_period_end_date: Optional[date] = None
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
