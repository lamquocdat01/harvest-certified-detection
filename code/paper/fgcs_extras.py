#!/usr/bin/env python3
"""fgcs_extras.py (topic 40, FGCS build): highlights generated from numbers.tex.

FGCS Guide for Authors: 3-5 bullet points, at most 85 characters each including spaces, in a separate editable
file whose name contains 'highlights'. Every number is read from numbers.tex (no hand typing).
Writes submission_package/FGCS/latex/highlights.txt (+ highlights.tex for the PDF used by the checks).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "FGCS" / "latex"
MAX_CHARS, MIN_N, MAX_N = 85, 3, 5


def macros():
    src = (LATEX / "numbers.tex").read_text(encoding="utf-8")
    return dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}\s*$", src, flags=re.M))


def plain(v):
    v = v.replace("{,}", ",").replace("\\,\\%", "%").replace("\\,", " ")
    return re.sub(r"[{}$\\]", "", v)


def main():
    m = {k: plain(v) for k, v in macros().items()}
    h1 = json.loads((ROOT / "results" / "prereg_score_test.json").read_text())["H1"]
    viol = sum(h1["familywise"].values()) + h1["analytic"]
    hl = [
        "A closed-form miss floor holds for every event-independent duty cycle",
        "The floor is tight for every duration law iff activation gaps differ by at most one",
        "An energy floor and a sizing sandwich give storage for a target miss rate",
        f"Periodic duty cycling needs {m['tsInvLo']}-{m['tsInvHi']}x the storage of the miss-optimal schedule",
        f"Pre-registered traces: {viol} of {m['nFloorChecks']} floor checks violated; artifact open",
    ]
    bad = [(h, len(h)) for h in hl if len(h) > MAX_CHARS]
    if bad or not MIN_N <= len(hl) <= MAX_N:
        sys.exit(f"highlights violate FGCS limits: {bad}")
    (LATEX / "highlights.txt").write_text("\n".join(hl) + "\n", encoding="ascii", newline="\r\n")
    print("\n".join(f"{len(h):3d}  {h}" for h in hl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
