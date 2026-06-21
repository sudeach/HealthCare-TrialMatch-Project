"""
Core data models for TrialWatch.

IMPORTANT: This project uses 100% synthetic, programmatically generated
data. It is a portfolio/research engineering demonstration only and is
NOT a medical device, NOT validated for clinical use, and NOT intended to
inform real patient care or regulatory trial enrollment decisions. See
README.md for full disclaimer.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import time


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"


@dataclass
class VitalReading:
    """One timestamped vitals observation (loosely FHIR Observation-shaped)."""
    timestamp: float
    heart_rate: float          # bpm
    resp_rate: float           # breaths/min
    spo2: float                # %
    systolic_bp: float         # mmHg
    temperature_c: float
    consciousness_alert: bool = True  # AVPU simplified: alert vs not


@dataclass
class LabResult:
    name: str                  # e.g. "creatinine", "egfr", "alt", "hba1c"
    value: float
    unit: str
    timestamp: float


@dataclass
class PatientRecord:
    """Synthetic patient, loosely FHIR-Patient + Condition + Observation shaped."""
    patient_id: str
    age: int
    sex: Sex
    conditions: list[str] = field(default_factory=list)        # SNOMED-style condition names
    medications: list[str] = field(default_factory=list)
    labs: list[LabResult] = field(default_factory=list)
    vitals_history: list[VitalReading] = field(default_factory=list)
    pregnant: bool = False

    def latest_vitals(self) -> Optional[VitalReading]:
        return self.vitals_history[-1] if self.vitals_history else None

    def latest_lab(self, name: str) -> Optional[LabResult]:
        matches = [l for l in self.labs if l.name == name]
        return max(matches, key=lambda l: l.timestamp) if matches else None


class CriterionType(str, Enum):
    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"


@dataclass
class EvidenceRef:
    """Points to the exact data field that justified a criterion decision.
    This is the audit-trail backbone -- every eligibility decision must be
    traceable to a specific piece of patient data, not a vague LLM claim."""
    field_path: str            # e.g. "labs.egfr", "vitals.spo2", "conditions"
    observed_value: Any
    timestamp: Optional[float] = None


@dataclass
class CriterionResult:
    criterion_id: str
    criterion_type: CriterionType
    description: str
    passed: bool
    evidence: list[EvidenceRef] = field(default_factory=list)
    reason: str = ""
    data_missing: bool = False   # True if we couldn't evaluate due to missing data


@dataclass
class TrialCriterion:
    """A single structured eligibility rule. `check_fn` is a pure function
    (patient, EarlyWarningState) -> CriterionResult, kept structured/explainable
    rather than left to free-text LLM judgment."""
    criterion_id: str
    criterion_type: CriterionType
    description: str
    check_fn: Any   # Callable[[PatientRecord, "EarlyWarningState"], CriterionResult]


@dataclass
class Trial:
    trial_id: str
    name: str
    criteria: list[TrialCriterion] = field(default_factory=list)


@dataclass
class EligibilityVerdict:
    trial_id: str
    patient_id: str
    eligible: bool
    criterion_results: list[CriterionResult]
    evaluated_at: float
    data_completeness: float   # fraction of criteria with no missing data

    def failed_criteria(self) -> list[CriterionResult]:
        return [c for c in self.criterion_results if not c.passed and not c.data_missing]


@dataclass
class AuditEvent:
    """Every state change gets logged here -- this IS the regulatory audit trail."""
    ts: float
    kind: str                  # "eligibility_evaluated", "status_changed", "deterioration_detected"
    patient_id: str
    trial_id: Optional[str]
    payload: dict = field(default_factory=dict)

    @staticmethod
    def now(kind: str, patient_id: str, trial_id: Optional[str] = None, **payload) -> "AuditEvent":
        return AuditEvent(ts=time.time(), kind=kind, patient_id=patient_id, trial_id=trial_id, payload=payload)
