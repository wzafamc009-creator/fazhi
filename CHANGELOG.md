# Changelog

All notable changes to the **plugin / hook layer**.
(The full agent runtime under `法/治理库/agentos` is a separate codebase and is not
distributed in this repository.)

## 0.1.1 — 2026-11-05

### Fixed
- **Fail-open → fail-closed.** Unknown tool names were silently **allowed**
  (`note: unmapped`). They are now **denied** with `E_UNKNOWN_TOOL`.
  This mattered: Cursor sends `tool_name: "Shell"`, while the hook only matched `bash`,
  so every terminal command passed through with no error at all.
  Escape hatch: `.fazhi/allow_tools.txt`.

### Added
- `verify_ledger.py` — standalone ledger verifier (pure stdlib, no imports from fazhi).
- `README`: "How is this different?" comparison table; ledger self-verification section.

## 0.1.0 — 2026-11-05

### Added
- First release: `hooks/fazhi_gate_min.py` (PreToolUse gate), `hooks/hooks.json`,
  plugin manifest, MIT license for the access layer.
- Denies: `push`, out-of-workspace paths, edits to the guard itself, ledger overwrite.
- Asks: `delete`, `commit`, `install`, `egress`, arbitrary `exec`.
- Hash-chained ledger at `.fazhi/ledger.jsonl`.

---

## Planned (not released yet — listed so nobody is misled)

- `0.1.2` — examples config, `.github/` recipe as a ready-to-copy file,
  better error text when `python` is not on PATH.
- Cursor: make `ask` authoritative (requires host support; currently only `deny` is).
- Installer: support repositories with no `.py` at the top level.

Anything above is a **plan**, not a promise. If it ships, it moves into a version section.
