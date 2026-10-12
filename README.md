# harvest-certified-detection

Code, pre-registration and derived results for the paper
**"Miss Floors and Storage Sizing for Energy-Harvesting Sensing Nodes Under Heavy-Tailed Events"** (Dat Lam Quoc).

The paper proves a miss floor for event-independent duty-cycle schedules, an energy-induced floor for finite
storage and a sizing sandwich for the smallest storage meeting a miss target, and checks them on satellite and
indoor-light harvest traces with a pre-registered train/test protocol. This repository rebuilds every number and
figure of the paper.

## Layout

| Path | Content |
|---|---|
| `code/sim40/` | trace loaders, storage dynamics, policies, event replay, grid stages, bootstrap, analysis, figures |
| `code/sim40/tests/` | machine checks of the theorems (`python -m pytest code/sim40/tests`) |
| `code/paper/` | generation of `numbers.tex`, figures, bibliography and render checks for the manuscript |
| `code/reproduce.sh` | one-command reproduction of all TEST results |
| `code/compare_results.py` | key-by-key comparison of a reproduced `results/` folder with the released one |
| `prereg/` | `PREREG_40.md` (v1, H1-H7, frozen before TEST; tag `prereg-40-v1`), `PREREG_40_v1.1_exploratory.md` (E1-E3, post-TEST exploratory), code hashes |
| `results/` | released derived results (JSON, the event-duration corpus CSV, figures) |

## Reproduce

```bash
pip install numpy==1.26.4 numba==0.65.1 scipy==1.16.3 pandas==2.3.3 matplotlib==3.10.8 psutil==7.2.1   # Python 3.11.9
export THS_DATASETS=/path/to/datasets      # folder described under "Data"
bash code/reproduce.sh 3                   # ~4-5 h on a 4-core laptop, needs >= 6 GB free RAM
python code/compare_results.py results /path/to/clean/clone/results
```
All randomness is seeded (seed 42). TRAIN = odd months and half of the videos (seeded permutation); TEST = even
months and the other videos. Grid checkpoints are written to `$THS_DATASETS/_derived/40/grid_ckpt`; delete that
folder for a run from scratch.

## Licenses

| What | Licence | File |
|---|---|---|
| Code (`code/`) | MIT | `LICENSE` |
| Derived data and figures (`results/`) | CC BY 4.0 | `LICENSE-DATA` |

Third-party input data keep their own terms (next section); none of them is redistributed here.

## Data provenance & licenses (third-party; not redistributed here)

| Data | Source | Licence (verbatim where available) | Used as |
|---|---|---|---|
| Satellite global horizontal irradiance 2025: Ho Chi Minh City (JMA/JAXA Himawari-9), Madrid and Uppsala (EUMETSAT LSA SAF MSG; EUMETSAT CM SAF SARAH-3) | Open-Meteo satellite API, `https://satellite-api.open-meteo.com/v1/archive` (DOI 10.5281/zenodo.7970649; SARAH-3 DOI 10.5676/EUM_SAF_CM/SARAH/V003) | "API data are offered under Attribution 4.0 International (CC BY 4.0)" (open-meteo.com/en/licence) | `$THS_DATASETS/OpenMeteo_SatRad/<site>_<product>_2025.csv` (columns `time_utc`, `ghi_wm2`) |
| Indoor irradiance, EnHANTS setups B-F | CRAWDAD columbia/enhants on IEEE DataPort, DOI 10.15783/C77P47 | `"license": "https://creativecommons.org/licenses/by/4.0/"` (CC BY 4.0, DataPort metadata); "Please acknowledge the source of the Data in any publications or presentations reporting use of this Data." | `$THS_DATASETS/EnHANTS/extracted/` |
| Event durations | per-frame detections (Ultralytics YOLO26s, CPU) on CDnet 2014, LASIESTA and BMC videos | videos and ground truth remain under their providers' terms; **no frame or ground truth is re-hosted** | the derived corpus `results/event_corpus_40.csv` (dataset, video, onset, duration; 121 videos, 3,713 events) is released; the detection dump is rebuilt from the public videos |

Derived files in `results/` are released under CC BY 4.0 (see `LICENSE-DATA`) with the attributions above.

## Status

Tags: `prereg-40-v1` (PREREG v1 frozen before TEST) and `v1.0.0-submission` (the state submitted with the
paper; its annotation records the commit and the SHA-256 of the submitted `main.pdf`).
`RELEASE_FILES.txt` lists every released file with its size and SHA-256; SHA-256 values printed in the paper refer
to the files at the submission tag.
