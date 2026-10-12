#!/usr/bin/env python3
"""make_package.py (topic 40): submission_package/IoTJ/04_Package/ = main.pdf, supp.pdf, cover_letter.pdf,
source.zip (main.tex, numbers.tex, sizing_table.tex, prereg_table.tex, refs.bib, main.bbl, figures used by main.tex) and SHA256SUMS.txt.
The source zip contains only what the manuscript needs (no data, no supplement sources)."""
from __future__ import annotations

import hashlib
import pathlib
import re
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "IoTJ" / "latex"
PKG = ROOT / "submission_package" / "IoTJ" / "04_Package"


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    for n in ("main.pdf", "supp.pdf", "cover_letter.pdf"):
        shutil.copy2(LATEX / n, PKG / n)
    src = (LATEX / "main.tex").read_text(encoding="utf-8") + (LATEX / "numbers.tex").read_text(encoding="utf-8")
    figs = sorted(set(re.findall(r"figures/[\w\-]+\.pdf", src)))
    with zipfile.ZipFile(PKG / "source.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for n in ["main.tex", "numbers.tex", "sizing_table.tex", "prereg_table.tex", "refs.bib", "main.bbl"] + figs:
            z.write(LATEX / n, n)
    lines = [f"{hashlib.sha256((PKG / n).read_bytes()).hexdigest()}  {n}"
             for n in ("main.pdf", "supp.pdf", "cover_letter.pdf", "source.zip")]
    (PKG / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
