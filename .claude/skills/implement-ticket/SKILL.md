---
name: implement-ticket
description: Protocol for implementing one numbered GitHub issue (ticket) from this repo's backlog. Use when asked to build, fix or take on issue #N, or "the next ticket".
---

# Implement one ticket

1. **Read the ticket**: `gh issue view <N> --comments`. It is self-contained; the ticket and its comments are the spec.
2. **Check the preconditions.** If one fails, stop and tell the user which:
   - The current branch is not `main`.
   - Every ticket in its "Blocked by" list has a commit: `git log --grep "Refs #<B>"` is non-empty. Issue state is no signal: finished tickets stay open.
   - The ticket carries everything you need. If not, list exactly what is missing instead of guessing.
3. **Implement only this ticket**, in the vocabulary of `CONTEXT.md` and the ADRs in `docs/adr/`. Write the tests for its behaviour with it.
4. **Run the full suite once at the end**: `python -m pytest -q -W ignore::DeprecationWarning` (`pytest.ini` does not filter the warnings).
5. **Commit** with `Refs #<N>` in the message. Pushing is the user's job; a hook blocks `git push`.
6. **Comment on the issue** (`gh issue comment <N>`): what changed, tests run, deviations from the ticket, what the ticket was missing.

## Done when

- `git log --grep "Refs #<N>"` shows your commit.
- The full suite passed, and you can quote its last line.
- Issue #N has your comment with all four parts.
- Every changed file traces to an item in the ticket's scope; other tickets' scope is untouched.
