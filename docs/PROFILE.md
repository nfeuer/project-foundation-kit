# The Project Profile (`.claude/kit.yaml`)

The profile is what makes the kit portable across languages and project types.
Instead of every skill hardcoding `uv run pytest`, skills read commands and
capability toggles from one file — `.claude/kit.yaml` — so adapting the kit to a
Node, Go, or Rust project (or a library vs. a deployed service) is a matter of
editing that one file, not a dozen skill bodies.

## How skills consume the profile

Skills are instructions to an agent, not compiled code, so consumption is by
convention, not a templating engine:

1. **Toolchain commands.** A step is tagged with the profile key it resolves to:

   ````
   ### 3. Tests
   ```bash
   # kit.yaml → toolchain.test
   uv run pytest tests/unit/ -m "not slow and not llm" --tb=short -q
   ```
   ````

   The executing agent runs the command from `kit.yaml` if the key is set; the
   literal shown is the **default** (a Python/uv project). An empty string in the
   profile means **skip this step** and mark it N/A.

2. **Capability gates.** A capability-specific skill checks its toggle first:

   > **Applies when** `capabilities.migrations.enabled` is true. If false, skip
   > and report N/A.

   This is how `pre-pr` runs the right subset: an LLM service runs eval /
   prompt-regression / cost gates; a Go CLI runs none of them, with no edits.

3. **Named values.** `trunk_branch`, `worktree_dir`, `alerts.channel`, and
   `capabilities.spec.file` are read wherever a skill or hook needs them.
   The `logging.*` block records what the `logging-init` skill probed, asked,
   and wired (library, destination, dev rendering) — `initialized: false` is a
   standing kit-doctor warning to run it.

## Gate strictness — ceremony scales with maturity

`gates.strictness` sets how hard the quality gates push, so a weekend prototype
and a production service can run the same kit without either drowning in
ceremony or shipping unguarded. Three levels:

| Level | Behavior |
|---|---|
| `prototype` | The *trend* gates — `coverage-ratchet`, `perf-budget`, and eval pass-gates in `prompt-regression` — run and **report** but never block a PR. There is no baseline worth defending yet; the numbers are informational. Hard-safety gates are unaffected: secrets scan, `migration-check`, and security review **always block** at every level. |
| `standard` | The documented default behavior of every gate. Regressions block; warnings warn. |
| `production` | Warnings harden into failures: a ratchet enabled with no baseline file blocks instead of warning, perf paths with sparse data (<20 observations) block instead of passing annotated, and `pre-pr` runs the security review on **every** diff rather than only ones touching sensitive surfaces. |

Skills read the level once at the start of a run. A skill that changes behavior
by level says so in its body ("At `prototype` strictness…"); a skill that
doesn't mention strictness behaves identically at all levels. Move the level up
deliberately — bootstrap starts brand-new repos at `prototype` with a TODO to
graduate, and presets default to `standard`.

## Where the profile comes from

- **New projects:** `new-project-bootstrap` detects the stack (probes for
  `pyproject.toml` / `package.json` / `go.mod` / `Cargo.toml`, reads existing CI
  or a Makefile for the real commands) and writes `kit.yaml`, picking a **preset**
  as the starting point.
- **Existing projects:** `adopt-existing-project` infers the profile from what's
  already there and merges rather than overwrites.
- **Presets** (`presets/*.yaml`) are archetype defaults — `library`, `service`,
  `llm-app`, `frontend`, `data-pipeline` — each enabling a curated capability set.

## Keeping it honest

`kit-doctor` verifies the profile is wired correctly: every non-empty toolchain
command actually runs, capability toggles match what's installed, hooks are
executable and referenced in settings, and `gh` is authed. Run it after any
profile edit. `kit-update` compares `kit_version` against the source kit so
improvements to a skill propagate instead of silently drifting.
