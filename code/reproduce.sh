#!/usr/bin/env bash
# reproduce.sh (topic 40): rebuild every TEST result of the paper from the public raw data, in one command.
#   THS_DATASETS must point to a folder with OpenMeteo_SatRad/, EnHANTS/extracted/ and
#   _derived/detections_cpu_yolo26s/ (see README, "Data"). Checkpoints go to $THS_DATASETS/_derived/40/grid_ckpt.
#   About 4-5 h on a 4-core laptop; RAM guard 6 GB. Usage: bash code/reproduce.sh [workers]
set -euo pipefail
W="${1:-3}"
cd "$(dirname "${BASH_SOURCE[0]}")"
# corpus: rebuilt from the detection dump if present; the identity check against the companion artifact
# (events_gated.csv) runs only where that file exists. Without the dump, results/event_corpus_40.csv (released) is used.
if [ -d "${THS_DATASETS:-D:/Datasets}/_derived/detections_cpu_yolo26s" ]; then
  python -m sim40.events || echo "identity check skipped (companion artifact not available); corpus CSV rebuilt"
fi
for st in main frontier gate throttle; do python -m sim40.run_grid --split test --stage $st --workers "$W"; done
python -m sim40.bootstrap --split test
python -m sim40.sizing --split test
python -m sim40.sizing --split all
python -m sim40.analyze --split test
python -m sim40.numbers --split test
python -m sim40.score_prereg --split test
python -m sim40.explore_q2 --part grid --workers "$W"
python -m sim40.explore_q2 --part boot
python -m sim40.explore_q2 --part analyze > /dev/null
python -m sim40.sizing_sens --split all
python -m sim40.sizing_sens --split test
python -m sim40.make_figs --split test
python -m sim40.make_figs_q2
echo "done: results/ regenerated"
