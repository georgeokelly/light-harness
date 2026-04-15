# Light Harness

Lightweight harness for daily AI coding tasks:

- Keep friction low for casual experiments.
- Add hard guardrails where rules are often ignored.
- Make intent, scope, verification, and iteration records explicit.

## What this repo contains

- `docs/light-harness.md`: design and rollout notes
- `content/rules/15-light-harness.md`: intent preflight and stop rules
- `content/rules/16-action-risk-matrix.md`: risk tiers and approval boundaries
- `content/rules/17-verification-levels.md`: V0-V3 verification policy
- `config/hooks/cursor.json`: Cursor hook manifest
- `config/hooks/codex.json`: Codex hook manifest
- `config/hooks/claude.json`: Claude Code hook manifest
- `scripts/light_harness_hook.py`: hook enforcement script
- `scripts/merge_runtime_config.py`: shared JSON merge helper
- `scripts/deploy_cursor_runtime.sh`: deploy rules/hooks into local `.cursor/` adapter
- `scripts/deploy_codex_runtime.sh`: deploy hooks/config into local `.codex/` adapter
- `scripts/deploy_claude_runtime.sh`: deploy hooks into local `.claude/` adapter
- `scripts/set_pretooluse_mode.sh`: switch pre-tool-use enforcement between `normal` and `sandbox`
- `scripts/init_local_state.sh`: initialize local state files from templates
- `templates/light-harness-preflight.md`: preflight template
- `templates/light-harness-record.md`: local record template

## Core idea

Rules define behavior expectations.
Hooks provide hard backstops for high-value constraints.

This project intentionally treats some constraints as hook-enforced:

- Missing preflight before implementation-heavy prompts
- High-risk shell commands without explicit approval
- Scope expansion outside declared planned scope
- Missing verification/record hints at task stop
- Missing reasoning chain when code files were changed

## Quick start

1. Initialize local state:

   - `bash scripts/init_local_state.sh`

2. Fill preflight fields before execution.

3. If you need high-risk actions, add an approval marker:

   - create `.agent-memory/records/current/approvals.md`
   - add one line: `R2:approved` or `R3:approved`

4. Deploy one local runtime adapter:

   - Cursor: `bash scripts/deploy_cursor_runtime.sh`
   - Codex: `bash scripts/deploy_codex_runtime.sh`
   - Claude Code (local-only): `bash scripts/deploy_claude_runtime.sh`
   - Claude Code (project-level): `bash scripts/deploy_claude_runtime.sh --scope project`

5. Hooks are injected into runtime config files:

   - Cursor rules: `.cursor/rules/*.mdc`
   - Codex hooks: `.codex/hooks.json`
   - Claude hooks: `.claude/settings.local.json` or `.claude/settings.json`

6. Optional: switch pre-tool-use mode:

   - current mode: `bash scripts/set_pretooluse_mode.sh show`
   - strict blocking: `bash scripts/set_pretooluse_mode.sh normal`
   - warning-only shell gate: `bash scripts/set_pretooluse_mode.sh sandbox`

## Notes

- Local records are intentionally `local-only` and excluded from git.
- Local runtime adapters under `.cursor/`, `.codex/`, and `.claude/` are also excluded from git.
- Deploy scripts are merge-aware and preserve unrelated user config where possible.
- The hook script is conservative by default and can block in strict events.
- `sandbox` mode only relaxes the pre-tool-use shell/Bash gate from block to warn.
- `rm` is forbidden in all modes and must go through `pending-rm.md`.
