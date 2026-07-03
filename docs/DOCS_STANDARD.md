# Documentation Standard

The contract for how this project's docs are organized, what's hand-written vs
generated, and how they stay in sync with the code. The `doc-sync` skill and
`docs-updater` agent both read this. Adapt the tooling names to your stack; keep
the split and the sync discipline.

## Core split: hand-written vs generated

**Hand-written** (edit these directly, review them like code):
`architecture/`, `domain/`, `workflows/`, `operations/`, `start-here/`,
`development/`, `troubleshooting/`, `glossary.md`, `changelog.md`, `decisions/`.

**Auto-generated** (NEVER hand-edit — they regenerate on every build):
`docs/reference/` (from docstrings), `docs/config/` (from YAML/JSON config),
`docs/schemas/` (from JSON schemas). If a generated page is wrong, fix the
docstring or config that produces it, not the page.

A generator script (e.g. `scripts/gen_ref_pages.py`) rebuilds the generated tree
on `docs build`. Commit source changes; never commit generated output.

## Taxonomy

| Section | Purpose | Include when |
|---|---|---|
| Home | What this is, stack overview | Always |
| Start Here | Install, quickstart, conventions | Always |
| Feature Map | Capabilities with status + deep links | 3+ features |
| Architecture | Overview, data flow, component map | Multi-module |
| Domain | One page per major subsystem | Multi-module |
| Workflows | Step-by-step walkthroughs of real flows | Always (min 2) |
| Config | Generated from config files | `config/` exists |
| Schemas | Generated from JSON schemas | `schemas/` exists |
| API Reference | Generated from docstrings | Always (typed langs) |
| Development | Contributing, testing, eval harness | Always |
| Operations | Docker, deploy, migrations, monitoring | Deployed services |
| Troubleshooting | Common issues; grows over time | Always |
| Decisions | Architecture Decision Records | Non-obvious choices exist |
| Changelog | What's new, from commits/PRs | Always |
| Glossary | Domain terms with links | 5+ domain terms |
| Canonical Specs | Embedded spec document(s) | A `spec*.md` exists |

## Page conventions
- Every **domain** page opens with a one-sentence summary and a spec citation
  block: `> Realizes: <spec.md> §X.Y`.
- **Workflow** pages are numbered steps a reader can actually follow; re-verify
  each step when the flow changes.
- Docstrings use a consistent style (e.g. Google) so the reference generator
  renders them. New modules need a module docstring; new public functions need
  Args / Returns / Raises.

## The sync discipline (this is the point)
Docs are updated in the **same PR** as the code, not later. The `doc-sync` skill
runs at the end of every change:
1. Diff the branch (`git diff main...HEAD --name-only`).
2. Update every affected hand-written page.
3. Cite — and where in scope, update — the canonical spec `§`.
4. Log accepted drift as a follow-up (`docs/followups.md`).
5. Verify internal links.

Three modes of operation:
- **init** — scaffold the taxonomy for a new project from its structure + git log.
- **update** (default) — diff-based, per-PR, as above.
- **audit** — full scan: every domain page vs code, dead links, orphaned pages,
  stale examples → a scored drift report. Run periodically, not per-PR.
