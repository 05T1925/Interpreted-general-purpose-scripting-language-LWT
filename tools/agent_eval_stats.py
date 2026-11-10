"""S48 WP1: small-sample statistics for the blind evaluation.

Standard library only. Implements:

* Wilson score interval (better than the normal approximation when p is near
  0/1 or n is small);
* pass@k = 1 - C(n-c, k) / C(n, k), with pass@1 equal to c/n;
* a group summary (total samples, passes, Wilson 95% CI, pass@k);
* an approximate interval for the T-C difference of proportions.

These are descriptive statistics for an observational comparison; they are not
a causal claim (model/routing unobserved, small task set, single platform).
"""

from __future__ import annotations

from math import comb, sqrt


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""

    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= successes <= n:
        raise ValueError("successes must be within [0, n]")
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = (z / denom) * sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator: 1 - C(n-c, k) / C(n, k)."""

    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= c <= n:
        raise ValueError("c must be within [0, n]")
    if k <= 0 or k > n:
        raise ValueError("k must be within [1, n]")
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def difference_interval(c1: int, n1: int, c2: int, n2: int,
                        z: float = 1.96) -> tuple[float, float]:
    """Approximate Wald interval for p1 - p2 (observational, not causal)."""

    if n1 <= 0 or n2 <= 0:
        raise ValueError("n must be positive")
    p1, p2 = c1 / n1, c2 / n2
    se = sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diff = p1 - p2
    return (diff - z * se, diff + z * se)


def summarize_group(name: str, per_task: dict[str, tuple[int, int]],
                    k: int | None = None) -> dict:
    """Summarise one group; ``per_task`` maps task id -> (passed, samples)."""

    total_n = sum(n for _, n in per_task.values())
    total_c = sum(c for c, _ in per_task.values())
    low, high = wilson_interval(total_c, total_n) if total_n else (0.0, 0.0)
    kk = k or (min(n for _, n in per_task.values()) if per_task else 1)
    return {
        "group": name,
        "tasks": len(per_task),
        "samples": total_n,
        "passed": total_c,
        "pass_at_1": (total_c / total_n) if total_n else None,
        "wilson_95": [round(low, 6), round(high, 6)] if total_n else None,
        "pass_at_k": {f"pass@{kk}": round(pass_at_k(total_n, total_c, kk), 6)}
        if total_n >= kk else {},
        "per_task": {
            task: {
                "passed": c, "samples": n,
                "pass_at_1": round(c / n, 6) if n else None,
                "wilson_95": [round(v, 6) for v in wilson_interval(c, n)] if n else None,
            }
            for task, (c, n) in sorted(per_task.items())
        },
    }
