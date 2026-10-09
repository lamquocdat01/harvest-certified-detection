#!/usr/bin/env python3
"""compare_results.py: key-by-key comparison of two results folders (reproduction check, checklist C7).
Usage: python code/compare_results.py <reference results dir> <reproduced results dir> [--rtol 1e-9]
Compares every JSON present in the reference list below; floats with relative tolerance rtol, everything else
exactly. Prints the first differences and a summary; exit 1 if any file differs."""
from __future__ import annotations

import json
import math
import pathlib
import sys

FILES = ["numbers.json", "prereg_score_test.json", "boot_test.json", "F5_sizing_test.json", "F5_sizing_all.json",
         "exploratory_q2_test.json", "exploratory_q2_boot_test.json", "sizing_block_sens_all.json",
         "sizing_block_sens_test.json", "corpus_rebuild_check.json", "summary_test.json"]


def walk(a, b, path, out, rtol):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: missing in {'reproduced' if k not in b else 'reference'}")
            else:
                walk(a[k], b[k], f"{path}/{k}", out, rtol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out, rtol)
    elif isinstance(a, float) or isinstance(b, float):
        if a is None or b is None or not (a == b or (math.isnan(a) and math.isnan(b))
                                          or math.isclose(a, b, rel_tol=rtol, abs_tol=1e-12)):
            out.append(f"{path}: {a} vs {b}")
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}")


def main():
    ref, rep = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    rtol = float(sys.argv[sys.argv.index("--rtol") + 1]) if "--rtol" in sys.argv else 1e-9
    bad = 0
    report = {}
    for f in FILES:
        if not (ref / f).exists():
            report[f] = "not in reference"
            continue
        if not (rep / f).exists():
            report[f] = "MISSING in reproduction"
            bad += 1
            continue
        diffs = []
        a, b = json.loads((ref / f).read_text()), json.loads((rep / f).read_text())
        if f == "corpus_rebuild_check.json":      # absolute paths differ between machines/clones
            for d in (a, b):
                d.pop("detections_root", None)
                d.get("reference", {}).pop("path", None)
        walk(a, b, f, diffs, rtol)
        report[f] = "identical" if not diffs else f"{len(diffs)} differences, e.g. {diffs[:3]}"
        bad += bool(diffs)
    for k, v in report.items():
        print(f"{k:34} {v}")
    print("ALL IDENTICAL" if not bad else f"{bad} file(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
