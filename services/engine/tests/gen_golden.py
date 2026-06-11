"""Regenerate the golden snapshot fixture.

Run from services/engine:  PYTHONPATH=src python tests/gen_golden.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.test_snapshot import GOLDEN_PATH, produce_snapshot  # noqa: E402


def main() -> None:
    os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
    snap = produce_snapshot()
    with open(GOLDEN_PATH, "w") as fh:
        fh.write(json.dumps(json.loads(snap.to_json()), indent=2, sort_keys=True))
        fh.write("\n")
    print("wrote", GOLDEN_PATH)


if __name__ == "__main__":
    main()
