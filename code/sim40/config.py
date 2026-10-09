"""Shared constants and paths for sim40 (topic 40, energy-harvesting sensing nodes).

All energies are dimensionless, in units of e_idle (the energy of one idle slot):
    slot energy   e(x) = 1 + x (r - 1) + l      (x in {0,1}, l = leakage per slot)
    harvest       h_t  = harvested energy in slot t / e_idle
    storage       C    = capacity / e_idle
A slot is one frame period, TAU = 0.1 s (10 fps).
"""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE = HERE.parent
TOPIC = CODE.parent
RES = TOPIC / "results"
FIGS = RES / "figs"

DS = Path(os.environ.get("THS_DATASETS", r"D:\Datasets"))
SAT = DS / "OpenMeteo_SatRad"
ENH = DS / "EnHANTS" / "extracted"
DET = DS / "_derived" / "detections_cpu_yolo26s"
CKPT = DS / "_derived" / "40" / "grid_ckpt"   # large dumps off the Drive-synced folder (CLAUDE.md)

# events_gated.csv of the 09.05 repo: READ ONLY, used only to assert that the corpus rebuilt
# here (events.py) is identical. Never copied, never imported.
LEGACY_EVENTS = Path(r"D:\THS Programing\09.05 Certifiable worst-case\certifiable-frame-skipping"
                     r"\data\processed\events_gated.csv")
LEGACY_EVENTS_SHA = "8fade8f15bbb4f09ec27cb25a355af92750c618017c04e4d5d7b1917bb7cf29d"

TAU = 0.1                      # slot length (s)
SLOTS_PER_MIN = int(round(60 / TAU))
SLOTS_PER_DAY = int(round(86400 / TAU))

R_LEVELS = (1.1, 1.3, 2.0, 5.0, 15.0, 40.0, 100.0, 300.0)
L_LEVELS = (0.0, 0.01, 0.04, 0.1)
M_LEVELS = (0.25, 1.0)
K_LEVELS = (2, 4, 8, 16, 32, 64)
K_REF = 8                      # design point that sizes the panel (season-neutral for periodic K_REF)
CUE_LEVELS = (0.02, 0.05, 0.1, 0.2)
N_C = 20

# anchors (P0/ENERGY_MODEL_40.md): class A GAP9+HM0360 r ~ 14 (10 fps) / 41; class B Orin Nano r ~ 1.08 / 1.23
R_ANCHOR_A = 14.0
R_ANCHOR_B = 1.08

SITES_OUT = {  # name: (file stem, step seconds)
    "HCMC": "HCMC_jma_jaxa_himawari_2025",
    "Madrid-MSG": "Madrid_eumetsat_lsa_saf_msg_2025",
    "Madrid-SARAH3": "Madrid_eumetsat_sarah3_2025",
    "Uppsala-MSG": "Uppsala_eumetsat_lsa_saf_msg_2025",
    "Uppsala-SARAH3": "Uppsala_eumetsat_sarah3_2025",
}
SITES_IN = ("SetupB", "SetupC", "SetupD", "SetupE", "SetupF")
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}

SEED = 42
B_BOOT = 1000
