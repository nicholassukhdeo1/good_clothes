"""Variance and fallback eval: is the same brand scored the same way twice?

  python -m evals.run_variance --n 5 --tier well_covered
  python -m evals.run_variance --n 10 --brands Shein Patagonia
  python -m evals.run_variance --n 1            # whole list, one pass: fallback rate

Needs ANTHROPIC_API_KEY and the Browserbase keys: unlike the injection eval this
one has to touch the real web, because the thing being measured is the product,
not the prompt. That makes it the expensive tier - n runs over 30 brands is 30n
research passes at roughly 14-26s each - so it belongs on a schedule and on
prompt changes, never on a push.

Two numbers come out of it:

  spread      max - min over n runs of one brand. This is what two users see for
              the same brand on the same afternoon, and it is the honest answer
              to "is this score meaningful".
  fallback    share of runs that degraded to 50/50. The badge renders that
              identically to a real score, so the user cannot tell.
"""

import argparse
import statistics
import sys
import time

from evals import brands as brand_list
from evals import metrics, report


def run_brand(name: str, n: int) -> dict:
    import synthesize

    ethics, ownership, fallbacks, elapsed = [], [], 0, []
    for i in range(1, n + 1):
        started = time.perf_counter()
        try:
            result = synthesize.synthesize(name)
        except Exception as e:  # a crash is a datapoint, not a reason to stop
            print(f"    run {i}: raised {type(e).__name__}: {e}", file=sys.stderr)
            fallbacks += 1
            continue
        took = time.perf_counter() - started
        elapsed.append(took)
        if metrics.is_fallback(result, synthesize.FALLBACK_SUMMARY):
            fallbacks += 1
        ethics.append(result.get("ethics_score"))
        ownership.append(result.get("ownership_score"))
        print(f"    run {i}: ethics={result.get('ethics_score'):<4} "
              f"ownership={result.get('ownership_score'):<4} {took:.1f}s")

    return {
        "brand": name,
        "runs": n,
        "ethics": metrics.summarize(ethics),
        "ownership": metrics.summarize(ownership),
        "fallbacks": fallbacks,
        "fallback_rate": metrics.rate(fallbacks, n),
        "latency_s": round(statistics.median(elapsed), 1) if elapsed else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=5, help="runs per brand")
    ap.add_argument("--brands", nargs="+", help="explicit brand names")
    ap.add_argument("--tier", choices=brand_list.TIERS, help="sample one coverage tier")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    import os
    missing = [k for k in ("ANTHROPIC_API_KEY", "BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID")
               if not os.environ.get(k)]
    if missing:
        print(f"missing keys: {', '.join(missing)}\n"
              f"This eval measures the real pipeline against the real web and cannot "
              f"be faked. Set them in backend/.env and re-run.", file=sys.stderr)
        return 2

    names = args.brands or brand_list.names(args.tier)
    report.heading(f"Variance over {len(names)} brands x {args.n} runs")

    results = []
    for name in names:
        print(f"  {name}")
        results.append(run_brand(name, args.n))

    total_runs = sum(r["runs"] for r in results)
    total_fallbacks = sum(r["fallbacks"] for r in results)
    spreads = [r["ethics"]["spread"] for r in results if r["ethics"]["spread"] is not None]

    report.heading("Summary")
    print(f"  brands           : {len(results)}")
    print(f"  runs             : {total_runs}")
    print(f"  fallback rate    : {total_fallbacks}/{total_runs}  "
          f"{report.pct(metrics.rate(total_fallbacks, total_runs))}")
    if spreads:
        print(f"  median spread    : {statistics.median(spreads):.0f} points")
        print(f"  worst spread     : {max(spreads)} points "
              f"({max(results, key=lambda r: r['ethics']['spread'] or 0)['brand']})")

    payload = {
        "runs_per_brand": args.n,
        "fallback_rate": metrics.rate(total_fallbacks, total_runs),
        "median_spread": statistics.median(spreads) if spreads else None,
        "brands": results,
    }
    if not args.no_save:
        print(f"\nwrote {report.save('variance', payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
