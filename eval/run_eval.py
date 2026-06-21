"""
Eval harness.

Demonstrates the core value claim of this project on a synthetic population:
continuous deterioration-triggered re-matching catches eligibility status
changes that a one-time-only baseline screen would miss entirely.

Run:
    python -m eval.run_eval
"""

from __future__ import annotations
import random

from trialwatch.synthetic_data import generate_patient, _deteriorating_vital
from trialwatch.sample_trials import sample_diabetes_trial, sample_cardiac_trial
from trialwatch.agent import TrialWatchAgent


def _generate_referred_patient(patient_id: str, seed: int, target_condition: str,
                                deteriorates: bool = False):
    """
    Models a realistic trial-recruitment population: patients have already
    been referred/screened by a clinician because they carry the relevant
    diagnosis (e.g. an endocrinology clinic's diabetic patients being
    screened for a diabetes trial) -- not a random slice of the general
    population. We force the target condition present, then layer the
    same randomized labs/vitals/comorbidities on top.
    """
    patient = generate_patient(patient_id, seed=seed, deteriorates=deteriorates)
    if target_condition not in patient.conditions:
        patient.conditions.append(target_condition)
    return patient


def run_population_eval(n_patients: int = 200, deterioration_rate: float = 0.35, seed: int = 1):
    trial = sample_diabetes_trial()
    rng = random.Random(seed)

    baseline_eligible = 0
    status_flips_detected = 0
    eligible_to_ineligible = 0
    ineligible_to_eligible = 0
    total_reevaluations = 0
    missed_by_static_screen = 0   # patients who WERE eligible at baseline but became unsafe to enroll

    for i in range(n_patients):
        patient = _generate_referred_patient(f"PT{i:04d}", seed=seed * 1000 + i,
                                              target_condition="type_2_diabetes")
        agent = TrialWatchAgent()
        verdict = agent.initial_match(patient, trial)
        was_eligible = verdict.eligible
        if was_eligible:
            baseline_eligible += 1

        # simulate this patient deteriorating during the monitoring window
        deteriorates = rng.random() < deterioration_rate
        if deteriorates:
            base_time = patient.latest_vitals().timestamp
            for step in range(1, 4):
                severity = step / 3 * rng.uniform(0.6, 1.0)
                reading = _deteriorating_vital(rng, base_time, step * 1800, severity)
                new_verdict = agent.process_new_vitals(patient, trial, reading)
                if new_verdict is not None:
                    total_reevaluations += 1
                    if new_verdict.eligible != was_eligible:
                        status_flips_detected += 1
                        if was_eligible and not new_verdict.eligible:
                            eligible_to_ineligible += 1
                            missed_by_static_screen += 1
                        elif not was_eligible and new_verdict.eligible:
                            ineligible_to_eligible += 1
                        was_eligible = new_verdict.eligible  # track running state for further flips

    print(f"Population size (pre-screened, all diagnosed with target condition): {n_patients}")
    print(f"Baseline eligible (static screen):  {baseline_eligible} ({baseline_eligible/n_patients*100:.1f}%)")
    print(f"Total deterioration re-evaluations: {total_reevaluations}")
    print(f"Status flips detected:              {status_flips_detected}")
    print(f"  eligible -> ineligible:           {eligible_to_ineligible}")
    print(f"  ineligible -> eligible:           {ineligible_to_eligible}")
    print()
    print(f"Patients a ONE-TIME static screen would have left enrolled despite")
    print(f"later becoming acutely unsafe to enroll: {missed_by_static_screen}")
    print(f"  -> {missed_by_static_screen/max(baseline_eligible,1)*100:.1f}% of baseline-eligible patients")
    print(f"     would have been silently missed without continuous monitoring.")


def run_audit_completeness_check(n_patients: int = 50, seed: int = 2):
    """Sanity check: every eligibility_evaluated audit event must cite evidence
    for every non-missing criterion result -- i.e. the audit trail is never
    'trust me', always 'here's the field and value used'."""
    trial = sample_cardiac_trial()
    rng = random.Random(seed)
    uncited_failures = 0
    total_checked = 0

    for i in range(n_patients):
        patient = generate_patient(f"PTB{i:04d}", seed=seed * 2000 + i,
                                    deteriorates=rng.random() < 0.3)
        agent = TrialWatchAgent()
        verdict = agent.initial_match(patient, trial)
        for c in verdict.criterion_results:
            total_checked += 1
            if not c.data_missing and len(c.evidence) == 0:
                uncited_failures += 1

    print(f"\nAudit-trail evidence completeness check:")
    print(f"  Criterion results checked: {total_checked}")
    print(f"  Results missing evidence citation: {uncited_failures}")
    print(f"  -> {'PASS: every evaluable criterion is cited' if uncited_failures == 0 else 'FAIL'}")


def main():
    print("=" * 70)
    print("TrialWatch eval: value of continuous deterioration-triggered re-matching")
    print("(synthetic data only)")
    print("=" * 70)
    run_population_eval()
    run_audit_completeness_check()


if __name__ == "__main__":
    main()
