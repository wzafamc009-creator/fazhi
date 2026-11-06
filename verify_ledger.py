#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_ledger.py — verify a fazhi ledger without trusting fazhi.

Pure stdlib. No imports from fazhi. No network.

Usage:
    python verify_ledger.py .fazhi/ledger.jsonl
    python verify_ledger.py .fazhi/ledger.jsonl --verbose

Exit codes: 0 = intact, 1 = broken chain, 2 = bad input

How the chain works
-------------------
Each line is a JSON object. Two extra fields carry the chain:

    prev : hash of the previous entry ("" for the first)
    h    : sha256(prev + body), where body = json.dumps(entry_without_prev_h_ts,
                                                       ensure_ascii=False,
                                                       sort_keys=True)

So anyone with plain hashlib can recompute every line. If one byte changed,
the chain breaks at that line and every line after it.
"""
import hashlib
import json
import sys


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def verify(path, verbose=False):
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
    except FileNotFoundError:
        print("ERROR: file not found: %s" % path)
        return 2
    except Exception as e:
        print("ERROR: cannot read %s: %s" % (path, e))
        return 2

    if not lines:
        print("0/0 entries, empty ledger (nothing to verify)")
        return 0

    prev_expected = ""
    ok = 0
    first_bad = None

    for i, line in enumerate(lines, 1):
        try:
            rec = json.loads(line)
        except Exception as e:
            print("BROKEN at line %d: not valid JSON (%s)" % (i, e))
            return 1

        claimed_h = rec.pop("h", None)
        claimed_prev = rec.pop("prev", None)
        rec.pop("ts", None)  # ts is added after the hash is computed

        if claimed_h is None or claimed_prev is None:
            print("BROKEN at line %d: missing 'prev' or 'h' field" % i)
            return 1

        if claimed_prev != prev_expected:
            if first_bad is None:
                first_bad = i
            print("BROKEN at line %d: prev does not match previous hash" % i)

        body = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        calc = sha256_text(prev_expected + body)

        if calc != claimed_h:
            if first_bad is None:
                first_bad = i
            print("BROKEN at line %d: hash mismatch" % i)
            if verbose:
                print("  claimed: %s" % claimed_h)
                print("  actual : %s" % calc)
        else:
            ok += 1

        prev_expected = claimed_h

    total = len(lines)
    if first_bad is None:
        print("%d/%d entries OK, chain intact" % (ok, total))
        return 0

    print("%d/%d entries OK; first break at line %d" % (ok, total, first_bad))
    return 1


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    verbose = "--verbose" in argv or "-v" in argv
    return verify(path, verbose)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
