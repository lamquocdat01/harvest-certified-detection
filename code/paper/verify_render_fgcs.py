#!/usr/bin/env python3
"""verify_render_fgcs.py (topic 40, FGCS build): gates on the RENDERED PDFs and their sources.

Hard in both modes unless stated:
  R1  placeholders ([[PENDING]], AUTHOR-CHECK, TODO, XXX, '??') = 0 on main/supp/cover letter (--final only for '??'
      and PENDING while drafting)
  R2  every rendered reference carries a DOI or URL; first-author family names of refs.bib appear on the page
  R3  every literal number in main.tex body is in numbers.tex or a declared model constant
  R4  no raw \\commands, no broken \\ref (ef{...}) on the page; no undefined citations/references in the log
  R5  tone words = 0; no 'IoT-J' / 'IEEE Internet of Things Journal' / '8 pages' / T30 in body or cover letter
  R6  title <= 15 words and not opening with 'Certified'; abstract 150..250 words, no math, no citation, first
      sentence contains 'energy-harvesting sensing nodes' and does not open with 'theorem'
  R7  keywords 6..10 (FGCS); highlights 3..5 bullets, each <= 85 characters
  R8  pages <= 18 (pdfinfo; FGCS full-length limit), overfull boxes <= 5 pt, figure hashes = results hashes
  R9  back matter: CRediT, competing interest, funding, AI declaration (Elsevier title) and data availability present,
      all before References; e-mail + ORCID on page 1; repository URL lamquocdat01 + tag v1.1.0-fgcs on main
  R10 Deep3 renders as 'L. Q. Dat' with its DOI; no table/figure caption after References
Writes results/verify_render_fgcs.json. Exit 1 on any failure.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "FGCS" / "latex"
PDF = LATEX / "main.pdf"
MAX_PAGES, MAX_ABS, MIN_ABS, MAX_TITLE = 18, 250, 150, 15
KW_MIN, KW_MAX, HL_MIN, HL_MAX, HL_CHARS = 6, 7, 3, 5, 85   # keywords: 2024 Guide 1-7, 2026 reading 6-10
TAG = "v1.1.0-fgcs"
CONSTANTS = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "16", "19", "20", "23", "25", "30", "32", "64",
             "100", "300", "0.01", "0.02", "0.2", "0.03", "0.036", "0.04", "0.05", "0.1", "0.25", "0.248", "0.45",
             "0.5", "0.6", "1.1", "14", "14.3", "15", "256", "1000", "2025", "2014", "1.1.0", "4.0"}
TONE = r"\b(novel|first-ever|significantly|guarantee[sd]?|superior|unprecedented|groundbreaking)\b"
FORBIDDEN = r"\b(IoT-J|IEEE Internet of Things Journal|8 pages|eight pages|T30|IoT-73792|SUSCOM|JNCA|NSRDB)\b"
AI_TITLE = "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process"


def text_of(pdf, first=None, last=None):
    cmd = ["pdftotext", "-enc", "UTF-8"] + (["-f", str(first), "-l", str(last)] if first else []) + [str(pdf), "-"]
    return subprocess.run(cmd, capture_output=True).stdout.decode("utf-8", errors="replace")


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


def main(final):
    res, fail = {}, []
    T = text_of(PDF)
    flat = re.sub(r"\s+", " ", T)
    src = (LATEX / "main.tex").read_text(encoding="utf-8")
    nums_tex = (LATEX / "numbers.tex").read_text(encoding="utf-8")
    ir = flat.rfind("References")
    body_text = flat[:ir] if ir > 0 else flat
    refpart = flat[ir:] if ir > 0 else ""
    vit = refpart.find("Vitae")
    refpart_only = refpart[:vit] if vit > 0 else refpart
    # R1 placeholders on all three PDFs
    texts = {"main": T, "supp": text_of(LATEX / "supp.pdf"), "cover_letter": text_of(LATEX / "cover_letter.pdf")}
    for n, t in texts.items():
        ph = re.findall(r"\[\[PENDING[^\]]*\]\]|AUTHOR-CHECK|TODO|XXX|\?\?", t)
        res[f"placeholders_{n}"] = ph
        if ph and (final or any("AUTHOR-CHECK" in p for p in ph)):
            fail.append(f"R1 placeholders on {n}.pdf: {sorted(set(ph))}")
    # R2 references
    # two-column text extraction can put the first entries of a column before the 'References' heading, so
    # entries are taken from line starts '[n] ' in the extracted text (last occurrence of each n), up to 'Vitae'
    T_refs = T[:T.rfind("Vitae")] if "Vitae" in T else T
    starts = list(re.finditer(r"^\f?\[(\d+)\] ", T_refs, flags=re.M))   # \f = page break
    entries = {}
    for j, mm in enumerate(starts):
        end = starts[j + 1].start() if j + 1 < len(starts) else len(T_refs)
        entries[int(mm.group(1))] = re.sub(r"\s+", " ", T_refs[mm.end():end])
    refpart_only = " ".join(entries.values())
    noid = [k for k, v in entries.items() if not re.search(r"doi|https?://", v, re.I)]
    bib = json.loads((ROOT / "results" / "bib_generation_fgcs.json").read_text(encoding="utf-8"))["entries"]
    cited = set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", (LATEX / "main.bbl").read_text(encoding="utf-8")))
    nref = norm(refpart_only)
    miss_fam = [bib[k]["family"] for k in cited if k in bib and bib[k]["family"]
                and norm(bib[k]["family"].split()[-1]) not in nref]
    res["references"] = {"rendered": len(entries), "cited_in_bbl": len(cited), "without_identifier": noid,
                         "family_not_on_page": miss_fam}
    if noid or len(entries) != len(cited):
        fail.append(f"R2 references without DOI/URL {noid} or rendered {len(entries)} != cited {len(cited)}")
    if miss_fam:
        fail.append(f"R2 first-author family not on page: {miss_fam}")
    # R3 literal numbers in the body source
    body = src[src.find(r"\begin{document}"):]
    body = re.sub(r"\\begin\{frontmatter\}.*?\\begin\{abstract\}", "", body, flags=re.S)
    body = re.sub(r"\\section\*\{Vitae\}.*", "", body, flags=re.S)
    body = re.sub(r"\d*\.?\d+\\textwidth", "", body)
    body = re.sub(r"\[\d+(?:\.\d+)?mm\]|\{\d+(?:\.\d+)?mm\}|\\dimexpr[^\\]*\\relax", "", body)
    body = re.sub(r"\\(cite|ref|label|includegraphics|input|bibliography|bibliographystyle|setlength|begin|end)"
                  r"(\[[^\]]*\])?\{[^}]*\}", "", body)
    body = re.sub(r"%.*", "", body)
    allowed = CONSTANTS | set(re.findall(r"\d+(?:\.\d+)?", nums_tex))
    lits = re.findall(r"(?<![\d.])(\d+(?:\.\d+)*)", re.sub(r"\\[A-Za-z]+", " ", body))
    bad = sorted(set(x for x in lits if x not in allowed))
    res["unlisted_numbers"] = bad
    if bad:
        fail.append(f"R3 numbers in text not in numbers.tex/constants: {bad}")
    # R4 raw commands / broken refs / log
    raw = re.findall(r"\\[A-Za-z]{2,}", flat)
    broken = re.findall(r"ef\{?(?:thm|prop|lem|cor|fig|tab|sec):\w+", flat)
    log = (LATEX / "main.log").read_text(encoding="utf-8", errors="replace")
    undef = re.findall(r"(Citation|Reference) `([^']+)' .*undefined", log)
    res.update(raw_commands=raw[:20], broken_refs=broken, undefined=undef)
    if raw or broken or undef:
        fail.append(f"R4 raw {raw[:5]} broken {broken[:3]} undefined {undef[:5]}")
    # R5 tone / forbidden
    tone = re.findall(TONE, body_text, re.I)
    forb = re.findall(FORBIDDEN, body_text) + re.findall(FORBIDDEN, re.sub(r"\s+", " ", texts["cover_letter"]))
    res.update(tone=tone, forbidden=forb)
    if tone:
        fail.append(f"R5 tone words: {tone}")
    if forb:
        fail.append(f"R5 forbidden names in body/cover letter: {forb}")
    # R6 title / abstract
    title = re.search(r"\\title\{([^}]*)\}", src).group(1)
    res["title_words"] = len(title.split())
    if len(title.split()) > MAX_TITLE or title.lower().startswith("certified"):
        fail.append("R6 title")
    m = re.search(r"Abstract (.*?) Keywords", flat)
    abs_txt = m.group(1) if m else ""
    na = len(re.findall(r"\b[\w'’.-]+\b", abs_txt))
    first = re.split(r"(?<=[.!?])\s", abs_txt.strip(), 1)[0] if abs_txt else ""
    res.update(abstract_words=na, abstract_first_sentence=first)
    if not MIN_ABS <= na <= MAX_ABS:
        fail.append(f"R6 abstract {na} words (FGCS <= {MAX_ABS})")
    abs_src = src[src.find(r"\begin{abstract}"):src.find(r"\end{abstract}")]
    if "$" in abs_src or r"\cite" in abs_src:
        fail.append("R6 abstract contains math or citations")
    if "energy-harvesting sensing nodes" not in first.lower() or first.lower().startswith("theorem"):
        fail.append("R6 abstract sentence 1")
    # R7 keywords / highlights
    kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", src, re.S).group(1)
    nkw = len([k for k in kw.split(r"\sep") if k.strip()])
    hl = [h for h in (LATEX / "highlights.txt").read_text(encoding="ascii").splitlines() if h.strip()]
    res.update(keywords=nkw, highlights=[(len(h), h) for h in hl])
    if not KW_MIN <= nkw <= KW_MAX:
        fail.append(f"R7 keywords {nkw}")
    if not HL_MIN <= len(hl) <= HL_MAX or any(len(h) > HL_CHARS for h in hl):
        fail.append("R7 highlights")
    # R8 pages / overfull / figures
    info = subprocess.run(["pdfinfo", str(PDF)], capture_output=True, text=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    over = [float(x) for x in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide", log)]
    res.update(pages=pages, overfull_pt=over)
    if pages > MAX_PAGES:
        fail.append(f"R8 pages {pages} > {MAX_PAGES}")
    if any(x > 5 for x in over):
        fail.append(f"R8 overfull > 5pt: {[x for x in over if x > 5]}")
    prov = json.loads((ROOT / "results" / "figure_provenance.json").read_text())
    used = set(re.findall(r"figures/([\w\-]+\.pdf)", src + nums_tex))
    badfig = [n for n in used if n not in prov or
              hashlib.sha256((LATEX / "figures" / n).read_bytes()).hexdigest() != prov[n]["results_sha256"]]
    res["figures_used"] = sorted(used)
    if badfig:
        fail.append(f"R8 figure provenance mismatch: {badfig}")
    # R9 back matter / page 1 / repository
    need = ["CRediT authorship contribution statement", "Declaration of competing interest", "Funding",
            AI_TITLE, "Data availability"]
    pos = {n: flat.find(n) for n in need}
    res["back_matter_positions"] = pos
    if any(p < 0 or p > ir for p in pos.values()):
        fail.append(f"R9 back matter missing or after References: {[n for n, p in pos.items() if p < 0 or p > ir]}")
    if "used Claude (Anthropic)" not in flat[pos[AI_TITLE]:ir]:
        fail.append("R9 AI declaration text")
    p1 = re.sub(r"\s+", " ", text_of(PDF, 1, 1))
    res["page1_email_orcid"] = "lamquocdat@gmail.com" in p1 and "0009-0004-5432-9343" in p1
    if not res["page1_email_orcid"]:
        fail.append("R9 e-mail/ORCID not on page 1")
    squeezed = re.sub(r"\s+", "", T)
    res["repo_ok"] = "github.com/lamquocdat01/harvest-certified-detection" in squeezed and TAG in squeezed
    if not res["repo_ok"] or "github.com/lamquocdat/" in squeezed:
        fail.append("R9 repository URL / tag")
    # R10 Deep3 / floats after references
    deep3 = [v for v in entries.values() if "jiot.2026.3740931" in v.lower()]
    res["deep3_entry"] = deep3[0] if deep3 else None
    if not deep3 or not re.search(r"L\.\s*Q\.\s*Dat", deep3[0]):
        fail.append("R10 Deep3 must render as 'L. Q. Dat' with its DOI")
    after = re.findall(r"\bTable \d+[:.]|\bFig\. \d+[:.]", refpart)
    res["floats_after_references"] = after
    if after:
        fail.append(f"R10 floats after References: {after}")
    res["failures"], res["final"] = fail, final
    (ROOT / "results" / "verify_render_fgcs.json").write_text(json.dumps(res, indent=1, ensure_ascii=False),
                                                              encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("pages", "abstract_words", "keywords", "references")}, ensure_ascii=False))
    print("FAILURES:" if fail else "ALL CHECKS PASS", *fail, sep="\n  ")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main("--final" in sys.argv))
