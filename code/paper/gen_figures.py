#!/usr/bin/env python3
"""gen_figures.py (topic 40): regenerate the TEST figures from the result JSONs, copy the PDFs used by the paper
into submission_package/IoTJ/latex/figures, and record SHA-256 of source and copy (checklist C8b provenance)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIGS = ROOT / "results" / "figs"
DST = ROOT / "submission_package" / "IoTJ" / "latex" / "figures"
USED = ["F2_miss_vs_floor_test.pdf", "F3_frontier_spread_vs_hf_test.pdf", "F6p_throttle_kansal_amax_test.pdf",
        "F7_kansal_obs_vs_pred_test.pdf", "F1_frontier_K_Cstar_test.pdf", "F4_gate_map_test.pdf",
        "F6_throttle_vs_blackout_test.pdf"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    code = ROOT / "code"
    for mod in ("sim40.make_figs", "sim40.make_figs_q2"):
        args = [sys.executable, "-m", mod] + (["--split", "test"] if mod.endswith("make_figs") else [])
        subprocess.run(args, cwd=code, check=True)
    DST.mkdir(parents=True, exist_ok=True)
    prov = {}
    for n in USED:
        s = FIGS / n
        shutil.copy2(s, DST / n)
        prov[n] = {"results_sha256": sha(s), "latex_sha256": sha(DST / n)}
        assert prov[n]["results_sha256"] == prov[n]["latex_sha256"]
    (ROOT / "results" / "figure_provenance.json").write_text(json.dumps(prov, indent=1))
    print(f"{len(prov)} figures copied, hashes equal")


if __name__ == "__main__":
    main()
