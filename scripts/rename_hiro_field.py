"""Atomic rename: hiro→flux, field→fog (the heatmap one only).

Strategy:
1. Identifier-level rename (case-preserving) via word-boundary regex.
2. Module path rename via specific string replace.
3. File renames via git mv.
4. Skip third-party SpotGamma TRACE references in research archives.
5. Skip pydantic Field / field_validator / dataclasses field — those
   are matched by exact-context patterns we DON'T touch.

We rename:
  hiro          → flux           (lowercase identifiers, attrs, docstrings)
  Hiro          → Flux           (PascalCase classes: HiroState→FluxState)
  HIRO          → FLUX           (constants, env keys, comments)
  engine.field  → engine.fog     (module path)
  engine.hiro   → engine.flux    (module path)
  field.py      → fog.py         (file)
  hiro.py       → flux.py        (file)
  FieldArrays   → FogArrays      (class) — SAFE because pydantic.Field doesn't have "Arrays"
  FieldGrid     → FogGrid        (class, in schema.py) — already done

For "field" lowercase: we ONLY rename when it's:
  - The snapshot key `field:` / `field=` / `.field` / `"field"`
  - Imports: `from engine.field` / `import field` (in engine context)
  - The FieldArrays / FieldGrid / field.gamma / field.delta / field.price_grid
We DO NOT rename:
  - pydantic.Field, pydantic.field_validator
  - dataclasses.field
  - Generic English "field" in docstrings (we'll grep-review)
  - `class Field` etc.

Approach: for `field`, we use SPECIFIC patterns rather than blanket replace.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\ollama\Downloads\flowdesk\flowdesk")
SERVICES = ROOT / "services"
PACKAGES = ROOT / "packages"
DOCS = ROOT / "docs"
ANALYSIS = ROOT / "analysis"

# Files to SKIP entirely (third-party product name references)
SKIP_PATHS_SUBSTR = [
    "docs/research/archive/",     # historical research
    "docs/research/verified/",    # references SpotGamma TRACE
    "docs/research/empirical/",   # may reference SpotGamma TRACE
    ".kilo/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".git/",
    "dist/",
    "build/",
    ".next/",
]

# Files we'll process
INCLUDE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".toml", ".yaml", ".yml", ".sh", ".env.example"}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    for sub in SKIP_PATHS_SUBSTR:
        if sub in rel:
            return True
    return False


def gather_files() -> list[Path]:
    out: list[Path] = []
    for base in [SERVICES, PACKAGES, DOCS, ANALYSIS, ROOT]:
        if not base.exists():
            continue
        if base == ROOT:
            # only top-level files, not subdirs (those handled separately)
            for p in ROOT.iterdir():
                if p.is_file() and p.suffix in INCLUDE_EXTS and not should_skip(p):
                    out.append(p)
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in INCLUDE_EXTS and not should_skip(p):
                out.append(p)
    return sorted(set(out))


# ---- Rename rules ----
# Order matters: longer patterns first to avoid partial replacement.

# (pattern, replacement) — applied in order via re.sub
RULES: list[tuple[re.Pattern, str]] = [
    # Module imports — engine.hiro / engine.field
    (re.compile(r"\bengine\.hiro\b"), "engine.flux"),
    (re.compile(r"\bengine\.field\b"), "engine.fog"),
    # Class names — Hiro* → Flux*
    (re.compile(r"\bHiroState\b"), "FluxState"),
    (re.compile(r"\bHiroSnapshot\b"), "FluxSnapshot"),
    (re.compile(r"\bHiroBucket\b"), "FluxBucket"),
    (re.compile(r"\bHiroTrade\b"), "FluxTrade"),
    (re.compile(r"\bHiroSeries\b"), "FluxSeries"),
    # Field* classes (only the heatmap ones — FieldArrays/FieldGrid)
    (re.compile(r"\bFieldArrays\b"), "FogArrays"),
    (re.compile(r"\bFieldGrid\b"), "FogGrid"),
    # Function names
    (re.compile(r"\bhiro_series\b"), "flux_series"),
    (re.compile(r"\bbuild_field\b"), "build_fog"),
    # Attribute / variable names commonly seen
    (re.compile(r"\bhiro_state\b"), "flux_state"),
    (re.compile(r"\bhiro_states\b"), "flux_states"),
    (re.compile(r"\b_hiro_states\b"), "_flux_states"),
    (re.compile(r"\b_hiro_state\b"), "_flux_state"),
    (re.compile(r"\bhiro_consumed\b"), "flux_consumed"),
    (re.compile(r"\bhiro_seed\b"), "flux_seed"),
    (re.compile(r"\bhiro_writes\b"), "flux_writes"),
    (re.compile(r"\bhiro_bus\b"), "flux_bus"),
    (re.compile(r"\bhiro_dump\b"), "flux_dump"),
    (re.compile(r"\bhiro_payload\b"), "flux_payload"),
    (re.compile(r"\bhiro_data\b"), "flux_data"),
    (re.compile(r"\bhiro_eval\b"), "flux_eval"),
    (re.compile(r"\bhiro_tier1\b"), "flux_tier1"),
    (re.compile(r"\bhiro_tier2\b"), "flux_tier2"),
    (re.compile(r"\bhiro_field\b"), "flux_field"),  # test func names
    # Method names: set_hiro_state / get_hiro_state / get_hiro_trades
    (re.compile(r"\bset_hiro_state\b"), "set_flux_state"),
    (re.compile(r"\bget_hiro_state\b"), "get_flux_state"),
    (re.compile(r"\bget_hiro_trades\b"), "get_flux_trades"),
    (re.compile(r"\bworker_hiro\b"), "worker_flux"),
    # Bare hiro identifier (variable, attribute) — must come AFTER specific compounds
    (re.compile(r"\bhiro\b"), "flux"),
    (re.compile(r"\bHIRO\b"), "FLUX"),
    # Snapshot key 'field' — very specific patterns
    # JSON / TS: "field": → "fog":
    (re.compile(r'"field"(\s*[:=])'), r'"fog"\1'),
    # Python: field=  in pydantic field=... ONLY when followed by FieldArrays/FieldGrid context
    # We'll handle pydantic `field: FogGrid` already via class rename.
    # Attribute access: snapshot.field, .field.gamma, .field.delta, .field.price_grid
    (re.compile(r"\.field\.gamma\b"), ".fog.gamma"),
    (re.compile(r"\.field\.delta\b"), ".fog.delta"),
    (re.compile(r"\.field\.price_grid\b"), ".fog.price_grid"),
    # snapshot.field reference (specifically when followed by space, comma, paren, end-of-line)
    (re.compile(r"snapshot\.field\b"), "snapshot.fog"),
    (re.compile(r"snap\.field\b"), "snap.fog"),
    (re.compile(r"s\.field\b"), "s.fog"),
    # `field=FieldArrays(` / `field=FogArrays(` (after class rename) — pattern: `field=Fog`
    (re.compile(r"\bfield=FogArrays\b"), "fog=FogArrays"),
    (re.compile(r"\bfield=FogGrid\b"), "fog=FogGrid"),
    # Pydantic field declaration in schema.py: `field: FogGrid | None` etc.
    (re.compile(r"(?m)^(\s+)field(\s*:\s*Fog)"), r"\1fog\2"),
]


# Module-import patterns that need extra handling
IMPORT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bfrom\s+engine\.hiro\s+import\b"), "from engine.flux import"),
    (re.compile(r"\bfrom\s+engine\.field\s+import\b"), "from engine.fog import"),
    (re.compile(r"\bimport\s+engine\.hiro\b"), "import engine.flux"),
    (re.compile(r"\bimport\s+engine\.field\b"), "import engine.fog"),
]

ALL_RULES: list[tuple[re.Pattern, str]] = IMPORT_PATTERNS + RULES


def transform(text: str) -> str:
    out = text
    for pat, repl in ALL_RULES:
        if isinstance(pat.flags, int) and pat.flags & re.MULTILINE:
            out = pat.sub(repl, out)
        else:
            out = pat.sub(repl, out)
    return out


def main() -> int:
    files = gather_files()
    print(f"[scan] {len(files)} files candidate", flush=True)

    # File rename map (module files only; tests already renamed by prior subagent
    # but we'll re-do with full set since stash reverted)
    file_renames = {
        SERVICES / "engine" / "src" / "engine" / "hiro.py": SERVICES / "engine" / "src" / "engine" / "flux.py",
        SERVICES / "engine" / "src" / "engine" / "field.py": SERVICES / "engine" / "src" / "engine" / "fog.py",
        SERVICES / "engine" / "tests" / "test_hiro.py": SERVICES / "engine" / "tests" / "test_flux.py",
        SERVICES / "engine" / "tests" / "test_field_levels.py": SERVICES / "engine" / "tests" / "test_fog_levels.py",
        SERVICES / "api" / "tests" / "test_worker_hiro.py": SERVICES / "api" / "tests" / "test_worker_flux.py",
        SERVICES / "api" / "tests" / "test_hiro_parity.py": SERVICES / "api" / "tests" / "test_flux_parity.py",
        ANALYSIS / "harness" / "hiro_eval.py": ANALYSIS / "harness" / "flux_eval.py",
        ANALYSIS / "harness" / "test_hiro_eval.py": ANALYSIS / "harness" / "test_flux_eval.py",
        ANALYSIS / "harness" / "run_hiro_eval.py": ANALYSIS / "harness" / "run_flux_eval.py",
        DOCS / "architecture" / "hiro-unification.md": DOCS / "architecture" / "flux-unification.md",
        PACKAGES / "contracts" / "examples" / "snapshot.nonfinite_field_gamma_inf.json": PACKAGES / "contracts" / "examples" / "snapshot.nonfinite_fog_gamma_inf.json",
    }

    # Apply git mv for files that exist and target doesn't
    for src, dst in file_renames.items():
        if src.exists() and not dst.exists():
            print(f"[mv ] {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}", flush=True)
            subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True)

    # Now re-gather (renamed files are at new paths)
    files = gather_files()

    # Transform each file
    changed = 0
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new = transform(text)
        if new != text:
            fp.write_text(new, encoding="utf-8")
            changed += 1
            print(f"[edit] {fp.relative_to(ROOT)}", flush=True)
    print(f"[done] {changed} files modified", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
