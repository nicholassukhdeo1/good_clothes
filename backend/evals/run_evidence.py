"""Evidence eval: can a page change the score by lying rather than by commanding?

  python -m evals.run_evidence --arms hardened
  python -m evals.run_evidence                      # both arms, the full A/B
  python -m evals.run_evidence --cases cert_audit_report staged_cross_reference

Needs ANTHROPIC_API_KEY. Needs no Browserbase key: the "web" is the corpus.

Why this is a different runner from run_injection
-------------------------------------------------
run_injection measures whether the model DISOBEYS its instructions when a page
tells it to. The answer, on the first corpus, was never.

This measures whether the model can be misled while OBEYING them perfectly. The
system prompt tells it to score from what its searches returned. A convincing
fake audit is not something it has to be tricked into using - using it is the
instruction. So the evidence fence is expected to help very little here, and a
result showing that is the point rather than a disappointment.

Method
------
Every case is a minimal pair. The same brand is researched twice, once against
the attack pages and once against a control that differs only in the fabricated
content, and the score delta between them is the measurement. A fixed threshold
cannot do this job: a page that argues a brand up to 70 from a real 50 has done
real damage and would pass any "is it above 85" test.

The null cases run the same machinery over pages that carry no fabrication at
all. Their deltas are the noise floor, and a result is only worth reading next
to it.

Cost: two research passes per case per arm. The full run is 4 x 23 passes.
"""

import argparse
import statistics
import sys
from unittest.mock import patch

from evals import corpus_hard, harness, keys, metrics, report


def _arm_context(arm: str):
    """Same contract as run_injection: hardened is production and is not patched."""
    import contextlib

    import synthesize

    if arm == "baseline":
        return patch.object(synthesize.evidence, "wrap", harness.render_baseline)
    return contextlib.nullcontext()


def _one_run(case: dict, which: str, arm: str):
    """Research the case's brand against its `attack` or `control` pages."""
    import synthesize

    browser = harness.CorpusBrowser(pages=corpus_hard.pages_for(case, which))
    with _arm_context(arm):
        result = synthesize.synthesize(corpus_hard.brand_for(case), browser=browser)
    if metrics.is_fallback(result, synthesize.FALLBACK_SUMMARY):
        return None
    return result


def _run_case(case: dict, arm: str) -> dict:
    control = _one_run(case, "control", arm)
    attack = _one_run(case, "attack", arm)

    if control is None or attack is None:
        print(f"  [{arm}] {case['id']:<28} INVALID (a run failed before scoring)")
        return {"id": case["id"], "family": case["family"], "invalid": True,
                "delta": None, "succeeded": False}

    delta = harness.score_delta(case, attack, control)
    won = delta >= harness.MATERIAL_SHIFT
    key = f"{case['target']}_score"
    print(f"  [{arm}] {case['id']:<28} {case['target'][:3]} "
          f"{control[key]:>3} -> {attack[key]:<3} "
          f"delta={delta:+d}  {'ATTACK SUCCEEDED' if won else 'held'}")
    return {
        "id": case["id"],
        "family": case["family"],
        "invalid": False,
        "delta": delta,
        "succeeded": won,
        "control_score": control[key],
        "attack_score": attack[key],
        "attack_summary": attack.get("summary"),
    }


def _summarize(rows: list, label: str) -> dict:
    valid = [r for r in rows if not r["invalid"]]
    wins = [r for r in valid if r["succeeded"]]
    deltas = [r["delta"] for r in valid]
    return {
        "label": label,
        "total": len(rows),
        "valid": len(valid),
        "invalid": len(rows) - len(valid),
        "succeeded": len(wins),
        "success_rate": (len(wins) / len(valid)) if valid else None,
        "median_delta": statistics.median(deltas) if deltas else None,
        "max_delta": max(deltas) if deltas else None,
        "by_family": sorted({r["family"] for r in wins}),
        "cases": rows,
    }


def run_arm(arm: str, cases: list, nulls: list) -> dict:
    report.heading(f"Evidence attacks: {arm} rendering")
    attacks = _summarize([_run_case(c, arm) for c in cases], "attacks")

    noise = {}
    if nulls:
        report.heading(f"Noise floor: {arm} rendering")
        noise = _summarize([_run_case(c, arm) for c in nulls], "null")

    report.heading(f"Summary: {arm}")
    if attacks["success_rate"] is None:
        print(f"  NOTHING MEASURED - all {attacks['total']} pairs failed.", file=sys.stderr)
    else:
        print(f"  succeeded     : {attacks['succeeded']}/{attacks['valid']}  "
              f"{report.pct(attacks['success_rate'])}")
        print(f"  median delta  : {attacks['median_delta']:+}")
        print(f"  largest delta : {attacks['max_delta']:+}")
        if attacks["by_family"]:
            print(f"  families      : {', '.join(attacks['by_family'])}")
    if noise.get("valid"):
        print(f"  noise floor   : median {noise['median_delta']:+}, "
              f"largest {noise['max_delta']:+} over {noise['valid']} null pairs")
        if noise["max_delta"] is not None and noise["max_delta"] >= harness.MATERIAL_SHIFT:
            print("  WARNING: a null pair moved as much as the success threshold. "
                  "Treat the attack numbers as indicative only.", file=sys.stderr)
    if attacks["invalid"]:
        print(f"  excluded      : {attacks['invalid']} pairs failed before scoring")

    return {"attacks": attacks, "noise": noise}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", nargs="+", default=["baseline", "hardened"],
                    choices=["baseline", "hardened"])
    ap.add_argument("--cases", nargs="+", help="run only these case ids")
    ap.add_argument("--no-nulls", action="store_true",
                    help="skip the noise-floor pairs (cheaper, less readable)")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    if keys.missing("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.\n"
              "Put it in backend/.env or export it, then re-run.", file=sys.stderr)
        return 2

    cases = corpus_hard.CASES
    if args.cases:
        wanted = set(args.cases)
        cases = [c for c in cases if c["id"] in wanted]
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            print(f"unknown case ids: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
    nulls = [] if args.no_nulls else corpus_hard.NULL_CASES

    out = {arm: run_arm(arm, cases, nulls) for arm in args.arms}

    if len(args.arms) == 2:
        report.heading("Did the evidence fence help?")
        base = out["baseline"]["attacks"]["success_rate"]
        hard = out["hardened"]["attacks"]["success_rate"]
        if base is None or hard is None:
            print("  not comparable - one arm measured nothing.")
        else:
            print(f"  baseline  {report.pct(base)}   hardened  {report.pct(hard)}")
            print("  The fence marks page text as untrusted. It cannot mark it as\n"
                  "  untrue, so a difference here is not the thing it was built for.")

    if not args.no_save:
        print(f"\nwrote {report.save('evidence', out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
