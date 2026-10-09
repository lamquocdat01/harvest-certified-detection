#!/usr/bin/env python3
"""verify_render.py (topic 40): gates on the RENDERED PDF and its sources (checklist C2-C8b, A2).

Checks: placeholders / '??' (hard only with --final), references machine-checkable (DOI or URL in every rendered
entry) and first-author family on the page, every literal number in main.tex is in numbers.tex or a declared
model constant, no raw \\commands in the PDF text, tone words, forbidden venue/data names, title <= 15 words,
abstract <= 250 words, first abstract sentence contains the community keyword and does not open with 'theorem',
pages <= 8 (pdfinfo), no overfull box > 5 pt, figure hashes = results hashes.
Writes results/verify_render.json. Exit code 1 on any failure.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "IoTJ" / "latex"
PDF = LATEX / "main.pdf"
MAX_PAGES, MAX_ABS, MAX_TITLE = 8, 250, 15
# model / protocol constants stated in the text by definition (not results)
CONSTANTS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "16", "20", "25", "30", "32", "64", "100", "300",
             "0.01", "0.02", "0.2", "0.03", "0.036", "0.04", "0.05", "0.1", "0.25", "0.248", "0.45", "0.5", "0.6", "1.1", "14",
             "14.3", "15", "256", "1000", "2025", "2014", "8.2.1"}
TONE = r"\b(novel|first-ever|significantly|guarantee[sd]?|superior|unprecedented|groundbreaking)\b"
FORBIDDEN = r"\b(JNCA|SUSCOM|TGCN|NSRDB|Sustainable Computing)\b"


def text_of(pdf):
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def main(final):
    res, fail = {}, []
    T = text_of(PDF)
    flat = re.sub(r"\s+", " ", T)
    src = (LATEX / "main.tex").read_text(encoding="utf-8")
    nums_tex = (LATEX / "numbers.tex").read_text(encoding="utf-8")
    # 1 placeholders
    ph = re.findall(r"\[\[PENDING[^\]]*\]\]|AUTHOR-CHECK|\?\?|TODO|XXX", flat)
    res["placeholders"] = ph
    if ph and final:
        fail.append(f"placeholders: {sorted(set(ph))}")
    # 2 references on the rendered page
    refpart = flat[flat.rfind("REFERENCES"):] if "REFERENCES" in flat else flat[flat.rfind("References"):]
    ents = re.split(r"\s\[(\d+)\]\s", " " + refpart)
    entries = {int(ents[i]): ents[i + 1] for i in range(1, len(ents) - 1, 2)}
    noid = [k for k, v in entries.items() if not re.search(r"doi|https?://", v, re.I)]
    bib = json.loads((ROOT / "results" / "bib_generation.json").read_text(encoding="utf-8"))["entries"]
    fams = [v["family"] for v in bib.values()]
    def norm(s):
        return re.sub(r"[^a-z]", "", s.lower())
    nflat = norm(refpart)
    missing_fam = [f for f in fams if f and norm(f.split()[-1]) not in nflat]
    res["references"] = {"rendered": len(entries), "without_identifier": noid, "family_not_on_page": missing_fam}
    if noid:
        fail.append(f"references without DOI/URL: {noid}")
    if missing_fam:
        fail.append(f"first-author family not found on page: {missing_fam}")
    # 3 literal numbers in the source body
    body = src[src.find(r"\begin{document}"):]
    body = re.sub(r"\\author\{.*?\\maketitle", "", body, flags=re.S)        # author block (ORCID digits)
    body = re.sub(r"p\{[\d.]+\\(?:column|text)width\}", "", body)             # tabular column widths
    body = re.sub(r"\\(cite|ref|label|includegraphics|input|bibliography|bibliographystyle|setlength|begin|end)"
                  r"(\[[^\]]*\])?\{[^}]*\}", "", body)
    body = re.sub(r"\{@\{\}[^}]*@\{\}\}|\{[lcrp]+\}", "", body)
    body = re.sub(r"%.*", "", body)
    allowed = CONSTANTS | set(re.findall(r"\d+(?:\.\d+)?", nums_tex))
    lits = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)", re.sub(r"\\[A-Za-z]+", " ", body))
    bad = sorted(set(x for x in lits if x not in allowed))
    res["unlisted_numbers"] = {x: [body[max(0, m.start() - 40):m.end() + 10] for m in
                                   re.finditer(r"(?<![\\w])" + re.escape(x) + r"(?![\d.])", body)][:2] for x in bad}
    if bad:
        fail.append(f"numbers in text not in numbers.tex/constants: {bad}")
    # 4 raw commands / tone / forbidden
    raw = re.findall(r"\\[A-Za-z]{2,}", flat)
    res["raw_commands"] = raw[:20]
    if raw:
        fail.append(f"raw LaTeX commands on page: {raw[:10]}")
    body_text = flat[:flat.rfind("REFERENCES")] if "REFERENCES" in flat else flat
    tone = re.findall(TONE, body_text, re.I)
    res["tone"] = tone
    if tone:
        fail.append(f"tone words: {tone}")
    forb = re.findall(FORBIDDEN, body_text)
    res["forbidden"] = forb
    if forb:
        fail.append(f"forbidden names: {forb}")
    # 5 title / abstract
    title = re.search(r"\\title\{([^}]*)\}", src).group(1)
    nt = len(title.split())
    res["title_words"] = nt
    if nt > MAX_TITLE or title.lower().startswith("certified"):
        fail.append(f"title {nt} words / starts with Certified")
    m = re.search(r"Abstract[—\-–\s]+(.*?)Index Terms", flat)
    abs_txt = m.group(1) if m else ""
    na = len(re.findall(r"\b[\w'’.-]+\b", abs_txt))
    res["abstract_words"] = na
    first = re.split(r"(?<=[.!?])\s", abs_txt.strip(), 1)[0] if abs_txt else ""
    res["abstract_first_sentence"] = first
    if na > MAX_ABS or na == 0:
        fail.append(f"abstract {na} words")
    if "energy-harvesting sensing nodes" not in first.lower() or first.lower().startswith("theorem"):
        fail.append("abstract sentence 1 lacks 'energy-harvesting sensing nodes' or opens with 'theorem'")
    kw = re.search(r"Index Terms[—\-–\s]+(.*?)\.\s", flat)
    res["keywords"] = kw.group(1) if kw else None
    # 6 pages / overfull
    info = subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    res["pages"] = pages
    if pages > MAX_PAGES:
        fail.append(f"pages {pages} > {MAX_PAGES}")
    log = (LATEX / "main.log").read_text(encoding="utf-8", errors="replace")
    over = [float(x) for x in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide", log)]
    res["overfull_pt"] = over
    if any(x > 5 for x in over):
        fail.append(f"overfull boxes > 5pt: {[x for x in over if x > 5]}")
    undef = re.findall(r"(Citation|Reference) `([^']+)' .*undefined", log)
    res["undefined"] = undef
    if undef:
        fail.append(f"undefined refs/cites: {undef}")
    # 7 figure provenance (C8b)
    prov = json.loads((ROOT / "results" / "figure_provenance.json").read_text())
    used = re.findall(r"figures/([\w\-]+\.pdf)", src + (LATEX / "numbers.tex").read_text(encoding="utf-8"))
    badfig = []
    for n in set(used):
        h = hashlib.sha256((LATEX / "figures" / n).read_bytes()).hexdigest()
        if n not in prov or prov[n]["results_sha256"] != h or \
                hashlib.sha256((ROOT / "results" / "figs" / n).read_bytes()).hexdigest() != h:
            badfig.append(n)
    res["figures_used"] = sorted(set(used))
    if badfig:
        fail.append(f"figure provenance mismatch: {badfig}")
    res["failures"] = fail
    res["final"] = final
    (ROOT / "results" / "verify_render.json").write_text(json.dumps(res, indent=1, ensure_ascii=False),
                                                         encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("pages", "abstract_words", "title_words", "references")}, ensure_ascii=False))
    print("FAILURES:" if fail else "ALL CHECKS PASS", *fail, sep="\n  ")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main("--final" in sys.argv))
