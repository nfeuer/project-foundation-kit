# Preset Reference

Presets are partial `kit.yaml` files under `presets/` that provide archetype-
appropriate defaults for the five most common project shapes. The bootstrap skill
loads the matching preset as the starting point for `.claude/kit.yaml`, then
overlays detected values on top — detected commands always win over preset defaults.

## The five presets

| Preset | What it enables | Typical toolchain |
|---|---|---|
| `library` | lint · type · test · test-gap · secret-scan · dep-audit · config-consistency · doc-sync · followups | Python/uv · `uv build` |
| `service` | + migrations · nightly-audit · incident-capture · healthwatch · alerts | Python/uv + Alembic |
| `llm-app` | + llm (eval-harness · prompt-regression · cost-check) | Python/uv + Alembic + LLM API |
| `frontend` | lint · type · test · build · secret-scan · doc-sync · followups | npm or pnpm |
| `data-pipeline` | + migrations · nightly-audit · healthwatch | Python/uv + Alembic |

**Picking a preset.** Match on the primary concern:

- Pure package going to a registry → `library`
- Backend with a database that you deploy → `service`
- Anything that calls an LLM API at runtime → `llm-app`
- Runs in a browser or mobile shell → `frontend`
- Scheduled ETL, batch, or training job → `data-pipeline`

If your project straddles two archetypes (e.g., a service that also calls an LLM),
start from the closer preset and flip the additional capability toggles in
`.claude/kit.yaml` after bootstrap. Use `custom` as the `preset` label when you do.

## Overriding a preset

Every preset key is a plain YAML value in `.claude/kit.yaml`. Edit it directly:

```yaml
# Example: add LLM support to a service project
capabilities:
  llm:
    enabled: true
    eval_dir: "fixtures"
    spend_table: "invocation_log"
```

Run `kit-doctor` after any profile edit to verify the wiring is still intact.

## Preset file format

Each `presets/*.yaml` is a valid partial `kit.yaml` — same keys, same types, same
dotted-path conventions that skills use when reading the profile. Fields omitted
from a preset resolve to disabled / empty at bootstrap time. The full schema is
annotated in `.claude/kit.yaml`; the consumption model is explained in
[The Project Profile](PROFILE.md).
