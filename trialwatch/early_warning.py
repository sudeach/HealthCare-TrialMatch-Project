"""
Early warning scoring, loosely modeled on the structure of NEWS2 (National
Early Warning Score 2), a real clinical deterioration scoring system used
in UK hospitals. This is a SIMPLIFIED, NON-VALIDATED reimplementation built
for this demo -- it must not be used as a substitute for a validated
clinical scoring tool. The point here is the software pattern (continuous
scoring -> trend detection -> trigger), not clinical accuracy.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .models import VitalReading


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class EarlyWarningState:
    score: int
    risk_level: RiskLevel
    contributing_factors: list[str]
    reading: VitalReading


def _band_score(value: float, bands: list[tuple[float, float, int]]) -> int:
    """bands: list of (low, high, score), checked in order; first match wins."""
    for lo, hi, s in bands:
        if lo <= value < hi:
            return s
    return 3  # most extreme bucket if outside all defined bands


def compute_news2_like_score(reading: VitalReading) -> EarlyWarningState:
    factors = []
    total = 0

    rr = _band_score(reading.resp_rate, [
        (0, 9, 3), (9, 12, 1), (12, 21, 0), (21, 25, 2), (25, 999, 3),
    ])
    if rr > 0:
        factors.append(f"resp_rate={reading.resp_rate} -> +{rr}")
    total += rr

    spo2 = _band_score(reading.spo2, [
        (0, 92, 3), (92, 94, 2), (94, 96, 1), (96, 101, 0),
    ])
    if spo2 > 0:
        factors.append(f"spo2={reading.spo2} -> +{spo2}")
    total += spo2

    sbp = _band_score(reading.systolic_bp, [
        (0, 91, 3), (91, 101, 2), (101, 111, 1), (111, 220, 0), (220, 999, 3),
    ])
    if sbp > 0:
        factors.append(f"systolic_bp={reading.systolic_bp} -> +{sbp}")
    total += sbp

    hr = _band_score(reading.heart_rate, [
        (0, 41, 3), (41, 51, 1), (51, 91, 0), (91, 111, 1), (111, 131, 2), (131, 999, 3),
    ])
    if hr > 0:
        factors.append(f"heart_rate={reading.heart_rate} -> +{hr}")
    total += hr

    temp = _band_score(reading.temperature_c, [
        (0, 35.1, 3), (35.1, 36.1, 1), (36.1, 38.1, 0), (38.1, 39.1, 1), (39.1, 99, 2),
    ])
    if temp > 0:
        factors.append(f"temp={reading.temperature_c} -> +{temp}")
    total += temp

    if not reading.consciousness_alert:
        factors.append("consciousness=not_alert -> +3")
        total += 3

    if total >= 7:
        risk = RiskLevel.HIGH
    elif total >= 5:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    return EarlyWarningState(score=total, risk_level=risk, contributing_factors=factors, reading=reading)


def detect_deterioration(history: list[VitalReading], window: int = 3) -> tuple[bool, str]:
    """
    Trend-based trigger: deterioration = current score is HIGH, OR score has
    risen by >=3 points over the last `window` readings (a rapid-trend signal
    that single-point thresholding misses).
    """
    if not history:
        return False, "no_data"

    scores = [compute_news2_like_score(r).score for r in history[-window:]]
    current = compute_news2_like_score(history[-1])

    if current.risk_level == RiskLevel.HIGH:
        return True, f"high_risk_score={current.score}"

    if len(scores) >= 2 and (scores[-1] - scores[0]) >= 3:
        return True, f"rapid_trend_increase={scores[0]}->{scores[-1]}"

    return False, "stable"
