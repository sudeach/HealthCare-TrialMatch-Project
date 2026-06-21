"""
Demo entry point.

Run:
    python main.py
    python main.py --patient-seed 42 --deteriorates

⚠ SYNTHETIC DATA ONLY. Not a medical device. Not for clinical use.
See README.md for full disclaimer.
"""

from __future__ import annotations
import argparse

from trialwatch.synthetic_data import generate_patient
from trialwatch.sample_trials import sample_diabetes_trial
from trialwatch.agent import TrialWatchAgent
from trialwatch.early_warning import compute_news2_like_score
from trialwatch.synthetic_data import _deteriorating_vital
import random


def main():
    parser = argparse.ArgumentParser(description="TrialWatch demo (synthetic data only)")
    parser.add_argument("--patient-seed", type=int, default=1)
    parser.add_argument("--deteriorates", action="store_true",
                         help="simulate the patient deteriorating during monitoring")
    args = parser.parse_args()

    print("=" * 70)
    print("⚠  SYNTHETIC DATA DEMO ONLY -- not a medical device, not for clinical use")
    print("=" * 70)

    patient = generate_patient("PT0001", seed=args.patient_seed, deteriorates=False)
    trial = sample_diabetes_trial()
    agent = TrialWatchAgent()

    print(f"\nPatient {patient.patient_id}: age={patient.age}, conditions={patient.conditions}, "
          f"medications={patient.medications}")
    print(f"Trial: {trial.name} ({trial.trial_id})\n")

    verdict = agent.initial_match(patient, trial)
    print(f"--- Initial eligibility: {'ELIGIBLE' if verdict.eligible else 'NOT ELIGIBLE'} "
          f"(data completeness: {verdict.data_completeness*100:.0f}%) ---")
    for c in verdict.criterion_results:
        mark = "✓" if c.passed else ("?" if c.data_missing else "✗")
        print(f"  [{mark}] {c.description:55s} {c.reason}")

    if args.deteriorates:
        print("\n--- Simulating live deterioration over 3 new vitals readings ---")
        rng = random.Random(args.patient_seed)
        base_time = patient.latest_vitals().timestamp
        for i in range(1, 4):
            severity = i / 3
            reading = _deteriorating_vital(rng, base_time, i * 1800, severity)
            new_verdict = agent.process_new_vitals(patient, trial, reading)
            ews = compute_news2_like_score(reading)
            print(f"  reading {i}: HR={reading.heart_rate:.0f} SpO2={reading.spo2:.0f}% "
                  f"RR={reading.resp_rate:.0f} -> EWS score={ews.score} ({ews.risk_level.value})")
            if new_verdict is not None:
                print(f"    -> RE-EVALUATION TRIGGERED. New status: "
                      f"{'ELIGIBLE' if new_verdict.eligible else 'NOT ELIGIBLE'}")
                for c in new_verdict.failed_criteria():
                    print(f"       failed: {c.description} ({c.reason})")

    print("\n--- Full audit trail ---")
    for ev in agent.get_audit_trail(patient_id=patient.patient_id):
        print(f"  [{ev.kind:22s}] {ev.payload}")


if __name__ == "__main__":
    main()
