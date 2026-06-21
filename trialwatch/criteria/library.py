"""
A small library of structured trial criteria.

Design choice (worth defending in an interview): eligibility checks are
*structured, deterministic functions*, not free-text LLM judgment calls.
An LLM is used upstream (see agent.py) only to parse free-text trial
protocols INTO this structured form -- never to make the eligibility call
itself. Every CriterionResult must cite the exact PatientRecord field that
justified it (EvidenceRef). This mirrors a real regulatory requirement:
trial eligibility decisions must be auditable back to source data.
"""

from __future__ import annotations
from trialwatch.models import (
    PatientRecord, CriterionResult, CriterionType, EvidenceRef, TrialCriterion,
)
from trialwatch.early_warning import EarlyWarningState, RiskLevel


def age_between(min_age: int, max_age: int) -> TrialCriterion:
    cid = f"age_{min_age}_{max_age}"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        passed = min_age <= patient.age <= max_age
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.INCLUSION,
            description=f"Age between {min_age} and {max_age}",
            passed=passed,
            evidence=[EvidenceRef(field_path="patient.age", observed_value=patient.age)],
            reason=f"age={patient.age}",
        )

    return TrialCriterion(cid, CriterionType.INCLUSION, f"Age {min_age}-{max_age}", check)


def excludes_condition(condition: str) -> TrialCriterion:
    cid = f"exclude_{condition.replace(' ', '_')}"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        present = condition in patient.conditions
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.EXCLUSION,
            description=f"Excludes patients with {condition}",
            passed=not present,
            evidence=[EvidenceRef(field_path="patient.conditions", observed_value=patient.conditions)],
            reason=f"condition_present={present}",
        )

    return TrialCriterion(cid, CriterionType.EXCLUSION, f"No {condition}", check)


def requires_condition(condition: str) -> TrialCriterion:
    cid = f"require_{condition.replace(' ', '_')}"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        present = condition in patient.conditions
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.INCLUSION,
            description=f"Requires diagnosis of {condition}",
            passed=present,
            evidence=[EvidenceRef(field_path="patient.conditions", observed_value=patient.conditions)],
            reason=f"condition_present={present}",
        )

    return TrialCriterion(cid, CriterionType.INCLUSION, f"Has {condition}", check)


def lab_within_range(lab_name: str, min_val: float, max_val: float) -> TrialCriterion:
    cid = f"lab_{lab_name}_{min_val}_{max_val}"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        lab = patient.latest_lab(lab_name)
        if lab is None:
            return CriterionResult(
                criterion_id=cid, criterion_type=CriterionType.INCLUSION,
                description=f"{lab_name} between {min_val}-{max_val}",
                passed=False, data_missing=True,
                reason=f"no {lab_name} result on file",
            )
        passed = min_val <= lab.value <= max_val
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.INCLUSION,
            description=f"{lab_name} between {min_val}-{max_val}",
            passed=passed,
            evidence=[EvidenceRef(field_path=f"labs.{lab_name}", observed_value=lab.value,
                                   timestamp=lab.timestamp)],
            reason=f"{lab_name}={lab.value}{lab.unit}",
        )

    return TrialCriterion(cid, CriterionType.INCLUSION, f"{lab_name} in range", check)


def excludes_pregnancy() -> TrialCriterion:
    cid = "exclude_pregnancy"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.EXCLUSION,
            description="Excludes pregnant patients",
            passed=not patient.pregnant,
            evidence=[EvidenceRef(field_path="patient.pregnant", observed_value=patient.pregnant)],
            reason=f"pregnant={patient.pregnant}",
        )

    return TrialCriterion(cid, CriterionType.EXCLUSION, "Not pregnant", check)


def excludes_high_deterioration_risk() -> TrialCriterion:
    """
    This is the criterion that ties trial eligibility to the live monitoring
    stream: many real trial protocols exclude patients who are acutely
    unstable, even if their static baseline data qualified them. This is the
    criterion that DRIVES re-evaluation when the early-warning state changes.
    """
    cid = "exclude_high_deterioration_risk"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        passed = ews.risk_level != RiskLevel.HIGH
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.EXCLUSION,
            description="Excludes patients currently at high acute-deterioration risk",
            passed=passed,
            evidence=[EvidenceRef(
                field_path="early_warning.score",
                observed_value=ews.score,
                timestamp=ews.reading.timestamp if ews.reading else None,
            )],
            reason=f"ews_score={ews.score} risk={ews.risk_level.value}",
        )

    return TrialCriterion(cid, CriterionType.EXCLUSION, "Not high acute risk", check)


def excludes_medication(medication: str) -> TrialCriterion:
    cid = f"exclude_med_{medication.replace(' ', '_')}"

    def check(patient: PatientRecord, ews: EarlyWarningState) -> CriterionResult:
        present = medication in patient.medications
        return CriterionResult(
            criterion_id=cid,
            criterion_type=CriterionType.EXCLUSION,
            description=f"Excludes patients on {medication}",
            passed=not present,
            evidence=[EvidenceRef(field_path="patient.medications", observed_value=patient.medications)],
            reason=f"on_medication={present}",
        )

    return TrialCriterion(cid, CriterionType.EXCLUSION, f"Not on {medication}", check)
