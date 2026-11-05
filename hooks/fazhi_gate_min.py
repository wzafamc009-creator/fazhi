#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fazhi minimal gate - a self-contained PreToolUse hook.

No dependencies. No network. No DLP. It only judges *actions*.

Contract (Claude Code / Cursor):
  allow -> exit 0
  ask   -> exit 0 + JSON {"hookSpecificOutput":{"permissionDecision":"ask",...}}
  deny  -> exit 2 + reason on stderr

Ledger: <cwd>/.fazhi/ledger.jsonl, one line per decision, chained by prev hash.
"""
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

PROTECTED_NAMES = (".git", ".fazhi", ".claude", ".cursor")
READONLY_HEADS = ("ls", "pwd", "cat", "type", "head", "tail", "which", "echo")
READONLY_GIT = ("status", "log", "diff", "show", "rev-parse", "remote", "branch")
DANGEROUS_META = (";", "&&", "||", "|", ">", "<", "$(", "`", "\n", "\r")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def inside(p, root):
    try:
        Path(p).resolve().relative_to(root)
        return True
    except Exception:
        return False


def is_protected(p, root):
    try:
        rel = Path(p).resolve().relative_to(root)
    except Exception:
        return False
    first = rel.parts[0].lower() if rel.parts else ""
    return first in PROTECTED_NAMES


def is_readonly_cmd(cmd, cwd, root):
    low = cmd.strip().lower()
    if any(m in cmd for m in DANGEROUS_META):
        return False
    parts = low.split()
    if not parts:
        return False
    head = parts[0]
    if head == "git":
        return len(parts) > 1 and parts[1] in READONLY_GIT
    if head not in READONLY_HEADS:
        return False
    for tok in parts[1:]:
        if tok.startswith("-"):
            continue
        p = tok.strip("\"'")
        if re.match(r"^[a-z]:", p) or p.startswith("/") or ".." in p:
            if not Path(p).is_absolute():
                p = str((Path(cwd) / p).resolve())
            if not inside(p, root):
                return False
    return True


def ledger(root, rec):
    """append-only, chained."""
    d = root / ".fazhi"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "ledger.jsonl"
    prev = ""
    if f.is_file():
        try:
            lines = f.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                prev = json.loads(lines[-1]).get("h", "")
        except Exception:
            prev = ""
    body = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    rec = dict(rec, prev=prev, h=sha(prev + body), ts=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with open(f, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec["h"]


def map_tool(tool, ti, cwd, root):
    n = str(tool).lower()
    if n in ("read", "glob", "grep", "ls", "notebookread"):
        return "read", str(ti.get("file_path") or ti.get("path") or cwd), True, ""
    if n in ("write", "edit", "multiedit", "notebookedit"):
        return "write", str(ti.get("file_path") or ti.get("notebook_path") or cwd), True, ""
    if n in ("webfetch", "websearch"):
        return "egress", str(ti.get("url") or n), False, ""
    if n in ("bash", "shell"):
        cmd = str(ti.get("command") or ti.get("cmd") or "")
        low = cmd.lower()
        for m in re.findall(r"[a-zA-Z]:\\[^\s\"']+", cmd):
            if not inside(m, root):
                return "read", m, True, "out-of-root"
        if "git push" in low:
            return "push", "origin", False, cmd
        if "git commit" in low:
            return "commit", cwd, False, cmd
        if any(x in low for x in ("pip install", "npm install", "yarn add",
                                  "apt-get", "choco install", "winget install")):
            return "install", cwd, False, cmd
        if any(x in low for x in ("curl ", "wget ", "invoke-webrequest", "iwr ")):
            return "egress", "url", False, cmd
        m = re.search(r"(?:^|[;&|]\s*)(?:rm|del|remove-item|rmdir|rd)\s+"
                      r"(?:-[^\s]+\s+)*([^\s;&|]+)", cmd, re.I)
        if m:
            p = m.group(1).strip("\"'")
            if not re.match(r"^[a-zA-Z]:", p) and not p.startswith("/"):
                p = str((Path(cwd) / p).resolve())
            return "delete", p, False, cmd
        if is_readonly_cmd(cmd, cwd, root):
            return "read", cwd, True, "readonly"
        return "exec", cwd, False, cmd
    return "unknown", cwd, False, "unmapped:" + n


def decide(action, target, root):
    t = str(target)
    is_abs = t.startswith(("/", "\\")) or bool(re.match(r"^[a-zA-Z]:", t))
    if action in ("read", "write"):
        if is_abs:
            if not inside(t, root):
                return "deny", "E_BAD_ROOT", "path outside workspace"
            if is_protected(t, root):
                return "deny", "E_DENY_PROTECTED", "protected path: %s" % t
        return "allow", "E_OK", ""
    if action == "delete":
        if is_abs and not inside(t, root):
            return "deny", "E_BAD_ROOT", "delete outside workspace"
        if is_protected(t, root):
            return "deny", "E_DENY_PROTECTED", "refuse to delete protected path"
        return "ask", "E_ASK_IRREVERSIBLE", "irreversible delete"
    if action == "push":
        return "deny", "E_DENY_PUSH", "push is outbound publish: denied"
    if action == "commit":
        return "ask", "E_ASK_COMMIT", "commit needs human approval"
    if action == "install":
        return "ask", "E_ASK_INSTALL", "package install needs human approval"
    if action == "egress":
        return "ask", "E_ASK_EGRESS", "outbound request needs human approval"
    if action == "exec":
        return "ask", "E_ASK_EXEC", "arbitrary command needs human approval"
    return "allow", "E_OK", "unmapped tool: allowed, still logged"


def main():
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        ev = json.loads(raw) if raw.strip() else {}
    except Exception:
        ev = {}
    tool = str(ev.get("tool_name") or "")
    ti = ev.get("tool_input") or {}
    cwd = Path(str(ev.get("cwd") or os.getcwd())).resolve()

    root = cwd
    for p in [cwd] + list(cwd.parents):
        if (p / ".fazhi").is_dir() or (p / ".git").is_dir():
            root = p
            break

    action, target, rev, note = map_tool(tool, ti, str(cwd), root)
    decision, code, msg = decide(action, target, root)

    try:
        h = ledger(root, {"tool": tool, "action": action,
                          "target": str(target)[:300], "decision": decision,
                          "code": code, "session": str(ev.get("session_id") or "")})
    except Exception:
        h = "-"

    if decision == "deny":
        sys.stderr.write("[fazhi] DENY %s: %s | H=%s\n" % (code, msg, h))
        return 2
    if decision == "ask":
        out = {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "[fazhi] %s: %s" % (code, msg)}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
