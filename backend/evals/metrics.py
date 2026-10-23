# metrics.py - the arithmetic the eval runners report.
#
# Pure functions, no I/O and no model calls, so every number the suite prints is
# produced by code that runs in CI on every push. The expensive, nondeterministic
# part is gathering the samples; turning samples into a result is not.

import math

# synthesize.py answers 50/50 with a fixed summary whenever the loop fails: bad
# JSON, an API error, a truncated turn, or the turn cap. The badge renders that
# exactly like a real score, so the share of runs that land here is a product
# metric, not a log line.
FALLBACK_SCORE = 50


def is_fallback(result: dict, fallback_summary: str) -> bool:
    """Did this run degrade to the 50/50 answer rather than score the brand?"""
    return (
        result.get("ethics_score") == FALLBACK_SCORE
        and result.get("ownership_score") == FALLBACK_SCORE
        and result.get("summary") == fallback_summary
    )


def is_degenerate(result: dict, fallback_summary: str) -> bool:
    """Did this run produce a score carrying no information?

    Wider than is_fallback on purpose. is_fallback identifies synthesize.py's own
    fallback path, which is the only case where the *code* gave up. The model gives
    up too, and when it does it writes its own summary, so the narrow check sails
    past it. A variance run against the live web found four such runs in ten on a
    thinly covered brand while is_fallback reported none.

    Both reach the badge looking exactly like a real score, so both have to stay
    out of a spread that is supposed to describe real scoring.

    Two signals beyond the fallback itself:

    No sources. synthesize.SYSTEM tells the model to score from what its searches
    returned, so a result with nothing behind it is ungrounded by the product's own
    definition rather than by a guess about the numbers.

    The fallback value on both axes. Downstream this is indistinguishable from the
    fallback whatever summary came with it. This one can in principle reject a brand
    that is honestly middling on both counts; that costs a usable sample, where
    keeping it costs a wrong spread, and the spread is the number being measured.
    """
    if is_fallback(result, fallback_summary):
        return True
    if not result.get("sources"):
        return True
    return (
        result.get("ethics_score") == FALLBACK_SCORE
        and result.get("ownership_score") == FALLBACK_SCORE
    )


def rate(hits: int, total: int) -> float:
    """Hits over total, as a fraction. An empty denominator is 0.0, not an error:
    a run with nothing in it has no rate, and crashing the report helps no one."""
    return hits / total if total else 0.0


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def stdev(values) -> float:
    """Population standard deviation.

    Population rather than sample: these are every run that was made, not a draw
    from a larger pool, and n is small enough that the Bessel correction would
    change the headline number more than it clarifies it.
    """
    values = list(values)
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def summarize(values) -> dict:
    """The shape every variance report uses: centre, spread, and range."""
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "mean": None, "stdev": None, "min": None, "max": None, "spread": None}
    return {
        "n": len(values),
        "mean": round(mean(values), 2),
        "stdev": round(stdev(values), 2),
        "min": min(values),
        "max": max(values),
        # Worst case two users see for the same brand on the same day, which is
        # what actually erodes trust in a score.
        "spread": max(values) - min(values),
    }
