"""Small, dependency-free statistics used by evaluation and experiments.

Choices: Wilson intervals for proportions (better coverage than the
normal approximation at small n and extreme p); exact Clopper-Pearson upper bound when zero events are observed
(rule of three ≈ 3/n); exact McNemar and Newcombe's paired score interval for paired binary outcomes; percentile bootstrap (paired,
optionally by cluster) for continuous statistics;
Holm step-down for multiple comparisons.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence

Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def zero_events_upper(n: int, alpha: float = 0.05) -> float:
    """Exact one-sided upper bound for a rate when 0 events were seen in n trials (≈ 3/n for alpha=0.05)."""
    if n == 0:
        return 1.0
    return 1 - alpha ** (1 / n)


def z_for(alpha: float) -> float:
    """Two-sided normal quantile for confidence level 1 − alpha."""
    from statistics import NormalDist

    return NormalDist().inv_cdf(1 - alpha / 2)


def newcombe_paired(both: int, only_first: int, only_second: int, neither: int, z: float = Z95) -> tuple[float, float]:
    """CI for p1 − p2 with paired binary data (Newcombe 1998, method 10: hybrid Wilson score with the
    continuity-corrected phi, which is the conservative choice). p1 = (both + only_first)/n, p2 = (both + only_second)/n.

    Unlike a percentile bootstrap it does not collapse to zero width when there are no discordant pairs: with n items
    and no disagreement the width still reflects the uncertainty of each proportion, shrunk by their correlation.
    """
    n = both + only_first + only_second + neither
    if n == 0:
        return (-1.0, 1.0)
    p1, p2 = (both + only_first) / n, (both + only_second) / n
    l1, u1 = wilson(both + only_first, n, z)
    l2, u2 = wilson(both + only_second, n, z)
    e, f, g, h = both + only_first, only_second + neither, both + only_second, only_first + neither
    den = e * f * g * h
    num = both * neither - only_first * only_second
    if den == 0:
        phi = 0.0
    elif num > n / 2:
        phi = (num - n / 2) / math.sqrt(den)
    elif num >= 0:
        phi = 0.0
    else:
        phi = num / math.sqrt(den)
    d = p1 - p2
    lo = d - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    hi = d + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return (max(-1.0, lo), min(1.0, hi))


def _binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from discordant counts b (A right, B wrong) and c (A wrong, B right)."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * _binom_cdf(min(b, c), n))


def bootstrap_ci(
    values: Sequence[float] | Sequence[Sequence[float]],
    stat: Callable[[list], float] = lambda xs: sum(xs) / len(xs),
    n_boot: int = 4000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap. ``values`` may be a list of per-item numbers, or a list of clusters (lists) resampled whole."""
    rng = random.Random(seed)
    items = list(values)
    if not items:
        return (float("nan"), float("nan"))
    clustered = isinstance(items[0], (list, tuple))
    reps = []
    for _ in range(n_boot):
        sample = [items[rng.randrange(len(items))] for _ in items]
        flat = [x for cl in sample for x in cl] if clustered else sample
        reps.append(stat(flat))
    reps.sort()
    lo = reps[int((alpha / 2) * n_boot)]
    hi = reps[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def holm(pvalues: dict[str, float], alpha: float = 0.05) -> dict[str, bool]:
    """Holm step-down: which hypotheses are rejected while controlling family-wise error at alpha."""
    order = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(order)
    out: dict[str, bool] = {}
    still = True
    for i, (name, p) in enumerate(order):
        still = still and p <= alpha / (m - i)
        out[name] = still
    return out


def brier(pairs: Sequence[tuple[float, bool]]) -> float | None:
    if not pairs:
        return None
    return sum((p - (1.0 if y else 0.0)) ** 2 for p, y in pairs) / len(pairs)


def ece(pairs: Sequence[tuple[float, bool]], bins: int = 5) -> float | None:
    """Expected calibration error with equal-width bins."""
    if not pairs:
        return None
    total = len(pairs)
    err = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, y) for p, y in pairs if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if sel:
            conf = sum(p for p, _ in sel) / len(sel)
            acc = sum(1 for _, y in sel if y) / len(sel)
            err += len(sel) / total * abs(conf - acc)
    return err


def platt(pairs: Sequence[tuple[float, bool]], iters: int = 2000, lr: float = 0.1) -> tuple[float, float] | None:
    """Fit p' = sigmoid(a*logit(p) + b) by gradient descent with Platt's target smoothing (suits small n)."""
    if len(pairs) < 8:
        return None
    pos = sum(1 for _, y in pairs if y)
    neg = len(pairs) - pos
    if pos == 0 or neg == 0:
        return None
    t_pos, t_neg = (pos + 1) / (pos + 2), 1 / (neg + 2)
    xs = [math.log(max(1e-6, min(1 - 1e-6, p)) / (1 - max(1e-6, min(1 - 1e-6, p)))) for p, _ in pairs]
    ts = [t_pos if y else t_neg for _, y in pairs]
    a, b = 1.0, 0.0
    for _ in range(iters):
        ga = gb = 0.0
        for x, t in zip(xs, ts):
            q = 1 / (1 + math.exp(-(a * x + b)))
            ga += (q - t) * x
            gb += q - t
        a -= lr * ga / len(xs)
        b -= lr * gb / len(xs)
    return (a, b)
