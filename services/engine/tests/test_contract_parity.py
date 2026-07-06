"""Automated pydantic <-> zod field-parity guard for the Snapshot contract.

Why this test exists
====================
The canonical Snapshot contract is maintained as TWO hand-kept mirrors that MUST
stay 1:1 at ``schema_version`` 2:

  * PYDANTIC : ``services/engine/src/engine/schema.py``
  * ZOD / TS : ``packages/contracts/src/snapshot.ts``

Nothing else in the repo verifies, across the language boundary, that the two
mirrors expose the SAME field names per model. ``test_snapshot.py`` hand-mirrors
the zod shape in Python (a manual mirror, itself unchecked against the .ts
source), and ``snapshot.ts`` has a compile-time tuple that only checks zod vs the
TS interface WITHIN that one file. So if someone adds/removes/renames a field on
one side and forgets the other, no test catches it. THIS test closes that gap.

How it works
============
1. The pydantic side is derived PROGRAMMATICALLY from ``engine.schema`` via each
   model's ``model_fields`` — so it is always current, never a copy.
2. The zod side is parsed from ``snapshot.ts`` as TEXT. For each ``z.object({…})``
   schema we brace-match the object body and collect its top-level keys. The
   parser only has to handle the actual shape of snapshot.ts (flat ``z.object``
   blocks whose values are either primitives, ``z.array(...)``, ``.nullish()`` /
   ``.nullable()`` refinements, or references to other named schemas — there are
   NO inline nested ``z.object`` literals in this file). ``.superRefine((…) =>
   {…})`` chained after ``.strict()`` is deliberately excluded because we stop at
   the matching close-brace of the ``.object({...})`` body.
3. For every model shared by both mirrors we assert the two field-name sets are
   identical, failing with an explicit per-side diff.

If ``snapshot.ts`` cannot be located (e.g. an engine-only checkout without the TS
package) the test SKIPs with a clear message rather than hard-failing. In this
repo the file exists, so the test actually runs.

This test asserts NAME/STRUCTURE parity only. Type/format parity (enums, finite
numbers, ISO strings, array-length invariants) is already covered by
``test_snapshot.py::_assert_zod_compatible``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine import schema as pyschema

# --------------------------------------------------------------------------- #
# Model map: pydantic model  <->  zod schema const name in snapshot.ts.
# The names mostly match after stripping "Schema"; the two exceptions are
# FogGrid<->FogSchema and OHLC<->OHLCSchema, so we spell the mapping out in full
# rather than guessing. Every entry MUST exist on both sides.
# --------------------------------------------------------------------------- #
MODEL_MAP: dict[type, str] = {
    pyschema.Axis: "AxisSchema",
    pyschema.Regime: "RegimeSchema",
    pyschema.ProfileRow: "ProfileRowSchema",
    pyschema.FogGrid: "FogSchema",
    pyschema.Levels: "LevelsSchema",
    pyschema.OHLC: "OHLCSchema",
    pyschema.Flux: "FluxSchema",
    pyschema.SyntheticOi: "SyntheticOiSchema",
    pyschema.ExposureExt: "ExposureExtSchema",
    pyschema.TotalHedging: "TotalHedgingSchema",
    pyschema.Surface: "SurfaceSchema",
    pyschema.Ddoi: "DdoiSchema",
    pyschema.Proprietary: "ProprietarySchema",
    pyschema.IvSmilePoint: "IvSmilePointSchema",
    pyschema.ThetaDecaySnapshot: "ThetaDecaySnapshotSchema",
    pyschema.MaxPainSnapshot: "MaxPainSnapshotSchema",
    pyschema.VolExpansionSnapshot: "VolExpansionSnapshotSchema",
    pyschema.Snapshot: "SnapshotSchema",
}


def _find_snapshot_ts() -> Path | None:
    """Locate packages/contracts/src/snapshot.ts relative to the repo root.

    This file lives at services/engine/tests/test_contract_parity.py, so the
    repo root is four parents up. Return None if the TS mirror is absent.
    """
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / "packages" / "contracts" / "src" / "snapshot.ts"
    return candidate if candidate.is_file() else None


def _extract_zod_object_fields(source: str, schema_const: str) -> set[str]:
    """Return the top-level field names of a ``z.object({...})`` zod schema.

    Strategy (pragmatic, tailored to snapshot.ts):
      1. Find ``export const <schema_const> = z``.
      2. Find the ``.object(`` that follows and its opening ``{``.
      3. Brace-match to the object body's closing ``}`` (so anything chained
         after ``.strict()``, e.g. ``.superRefine(...)``, is excluded).
      4. Collect identifiers that appear as ``key:`` at brace/paren/bracket
         depth 0 within the body — i.e. the object's own fields.
    """
    decl = re.search(rf"export\s+const\s+{re.escape(schema_const)}\s*=\s*z\b", source)
    if decl is None:
        raise AssertionError(
            f"zod schema `{schema_const}` not found in snapshot.ts "
            f"(pydantic model expects a matching mirror)"
        )
    obj = source.find(".object(", decl.end())
    if obj == -1:
        raise AssertionError(f"`{schema_const}` is not a z.object(...) schema")
    brace_start = source.find("{", obj)
    if brace_start == -1:
        raise AssertionError(f"`{schema_const}` .object( has no opening brace")

    # Brace-match the object body. snapshot.ts z.object bodies contain no string
    # literals with unbalanced braces, so a plain counter is sufficient here.
    depth = 0
    end = -1
    for i in range(brace_start, len(source)):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise AssertionError(f"`{schema_const}` .object body is not balanced")

    body = source[brace_start + 1 : end]

    # Collect top-level keys. Track nesting across (){}[] so a hypothetical
    # future inline nested object would not leak its keys; check the key BEFORE
    # applying this line's bracket deltas because a field line starts at depth 0.
    fields: set[str] = set()
    nesting = 0
    key_re = re.compile(r"([A-Za-z_]\w*)\s*:")
    for line in body.splitlines():
        stripped = line.strip()
        if nesting == 0:
            match = key_re.match(stripped)
            if match:
                fields.add(match.group(1))
        nesting += line.count("{") + line.count("(") + line.count("[")
        nesting -= line.count("}") + line.count(")") + line.count("]")
    return fields


def test_pydantic_zod_field_parity() -> None:
    """Every shared model must expose identical field-name sets on both sides."""
    ts_path = _find_snapshot_ts()
    if ts_path is None:
        pytest.skip(
            "snapshot.ts not found (engine-only checkout); zod parity not checkable"
        )
    source = ts_path.read_text(encoding="utf-8")

    mismatches: list[str] = []
    checked_fields = 0
    for model, schema_const in MODEL_MAP.items():
        py_fields = set(model.model_fields.keys())
        zod_fields = _extract_zod_object_fields(source, schema_const)
        checked_fields += len(py_fields)
        if py_fields != zod_fields:
            only_py = sorted(py_fields - zod_fields)
            only_zod = sorted(zod_fields - py_fields)
            mismatches.append(
                f"  {model.__name__} <-> {schema_const}:\n"
                f"    only in pydantic: {only_py}\n"
                f"    only in zod     : {only_zod}"
            )

    assert not mismatches, (
        "Snapshot mirror DRIFT — pydantic and zod field names diverge:\n"
        + "\n".join(mismatches)
    )

    # Guard against the parser silently matching nothing and passing vacuously.
    assert len(MODEL_MAP) == 18, "expected 17 nested models + Snapshot"
    assert checked_fields >= 60, (
        f"parser extracted too few fields ({checked_fields}); it likely failed "
        f"to parse snapshot.ts rather than genuinely passing"
    )
