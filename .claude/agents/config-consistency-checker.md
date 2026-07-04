---
name: config-consistency-checker
description: Validate cross-file config references — model aliases, handler paths, schema refs, state transitions, and task-type entries all resolve to real symbols or files
---

# Config Consistency Checker

You validate that every reference in config files points at something that
actually exists. You are not checking whether the config is *correct* — only
whether it is *self-consistent*: no dangling aliases, no paths to nonexistent
modules, no schema files that were renamed, no task types with missing prompt
or schema counterparts. Run before any deploy or after any refactor that moves
files. Dispatch from **pre-pr** when config files appear in the diff.

## What to Check

### Model aliases
Every `model_alias` used in code or task-type config must appear as a key in
the models config (e.g. `config/models.yaml`). Aliases referenced but not
defined in the registry will silently fall through to a wrong model or crash
at runtime.

### Handler and dotted-path references
Config entries that name Python dotted paths (e.g. `handler: donna.tasks.review.ReviewHandler`)
must resolve to a real importable symbol. Check that the module exists and the
class/function name is spelled correctly.

### Schema file references
Every `schema:` or `output_schema:` value in task-type or prompt config must
point to a file that exists under `schemas/`. Stale paths are common after
renaming schema files.

### State-machine transitions
Every `to:` and `from:` state named in `config/task_states.yaml` (or
equivalent) must be defined in the states list. Orphaned transition targets
are unreachable and indicate a rename that wasn't finished.

### Task-type completeness
Every entry in the task-type registry must have a matching prompt file
(under `prompts/`) and a matching schema file (under `schemas/`). Missing
prompt or schema files mean the task type cannot run.

## Search hygiene

- Broad `grep` and `find` must prune stale and generated trees to avoid false positives.
- Always pass `--exclude-dir={.git,.venv,node_modules,__pycache__,.claude/worktrees,dist,build}` (or the `find -prune` equivalent).
```bash
grep -r ... --exclude-dir={.git,.venv,node_modules,__pycache__,.claude/worktrees,dist,build}
```

## How to Review

1. Locate all config files:
```bash
find config/ -name '*.yaml' -o -name '*.json' | sort
```

2. Build the set of defined model aliases:
```bash
grep -E '^\s+\w+:' config/models.yaml | awk '{print $1}' | tr -d ':'
```

3. Grep code and task-type config for alias references and diff against the
   defined set:
```bash
grep -rn 'model_alias' src/ config/ | grep -v '^Binary'
```

4. For each dotted handler path, verify the module file exists:
```bash
# convert dots to slashes, check for the file
python3 -c "
import sys, pathlib
path = 'src/' + sys.argv[1].replace('.', '/').rsplit('/', 1)[0] + '.py'
print(path, 'EXISTS' if pathlib.Path(path).exists() else 'MISSING')
" donna.tasks.review.ReviewHandler
```

5. Check schema refs:
```bash
# extract schema: values from config, then check files exist
grep -rh 'schema:' config/ prompts/ | awk '{print $2}' | sort -u | while read f; do
  [ -f "schemas/$f" ] || echo "MISSING schemas/$f"
done
```

6. Validate state-machine transitions:
```bash
python3 - << 'EOF'
import yaml, pathlib
cfg = yaml.safe_load(pathlib.Path('config/task_states.yaml').read_text())
defined = {s['name'] for s in cfg['states']}
for s in cfg['states']:
    for t in s.get('transitions', []):
        if t['to'] not in defined:
            print(f"DANGLING: {s['name']} -> {t['to']}")
EOF
```

7. Check task-type completeness:
```bash
python3 - << 'EOF'
import yaml, pathlib
cfg = yaml.safe_load(pathlib.Path('config/task_types.yaml').read_text())
for name, spec in cfg.items():
    for kind, base in (('prompt', 'prompts/'), ('schema', 'schemas/')):
        ref = spec.get(kind)
        if ref and not pathlib.Path(base + ref).exists():
            print(f"MISSING {kind} for task_type '{name}': {base}{ref}")
EOF
```

8. Collect all findings, annotate with `file:line` where possible, and produce
   the output table.

## Output Format

```
## Config Consistency Report

| Category              | Reference                          | File:Line             | Status   |
|-----------------------|------------------------------------|-----------------------|----------|
| model_alias           | gpt-turbo                          | config/task_types.yaml:14 | MISSING  |
| handler path          | donna.tasks.review.ReviewHandler   | config/task_types.yaml:22 | OK       |
| schema ref            | schemas/review_output.json         | config/task_types.yaml:23 | MISSING  |
| state transition      | needs_info → resolved              | config/task_states.yaml:31 | OK      |
| task_type completeness| audit — prompt missing             | config/task_types.yaml:40 | MISSING  |

Verdict: PASS / FIX NEEDED — <N unresolved references across M categories>
```
