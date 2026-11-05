# fazhi — a brake pedal for your AI

> **Your AI can still work. It just can't do the things it shouldn't — and every decision leaves a receipt.**

## The problem (4 real situations)

| # | What happens | What it costs you |
|---|---|---|
| 1 | You say "clean up the project" — it deletes a whole directory | days of work |
| 2 | You ask for a one-line fix — it quietly deletes your tests | you find out 3 days later |
| 3 | You say "commit this" — it runs `git push` and your keys go public | unrecoverable |
| 4 | Something breaks — you ask "what did you actually do?" | it says "I don't recall", and there is no log |

## What this does

Three things, nothing more:

1. **Gate before it acts** — irreversible actions stop and ask a human.
2. **Deny means deny** — `push`, out-of-workspace paths, edits to the guard itself: **physically refused**, not "advised against".
3. **Every decision leaves a receipt** — an append-only, hash-chained ledger (`.fazhi/ledger.jsonl`); change one line and the chain breaks.

## Install

### As a Claude Code plugin
```
/plugin marketplace add <this-repo>
/plugin install fazhi
```

### Manual (Claude Code or Cursor)
Copy `hooks/fazhi_gate_min.py` somewhere, then point your host at it:

**Claude Code** — `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "python \"<path>/fazhi_gate_min.py\"" }
      ]}
    ]
  }
}
```

**Cursor** — `.cursor/hooks.json` (must be **UTF-8 without BOM**):
```json
{
  "hooks": {
    "preToolUse": [
      { "matcher": "", "hooks": [
        { "type": "command", "command": "python \"<path>/fazhi_gate_min.py\"" }
      ]}
    ]
  }
}
```

Then restart the host (hooks load at startup).

## Verify it actually works

Ask your agent: **`用终端执行 git push`** / **`run git push in the terminal`**

Expected: the agent reports it was **rejected**, with a line like

```
[fazhi] DENY E_DENY_PUSH: push is outbound publish: denied | H=H23
```

And the target repo receives **no commit**. Check:
```
git --git-dir=<your-remote> log     # should say: does not have any commits yet
```

## What it does NOT do (read this part)

- ❌ **No detection-rate promise.** It is a conservative gate, not a detector. Some dangerous actions will look ordinary and pass.
- ❌ **No DLP.** It judges *actions*, not file contents.
- ❌ **No sandbox.** It does not isolate processes.
- ❌ **Not a replacement for code review.** It answers "may this happen?", not "is this correct?".
- ⚠️ **`ask` may not be honoured by every host.** In Cursor, `deny` is enforced (tested); `ask` is currently not — treat `deny` as the hard guarantee.
- ✅ **Fail-closed on unknown tools** (since 0.1.1): if the host sends a tool name we don't
  recognise, the action is **denied**, not allowed. If a legitimate tool gets blocked, add its
  name to `.fazhi/allow_tools.txt` (one per line, `#` for comments, `*` = allow all).

## Changelog

- **0.1.1** — fix a fail-open bug: unknown tool names were silently **allowed**. They are now
  **denied** by default. This matters because hosts do rename tools (Cursor sends `Shell`, not
  `Bash`); a hook matching only `Bash` silently allows every command without any error.
  Escape hatch: `.fazhi/allow_tools.txt`.
- **0.1.0** — first release.

## Ledger

`.fazhi/ledger.jsonl`, one line per decision:

```json
{"action":"push","decision":"deny","code":"E_DENY_PUSH","tool":"Shell","prev":"…","h":"…"}
```

Each line stores `prev` (previous hash) and `h = sha256(prev + body)`. Anyone can recompute it with plain `sha256` — **you don't have to trust us to verify it.**

## License

MIT for this hook / plugin layer. Name and logo are trademarks of Ruojian Digital Technology (Wenzhou) Co., Ltd.
