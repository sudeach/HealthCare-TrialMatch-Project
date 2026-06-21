"""
Unit tests. Run with: pytest -q

⚠ All data here is synthetic / fabricated for testing purposes only.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trialwatch.models import PatientRecord, Sex, VitalReading, LabResult
from trialwatch.early_warning import compute_news2_like_score, detect_deterioration, RiskLevel
from trialwatch.criteria.library import (
    age_between, excludes_condition, requires_condition, lab_within_range, excludes_pregnancy,
)
from trialwatch.models import Trial
from trialwatch.eligibility import evaluate_eligibility
from trialwatch.agent import TrialWatchAgent
from trialwatch.sample_trials import sample_diabetes_trial


def _normal_reading(ts=0.0):
    return VitalReading(timestamp=ts, heart_rate=75, resp_rate=16, spo2=97,
                         systolic_bp=120, temperature_c=36.8, consciousness_alert=True)


def _critical_reading(ts=0.0):
    return VitalReading(timestamp=ts, heart_rate=140, resp_rate=30, spo2=85,
                         systolic_bp=85, temperature_c=39.5, consciousness_alert=False)


def test_news2_score_normal_vitals_is_low_risk():
    state = compute_news2_like_score(_normal_reading())
    assert state.risk_level == RiskLevel.LOW
    assert state.score == 0


def test_news2_score_critical_vitals_is_high_risk():
    state = compute_news2_like_score(_critical_reading())
    assert state.risk_level == RiskLevel.HIGH
    assert state.score >= 7


def test_detect_deterioration_flags_high_risk():
    history = [_normal_reading(0), _normal_reading(1), _critical_reading(2)]
    triggered, reason = detect_deterioration(history)
    assert triggered
    assert "high_risk" in reason


def test_detect_deterioration_flags_rapid_trend_even_if_not_yet_high():
    # individually medium, but rising fast
    readings = [
        VitalReading(0, 75, 16, 97, 120, 36.8, True),    # score 0
        VitalReading(1, 95, 22, 93, 105, 37.0, True),     # score ~ medium-ish
    ]
    triggered, reason = detect_deterioration(readings)
    # whichever path triggers, deterioration must be caught
    assert triggered


def test_detect_deterioration_no_trigger_on_stable_normal_vitals():
    history = [_normal_reading(i) for i in range(5)]
    triggered, reason = detect_deterioration(history)
    assert not triggered
    assert reason == "stable"


def test_criterion_age_between_evidence_is_cited():
    patient = PatientRecord("P1", age=30, sex=Sex.MALE)
    crit = age_between(18, 65)
    result = crit.check_fn(patient, compute_news2_like_score(_normal_reading()))
    assert result.passed
    assert len(result.evidence) == 1
    assert result.evidence[0].observed_value == 30


def test_criterion_missing_lab_data_marks_data_missing_not_failed_silently():
    patient = PatientRecord("P1", age=30, sex=Sex.MALE)  # no labs at all
    crit = lab_within_range("hba1c", 6.0, 9.0)
    result = crit.check_fn(patient, compute_news2_like_score(_normal_reading()))
    assert result.data_missing
    assert not result.passed


def test_eligibility_evaluator_requires_all_criteria_to_pass():
    patient = PatientRecord("P1", age=30, sex=Sex.MALE, conditions=["asthma"])
    trial = Trial("T1", "Test trial", criteria=[
        age_between(18, 65),
        requires_condition("type_2_diabetes"),  # patient doesn't have this -> fails
    ])
    verdict = evaluate_eligibility(patient, trial, compute_news2_like_score(_normal_reading()))
    assert not verdict.eligible
    assert len(verdict.failed_criteria()) == 1


def test_agent_initial_match_logs_audit_event():
    patient = PatientRecord("P1", age=30, sex=Sex.MALE, conditions=["type_2_diabetes"],
                             vitals_history=[_normal_reading()],
                             labs=[LabResult("hba1c", 8.0, "%", 0), LabResult("egfr", 90, "mL/min/1.73m2", 0)])
    trial = sample_diabetes_trial()
    agent = TrialWatchAgent()
    verdict = agent.initial_match(patient, trial)
    audit = agent.get_audit_trail(patient_id="P1")
    assert len(audit) == 1
    assert audit[0].kind == "eligibility_evaluated"


def test_agent_detects_status_change_on_deterioration():
    patient = PatientRecord(
        "P1", age=30, sex=Sex.MALE, conditions=["type_2_diabetes"],
        vitals_history=[_normal_reading(0)],
        labs=[LabResult("hba1c", 8.0, "%", 0), LabResult("egfr", 90, "mL/min/1.73m2", 0)],
    )
    trial = sample_diabetes_trial()
    agent = TrialWatchAgent()
    baseline = agent.initial_match(patient, trial)
    assert baseline.eligible  # sanity check on test fixture

    new_verdict = agent.process_new_vitals(patient, trial, _critical_reading(1))
    assert new_verdict is not None  # re-evaluation must have triggered
    assert not new_verdict.eligible  # high deterioration risk excludes them

    status_change_events = [e for e in agent.get_audit_trail(patient_id="P1") if e.kind == "status_changed"]
    assert len(status_change_events) == 1
    assert status_change_events[0].payload["previous_eligible"] is True
    assert status_change_events[0].payload["new_eligible"] is False


def test_agent_does_not_reevaluate_on_stable_vitals():
    patient = PatientRecord(
        "P1", age=30, sex=Sex.MALE, conditions=["type_2_diabetes"],
        vitals_history=[_normal_reading(0)],
        labs=[LabResult("hba1c", 8.0, "%", 0), LabResult("egfr", 90, "mL/min/1.73m2", 0)],
    )
    trial = sample_diabetes_trial()
    agent = TrialWatchAgent()
    agent.initial_match(patient, trial)
    result = agent.process_new_vitals(patient, trial, _normal_reading(1))
    assert result is None  # no deterioration -> no wasted re-evaluation


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
