# report.py - writing a run to disk and printing it.
#
# Every run is kept as a dated JSON file so quality is diffable over time: the
# question "did the prompt change make this worse" is answered by two files, not
# by remembering what the number was last month.

import json
import pathlib
import platform
import sys
from datetime import datetime, timezone

RESULTS = pathlib.Path(__file__).parent / "results"


def save(name: str, payload: dict) -> pathlib.Path:
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    payload = dict(payload)
    payload["recorded_at"] = stamp
    # Pin what produced the number. A result without the model that made it is
    # not comparable to the next one.
    payload["environment"] = {
        "python": platform.python_version(),
        "argv": " ".join(sys.argv),
    }
    path = RESULTS / f"{stamp}-{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def heading(text: str) -> None:
    print(f"\n{text}\n" + "-" * len(text))
