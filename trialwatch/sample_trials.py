"""
Sample synthetic trial protocols, built from the structured criteria library.
These are FABRICATED for demo purposes and do not represent real trials.
"""

from __future__ import annotations
from trialwatch.models import Trial
from trialwatch.criteria.library import (
    age_between, excludes_condition, requires_condition, lab_within_range,
    excludes_pregnancy, excludes_high_deterioration_risk, excludes_medication,
)


def sample_diabetes_trial() -> Trial:
    return Trial(
        trial_id="T-DM2-014",
        name="Novel GLP-1 Adjunct Therapy for Type 2 Diabetes",
        criteria=[
            age_between(18, 75),
            requires_condition("type_2_diabetes"),
            lab_within_range("hba1c", 7.0, 11.0),
            lab_within_range("egfr", 45, 200),
            excludes_condition("heart_failure"),
            excludes_pregnancy(),
            excludes_medication("insulin"),
            excludes_high_deterioration_risk(),
        ],
    )


def sample_cardiac_trial() -> Trial:
    return Trial(
        trial_id="T-CHF-007",
        name="Heart Failure Remote Monitoring Intervention Study",
        criteria=[
            age_between(40, 85),
            requires_condition("heart_failure"),
            excludes_pregnancy(),
            lab_within_range("creatinine", 0.4, 2.5),
            excludes_high_deterioration_risk(),
        ],
    )
