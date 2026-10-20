"""Attach experiment results to findings. This is the only path to PROVEN.

Matching: an experiment names the finding id it tests (preferred) or a (rule, component) pair. Effects:

* ACCEPT on a finding that survived adversarial review -> PROVEN. On a finding the review blocked, the result is
  attached but the level is kept: the experiment measured quality on its dataset, not the reason the review blocked it
  (guardrail, risk domain, user-facing output...).
* REJECT -> the recommendation is discarded (blocking "experiment" challenge, DO_NOT_OPTIMIZE): it was tested and lost.
* INCONCLUSIVE -> attached, level unchanged; the report shows the extra n needed.
"""

from __future__ import annotations

from ai_auditor.analyzers.finding import Challenge, EvidenceLevel, Evidence, Finding
from ai_auditor.evaluation.golden import component_match
from ai_auditor.experiments.runner import ExperimentResult


def _targets(findings: list[Finding], r: ExperimentResult) -> list[Finding]:
    if r.finding:
        return [f for f in findings if f.id == r.finding]
    if r.rule:
        return [f for f in findings if f.rule_id == r.rule and component_match(f.component, r.component)]
    return []


def attach_experiments(findings: list[Finding], results: list[ExperimentResult]) -> list[str]:
    """Mutates findings in place; returns notes about experiments that matched nothing."""
    notes: list[str] = []
    for r in results:
        targets = _targets(findings, r)
        if not targets:
            notes.append(f"experiment {r.id} matched no finding (finding={r.finding}, rule={r.rule}, component={r.component})")
            continue
        for f in targets:
            f.impact.validated = r.to_validated()
            detail = f"experiment {r.id}: {r.decision} ({r.mode}, n={r.n}); " + "; ".join(r.reasons[:2])
            if r.decision == "ACCEPT":
                if f.actionable and f.level != EvidenceLevel.DO_NOT_OPTIMIZE:
                    f.evidence.append(Evidence("experiment", detail, value=r.id, weight=0.0))
                    f.level = EvidenceLevel.PROVEN
                else:
                    f.evidence.append(Evidence("experiment", detail + " — level kept: the adversarial review blocked this "
                                               "finding for a reason the experiment does not measure", value=r.id))
            elif r.decision == "REJECT":
                f.evidence.append(Evidence("experiment", detail, value=r.id, weight=-1.0))
                f.challenges.append(Challenge("experiment", "failed", detail, blocking=True))
                if f.level != EvidenceLevel.DO_NOT_OPTIMIZE:
                    f.demoted_from = f.demoted_from or str(f.level)
                f.level = EvidenceLevel.DO_NOT_OPTIMIZE
                f.survived_review = False
            else:
                f.evidence.append(Evidence("experiment", detail, value=r.id))
    return notes
