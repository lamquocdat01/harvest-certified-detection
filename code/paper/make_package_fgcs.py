#!/usr/bin/env python3
"""make_package_fgcs.py (topic 40): submission_package/FGCS/04_Package_FGCS/ for Editorial Manager.

Contents: main.pdf (reference build), highlights.txt, cover_letter.pdf, supp.pdf, Figure_<n>.pdf (one file per figure,
numbered in order of first appearance), author_photo.jpg, source_flat/ (flat LaTeX: main.tex with Figure_<n>.pdf paths,
numbers.tex, generated tables, related_work.tex, refs.bib, main.bbl, figures, photo, elsarticle.cls/.bst), source.zip,
SHA256SUMS.txt. The flat source is rebuilt in an empty temporary folder and must give the same page count.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "FGCS" / "latex"
PKG = ROOT / "submission_package" / "FGCS" / "04_Package_FGCS"
FLAT_TEX = ["main.tex", "numbers.tex", "prereg_table.tex", "sizing_table.tex", "related_work.tex", "refs.bib",
            "main.bbl"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def kpse(name):
    return pathlib.Path(subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip())


def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))


def main():
    flat = PKG / "source_flat"
    if PKG.exists():                    # clear files only: the synced folder (Google Drive) may hold a lock on dirs
        for p in sorted(PKG.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
    flat.mkdir(parents=True, exist_ok=True)
    main_src = (LATEX / "main.tex").read_text(encoding="utf-8")
    nums = (LATEX / "numbers.tex").read_text(encoding="utf-8")
    order = []
    for m in re.finditer(r"\\input\{([\w.]+)\}|figures/([\w\-]+\.pdf)", main_src):
        if m.group(1) == "numbers.tex":
            continue
        if m.group(2) and m.group(2) not in order:
            order.append(m.group(2))
    # figures inside the \Esection macro appear where \Esection is used
    esec = re.findall(r"figures/([\w\-]+\.pdf)", nums)
    pos_e = main_src.find(r"\Esection")
    before = [f for f in order if main_src.find("figures/" + f) < pos_e]
    after = [f for f in order if main_src.find("figures/" + f) > pos_e]
    order = before + [f for f in esec if f not in before] + after
    fmap = {f: f"Figure_{i + 1}.pdf" for i, f in enumerate(order)}
    for f, new in fmap.items():
        shutil.copy2(LATEX / "figures" / f, flat / new)
        shutil.copy2(LATEX / "figures" / f, PKG / new)
    for n in FLAT_TEX:
        t = (LATEX / n).read_text(encoding="utf-8")
        for f, new in fmap.items():
            t = t.replace("figures/" + f, new)
        (flat / n).write_text(t, encoding="utf-8")
    for n in ("author_photo.jpg",):
        shutil.copy2(LATEX / n, flat / n)
        shutil.copy2(LATEX / n, PKG / n)
    for n in ("elsarticle.cls", "elsarticle-num.bst"):
        shutil.copy2(kpse(n), flat / n)
    (flat / "FIGURE_MAP.txt").write_text("\n".join(f"{v}  <-  results/figs/{k}" for k, v in fmap.items()) + "\n",
                                         encoding="utf-8")
    for n in ("main.pdf", "supp.pdf", "cover_letter.pdf", "highlights.txt"):
        shutil.copy2(LATEX / n, PKG / n)
    with zipfile.ZipFile(PKG / "source.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(flat.iterdir()):
            z.write(p, p.name)
    # rebuild the flat source in an empty folder (no bibtex: main.bbl is shipped)
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(PKG / "source.zip") as z:
            z.extractall(td)
        for _ in range(3):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "main.tex"], cwd=td, capture_output=True)
        npg, nref = pages(pathlib.Path(td) / "main.pdf"), pages(LATEX / "main.pdf")
        log = (pathlib.Path(td) / "main.log").read_text(encoding="utf-8", errors="replace")
        undef = len(re.findall(r"undefined", log))
    rep = {"figure_map": fmap, "flat_build_pages": npg, "reference_pages": nref, "flat_build_undefined": undef}
    files = sorted(p.name for p in PKG.iterdir() if p.is_file())
    lines = [f"{sha(PKG / n)}  {n}" for n in files]
    (PKG / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "results" / "package_fgcs.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))
    print("\n".join(lines))
    if npg != nref or undef:
        print("FLAT BUILD MISMATCH")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
