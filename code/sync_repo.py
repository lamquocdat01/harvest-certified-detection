#!/usr/bin/env python3
"""sync_repo.py: copy the release allow-list from the topic folder into the local repository
D:\\Repos\\harvest-certified-detection (nothing outside RELEASE is ever copied; no raw data, no checkpoints).
Writes RELEASE_FILES.txt (path, size, SHA-256) into the repository. Does not commit or push."""
from __future__ import annotations

import hashlib
import pathlib
import shutil

TOPIC = pathlib.Path(__file__).resolve().parents[1]
REPO = pathlib.Path(r"D:\Repos\harvest-certified-detection")
RELEASE = {
    "code": ["sim40/*.py", "sim40/tests/*.py", "paper/*.py", "paper/build_paper.sh", "reproduce.sh",
             "compare_results.py", "sync_repo.py"],
    "results": ["summary_test.json", "numbers.json", "prereg_score_test.json", "boot_test.json",
                "F5_sizing_test.json", "F5_sizing_all.json", "exploratory_q2_test.json",
                "exploratory_q2_boot_test.json", "exploratory_q2_boot_test.buggy_holm_direction.json",
                "sizing_block_sens_all.json", "sizing_block_sens_test.json", "interp_sensitivity_test.json",
                "corpus_rebuild_check.json", "event_corpus_40.csv", "numbers_provenance.json",
                "figure_provenance.json", "figs/*_test.pdf", "figs/*_test.png", "figs/F2_caption_test.txt"],
    "P1": ["PREREG_40.md", "PREREG_40.sha256", "PREREG_40_v1.1_exploratory.md", "PREREG_40_v1.1_exploratory.sha256"],
}
DEST = {"code": "code", "results": "results", "P1": "prereg"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    lines = []
    for src, pats in RELEASE.items():
        for pat in pats:
            for f in sorted((TOPIC / src).glob(pat)):
                if "__pycache__" in f.parts:
                    continue
                rel = f.relative_to(TOPIC / src)
                dst = REPO / DEST[src] / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
                lines.append(f"{(pathlib.Path(DEST[src]) / rel).as_posix()}\t{f.stat().st_size}\t{sha(dst)}")
    (REPO / "RELEASE_FILES.txt").write_text("path\tbytes\tsha256\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} files synced to {REPO}")


if __name__ == "__main__":
    main()
