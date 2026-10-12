#!/usr/bin/env bash
# build_paper.sh (topic 40, IEEE IoT-J): numbers -> figures -> bib -> LaTeX -> verify -> pdfinfo.
# Usage: bash code/paper/build_paper.sh [--final]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
LATEX="$ROOT/submission_package/IoTJ/latex"
FINAL="${1:-}"
# fixed timestamps -> byte-reproducible figure PDFs (matplotlib) and LaTeX PDFs (pdfTeX); 2026-10-12 00:00 UTC
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1791763200}" FORCE_SOURCE_DATE=1 PYTHONIOENCODING=utf-8
echo "### 1/6 numbers.tex";  python "$HERE/gen_numbers.py"
echo "### 2/6 figures";      python "$HERE/gen_figures.py"
echo "### 3/6 refs.bib";     python "$HERE/make_bib.py" > "$ROOT/results/log_make_bib.txt"; tail -1 "$ROOT/results/log_make_bib.txt"
echo "### 4/6 pdflatex/bibtex"
cd "$LATEX"
rm -f main.aux main.bbl main.blg main.log main.out main.pdf
pdflatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
bibtex main >/dev/null || true
pdflatex -interaction=nonstopmode main.tex >/dev/null
pdflatex -interaction=nonstopmode main.tex >/dev/null
for f in supp cover_letter; do
  if [ -f "$f.tex" ]; then
    rm -f $f.aux $f.bbl; pdflatex -interaction=nonstopmode $f.tex >/dev/null
    [ -f $f.aux ] && grep -q bibdata $f.aux && (bibtex $f >/dev/null || true)
    pdflatex -interaction=nonstopmode $f.tex >/dev/null; pdflatex -interaction=nonstopmode $f.tex >/dev/null
  fi
done
echo "### 5/6 verify_render"
cd "$ROOT"; RC=0; python "$HERE/verify_render.py" $FINAL || RC=$?
echo "### 6/6 pdfinfo"; for f in main supp cover_letter; do [ -f "$LATEX/$f.pdf" ] && echo "$f: $(pdfinfo "$LATEX/$f.pdf" | grep Pages)"; done
exit $RC
