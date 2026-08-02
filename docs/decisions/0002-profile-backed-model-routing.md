# 0002. Profile-backed model routing (models.* keys in kit.yaml)

**Status:** proposed
**Date:** 2026-07-31
**Author:** Claude 5 skill refresh (docs/plans/claude5-skill-refresh.md)

---

## Context

The kit has no convention for which model executes which shape of work. The kit
owner's operating rule is: code-writing runs on `claude-opus-5` /
`claude-sonnet-5`, planning and validation on `claude-fable-5`, mechanical
checks on `claude-haiku-4-5`. That rule needs a durable home that skills can
cite without hardcoding model IDs — the same problem `toolchain.*` already
solves for commands.

---

## Decision

We will add a `models:` block to `.claude/kit.yaml` (roles: `code`,
`code_light`, `plan`, `mechanical`, plus per-role `effort` defaults). Skills and
the dispatcher cite role keys (`models.plan`), never literal model IDs; the
routing table lives in a new `## Model routing` section of `using-the-kit`.

---

## Options Considered

### Option A: Profile keys + dispatcher table ✅ chosen

**Pros:** follows the kit's own "never hardcode a toolchain" convention;
retargeting the whole kit is a one-line profile edit; machine-readable for
hooks/CI.
**Cons:** full registration cost — kit.yaml, all five presets, `docs/PROFILE.md`,
one `kit-doctor` check.

### Option B: `model:` frontmatter key per skill ❌ rejected

**Pros:** visible at the top of each skill.
**Cons:** frontmatter is a fixed contract consumed by the loader and
`kit-doctor`; a per-skill key hardcodes a project-varying value into 30 files —
exactly what the profile exists to avoid.

### Option C: Dispatcher prose only, bare IDs ❌ rejected

**Pros:** smallest diff (one section in `using-the-kit`).
**Cons:** hardcodes IDs in prose; every model generation change becomes a prose
sweep instead of a profile edit; nothing machine-checkable.

---

## Consequences

Model choices become configuration: presets can differ (`library` may prefer
`code: claude-sonnet-5`), and `kit-doctor` can FAIL retired or date-suffixed
IDs. Skills gain an optional one-line "model fit" note citing role keys.

---

## Related

- docs/plans/claude5-skill-refresh.md — Part 3, Wave 1b
- docs/PROFILE.md (gains the key reference), presets/*.yaml
