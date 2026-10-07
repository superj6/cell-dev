#!/bin/bash
# Measures every population given on the command line (npz paths or smoke:<run dir>) that has no meas/ file yet,
# ${P:-3} processes at a time (4 kernel threads each).
cd "$(dirname "$0")"
PY=/home/jgon/project/ml/cell-dev/.venv/bin/python
for src in "$@"; do
  case "$src" in smoke:*) name="smoke40_$(basename "${src#smoke:}")";; *) name=$(basename "$src" .npz);; esac
  [ -f "meas/$name.npz" ] || echo "$PY measure.py $src --lives ${LIVES:-128} > logs/meas_$name.log 2>&1"
done | xargs -P ${P:-3} -I{} bash -c "{} || true"
