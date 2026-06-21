"""
TrialWatchAgent: the orchestrator that makes this project more than "a
matching function." It maintains state per patient-trial pair, watches the
vitals stream, and re-runs eligibility specifically when deterioration is
detected -- not on a fixed polling schedule and not on every single vitals
tick (both of which would be wasteful and noisy). Every transition is
logged to an immutable audit trail.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from trialwatch.models import PatientRecord, Trial, EligibilityVerdict, AuditEvent
from trialwatch.early_warning import compute_news2_like_score, detect_deterioration, EarlyWarningState, RiskLevel
from trialwatch.eligibility import evaluate_eligibility


@dataclass
class MatchState:
    patient_id: str
    trial_id: str
    last_verdict: Optional[EligibilityVerdict] = None
    re_evaluations: int = 0


class TrialWatchAgent:
    def __init__(self):
        self.audit_log: list[AuditEvent] = []
        self.states: dict[tuple, MatchState] = {}

    def _log(self, event: AuditEvent):
        self.audit_log.append(event)

    def initial_match(self, patient: PatientRecord, trial: Trial) -> EligibilityVerdict:
        """Baseline eligibility screen using the patient's current vitals snapshot."""
        latest = patient.latest_vitals()
        ews = compute_news2_like_score(latest) if latest else EarlyWarningState(
            score=0, risk_level=RiskLevel.LOW, contributing_factors=[], reading=None,
        )
        verdict = evaluate_eligibility(patient, trial, ews)

        key = (patient.patient_id, trial.trial_id)
        self.states[key] = MatchState(patient.patient_id, trial.trial_id, last_verdict=verdict)

        self._log(AuditEvent.now(
            "eligibility_evaluated", patient.patient_id, trial.trial_id,
            eligible=verdict.eligible, data_completeness=verdict.data_completeness,
            failed_criteria=[c.criterion_id for c in verdict.failed_criteria()],
            trigger="initial_screen",
        ))
        return verdict

    def process_new_vitals(self, patient: PatientRecord, trial: Trial,
                            new_reading) -> Optional[EligibilityVerdict]:
        """
        Call this each time a new vitals reading arrives for a patient who has
        an active trial match. Returns a new EligibilityVerdict only if a
        re-evaluation was actually triggered (deterioration detected);
        otherwise returns None to signal "no change, no action taken."
        """
        patient.vitals_history.append(new_reading)
        key = (patient.patient_id, trial.trial_id)
        state = self.states.get(key)
        if state is None:
            # no baseline match exists yet -- caller should call initial_match first
            return None

        triggered, reason = detect_deterioration(patient.vitals_history)
        if not triggered:
            return None

        self._log(AuditEvent.now(
            "deterioration_detected", patient.patient_id, trial.trial_id, reason=reason,
        ))

        ews = compute_news2_like_score(new_reading)
        new_verdict = evaluate_eligibility(patient, trial, ews)
        state.re_evaluations += 1

        status_changed = (state.last_verdict is not None and
                           state.last_verdict.eligible != new_verdict.eligible)

        self._log(AuditEvent.now(
            "eligibility_evaluated", patient.patient_id, trial.trial_id,
            eligible=new_verdict.eligible, data_completeness=new_verdict.data_completeness,
            failed_criteria=[c.criterion_id for c in new_verdict.failed_criteria()],
            trigger=f"deterioration:{reason}",
        ))

        if status_changed:
            self._log(AuditEvent.now(
                "status_changed", patient.patient_id, trial.trial_id,
                previous_eligible=state.last_verdict.eligible,
                new_eligible=new_verdict.eligible,
                reason=reason,
            ))

        state.last_verdict = new_verdict
        return new_verdict

    def get_audit_trail(self, patient_id: Optional[str] = None,
                         trial_id: Optional[str] = None) -> list[AuditEvent]:
        events = self.audit_log
        if patient_id:
            events = [e for e in events if e.patient_id == patient_id]
        if trial_id:
            events = [e for e in events if e.trial_id == trial_id]
        return events
