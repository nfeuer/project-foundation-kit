---
name: writing-kit-skills
description: Author a new kit-compatible skill — frontmatter conventions, sharp trigger descriptions, kit.yaml profile tagging, capability gates, report formats, and how to register the skill so it actually fires. Use this to extend the kit instead of forking it.
cost: free
protects: "A newly written skill actually gets discovered and triggered when it's needed, instead of becoming dead documentation nobody invokes."
requires: nothing
gate_key: none
ci_job: none
---

# Writing Kit Skills

The kit stays coherent because every skill follows the same conventions: it
declares *when* it triggers, reads the project profile instead of hardcoding
commands, gates itself on capabilities, and ends with a verifiable report.
A skill that breaks these conventions either never fires, fires with the wrong
toolchain, or reports success it can't back up. Follow this guide when adding
a skill to the kit or to a project that adopted it.

## 1. Layout and frontmatter

One directory per skill: `.claude/skills/<kebab-name>/SKILL.md`, with YAML
frontmatter:

```yaml
---
name: <kebab-name>            # must match the directory name
description: <one sentence of WHAT it does — then the trigger: WHEN to run it>
---
```

**The description field is the single most important line you will write.**
Skills are surfaced by matching user intent against it. A vague description
means the skill never fires. State the trigger condition explicitly:

- ❌ `description: Helps with database migrations`
- ✅ `description: Catch dangerous DB schema migrations before they hit the
  primary DB or any replica — verify single head, reversibility, and no
  unguarded destructive ops`

Write it as *situation → action*: someone (or the dispatcher in
`using-the-kit`) reading only this line must know exactly when to invoke it.

**Keep it YAML-safe.** The description is an unquoted scalar, so a colon
followed by a space (`…before responding: scan the index`) makes a strict
parser read it as a nested mapping and reject the whole frontmatter block —
the skill then fails to load rather than loading with a bad description.
Rephrase with a period or an em dash, or quote the entire value. The same
applies to a value starting with `[`, `{`, `>`, `|`, `&`, `*`, or `#`.
Verify before committing:

```bash
python3 -c "
import glob, yaml
bad = 0
for f in sorted(glob.glob('.claude/skills/*/SKILL.md')):
    try:
        yaml.safe_load(open(f).read().split('---')[1])
    except Exception as e:
        print('FAIL', f, e); bad += 1
print('frontmatter parses in every skill' if not bad else '%d file(s) failed' % bad)
"
```

Optionally state the skill's **model fit** in the intro paragraph: code-writing/
execution skills suit `models.code` / `models.code_light`; planning, validation,
or review skills suit `models.plan`. Write the role key, not a bare model ID —
the routing table lives in `using-the-kit` and the keys in `.claude/kit.yaml`
(see `docs/PROFILE.md`). One line of prose, not a frontmatter field.

## 2. Read the profile — never hardcode a toolchain

Any command that varies by project reads from `.claude/kit.yaml`. Tag the step
with the dotted key, and show the **default** as the literal:

````markdown
### 3. Tests
```bash
# kit.yaml → toolchain.test
uv run pytest tests/unit/ -m "not slow and not llm" --tb=short -q
```
````

The executing agent runs the profile's value if set; the literal shown is only
the fallback default. An empty string in the profile means **skip the step and
mark it N/A**. Named values (`trunk_branch`, `alerts.channel`,
`capabilities.spec.file`) follow the same convention. See `docs/PROFILE.md`.

## 3. Gate on capabilities

If the skill only makes sense for some project archetypes, gate the whole
skill (or the specific step) on a toggle, stated in this exact form near the
top so it is impossible to miss:

```markdown
**Applies when** `capabilities.<name>.enabled` is true in `.claude/kit.yaml`.
If false, skip and report N/A.
```

Reporting N/A is a feature — it lets `pre-pr` and `using-the-kit` invoke every
skill unconditionally and stay correct on any project. If no existing
capability fits, add a new toggle to `kit.yaml`, the five `presets/*.yaml`,
and `docs/PROFILE.md` in the same change.

## 4. Structure the body

