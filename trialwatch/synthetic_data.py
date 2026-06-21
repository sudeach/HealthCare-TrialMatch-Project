"""
Synthetic data generator. Produces fully fabricated PatientRecords and
vitals streams -- no real patient data of any kind is used anywhere in
this project.
"""

from __future__ import annotations
import random
import time

from trialwatch.models import PatientRecord, Sex, VitalReading, LabResult


CONDITIONS_POOL = ["type_2_diabetes", "hypertension", "chronic_kidney_disease",
                    "asthma", "copd", "atrial_fibrillation", "heart_failure"]
MEDICATIONS_POOL = ["metformin", "lisinopril", "warfarin", "insulin",
                     "albuterol", "atorvastatin"]


def _normal_vital(rng: random.Random, base_time: float, offset_s: float) -> VitalReading:
    return VitalReading(
        timestamp=base_time + offset_s,
        heart_rate=rng.gauss(75, 8),
        resp_rate=rng.gauss(16, 2),
        spo2=rng.gauss(97, 1.2),
        systolic_bp=rng.gauss(122, 10),
        temperature_c=rng.gauss(36.8, 0.3),
        consciousness_alert=True,
    )


def _deteriorating_vital(rng: random.Random, base_time: float, offset_s: float,
                          severity: float) -> VitalReading:
    """severity in [0,1]: 0 = normal, 1 = critical."""
    return VitalReading(
        timestamp=base_time + offset_s,
        heart_rate=rng.gauss(75 + severity * 60, 8),
        resp_rate=rng.gauss(16 + severity * 14, 2),
        spo2=rng.gauss(97 - severity * 12, 1.5),
        systolic_bp=rng.gauss(122 - severity * 40, 10),
        temperature_c=rng.gauss(36.8 + severity * 1.8, 0.3),
        consciousness_alert=rng.random() > severity * 0.6,
    )


def generate_patient(patient_id: str, seed: int, deteriorates: bool = False,
                      n_readings: int = 8) -> PatientRecord:
    rng = random.Random(seed)
    age = rng.randint(22, 85)
    sex = rng.choice(list(Sex))
    n_conditions = rng.randint(0, 3)
    conditions = rng.sample(CONDITIONS_POOL, n_conditions)
    n_meds = rng.randint(0, 2)
    medications = rng.sample(MEDICATIONS_POOL, n_meds)
    pregnant = sex == Sex.FEMALE and rng.random() < 0.05 and age < 45

    base_time = time.time() - n_readings * 3600
    vitals = []
    for i in range(n_readings):
        if deteriorates and i >= n_readings - 3:
            # ramp severity over the last 3 readings
            severity = (i - (n_readings - 3)) / 2 * rng.uniform(0.7, 1.0)
            vitals.append(_deteriorating_vital(rng, base_time, i * 3600, severity))
        else:
            vitals.append(_normal_vital(rng, base_time, i * 3600))

    labs = [
        LabResult("egfr", rng.gauss(85, 20), "mL/min/1.73m2", base_time),
        LabResult("creatinine", rng.gauss(0.9, 0.3), "mg/dL", base_time),
        LabResult("hba1c", rng.gauss(6.0, 1.2), "%", base_time),
        LabResult("alt", rng.gauss(25, 10), "U/L", base_time),
    ]

    return PatientRecord(
        patient_id=patient_id, age=age, sex=sex, conditions=conditions,
        medications=medications, labs=labs, vitals_history=vitals, pregnant=pregnant,
    )


def generate_population(n: int = 50, deterioration_rate: float = 0.3, seed: int = 1) -> list[PatientRecord]:
    rng = random.Random(seed)
    patients = []
    for i in range(n):
        deteriorates = rng.random() < deterioration_rate
        patients.append(generate_patient(f"PT{i:04d}", seed=seed * 1000 + i, deteriorates=deteriorates))
    return patients
