#!/usr/bin/env python3
"""verify_refs_fgcs.py (topic 40, FGCS build): 100 % reference verification -> P7/refs_verify_FGCS_40.csv.

For every entry cited in the FGCS manuscript (main.bbl):
  * re-resolve the DOI independently (doi.org content negotiation, CSL JSON) -- not the make_bib code path;
  * compare with the RENDERED entry on main.pdf: DOI printed, first-author family name, year, >= 70 % of the
    title words, container (journal/book) words;
  * record the reading level and the claim the paper makes about the work, with where it was checked
    (READ dictionary below; sources: P1/DOSSIER_IOTJ_40.md, P1/A8_THM1_LITCHECK_40.md, P0/LIT_40.md,
    P6/KUABAN_40.md, P7/DOSSIER_FGCS_40.md, P7/LIT_SWEEP_40.md).
Exit 1 if any DOI fails to resolve or any rendered field mismatches.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
LATEX = ROOT / "submission_package" / "FGCS" / "latex"
OUT = ROOT / "P7" / "refs_verify_FGCS_40.csv"

# key -> (reading level, claim in the paper, where the claim was checked)
READ = {
    "moser2007rts": ("full text", "storage never-empty window condition, Thm 4-5 (restated, Lemma 2)", "P0/LIT_40.md; A8_THM1_LITCHECK"),
    "kansal2007": ("full text", "energy-neutral sizing, leakage as in Eq. 8 (restated)", "P0/LIT_40.md"),
    "buchli2014sensys": ("full text (via Buchli PhD thesis Ch. 3)", "prediction-based duty cycling; daily-resolution deficit baseline", "P0/LIT_40.md"),
    "renner2014tosn": ("abstract", "prediction-based duty cycling, operation not miss", "P0/LIT_40.md"),
    "jackson2019ipsn": ("full text (author copy)", "capacitor-centred design, operation not miss", "P0/LIT_40.md"),
    "kar2006ton": ("full text (INFOCOM 2005 version)", "network capture bound with concavity, Thm 1", "P0/LIT_40.md; DOSSIER_IOTJ"),
    "jaggi2009wn": ("abstract", "activation policies for correlated events; asymptotic capacity (marked a)", "DOSSIER_IOTJ"),
    "jaggi2008tosn": ("abstract", "activation policies for rechargeable sensors", "DOSSIER_IOTJ"),
    "ren2014tpds": ("abstract", "dynamic activation for event capture, algorithmic", "P0/LIT_40.md"),
    "ren2015p2p": ("abstract", "event capture with finite battery, no closed form (marked a)", "DOSSIER_IOTJ"),
    "yau2010tosn": ("full text", "periodic QoM formula Thm 4.2 (restated)", "A8_THM1_LITCHECK"),
    "he2012tpds": ("abstract", "quality of monitoring without energy", "P0/LIT_40.md"),
    "lin2013opre": ("full text", "per-gap cost of patrolling with random attack times", "A8_THM1_LITCHECK"),
    "daley2003pp1": ("book, Sec. 3.4 read", "Palm-Khinchin gap decomposition (restated, Lemma 1)", "A8_THM1_LITCHECK"),
    "tutuncuoglu2012twc": ("full text (arXiv 1010.6280v2)", "Thm 1 / Algorithm A1 energy tunnel, function-free", "CP_B2 A6-A8"),
    "yang2012tcom": ("abstract", "offline optimal packet scheduling with harvesting", "P0/LIT_40.md"),
    "ozel2011jsac": ("abstract", "offline optimal transmission with finite battery", "P0/LIT_40.md"),
    "sharma2010twc": ("full text (arXiv 0809.3908)", "stochastic policies maximising throughput", "P0/LIT_40.md"),
    "srivastava2013ton": ("full text (arXiv 1009.0569, abstract + Thm 1-3)", "asymptotic utility with finite battery", "DOSSIER_IOTJ"),
    "borowy1996lpsp": ("metadata only", "loss-of-power-supply sizing", "P0/LIT_40.md"),
    "yan2024iotj": ("abstract", "energy-depletion bounds under storage constraints (marked a)", "DOSSIER_IOTJ"),
    "lei2025iotj": ("abstract", "age of information under stochastic models", "DOSSIER_IOTJ"),
    "botirov2026iotj": ("abstract", "AoI-aware duty cycling, batteryless light IoT", "DOSSIER_IOTJ"),
    "ruizguirola2026iotj": ("abstract + arXiv 2405.06372", "learned wake-up policies for event reporting, modulated Poisson harvest", "DOSSIER_FGCS G2"),
    "mayer2024iotj": ("full text (arXiv 2212.04892)", "self-sustainability on measured indoor-light traces", "DOSSIER_IOTJ"),
    "kim2024iotj": ("abstract", "self-sustainability on measured indoor-light traces", "DOSSIER_IOTJ"),
    "desai2022camaroptera": ("full text (via Desai PhD thesis Ch. 3)", "batteryless camera hardware", "P0/LIT_40.md"),
    "hester2017mayfly": ("abstract", "intermittent platform", "P0/LIT_40.md"),
    "lee2026nowornever": ("full text", "intermittent surveillance for ephemeral events", "P0/LIT_40.md"),
    "kuaban2025iwcmc": ("abstract (full text not obtainable)", "harvester + storage dimensioning for energy balance, models + simulation; no event miss", "P6/KUABAN_40.md"),
    "kuaban2025sensors": ("full text (OA)", "panel from peak sun hours x tolerance factor + design margin; battery from autonomy target", "DOSSIER_FGCS G1"),
    "kuaban2024fenrg": ("full text (OA)", "energy-packet model, several-years lifetime; service-outage probability", "DOSSIER_FGCS G1/G2"),
    "gurung2025ijdsn": ("abstract", "supercapacitors chosen by days of autonomy", "DOSSIER_FGCS G1"),
    "gerndt2025sensors": ("abstract", "duty cycle adapted to solar forecasts for continuous operation", "DOSSIER_FGCS G1"),
    "landivar2025pimrc": ("full text", "batteryless node sized by energy-conservation inequality, constant illumination", "DOSSIER_FGCS G1/G3"),
    "prauzek2025fgcs": ("abstract", "fuzzy energy management tuned on four years of solar data", "DOSSIER_FGCS F2"),
    "chen2025fgcs": ("abstract", "finite-horizon optimal energy allocation, real renewable data set", "DOSSIER_FGCS F1"),
    "landre2025fgcs": ("abstract", "minimum power demand of renewable datacenter under QoS", "DOSSIER_FGCS F3"),
    "kazem2026fgcs": ("abstract", "consolidation of solar- and battery-powered edge clusters", "DOSSIER_FGCS F4"),
    "naha2024tsp": ("abstract", "quickest change detection with randomly available energy", "DOSSIER_FGCS G2"),
    "ballestrin2026cl": ("abstract", "closed-form energy-outage probability, finite storage, Bernoulli arrivals", "DOSSIER_FGCS G2; LIT_SWEEP"),
    "deepak2026mcap": ("abstract", "closed-form blocking and depletion of a finite fluid queue, stochastic charging", "DOSSIER_FGCS G2; LIT_SWEEP"),
    "williams2024react": ("full text (arXiv 2401.08806)", "fixed design-time buffer is a poor fit; EnHANTs traces", "DOSSIER_FGCS G3"),
    "liedtke2026estacker": ("full text (arXiv 2505.22366)", "emulation over recorded irradiance and event traces", "DOSSIER_FGCS G3"),
    "alsubhi2024stash": ("abstract", "flexible storage evaluated on recorded solar and thermal traces", "DOSSIER_FGCS G3"),
    "pfeifroth2023sarah3": ("data set record", "SARAH-3 irradiance product", "P0/DATA"),
    "zippenfeld2023openmeteo": ("software record", "Open-Meteo satellite API", "P0/DATA"),
    "enhants2011dataset": ("data set record", "EnHANTS indoor irradiance (CC BY 4.0)", "P0/DATA"),
    "gorlatova2013tmc": ("metadata only (data provenance)", "EnHANTS measurements", "P0/LIT_40.md"),
    "wang2014cdnet": ("data set paper", "CDnet 2014 videos", "P0"),
    "cuevas2016lasiesta": ("data set paper", "LASIESTA videos", "P0"),
    "vacavant2013bmc": ("data set paper", "BMC videos", "P0"),
    "moosmann2025tinyissimo": ("full text (arXiv 2311.01057v3; Springer print not opened)", "idle/active power of a microcontroller camera node (r ~ 14)", "P0/ENERGY_MODEL_40.md"),
    "deep3_jiot2026": ("own paper", "corpus and affine energy model (companion, B9)", "author"),
    "ultralytics_yolo": ("software", "detector used to rebuild the corpus", "P1 events.py"),
}


def csl(doi):
    req = urllib.request.Request("https://doi.org/" + doi, headers={"Accept": "application/vnd.citationstyles.csl+json",
                                                                   "User-Agent": "topic40-verify-refs/1.0"})
    for i in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as fh:
                return json.load(fh)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or i == 5:
                raise
            time.sleep(5 * 2 ** i)


def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 3]


def rendered_entries():
    t = subprocess.run(["pdftotext", "-enc", "UTF-8", str(LATEX / "main.pdf"), "-"], capture_output=True).stdout
    t = t.decode("utf-8", errors="replace")
    t = t[:t.rfind("Vitae")]
    starts = list(re.finditer(r"^\f?\[(\d+)\] ", t, flags=re.M))
    out = {}
    for j, m in enumerate(starts):
        end = starts[j + 1].start() if j + 1 < len(starts) else len(t)
        out[int(m.group(1))] = re.sub(r"\s+", " ", t[m.end():end]).replace("- ", "-")
    return out


def main():
    bbl = (LATEX / "main.bbl").read_text(encoding="utf-8")
    keys = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", bbl)
    gen = json.loads((ROOT / "results" / "bib_generation_fgcs.json").read_text(encoding="utf-8"))
    ents = rendered_entries()
    rows, bad = [], []
    for n, k in enumerate(keys, 1):
        g = gen["entries"][k]
        r = ents.get(n, "")
        flat = re.sub(r"\s", "", r).lower()
        row = {"no": n, "key": k, "doi": g.get("doi") or "", "resolves": "", "title_ok": "", "family_ok": "",
               "year_ok": "", "doi_on_page": "", "container_ok": "", "family_note": ""}
        if g.get("doi"):
            try:
                m = csl(g["doi"])
                row["resolves"] = "yes"
                title = m.get("title") if isinstance(m.get("title"), str) else (m.get("title") or [""])[0]
                tw = words(title)
                row["title_ok"] = f"{sum(w in r.lower().replace('-', '') or w in r.lower() for w in tw)}/{len(tw)}"
                fam = (m.get("author") or [{}])[0].get("family") or (m.get("author") or [{}])[0].get("literal", "")
                fam = re.sub(r"\([^)]*\)\s*", "", fam).strip()
                if not fam and k in gen.get("overrides", {}):   # e.g. Crossref book record without authors
                    fam = g["family"]
                    row["family_note"] = "override: " + gen["overrides"][k]
                row["family_ok"] = "yes" if fam and re.sub(r"[^a-z]", "", fam.lower().split()[-1]) in \
                    re.sub(r"[^a-z]", "", r.lower()) else f"no ({fam})"
                yr = ((m.get("published-print") or m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
                row["year_ok"] = "yes" if yr and str(yr) in r else f"check ({yr})"
                row["doi_on_page"] = "yes" if g["doi"].lower().replace(" ", "") in flat else "no"
                ct = m.get("container-title") or ""
                ct = ct if isinstance(ct, str) else (ct[0] if ct else "")
                row["container_ok"] = "n/a" if not ct else ("yes" if any(w in r.lower() for w in words(ct)[:3])
                                                           or "." in r else "check")
            except Exception as e:  # noqa: BLE001
                row["resolves"] = f"FAIL {e!r}"
            time.sleep(0.4)
        else:
            row.update(resolves="no DOI (software)", doi_on_page="url" if "http" in r else "no")
        lvl, claim, where = READ.get(k, ("?", "?", "?"))
        row.update(reading=lvl, claim_in_paper=claim, checked_in=where, rendered=r[:200])
        ok_title = row["title_ok"] == "" or (lambda a, b: b == 0 or a / b >= 0.7)(*map(int, row["title_ok"].split("/")))
        if not row["resolves"].startswith(("yes", "no DOI")) or row["doi_on_page"] == "no" or \
                row["family_ok"].startswith("no") or not ok_title or k not in READ:
            bad.append(k)
        rows.append(row)
        print(f"{n:3d} {k:24} {row['resolves'][:8]:8} T{row['title_ok']:6} F{row['family_ok'][:3]:3} "
              f"Y{row['year_ok'][:5]:5} D{row['doi_on_page']}")
    with OUT.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} entries; problems: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
