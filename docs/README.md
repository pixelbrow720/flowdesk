# FlowDesk Documentation

This folder is the **single home for all FlowDesk documentation**. It replaces
the previous scatter of root-level planning docs, per-phase READMEs, and the
`Research/` drafts.

> **AI agents:** your operating manual is [`../AGENTS.md`](../AGENTS.md). Read it first.

## Authoritative docs (read in order)

| # | Doc | What it covers |
|---|---|---|
| 00 | [Overview](00-overview.md) | What FlowDesk is, who it's for, the big picture |
| 01 | [Architecture](01-architecture.md) | Monorepo layout, the Snapshot pipeline, runtime data flow |
| 02 | [Locked Contract](02-locked-contract.md) | Non-negotiable values: colors, fonts, math, ENV, schema |
| 03 | [Data Contract](03-data-contract.md) | The `Snapshot` schema, field by field |
| 04 | [Engine](04-engine.md) | The compute core: Black-76, IV, exposure, field, levels, snapshot, HIRO, surface |
| 05 | [Data & Feeds](05-data-and-feeds.md) | Databento schemas, feed adapters, the batched ingest |
| 06 | [API & Auth](06-api-and-auth.md) | REST/WS endpoints, the worker, Discord OAuth gating |
| 07 | [Frontend](07-frontend.md) | The Next.js app, design tokens, what's built |
| 08 | [Status & Gaps](08-status-and-gaps.md) | **Honest** map: real vs. stubbed vs. naive — the backlog |
| 09 | [Roadmap](09-roadmap.md) | MVP → v4, mapped to current status |
| 10 | [Acceptance & Testing](10-acceptance-and-testing.md) | The T-01…T-10 gate and how the suites are run |

## Reference & research (preserved source material)

- [`reference/PRD-Gabungan.md`](reference/PRD-Gabungan.md) — the full combined PRD (authoritative product spec).
- [`reference/Build-Playbook-PerFase.md`](reference/Build-Playbook-PerFase.md) — the original prompt-by-prompt build playbook.
- [`reference/Stitching-Guide.md`](reference/Stitching-Guide.md) — how the release patches were stitched; full locked-contract text + acceptance gate.
- [`reference/methodology-decisions.md`](reference/methodology-decisions.md) — the 5 methodology divergence decisions + heavy unbuilt items.
- [`reference/implementation-status-2026-06-11.md`](reference/implementation-status-2026-06-11.md) — a dated, detailed status snapshot vs. the research blueprint.
- [`research/verified/`](research/verified/) — **canonical, independently-verified research** (source of truth): the definitive report, the red-team validation audit, and `black76_validate.py` (Black-76 greeks re-derived vs finite-difference, academic sources checked, zero fabrications).
- [`research/archive/`](research/archive/) — superseded raw methodology drafts (HIRO, SpotGamma reverse-engineering, FlowGreeks blueprint, mega-riset 1 & 2), kept for provenance only. The `verified/` package wins on any disagreement.
- [`research/empirical/`](research/empirical/) — **empirical findings (harness v1, NOT yet verified):** the Lapis 1 ΔOI reconciliation result (positive-control passed), the exploratory GEX case study, and the Track-F + DDOI exposure/vol-surface layers. ⚠️ **Read [`symbology-0dte-findings.md`](research/empirical/symbology-0dte-findings.md) first:** the original 8-day dataset was pulled with the wrong symbology (quarterly, not 0DTE), contaminating all greek-based findings. The symbology bug is now **FIXED & PROVEN** — correct 0DTE data exists for Jun 5/8/9/10 (`data/raw/zerodte/`, IV verified sane ~26.7%). The greek layers have been **RE-RUN on it** — see [`synthetic-oi-0dte.md`](research/empirical/synthetic-oi-0dte.md). Flow-based findings (Lapis 1, DDOI) are unaffected and valid.
- [`research/empirical/synthetic-oi-0dte.md`](research/empirical/synthetic-oi-0dte.md) — greek re-run on correct 0DTE data: vol surface theory-consistent (IV 22–54%, rises on crash, put skew); three positioning lenses (VOL vs OI vs FLOW) with honest structural findings (VOL≈OI on sign; FLOW diverges on crash days — flow-leads-stock); and a roadmap of more robust synthetic-OI formulas (hybrid OI-anchored #4, total-hedging #7) for the ~90-day forward test.
- [`research/empirical/validation-harness.md`](research/empirical/validation-harness.md) — the offline validation harness (`analysis/harness/`): **mechanism built, NOT evidence.** Magnitude-only ΔOI reconciliation (directional is degenerate on 0DTE) — volume-controlled `rho|vol` collapses to ~0.08–0.24, so the raw flow↔OI correlation is mostly activity, not skill; no pinning signal on 4 days. Two artefacts (look-ahead, unfair baseline) caught + fixed in review. Run the ~90-day forward pull through the same code before reading any result.
- [`research/empirical/synthetic-oi-roadmap.md`](research/empirical/synthetic-oi-roadmap.md) — **PLAN only (not built):** buildable specs for synthetic-OI #5 (decay-weighted), #6 (size-tiered), #7 (total-hedging gamma+charm+vanna). Data-checked feasibility (#7 = VEX/CHEX on the `Q` base, zero new data; #5/#6 need a per-trade-tape refactor). Build order #7→#6→#5; all EXPERIMENTAL, none before the harness has a forward dataset.
- [`research/RISET1407.md`](research/RISET1407.md) — deep research (primary-source cited) confirming /ES /NQ 0DTE exists, the `ES.OPT`-is-quarterly-only root cause, the deterministic 0DTE re-pull recipe, and the GLBX-over-OPRA decision.

## Code-adjacent docs (kept next to the code they describe)

These intentionally stay with their modules:

- `packages/contracts/CONTRACT.md` — canonical Snapshot contract, beside `snapshot.ts`.
- `packages/tokens/USAGE.md` — design-token usage.
- `services/api/src/api/{AUTH,FE_AUTH_CONTRACT,REST,STATE,WORKER,WS}_README.md` — per-module API docs.
- `services/api/tests/AUTH_TEST_NOTES.md` — auth test rationale.
- `services/engine/README.md` — engine package quickstart.
