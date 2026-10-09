#!/usr/bin/env python3
"""make_bib.py (topic 40): generate refs.bib from live Crossref/DataCite metadata.

Rules (checklist C4/C5):
  * no bibliographic field is typed by hand for DOI-bearing entries; an unresolved DOI fails the build;
  * the DOI is printed through `note` (IEEEtran.bst drops `doi`); entries with a DOI carry no `url`;
  * HTML entities / JATS tags from Crossref are stripped;
  * the first author's family name is recorded so verify_render.py can check it on the rendered page.
Declared non-DOI sources (software, web data portals) live in MANUAL with a stable URL.
No e-mail address is sent in any request.
Usage: python code/paper/make_bib.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "IoTJ" / "latex"
UA = {"User-Agent": "topic40-make-bib/1.0"}

DOI_REFS = {
    # energy as a curve, energy-neutral operation, sizing
    "moser2007rts": "10.1007/s11241-007-9027-0",
    "kansal2007": "10.1145/1274858.1274870",
    "buchli2014sensys": "10.1145/2668332.2668333",
    "renner2014tosn": "10.1145/2566675",
    "jackson2019ipsn": "10.1145/3302506.3310400",
    "borowy1996lpsp": "10.1109/60.507648",
    # event capture with rechargeable sensors, quality of monitoring, point processes, search
    "kar2006ton": "10.1109/tnet.2005.863710",
    "jaggi2009wn": "10.1007/s11276-007-0091-0",
    "jaggi2008tosn": "10.1145/1362542.1362548",
    "ren2014tpds": "10.1109/tpds.2013.2297096",
    "ren2015p2p": "10.1007/s12083-013-0238-y",
    "yau2010tosn": "10.1145/1824766.1824774",
    "he2012tpds": "10.1109/tpds.2011.242",
    "lin2013opre": "10.1287/opre.1120.1149",
    "daley2003pp1": "10.1007/b97277",
    # energy-harvesting communication: offline optimum, storage-limited bounds
    "tutuncuoglu2012twc": "10.1109/TWC.2012.012412.110805",
    "yang2012tcom": "10.1109/TCOMM.2011.112811.100349",
    "ozel2011jsac": "10.1109/JSAC.2011.110921",
    "sharma2010twc": "10.1109/TWC.2010.04.080749",
    "srivastava2013ton": "10.1109/tnet.2012.2218123",
    # IEEE IoT-J 2024-2026 (dossier P1/DOSSIER_IOTJ_40.md)
    "yan2024iotj": "10.1109/jiot.2024.3443209",
    "lei2025iotj": "10.1109/jiot.2025.3557040",
    "mayer2024iotj": "10.1109/jiot.2023.3289568",
    "ruizguirola2026iotj": "10.1109/jiot.2026.3664201",
    "botirov2026iotj": "10.1109/jiot.2026.3719857",
    "kim2024iotj": "10.1109/jiot.2024.3402168",
    # intermittent / batteryless sensing
    "desai2022camaroptera": "10.1145/3510850",
    "lee2026nowornever": "10.1145/3774905.3794709",
    "hester2017mayfly": "10.1145/3131672.3131673",
    # data, corpus, energy anchor
    "pfeifroth2023sarah3": "10.5676/EUM_SAF_CM/SARAH/V003",
    "zippenfeld2023openmeteo": "10.5281/zenodo.7970649",
    "enhants2011dataset": "10.15783/C77P47",
    "gorlatova2013tmc": "10.1109/TMC.2012.154",
    "wang2014cdnet": "10.1109/CVPRW.2014.126",
    "cuevas2016lasiesta": "10.1016/j.cviu.2016.08.005",
    "vacavant2013bmc": "10.1007/978-3-642-37410-4_25",
    "moosmann2025tinyissimo": "10.1007/978-3-031-91989-3_17",
    "deep3_jiot2026": "10.1109/jiot.2026.3740931",
}

# Deep3 metadata: the author has not yet confirmed the Xplore record (doc 11721175) -> flagged, not blocking
AUTHOR_CHECK = {"deep3_jiot2026"}

# Corrections of Crossref metadata errors (each one justified; recorded in bib_generation.json)
OVERRIDES = {
    "daley2003pp1": {"authors": "Daley, D. J. and Vere-Jones, D.", "family": "Daley",
                     "why": "Crossref book record (10.1007/b97277) has no author field; authors from the title page"},
    "deep3_jiot2026": {"authors": "{Lam Quoc}, Dat", "family": "Lam Quoc",
                       "why": "Crossref swaps given/family (given 'Lam Quoc', family 'Dat'); the author's name is "
                              "Dat Lam Quoc (ORCID 0009-0004-5432-9343). Pending the author's Crossref fix"},
}

MANUAL = {
    "ultralytics_yolo": {
        "type": "misc",
        "fields": {"author": "{Ultralytics}", "title": "{Ultralytics YOLO}", "year": "2026",
                   "howpublished": r"\url{https://github.com/ultralytics/ultralytics}",
                   "note": "Software; model YOLO26s, CPU inference"},
        "why": "software release without DOI",
        "family": "Ultralytics",
    },
}

ACC = {"á": r"\'{a}", "à": r"\`{a}", "ä": r'\"{a}', "â": r"\^{a}", "å": r"\r{a}", "é": r"\'{e}", "è": r"\`{e}",
       "ë": r'\"{e}', "ê": r"\^{e}", "í": r"\'{i}", "ï": r'\"{i}', "î": r"\^{i}", "ó": r"\'{o}", "ö": r'\"{o}',
       "ô": r"\^{o}", "ø": r"{\o}", "ú": r"\'{u}", "ü": r'\"{u}', "ñ": r"\~{n}", "ç": r"\c{c}", "ß": r"{\ss}",
       "Á": r"\'{A}", "É": r"\'{E}", "Ö": r'\"{O}', "Ü": r'\"{U}', "ğ": r"\u{g}", "ı": r"{\i}", "ş": r"\c{s}",
       "–": "--", "—": "---", "’": "'", "‘": "`", "“": "``", "”": "''", "×": r"$\times$", "−": "-",
       "μ": r"$\mu$", "µ": r"$\mu$"}


def tex(s):
    return "".join(ACC.get(c, ("\\" + c) if c in "&%$#_" else c) for c in (s or ""))


def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+([:;,.])", r"\1", s)


def protect(t):
    return re.sub(r"\b([A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9\-]*)\b", r"{\1}", t)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as fh:
        return json.load(fh)


def crossref(doi):
    m = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")["message"]
    yr = ((m.get("published-print") or m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    au = []
    for a in (m.get("author") or []):
        if not a.get("family"):
            continue
        if not a.get("given") and " " in a["family"].strip():     # 'Given Family' packed into family
            *gv, fam = a["family"].split()
            a = {"family": fam, "given": " ".join(gv)}
        au.append(a)
    typ = {"journal-article": "article", "proceedings-article": "inproceedings",
           "book-chapter": "incollection", "book": "book", "monograph": "book"}.get(m.get("type"), "misc")
    return {"type": typ, "title": clean((m.get("title") or [""])[0]),
            "authors": " and ".join(f"{clean(a['family'])}, {clean(a.get('given', ''))}".strip(", ") for a in au),
            "family": clean(au[0]["family"]) if au else "",
            "container": clean((m.get("container-title") or [""])[0]), "year": yr,
            "volume": m.get("volume"), "number": m.get("issue"), "pages": (m.get("page") or "").replace("-", "--"),
            "publisher": clean(m.get("publisher", "")), "doi": m.get("DOI"), "src": "crossref"}


def datacite(doi):
    a = get(f"https://api.datacite.org/dois/{urllib.parse.quote(doi)}")["data"]["attributes"]
    cr = a.get("creators", [])

    def nm(c):
        if c.get("familyName"):
            return f"{c['familyName']}, {c.get('givenName', '')}".strip(", ")
        return "{" + c.get("name", "") + "}"
    return {"type": "misc", "title": clean(a["titles"][0]["title"]), "authors": " and ".join(nm(c) for c in cr),
            "family": (cr[0].get("familyName") or cr[0].get("name", "")) if cr else "",
            "container": clean(a.get("publisher") or ""), "year": a.get("publicationYear"), "volume": None,
            "number": None, "pages": "", "publisher": clean(a.get("publisher") or ""), "doi": a.get("doi"),
            "src": "datacite"}


def entry(key, r, flag=False):
    f = [("author", tex(r["authors"])), ("title", protect(tex(r["title"])))]
    if r["type"] == "article":
        f.append(("journal", tex(r["container"])))
    elif r["type"] in ("inproceedings", "incollection"):
        f.append(("booktitle", tex(r["container"])))
        if r.get("publisher"):
            f.append(("publisher", tex(r["publisher"])))
    elif r["type"] == "book":
        f.append(("publisher", tex(r["publisher"])))
    else:
        f.append(("howpublished", tex(r["container"])))
    for k in ("volume", "number"):
        if r.get(k):
            f.append((k, str(r[k])))
    if r.get("pages"):
        f.append(("pages", r["pages"]))
    f.append(("year", str(r["year"])))
    note = f"doi: \\url{{https://doi.org/{r['doi']}}}"
    if flag:
        note += " [AUTHOR-CHECK: Xplore metadata not yet confirmed by the author]"
    f.append(("note", note))
    body = ",\n".join(f"  {k:10} = {{{v}}}" for k, v in f if v)
    return f"@{r['type']}{{{key},\n{body}\n}}\n"


def main():
    LATEX.mkdir(parents=True, exist_ok=True)
    lines = ["% refs.bib: GENERATED by code/paper/make_bib.py from live Crossref/DataCite. Do not hand-edit.",
             f"% generated {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    rep = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "entries": {}, "failures": [], "author_check": []}
    for key, doi in DOI_REFS.items():
        try:
            r = datacite(doi) if doi.lower().startswith(("10.5281/", "10.15783/", "10.5676/", "10.48550/")) \
                else crossref(doi)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {key} {doi}: {e!r}")
            rep["failures"].append({"key": key, "doi": doi, "error": repr(e)})
            continue
        flag = key in AUTHOR_CHECK
        if key in OVERRIDES:
            o = OVERRIDES[key]
            r.update({k: v for k, v in o.items() if k != "why"})
            rep.setdefault("overrides", {})[key] = o["why"]
        lines.append(entry(key, r, flag))
        rep["entries"][key] = {"doi": r["doi"], "year": r["year"], "family": r["family"], "title": r["title"],
                               "container": r["container"], "src": r["src"]}
        if flag:
            rep["author_check"].append(key)
        print(f"ok   {key:24} {r['year']} {r['family'][:16]:16} {r['title'][:60]}")
        time.sleep(0.3)
    for key, s in MANUAL.items():
        body = ",\n".join(f"  {k:10} = {{{v}}}" for k, v in s["fields"].items())
        lines.append(f"@{s['type']}{{{key},\n{body}\n}}\n")
        rep["entries"][key] = {"doi": None, "family": s["family"], "why_no_doi": s["why"]}
    (LATEX / "refs.bib").write_text("\n".join(lines), encoding="utf-8")
    (ROOT / "results" / "bib_generation.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False),
                                                          encoding="utf-8")
    print(f"{len(rep['entries'])} entries, {len(rep['failures'])} failures, author-check {rep['author_check']}")
    return 1 if rep["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
