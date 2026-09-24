# Evidence: instruction fired, enforcement blocked

Companion to `docs/agent-control.md`. All tests below ran with a genuinely fresh context (a subagent with no memory of prior conversation, or a live tool call in this session).

## Instruction: `keep-app-working`

### 1. Should fire — naturally worded UI task

Prompt: *"Quero adicionar um botão na janela principal que exporte o histórico de leituras dos canais para um CSV."* (never mentions the skill name or its trigger paths)

Result: the fresh session read `CLAUDE.md`, `docs/agents/issue-tracker.md`, `CONTEXT.md`, then invoked the skill unprompted:

> Invoquei o skill que casa diretamente com a tarefa: `keep-app-working`. Conteúdo: ... Nenhuma edição de arquivo foi feita — apenas leitura de CLAUDE.md, docs/agents/issue-tracker.md, CONTEXT.md, e invocação da skill keep-app-working via ferramenta Skill.

### 2. Should not fire — docs-only task

Prompt: *"Atualiza o README explicando como instalar as dependências do projeto com pip, o Python está desatualizado na versão atual do documento."*

Result:

> Skills considered but not invoked: ... **keep-app-working** — declined: only applies to edits under datalogger_client/ui/, io_layer/, or main.py; README is docs-only, no app behavior changes.

### 3. Edge case — read-only question about UI code

Prompt: *"Me explica como o main_window.py decide quando mostrar o estado 'Stale' da conexão."*

Result:

> Skill invocado? Nenhum. É pergunta de leitura/explicação sobre lógica já existente, não um review, refactor, edição de UI (o que acionaria `keep-app-working`)...

No sharpening was needed: the pointer fired correctly on the first try in all three cases, so there is only one version of the description, not two.

## Prune (step 3b)

Original draft had three extra lines, cut and retested:

1. *"Do not add `pytest-qt` or another Qt-testing dependency — tests use a hand-driven `QApplication`."* — Hypothesis: not a no-op, models default to `pytest-qt` for Qt testing. Tested by asking a fresh session to plan a test for a new Qt button with the line already removed. It read `tests/conftest.py`, found the existing `QApplication` fixture and the `QT_QPA_PLATFORM=offscreen` default, and concluded on its own: *"Não pretendo adicionar pytest-qt nem qualquer nova dependência — o padrão já estabelecido no projeto ... é suficiente."* **No-op confirmed** — stays deleted.
2. *"Check `tests/` for a file already covering the feature you touched. If none exists, add one instead of checking it by hand."* — cut at the same time; the retest above still independently checked `tests/` before proposing a test. **No-op confirmed** — stays deleted.
3. The explicit `QT_QPA_PLATFORM=offscreen python -m pytest ...` command duplicated a command already spelled out in `.claude/skills/implement-ticket/SKILL.md` step 4, and the env var it added is redundant: `tests/conftest.py` already does `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`. Replaced with a pointer ("same command as `implement-ticket` step 4") instead of a second copy. **Duplicate, not a no-op** — collapsed to one authoritative copy.

No rule about the removed compatibility adapter (ticket #12, already closed) was ever written into the skill — all migration tickets (#6–#19) are closed, so that subject no longer exists in the codebase and was deliberately left out rather than generalized into "broader advice."

## Enforcement: `block-dangerous-git.sh`

The bundled script from `git-guardrails-claude-code` shells out to `jq`, which is not installed on this machine (`which jq` → not found). Rewrote the JSON extraction to use `node` (already present) instead of adding a new dependency, then verified directly:

```
$ echo '{"tool_input":{"command":"git push origin main"}}' | bash .claude/hooks/block-dangerous-git.sh
BLOCKED: 'git push origin main' matches dangerous pattern 'git push'. The user has prevented you from doing this.
exit code: 2

$ echo '{"tool_input":{"command":"git status"}}' | bash .claude/hooks/block-dangerous-git.sh
exit code: 0
```

Then, live in this session, with the hook wired into `.claude/settings.json`:

```
$ git push --dry-run origin feature/ui-decoupling
PreToolUse:Bash hook error: ["$CLAUDE_PROJECT_DIR"/.claude/hooks/block-dangerous-git.sh]: BLOCKED: 'git push --dry-run origin feature/ui-decoupling' matches dangerous pattern 'git push'. The user has prevented you from doing this.

$ git status --short
?? .claude/
```

The push was blocked before the shell ever ran it (no dry-run output, no network call); the read-only command right after passed through untouched.

### A real misfire, found while committing this work

The first version of the script matched `git push` anywhere in the raw command string. Writing the commit message for this very change (which quotes the phrase "a hook blocks git push" as prose) tripped it — the hook blocked the `git commit` call itself:

```
PreToolUse:Bash hook error: [...block-dangerous-git.sh]: BLOCKED: 'git commit -m "..."'
matches dangerous pattern 'git push'. The user has prevented you from doing this.
```

Fixed by anchoring each pattern to a command boundary (start of line, or right after `;`, `&`, or `|`) instead of matching anywhere in the string, and checking line-by-line so a real invocation on its own line is still caught even without a preceding separator. Retested after the fix:

```
=== should PASS (prose mentions the phrase, not invoked) ===
exit: 0
=== should BLOCK (real push, no separator) ===
BLOCKED: 'git push origin main' matches dangerous pattern '(^|[;&|])[[:space:]]*git push'.
exit: 2
=== should BLOCK (chained after &&) ===
BLOCKED: 'cd repo && git push origin main' matches dangerous pattern '(^|[;&|])[[:space:]]*git push'.
exit: 2
=== should PASS (git log --grep mentioning the phrase) ===
exit: 0
```

### A second gap: the hook only covered one of two shells

This environment exposes both a `Bash` tool and a separate `PowerShell` tool. The hook's `matcher` in `.claude/settings.json` originally listed only `"Bash"`, so the same `git push` run through the `PowerShell` tool would never trigger the hook at all — a silent bypass, not a misfire. Added a second `PreToolUse` entry with `"matcher": "PowerShell"` pointing at the same script, then verified live, through the actual `PowerShell` tool rather than a simulated payload:

```
PS> git push --dry-run origin feature/ui-decoupling
PreToolUse:PowerShell hook error: [...block-dangerous-git.sh]: BLOCKED: 'git push --dry-run origin feature/ui-decoupling'
matches dangerous pattern '(^|[;&|])[[:space:]]*git push'. The user has prevented you from doing this.

PS> git status --short
 M .claude/settings.json
```

Blocked through PowerShell exactly as it was through Bash; the read-only command still passes.
