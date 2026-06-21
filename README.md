# TrialWatch

A clinical-trial eligibility agent that does something most trial-matching
tools don't: it doesn't just screen a patient once and stop. It watches a
patient's live vitals stream, detects clinically meaningful deterioration,
and **automatically re-evaluates trial eligibility** when it does — with
every decision traced back to the exact data field that justified it.

> ## ⚠️ Important disclaimer - read this first
> This project uses **100% synthetic, programmatically generated data**.
> No real patient data, real trial protocols, or real clinical datasets are
> used anywhere in this repository. The early-warning scoring logic is a
> **simplified, non-validated reimplementation** loosely inspired by the
> structure of NEWS2 (a real clinical deterioration score) - it has not
> been clinically validated and must never be used for real patient care,
> real trial enrollment, or any other clinical decision. This is a software
> architecture and systems-design portfolio project, not a medical device,
> not FDA-cleared, and not a substitute for validated clinical software.

## Why this is a different shape of project than the usual trial-matching demo

Most public "trial matching AI" projects do one thing: take a patient
profile and a trial protocol, and produce a single yes/no match — typically
using an LLM to interpret free-text criteria directly against free-text
patient notes, with no structured audit trail.

TrialWatch is built around three things that real trial operations
actually need but that single-shot matchers don't address:

1. **Continuous re-evaluation, not a one-time screen.** Patient state
   changes - a trial protocol's exclusion criteria (e.g. "not in acute
   decompensation") can flip from "met" to "violated" mid-monitoring. A
   static screen run once at intake has no way to catch that.
2. **Deterioration-triggered, not poll-triggered.** Re-checking eligibility
   on every single vitals tick would be wasteful and noisy; re-checking
   only on a fixed schedule would miss fast-moving events. TrialWatch
   re-evaluates specifically when an early-warning trend crosses a
   clinically meaningful threshold.
3. **Every decision is cited, not asserted.** Each criterion result carries
   an `EvidenceRef` pointing to the exact patient field and timestamp that
   justified it. This mirrors a real regulatory requirement (trial
   eligibility decisions must be auditable to source data) that almost no
   portfolio project bothers to model.

## Architecture

```
SyntheticDataGenerator ──► PatientRecord (vitals stream, labs, conditions)
                                   │
                                   ▼
                         TrialWatchAgent.initial_match()
                                   │
                    EligibilityEvaluator runs every
                    TrialCriterion.check_fn(patient, ews)
                    -> CriterionResult + EvidenceRef per criterion
                                   │
                                   ▼
                         EligibilityVerdict (cited, auditable)
                                   │
              ── new vitals reading arrives ──►
                                   │
                    detect_deterioration(history)
                    (NEWS2-like score + rapid-trend check)
                                   │
                        triggered? ─── no ──► no action (no wasted re-check)
                                   │
                                  yes
                                   │
                                   ▼
                    re-run EligibilityEvaluator
                    -> compare to previous verdict
                    -> log status_changed if eligibility flipped
                                   │
                                   ▼
                          AuditEvent log (full trace)
```

Key files:
- `trialwatch/models.py` - PatientRecord, TrialCriterion, EvidenceRef, AuditEvent
- `trialwatch/early_warning.py` - NEWS2-inspired deterioration scoring + trend detection
- `trialwatch/criteria/library.py` - structured, cited eligibility criteria (age, labs, conditions, live risk state)
- `trialwatch/eligibility.py` - runs all criteria for a trial against a patient
- `trialwatch/agent.py` — orchestrates monitoring → deterioration detection → re-matching → audit log
- `trialwatch/synthetic_data.py` - fully fabricated patient/vitals generator
- `trialwatch/sample_trials.py` - example synthetic trial protocols
- `eval/run_eval.py` — population-level evaluation (see results below)
- `tests/test_trialwatch.py` - unit tests covering scoring, criteria, and agent behavior

## Evaluation results

```
python -m eval.run_eval
```

```
Population size (pre-screened, all diagnosed with target condition): 200
Baseline eligible (static screen):  21 (10.5%)
Total deterioration re-evaluations: 159
Status flips detected:              4
  eligible -> ineligible:           4
  ineligible -> eligible:           0

Patients a ONE-TIME static screen would have left enrolled despite
later becoming acutely unsafe to enroll: 4
  -> 19.0% of baseline-eligible patients would have been silently
     missed without continuous monitoring.

Audit-trail evidence completeness check:
  Criterion results checked: 250
  Results missing evidence citation: 0
  -> PASS: every evaluable criterion is cited
```

The headline number: on this synthetic population, **~19% of patients who
passed a one-time baseline eligibility screen later became unsafe to
enroll** due to acute deterioration that a static screen would never catch.
Continuous re-matching surfaces exactly these cases, with a full audit
trail for why.

## Running it

```bash
pip install -r requirements.txt

# Single-patient demo with a live deterioration scenario
python main.py --patient-seed 58 --deteriorates

# Population-level evaluation
python -m eval.run_eval

# Tests
python -m pytest tests/ -v
```

## Design decisions worth discussing in an interview

- **Why structured criterion functions instead of letting an LLM judge
  eligibility directly?** Free-text LLM judgment against free-text notes is
  the standard approach in most trial-matching demos, and it's exactly the
  part that's hardest to audit or trust at the threshold an IRB or sponsor
  would require. Here, an LLM could be used *upstream* to parse a written
  protocol into structured `TrialCriterion` objects - but the eligibility
  *decision itself* is a deterministic, testable function with a citation.
  That's a real, defensible boundary: use the LLM for language understanding,
  not for the safety-critical judgment call.
- **Why trigger re-evaluation on deterioration trend, not a fixed polling
  interval?** Real monitoring systems alarm-fatigue clinicians when they
  fire on every reading. Triggering specifically on a clinically meaningful
  signal (NEWS2-style threshold or rapid trend) is both cheaper computationally
  and more aligned with how real early-warning systems are designed to behave.
- **Why pre-screen the eval population by condition instead of using a
  uniform random population?** A uniform random population isn't how trial
  recruitment actually works - patients are referred because they plausibly
  match. Evaluating against a referred-style population produces a baseline
  eligible rate that's realistic enough to make the deterioration-detection
  numbers meaningful rather than trivially rare.
- **Known limitations, stated plainly:** the NEWS2-like scorer is a
  simplified, unvalidated reimplementation; the synthetic vitals generator
  uses simple Gaussian noise rather than physiologically realistic
  time-series dynamics; and the criteria library covers a representative
  but small slice of what a real protocol's eligibility section contains
  (no temporal criteria like "no hospitalization in last 90 days", no
  combination/washout logic). These are the natural next extensions.

## Extending this

- Add new criteria types in `trialwatch/criteria/library.py` following the
  existing `(patient, ews) -> CriterionResult` pattern.
- Add an LLM-based protocol parser that turns free-text inclusion/exclusion
  text into `TrialCriterion` objects (keeping the evaluation itself
  structured, per the design decision above).
- Swap `synthetic_data.py` for a real FHIR/Synthea-based generator if you
  want closer-to-real-world data shapes - still synthetic, still safe to
  publish.
