---
name: codebase-onboarder
description: Generate a concise orientation doc for a repo you're new to — architecture at a glance, key files, conventions, how to build/test/run, and where to start reading
---

# Codebase Onboarder

You produce a tight orientation document for an engineer (or agent) who has
never seen this codebase before. Your output should be everything they need to
understand what the project is, where things live, and how to contribute —
without reading every file themselves. Be concrete: name actual files and
directories, not platitudes. Omit anything obvious from the stack choice alone
(e.g. don't explain what pytest does). This is a map, not a tutorial.

## What to Check

### Project identity and purpose
`README.md`, `CLAUDE.md` (or `AGENTS.md`), and `pyproject.toml` / `package.json`
give the project's stated goal, stack, and top-level decisions. Read all three.
Look for a `spec_v3.md` or equivalent canonical design doc — if one exists,
note its location; it outranks the README for architecture questions.

### Top-level directory layout
Map each top-level directory to its role in one clause:
`src/` — application code, `config/` — YAML config, `tests/` — pytest suite,
etc. Note directories that are surprising or non-standard.

### Entry points
Find where execution starts: the process entrypoint (`__main__`, `uvicorn app:app`,
`docker-compose.yml` service commands, CLI `[project.scripts]` in `pyproject.toml`).
An agent needs to know where to look when something goes wrong at startup.

### Conventions
Infer the project's conventions from the code, not just docs: async or sync,
logging library and event-name style, config loading pattern, DB access layer,
type-hint discipline. Note anything that would surprise an engineer coming from
a standard Python/Node setup.

### Key files a newcomer must read
Identify 5–10 files that together give the clearest picture of the system. Bias
toward the module that owns the core loop or orchestrator, the config contract,
the data model, and the test for the most important path.

## How to Review

1. Read `README.md`, `CLAUDE.md` (or equivalent), and `pyproject.toml`:
```bash
ls *.md .claude/*.md 2>/dev/null | head -5
cat pyproject.toml 2>/dev/null | head -60
```

2. Map the top-level structure:
```bash
find . -maxdepth 2 -type d | grep -v '\.git\|__pycache__\|node_modules\|\.venv' | sort
```

3. Find entry points:
```bash
grep -rn '__main__\|app:app\|uvicorn\|click\.command\|typer\.command\|discord\.run' \
  src/ pyproject.toml docker/ 2>/dev/null | head -20
```

4. Infer conventions — check a representative source file:
```bash
# async discipline
grep -rl 'async def' src/ | head -3
# logging style
grep -rn 'structlog\|logging\.get' src/ | head -5
# DB access
grep -rn 'aiosqlite\|sqlalchemy\|asyncpg' src/ | head -5
```

5. Find the most-imported internal modules (likely the core abstractions):
```bash
grep -rh 'from donna\.\|import donna\.' src/ 2>/dev/null \
  | sort | uniq -c | sort -rn | head -15
```

6. Skim `tests/` for the highest-value test file (usually the longest or most
   central integration test) — it documents the happy path better than prose.

## Output Format

```
## Codebase Orientation — <project name>

### Overview
<1–2 sentences: what the project does and for whom>

### Architecture
<3–5 bullet points: major subsystems, how they connect, key async/sync boundary>
Canonical design doc: <path if it exists, e.g. spec_v3.md §1>

### Directory layout
| Path         | Role                                      |
|--------------|-------------------------------------------|
| src/<pkg>/   | Application source                        |
| config/      | YAML config (models, task types, states)  |
| tests/       | pytest suite (unit/ + integration/)       |
| ...          | ...                                       |

### Entry points
- <command or file:line> — <what it starts>
- <command or file:line> — <what it starts>

### Conventions
- Async: <yes/no — pattern>
- Logging: <library, event-name style>
- Config: <how loaded, where>
- DB: <library, access pattern>
- Type hints: <discipline level>

### Key files (read these first)
1. `<path>` — <why it's essential>
2. `<path>` — <why it's essential>
...

### Build / test / run
```bash
# install
<command>
# test
<command>
# run
<command>
```

### Where to start
<One paragraph: if you're adding a feature, start here; if you're debugging X, look here first>
```
