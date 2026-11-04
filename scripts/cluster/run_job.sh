#!/bin/sh
# Run inside an existing scheduler allocation. No scheduler/module assumptions.
set -eu
if [ "$#" -ne 3 ]; then
    echo 'usage: sh scripts/cluster/run_job.sh CONFIG_JSON BUILD_DIR NEW_OUTPUT_DIR' >&2
    exit 2
fi
if [ -z "${SLURM_JOB_ID:-}${PBS_JOBID:-}${LSB_JOBID:-}" ]; then
    echo 'No scheduler job ID: obtain a real Atlas/Vanda allocation first.' >&2
    exit 2
fi
python_bin=${PROJECT3_PYTHON:-python3}
"$python_bin" scripts/run_experiments.py --config "$1" --bin-dir "$2" --output "$3"
"$python_bin" scripts/summarize_results.py --input "$3" --output "$3/summary"
"$python_bin" scripts/plot_results.py --summary "$3/summary/summary.json" --output "$3/figures"