The house style, in order:

1. **Intro paragraph** — why the skill exists: the failure it prevents, in
   terms of cost (money, red CI, silent breakage). Not a feature list.
2. **`## Workflow`** (or `## Checks`) — numbered steps. Each step is
   verifiable: a command with expected output, or a judgment with explicit
   criteria. **State the boundary in the intro — one sentence.** Read-only
   skills say so plainly ("It reads and checks only — it never modifies
   files"; `kit-doctor` is canonical). Skills that write something narrow name
   the write and the non-write. The boundary must be exhaustive-accurate — an
   over-broad "read-only" claim on a skill that also writes a baseline file, a
   sentinel, or a chat alert is worse than no boundary at all.
3. **Decision tables** for outcomes — `| Outcome | Action |` beats prose
   (see `coverage-ratchet` step 3).
4. **`## Output`** — a fenced report template the agent must fill with real
   results. Every conditional item gets an explicit N/A form. End destructive
   or irreversible flows with a confirmation requirement, and honesty rules
   like: "never check a box you didn't verify."

## 5. Register it — an unregistered skill is dead code

A new skill isn't done until it is discoverable and maintained:

- [ ] Add a row to the **trigger index** in `using-the-kit/SKILL.md` — the
  dispatcher only fires skills whose index row matches; no row, no trigger.
- [ ] Add it to the README: the `What's inside` tree **and** the workflow
  catalog under the right purpose group.
- [ ] If `pre-pr` should invoke it, add a checklist step + an output line there.
- [ ] If it adds hooks or settings entries, extend `kit-doctor`'s checks so a
  broken install is caught.
- [ ] If it introduces a new `kit.yaml` key: update `kit.yaml`, all five
  `presets/*.yaml`, and `docs/PROFILE.md`.
- [ ] Bump `kit_version` in the source kit's `kit.yaml` so `kit-update` offers
  the new skill to adopted projects.
- [ ] Run `config-audit` — a skill is agent-facing config; make sure it doesn't
  introduce injection-shaped instructions.

## 6. Style rules

- Address the executing agent in the imperative ("Run", "Read", "Stop and fix").
- Long-running multi-step skills keep a **progress ledger** (see
  `docs/PROGRESS_LEDGER.md`) so an interrupted run resumes instead of restarting.
- Bash snippets must be copy-runnable from the repo root; prefer `python3 -c`
  one-liners over pseudo-code for anything that parses YAML/JSON.
- State blocking vs. advisory explicitly for every check, and how
  `gates.strictness` (see `docs/PROFILE.md`) changes that, if it does.
- Trigger on a stated condition, not on doubt. Write "Run this when
  `<condition>`"; never "if there is even a chance…" or `You MUST` unless the
  rule is genuinely absolute (secrets, destructive ops, a blocking gate).
- Skills that request findings ask for **every** finding with confidence and
  severity, and triage downstream — never instruct the finder to pre-filter.
- Skills that produce a written document carry one length-calibration sentence.
- Do not tell the agent to double-check, re-verify, or spawn a subagent to
  review its own output — that is built in and only burns tokens. Command-backed
  verification steps are workflow; keep those. Fan-out guidance names a cap and
  a criterion: only genuinely independent, sizeable tracks; never to verify
  your own work.
- Keep it as short as the content allows. A skill is loaded into context when
  invoked — every line costs tokens, and Sonnet 5's tokenizer uses ~30% more
  tokens for the same text than Sonnet 4.6, so trimming redundant prose pays
  off more than it used to.

## Output

```
## New Skill: <name>

- SKILL.md: written (<n> lines), description states trigger: yes
- Profile keys read: <list / none>
- Capability gate: <capabilities.X.enabled / none — always applies>
- Boundary stated: <read-only | writes: <what> | none stated>
- Model fit: <code | planning/validation | mechanical | none stated>
- Registered: using-the-kit index ▢  README tree ▢  README catalog ▢
  pre-pr step ▢/N/A  kit-doctor check ▢/N/A  presets+PROFILE.md ▢/N/A
- kit_version bumped: <old> → <new>
```
