#!/bin/bash
# Runs every line of the job file (default grow_jobs.txt) with grow.py, 3 processes at a time (4 kernel threads each).
cd "$(dirname "$0")"
PY=/home/jgon/project/ml/cell-dev/.venv/bin/python
while read -r line; do
  name=$(echo "$line" | awk '{print $2}' | sed 's#pops/##')
  echo "$PY grow.py $line > logs/grow_$name.log 2>&1"
done < "${1:-grow_jobs.txt}" | xargs -P ${P:-3} -I{} bash -c "{} || true"
