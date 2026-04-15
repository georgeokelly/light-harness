# Verification Levels

## Matrix

| Level | Use when | Required evidence |
| --- | --- | --- |
| V0 | disposable spike with explicit justification | reason why minimal verification is acceptable |
| V1 | code-oriented tasks | lint/build/test/static-check outputs or clear reason if unavailable |
| V2 | app/UI/runtime behavior changes | runtime smoke result, command/output summary, timeout/result status |
| V3 | automation is impossible or unsuitable | what was auto-verified, what remains manual, why manual is necessary |

## Selection policy

- Default is `V1` unless explicitly downgraded/upgraded.
- `V0` requires explicit written justification.
- `V2` is expected for runtime behavior changes.
- `V3` is only allowed when user judgment, credentials, unavailable environment, or tooling limits prevent automation.

## User is fallback verifier

The user is not default QA.
When asking user verification, the agent **MUST** include:

1. What was already verified automatically
2. What remains unverified
3. Why automation is not feasible
4. The smallest manual check required

## Stop-time check

Before task stop for V1+ tasks, record should include:

- Verification performed
- Unverified items
- Next user action (if any)
