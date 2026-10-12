#!/usr/bin/env bash
# build_fgcs.sh (topic 40, Future Generation Computer Systems): numbers -> figures -> bib (elsarticle) ->
# shared generated tables -> highlights -> LaTeX (main, supp, cover letter) -> verify -> pdfinfo.
# Shares numbers.tex / prereg_table.tex / sizing_table.tex / figures with the IoT-J build (Plan B).
# Usage: bash code/paper/build_fgcs.sh [--final]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
IOTJ="$ROOT/submission_package/IoTJ/latex"
LATEX="$ROOT/submission_package/FGCS/latex"
FINAL="${1:-}"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1791763200}" FORCE_SOURCE_DATE=1 PYTHONIOENCODING=utf-8
echo "### 1/7 numbers.tex";  python "$HERE/gen_numbers.py"
echo "### 2/7 figures";      python "$HERE/gen_figures.py"
echo "### 3/7 refs.bib (elsarticle)"; python "$HERE/make_bib.py" --style fgcs > "$ROOT/results/log_make_bib_fgcs.txt"; tail -1 "$ROOT/results/log_make_bib_fgcs.txt"
echo "### 4/7 shared generated files + highlights"
mkdir -p "$LATEX/figures"
cp "$IOTJ/numbers.tex" "$IOTJ/prereg_table.tex" "$IOTJ/sizing_table.tex" "$IOTJ/supp_tables.tex" "$LATEX/"
cp "$IOTJ"/figures/*.pdf "$LATEX/figures/"
python "$HERE/fgcs_extras.py"
echo "### 5/7 pdflatex/bibtex"
cd "$LATEX"
for f in main supp cover_letter; do
  rm -f $f.aux $f.bbl $f.blg $f.log $f.out $f.pdf
  pdflatex -interaction=nonstopmode -halt-on-error $f.tex >/dev/null || { tail -30 $f.log; exit 1; }
  grep -q bibdata $f.aux && (bibtex $f >/dev/null || true)
  pdflatex -interaction=nonstopmode $f.tex >/dev/null; pdflatex -interaction=nonstopmode $f.tex >/dev/null
done
echo "### 6/7 verify_render_fgcs"
cd "$ROOT"; RC=0; python "$HERE/verify_render_fgcs.py" $FINAL || RC=$?
echo "### 7/7 pdfinfo"; for f in main supp cover_letter; do echo "$f: $(pdfinfo "$LATEX/$f.pdf" | grep Pages)"; done
exit $RC
