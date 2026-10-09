# harvest-certified-detection (topic 40) — LOCAL, NOT PUBLISHED

Simulator and pre-registration for "miss floors and storage sizing for energy-harvesting sensing nodes".
- `code/sim40/` — trace loaders, storage dynamics, policies, metrics, grid runner (Python 3.11, numpy, numba, scipy).
- `prereg/PREREG_40.md` — predictions frozen before the TEST run (tag `prereg-40-v1`).
- Data are third-party and NOT redistributed: Open-Meteo satellite radiation (CC BY 4.0), EnHANTS (CC BY 4.0),
  per-frame detections of CDnet2014 / LASIESTA / BMC (event corpus is rebuilt by `code/sim40/events.py`).
Paths are read from THS_DATASETS (default D:\Datasets).
