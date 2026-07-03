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
