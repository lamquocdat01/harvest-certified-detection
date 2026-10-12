#!/usr/bin/env python3
"""make_bib.py (topic 40): generate refs.bib from live Crossref/DataCite metadata.

Rules (checklist C4/C5):
  * no bibliographic field is typed by hand for DOI-bearing entries; an unresolved DOI fails the build;
  * the DOI is printed through `note` (IEEEtran.bst drops `doi`); entries with a DOI carry no `url`;
  * HTML entities / JATS tags from Crossref are stripped;
  * the first author's family name is recorded so verify_render.py can check it on the rendered page.
Declared non-DOI sources (software, web data portals) live in MANUAL with a stable URL.
No e-mail address is sent in any request.
Usage: python code/paper/make_bib.py [--style fgcs]
  default : IEEEtran (IoT-J build), DOI printed through `note`, -> submission_package/IoTJ/latex/refs.bib
  fgcs    : elsarticle-num (FGCS build), DOI in the `doi` field (elsarticle-num prints it), journal titles
            abbreviated per ISO 4 / LTWA, data sets tagged [dataset], software with URL and access date
            -> submission_package/FGCS/latex/refs.bib, report results/bib_generation_fgcs.json
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "IoTJ" / "latex"
UA = {"User-Agent": "topic40-make-bib/1.0"}
STYLE = "fgcs" if "--style" in sys.argv and sys.argv[sys.argv.index("--style") + 1] == "fgcs" else "ieee"
if STYLE == "fgcs":
    LATEX = ROOT / "submission_package" / "FGCS" / "latex"

# ISO 4 abbreviations (LTWA) used by the FGCS build; single-word titles are not abbreviated.
LTWA = {
    "Real-Time Systems": "Real-Time Syst.",
    "ACM Transactions on Embedded Computing Systems": "ACM Trans. Embed. Comput. Syst.",
    "ACM Transactions on Sensor Networks": "ACM Trans. Sens. Netw.",
    "IEEE Transactions on Energy Conversion": "IEEE Trans. Energy Convers.",
    "IEEE/ACM Transactions on Networking": "IEEE/ACM Trans. Netw.",
    "Wireless Networks": "Wirel. Netw.",
    "IEEE Transactions on Parallel and Distributed Systems": "IEEE Trans. Parallel Distrib. Syst.",
    "Peer-to-Peer Networking and Applications": "Peer-to-Peer Netw. Appl.",
    "Operations Research": "Oper. Res.",
    "IEEE Transactions on Wireless Communications": "IEEE Trans. Wirel. Commun.",
    "IEEE Transactions on Communications": "IEEE Trans. Commun.",
    "IEEE Journal on Selected Areas in Communications": "IEEE J. Sel. Areas Commun.",
    "IEEE Internet of Things Journal": "IEEE Internet Things J.",
    "IEEE Transactions on Mobile Computing": "IEEE Trans. Mob. Comput.",
    "Computer Vision and Image Understanding": "Comput. Vis. Image Underst.",
    "Future Generation Computer Systems": "Future Gener. Comput. Syst.",
    "Sustainable Computing: Informatics and Systems": "Sustain. Comput. Inform. Syst.",
    "Journal of Systems Architecture": "J. Syst. Archit.",
    "Journal of Network and Computer Applications": "J. Netw. Comput. Appl.",
    "Ad Hoc Networks": "Ad Hoc Netw.",
    "Computer Networks": "Comput. Netw.",
    "Computer Communications": "Comput. Commun.",
    "Internet of Things": "Internet Things",
    "IEEE Sensors Journal": "IEEE Sens. J.",
    "Sensors": "Sensors",
    "Energies": "Energies",
    "Applied Energy": "Appl. Energy",
    "IEEE Transactions on Green Communications and Networking": "IEEE Trans. Green Commun. Netw.",
    "IEEE Transactions on Industrial Informatics": "IEEE Trans. Ind. Inform.",
    "IEEE Transactions on Sustainable Computing": "IEEE Trans. Sustain. Comput.",
    "ACM Transactions on Internet of Things": "ACM Trans. Internet Things",
    "Proceedings of the IEEE": "Proc. IEEE",
    "Frontiers in Energy Research": "Front. Energy Res.",
    "IEEE Communications Letters": "IEEE Commun. Lett.",
    "IEEE Transactions on Signal Processing": "IEEE Trans. Signal Process.",
    "International Journal of Distributed Sensor Networks": "Int. J. Distrib. Sens. Netw.",
    "Methodology and Computing in Applied Probability": "Methodol. Comput. Appl. Probab.",
}
DATASETS = {"enhants2011dataset", "pfeifroth2023sarah3"}
UNABBREVIATED: set[str] = set()


def ltwa(j):
    if j in LTWA:
        return LTWA[j]
    if len(j.split()) > 1:
        UNABBREVIATED.add(j)
    return j

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
    # P6/P7 additions (P6/KUABAN_40.md, P7/LIT_SWEEP_40.md): node dimensioning; closed forms for point arrivals
    "kuaban2025iwcmc": "10.1109/IWCMC65282.2025.11059677",
    "deepak2026mcap": "10.1007/s11009-026-10314-6",
    "ballestrin2026cl": "10.1109/LCOMM.2026.3671672",
    "kuaban2025sensors": "10.3390/s25103137",
    # FGCS build only (P7/DOSSIER_FGCS_40.md): FGCS precedents and research-gap references, DOIs verified
    "chen2025fgcs": "10.1016/j.future.2024.107493",
    "prauzek2025fgcs": "10.1016/j.future.2025.107717",
    "landre2025fgcs": "10.1016/j.future.2025.107710",
    "kazem2026fgcs": "10.1016/j.future.2026.108737",
    "gurung2025ijdsn": "10.1155/dsn/4253030",
    "gerndt2025sensors": "10.3390/s25144500",
    "landivar2025pimrc": "10.1109/PIMRC62392.2025.11275074",
    "kuaban2024fenrg": "10.3389/fenrg.2024.1399371",
    "naha2024tsp": "10.1109/TSP.2024.3350340",
    "williams2024react": "10.1145/3620666.3651370",
    "liedtke2026estacker": "10.1145/3772371",
    "alsubhi2024stash": "10.1145/3641511",
}

# Deep3 (doc 11721175): the author confirmed on 12-10-2026 that IEEE typeset and index the paper with
# family = "Dat", given = "Lam Quoc"; Crossref matches Xplore, so no override and no AUTHOR-CHECK flag.
AUTHOR_CHECK: set[str] = set()

# Corrections of Crossref metadata errors (each one justified; recorded in bib_generation.json)
OVERRIDES = {
    "deepak2026mcap": {"authors": "P, Nikhil A. and Deepak, T. G.", "family": "P",
                       "why": "Crossref given name 'T.G.' has no space, so the styles print 'T. Deepak'; initials "
                              "spaced, names otherwise as in Crossref (first author's family name is 'P')"},
    "daley2003pp1": {"authors": "Daley, D. J. and Vere-Jones, D.", "family": "Daley",
                     "why": "Crossref book record (10.1007/b97277) has no author field; authors from the title page"},
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
       "–": "--", "—": "---", "‐": "-", "‑": "-", "’": "'", "‘": "`", "“": "``", "”": "''", "×": r"$\times$", "−": "-",
       "μ": r"$\mu$", "µ": r"$\mu$"}


def tex(s):
    return "".join(ACC.get(c, ("\\" + c) if c in "&%$#_" else c) for c in (s or ""))


def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+([:;,.])", r"\1", s)


# proper nouns with a single capital that the bibliography styles would otherwise lower-case
PROPER = ("Open-Meteo.com", "Heliosat", "Palm", "Khinchin", "Kansal", "Internet of Things")


def protect(t):
    t = re.sub(r"\b([A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9\-]*)\b", r"{\1}", t)
    for w in PROPER:
        t = re.sub(r"(?<!\{)\b" + re.escape(w) + r"\b(?!\})", "{" + w + "}", t)
    return t


def get(url, tries=6):
    for i in range(tries):                       # back off on 429/5xx (shared Crossref rate limit)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as fh:
                return json.load(fh)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or i == tries - 1:
                raise
            time.sleep(5 * 2 ** i)


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
    pages = (m.get("page") or "").replace("-", "--")
    early = typ == "article" and not m.get("volume") and pages in ("", "1--1")
    if early:                       # IEEE early access: Crossref prints the placeholder page '1-1'
        pages, yr = "", f"early access, {yr}"
    return {"type": typ, "title": clean((m.get("title") or [""])[0]), "early_access": early,
            "authors": " and ".join(f"{clean(a['family'])}, {clean(a.get('given', ''))}".strip(", ") for a in au),
            "family": clean(au[0]["family"]) if au else "",
            "container": clean((m.get("container-title") or [""])[0]), "year": yr,
            "volume": m.get("volume"), "number": m.get("issue"), "pages": pages,
            "publisher": clean(m.get("publisher", "")), "doi": m.get("DOI"), "src": "crossref"}


def datacite(doi):
    a = get(f"https://api.datacite.org/dois/{urllib.parse.quote(doi)}")["data"]["attributes"]
    cr = a.get("creators", [])

    def nm(c):
        if c.get("familyName"):   # DataCite may carry a nickname in the family field: '(John) Kymissis'
            fam = re.sub(r"\([^)]*\)\s*", "", c["familyName"]).strip()
            return f"{fam}, {c.get('givenName', '')}".strip(", ")
        return "{" + c.get("name", "") + "}"
    return {"type": "misc", "title": clean(a["titles"][0]["title"]), "authors": " and ".join(nm(c) for c in cr),
            "family": (cr[0].get("familyName") or cr[0].get("name", "")) if cr else "",
            "container": clean(a.get("publisher") or ""), "year": a.get("publicationYear"), "volume": None,
            "number": None, "pages": "", "publisher": clean(a.get("publisher") or ""), "doi": a.get("doi"),
            "src": "datacite"}


def entry(key, r, flag=False):
    if STYLE == "fgcs":
        return entry_fgcs(key, r)
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


def entry_fgcs(key, r):
    f = [("author", tex(r["authors"])), ("title", protect(tex(r["title"])))]
    if r["type"] == "article":
        f.append(("journal", tex(ltwa(r["container"]))))
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
    yr = str(r["year"])
    notes = []
    if yr.startswith("early access, "):          # elsarticle-num: '<journal> (early access) (2026). doi:'
        yr = yr.split(", ")[1]
        f = [(k, v + " (early access)" if k == "journal" else v) for k, v in f]
    if key in DATASETS:
        notes.insert(0, "[dataset]")
    f.append(("year", yr))
    if notes:
        f.append(("note", ". ".join(notes)))
    f.append(("doi", r["doi"]))
    body = ",\n".join(f"  {k:10} = {{{v}}}" for k, v in f if v)
    return f"@{r['type']}{{{key},\n{body}\n}}\n"


MANUAL_FGCS = {
    "ultralytics_yolo": {"type": "misc",
                         "fields": {"author": "{Ultralytics}", "title": "{Ultralytics YOLO}", "year": "2026",
                                    "url": "https://github.com/ultralytics/ultralytics",
                                    "note": "Software, model YOLO26s, CPU inference; accessed 12 October 2026"}},
}


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
                               "container": r["container"], "src": r["src"],
                               "early_access": bool(r.get("early_access"))}
        if flag:
            rep["author_check"].append(key)
        print(f"ok   {key:24} {r['year']} {r['family'][:16]:16} {r['title'][:60]}")
        time.sleep(0.3)
    for key, s in (MANUAL_FGCS if STYLE == "fgcs" else MANUAL).items():
        body = ",\n".join(f"  {k:10} = {{{v}}}" for k, v in s["fields"].items())
        lines.append(f"@{s['type']}{{{key},\n{body}\n}}\n")
        rep["entries"][key] = {"doi": None, "family": MANUAL[key]["family"], "why_no_doi": MANUAL[key]["why"]}
    (LATEX / "refs.bib").write_text("\n".join(lines), encoding="utf-8")
    rep["style"] = STYLE
    rep["not_in_ltwa_table"] = sorted(UNABBREVIATED)
    out = "bib_generation_fgcs.json" if STYLE == "fgcs" else "bib_generation.json"
    (ROOT / "results" / out).write_text(json.dumps(rep, indent=1, ensure_ascii=False),
                                                          encoding="utf-8")
    print(f"{len(rep['entries'])} entries, {len(rep['failures'])} failures, author-check {rep['author_check']}"
          + (f", not in LTWA table: {sorted(UNABBREVIATED)}" if UNABBREVIATED else ""))
    return 1 if rep["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
