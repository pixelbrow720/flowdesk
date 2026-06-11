"""Cross-language validation harness for the Snapshot contract (Python side).

Loads the shared fixtures from ``packages/contracts/examples`` and asserts:
  - snapshot.example.json   is ACCEPTED
  - snapshot.malformed.json is REJECTED

Run (after ``pip install -e ".[dev]"`` in services/engine):
    python services/engine/scripts/validate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from engine.schema import parse_snapshot

# repo_root/services/engine/scripts/validate.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "packages" / "contracts" / "examples"


def _load(name: str) -> object:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def main() -> int:
    ok = True

    try:
        parse_snapshot(_load("snapshot.example.json"))
        print("snapshot.example.json   -> ACCEPTED")
    except ValidationError as exc:
        ok = False
        print("snapshot.example.json   -> REJECTED (unexpected)")
        print(exc)

    try:
        parse_snapshot(_load("snapshot.malformed.json"))
        ok = False
        print("snapshot.malformed.json -> ACCEPTED (unexpected)")
    except ValidationError as exc:
        first = exc.errors()[0]
        print("snapshot.malformed.json -> REJECTED (expected)")
        print(f"  reason: {exc.error_count()} error(s); first: {first['msg']}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
