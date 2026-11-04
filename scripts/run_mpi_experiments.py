#!/usr/bin/env python3
"""Collect matched V0/V1/V3 fixed-work timings inside an existing allocation.

Does not submit jobs or infer cluster resources. Launcher argv is never a shell.
All warmups/failures retain logs; only successful measured runs enter summaries.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone

from run_acceptance import invoke

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_METADATA = ("cluster", "job_id", "node_count", "cpu_model", "physical_cores_per_node",
    "compiler", "flags", "mpi_version", "rank_binding", "validation_evidence")


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def positive(value):
    return type(value) is int and value > 0


def validate(config, dry_run):
    if config.get("schema_version") != 1: raise ValueError("expected schema_version=1")
    if not positive(config.get("repeats")) or config["repeats"] < 3:
        raise ValueError("at least 3 measured repeats required")
    if not positive(config.get("warmups")): raise ValueError("at least one warmup required")
    timeout = config.get("timeout_seconds")
    if type(timeout) not in (float, int) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("positive finite timeout_seconds required")
    prefix = config.get("launcher")
    if not isinstance(prefix, list) or not prefix or not all(isinstance(s, str) for s in prefix):
        raise ValueError("launcher must be a nonempty argv list")
    if not any("{ranks}" in s for s in prefix): raise ValueError("launcher must contain {ranks}")
    for key in ("mpi_exe", "serial_exe"):
        if not isinstance(config.get(key), str) or not config[key]: raise ValueError(key + " required")
        if not dry_run and not os.access(config[key], os.X_OK): raise ValueError(key + " is not executable")
    metadata = config.get("metadata", {})
    for key in REQUIRED_METADATA:
        if not metadata.get(key) or (not dry_run and "FILL" in str(metadata[key])):
            raise ValueError("fill metadata." + key + " from the actual allocation/validation")
    if not config.get("cases"): raise ValueError("cases must not be empty")
    for case in config["cases"]:
        for key in ("n", "iterations", "check_every", "ranks", "ranks_per_node"):
            if not positive(case.get(key)): raise ValueError("case requires positive " + key)
        if case["ranks"] > case["n"]: raise ValueError("ranks must not exceed n")
        if case.get("communication") not in ("sendrecv", "overlap"): raise ValueError("invalid communication")
        if not dry_run:
            nodes, cores = metadata["node_count"], metadata["physical_cores_per_node"]
            if not positive(nodes) or not positive(cores): raise ValueError("actual node/core counts must be positive integers")
            if case["ranks_per_node"] > cores or case["ranks"] > nodes * case["ranks_per_node"]:
                raise ValueError("resource metadata cannot accommodate requested ranks")
    env = config.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("env must map strings to strings")
    if env.get("OMP_NUM_THREADS", "1") != "1": raise ValueError("this is the MPI-only experiment collector")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    config = json.loads(args.config.read_text())
    validate(config, args.dry_run)
    args.output.mkdir(parents=True, exist_ok=False)
    dump(args.output / "config.json", config)
    env = os.environ.copy()
    overrides = dict(config.get("env", {}), OMP_NUM_THREADS="1")
    env.update(overrides)
    work = []
    seen_serial = set()
    for case in config["cases"]:
        key = (case["n"], case["iterations"], case["check_every"])
        if key not in seen_serial:
            work.append(("serial", dict(case, ranks=1, ranks_per_node=1)))
            seen_serial.add(key)
        work.append(("mpi-" + case["communication"], case))
    plan = []
    for variant, case in work:
        command = ([config["serial_exe"]] if variant == "serial" else
            [s.format(ranks=case["ranks"], ranks_per_node=case["ranks_per_node"]) for s in config["launcher"]]
            + [config["mpi_exe"], "--communication", case["communication"]])
        command += ["--n", str(case["n"]), "--mode", "fixed", "--problem", "continuous-sine",
                    "--iterations", str(case["iterations"]), "--check-every", str(case["check_every"])]
        for repeat in range(-config["warmups"], config["repeats"]):
            plan.append(dict(variant=variant, case=case, repeat=repeat, warmup=repeat < 0, argv=command))
    dump(args.output / "plan.json", dict(dry_run=args.dry_run, env_overrides=overrides, runs=plan))
    if args.dry_run:
        print("Plan only: %d launches; no programs executed" % len(plan))
        return 0
    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=ROOT, text=True).strip()
    source_paths = [*ROOT.glob("src/*.cpp"), *ROOT.glob("include/*.hpp"), ROOT / "CMakeLists.txt", Path(__file__)]
    manifest = dict(started_utc=datetime.now(timezone.utc).isoformat(), host=platform.platform(),
        commit=git("rev-parse", "HEAD"), dirty=bool(git("status", "--porcelain")),
        sources_sha256={str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in source_paths},
        executables_sha256={key: hashlib.sha256(Path(config[key]).read_bytes()).hexdigest() for key in ("mpi_exe", "serial_exe")},
        scheduler_environment={k: v for k, v in os.environ.items() if k.startswith(("SLURM_", "PBS_", "LSB_"))})
    dump(args.output / "manifest.json", manifest)
    rows = []
    for i, run in enumerate(plan):
        folder = args.output / ("run-%04d" % i)
        folder.mkdir()
        dump(folder / "command.json", run)
        code, stdout, stderr, error = invoke(run["argv"], env, config["timeout_seconds"])
        (folder / "stdout.log").write_text(stdout)
        (folder / "stderr.log").write_text(stderr)
        row = dict(run_id=folder.name, variant=run["variant"], **run["case"], repeat=run["repeat"],
                   warmup=run["warmup"], status="FAIL", exit_code=code)
        try:
            if error or code != 0: raise ValueError(error or "nonzero exit")
            result = json.loads(stdout)
            for key, expected in (("variant", run["variant"]), ("n", run["case"]["n"]),
                ("ranks", run["case"]["ranks"]), ("threads_per_rank", 1), ("mode", "fixed"),
                ("problem", "continuous-sine"), ("actual_iterations", run["case"]["iterations"]),
                ("check_every", run["case"]["check_every"])):
                if result[key] != expected: raise ValueError("mismatched " + key)
            for key in ("solve_seconds_max", "final_relative_residual"):
                if not math.isfinite(result[key]) or result[key] < 0: raise ValueError("invalid " + key)
            if result["solve_seconds_max"] == 0: raise ValueError("zero duration")
            row.update(status="PASS", solve_seconds_max=result["solve_seconds_max"],
                       final_relative_residual=result["final_relative_residual"])
            dump(folder / "result.json", result)
        except (ValueError, KeyError, TypeError) as exc:
            row["error"] = str(exc)
        dump(folder / "verdict.json", row)
        rows.append(row)
        print(folder.name, run["variant"], row["status"], flush=True)
    columns = sorted(set().union(*(row.keys() for row in rows)))
    with (args.output / "runs.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    groups = {}
    for row in rows:
        if row["status"] != "PASS" or row["warmup"]: continue
        key = tuple(row[k] for k in ("variant", "n", "iterations", "check_every", "ranks", "ranks_per_node"))
        groups.setdefault(key, []).append(row["solve_seconds_max"])
    summary = [dict(zip(("variant", "n", "iterations", "check_every", "ranks", "ranks_per_node"), key),
                    samples=len(times), median_seconds=statistics.median(times),
                    min_seconds=min(times), max_seconds=max(times)) for key, times in groups.items()]
    failed = sum(row["status"] != "PASS" for row in rows)
    dump(args.output / "summary.json", dict(status="FAIL" if failed else "PASS", failed_runs=failed,
         scope="timings from metadata.cluster only; validation_evidence is separately supplied", groups=summary))
    return int(failed > 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print("error:", exc, file=sys.stderr)
        sys.exit(2)
