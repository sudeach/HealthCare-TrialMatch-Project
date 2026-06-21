"""
EligibilityEvaluator: runs every criterion in a Trial against a PatientRecord
+ current EarlyWarningState, and produces a fully-cited EligibilityVerdict.

Kept deliberately separate from the agent orchestration logic so it can be
unit tested in isolation and reused outside the monitoring loop (e.g. for a
one-off batch eligibility screen).
"""

from __future__ import annotations
import time

from trialwatch.models import PatientRecord, Trial, EligibilityVerdict, CriterionResult
from trialwatch.early_warning import EarlyWarningState


def evaluate_eligibility(patient: PatientRecord, trial: Trial,
                          ews: EarlyWarningState) -> EligibilityVerdict:
    results: list[CriterionResult] = []
    for criterion in trial.criteria:
        result = criterion.check_fn(patient, ews)
        results.append(result)

    evaluable = [r for r in results if not r.data_missing]
    completeness = len(evaluable) / len(results) if results else 1.0

    # Conservative rule: any criterion that's missing data or fails -> not eligible.
    # (A real system might allow partial/provisional eligibility; here we make
    # the strict choice explicit and auditable rather than silently guessing.)
    eligible = all(r.passed and not r.data_missing for r in results)

    return EligibilityVerdict(
        trial_id=trial.trial_id,
        patient_id=patient.patient_id,
        eligible=eligible,
        criterion_results=results,
        evaluated_at=time.time(),
        data_completeness=completeness,
    )
