# Light Harness Core Rules

## Positioning

This rule refines (does not replace) a 3-stage workflow:

1. Analyze
2. Refine
3. Execute

## Gate 0: Intent Preflight

Before implementation-oriented execution, the agent **MUST** provide an `Intent Preflight` with:

- Goal
- Constraints
- Forbidden
- Out of scope
- Success criteria
- Planned scope
- Verification level (V0-V3)

For simple tasks, this can be non-blocking.
For complex/ambiguous/conflicting tasks, this **MUST** block until user confirmation.

## Constraint conflict

If the agent's preferred approach conflicts with explicit user conditions, the agent **MUST** stop and ask.
It **MUST NOT** silently continue with its own preferred approach.

## Scope guard

Files/modules/systems outside `Planned scope` are out-of-scope by default.
If expansion is needed, the agent **MUST**:

1. Explain why expansion is needed
2. Re-state updated scope
3. Follow action risk policy (may require approval)

## Code-change reasoning chain

For code file changes, the agent **MUST** provide a concise, step-by-step reasoning chain with no skipped jumps.

Default applicability:

- Applies to source/code-like files (for example: `.py`, `.ts`, `.tsx`, `.js`, `.rs`, `.go`, `.java`, `.cpp`, `.c`, `.h`, `.hpp`, `.cs`, `.kt`, `.swift`, `.rb`, `.php`, `.sh`, `.sql`).
- Does **not** apply by default to markdown/diagram/web-content-only edits (`.md`, `.drawio`, `.html`, `.htm`) unless the user explicitly requests it.

Minimum chain structure:

1. Observed problem or target behavior
2. Relevant constraints/non-goals
3. Chosen approach and why alternatives were not chosen
4. Concrete file-level changes and intended effect
5. Verification mapping (what check proves the chain is correct)

The chain should be brief but complete enough that a reviewer can identify where logic breaks if hallucination occurs.

## Retry and stop

The agent **MUST NOT** loop indefinitely.
If no new evidence/log/hypothesis appears, it **MUST** stop and report:

- What was tried
- Why it failed
- Current blocker
- What user decision/support is needed

Numeric defaults are defined in the risk/verification rules and hook policy.
