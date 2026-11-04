#!/usr/bin/env python3
"""Run small correctness cases with independent oracles and persistent logs."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone

from compare_grids import compare_files, load_grid, validate_tolerances
from validation_oracle import PROBLEMS, field_at_step, residual_metrics, write_grid

ROOT = Path(__file__).resolve().parents[1]
RESERVED = {"--n", "--mode", "--problem", "--iterations", "--tol", "--check-every", "--solution", "--help"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def parse_json(text):
    def invalid(value):
        raise ValueError("nonfinite JSON constant: " + value)
    return json.loads(text, object_pairs_hook=no_duplicates, parse_constant=invalid)


def integer(value, name, lower=0):
    require(type(value) is int and value >= lower, name + " must be an integer >= " + str(lower))


def finite(value, name, positive=False):
    require(type(value) in (int, float) and math.isfinite(value), name + " must be finite")
    require(value > 0 if positive else value >= 0, name + " has invalid sign")


def keys(obj, allowed, label):
    require(isinstance(obj, dict), label + " must be an object")
    require(not set(obj)-set(allowed), label + " contains unknown keys: " + str(set(obj)-set(allowed)))


def validate_config(config):
    keys(config, ("schema_version", "timeout_seconds", "comparison", "launch", "cases"), "config")
    require(type(config.get("schema_version")) is int and config["schema_version"] == 1, "unsupported schema version")
    config.setdefault("timeout_seconds", 30.0)
    finite(config["timeout_seconds"], "timeout_seconds", True)
    comparison = config.setdefault("comparison", {})
    keys(comparison, ("atol", "rtol", "boundary_atol"), "comparison")
    for name, default in (("atol",1e-10),("rtol",1e-10),("boundary_atol",0.0)):
        comparison.setdefault(name, default)
    validate_tolerances(**comparison)
    launch = config.setdefault("launch", {})
    keys(launch, ("prefix", "extra_args", "env", "expected_ranks", "expected_threads"), "launch")
    for key in ("prefix", "extra_args"):
        launch.setdefault(key, [])
        require(isinstance(launch[key], list) and all(isinstance(v,str) and v for v in launch[key]), key + " must be a string array")
    require(not any(arg.split("=")[0] in RESERVED for arg in launch["extra_args"]), "extra_args must not override case parameters")
    launch.setdefault("env", {})
    require(isinstance(launch["env"],dict), "launch.env must be an object")
    require(all(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*",k) and isinstance(v,str) and "\0" not in v
                for k,v in launch["env"].items()), "invalid environment override")
    for key in ("expected_ranks","expected_threads"):
        launch.setdefault(key,1)
        integer(launch[key], key, 1)
    if "OMP_NUM_THREADS" in launch["env"]:
        require(launch["env"]["OMP_NUM_THREADS"] == str(launch["expected_threads"]), "OMP_NUM_THREADS must match expected_threads")
    require(isinstance(config.get("cases"),list) and config["cases"], "cases must be a nonempty list")
    names = set()
    for case in config["cases"]:
        keys(case, ("name","n","problem","mode","iterations","tol","check_every","expected_exit"), "case")
        require(isinstance(case.get("name"),str) and re.fullmatch(r"[A-Za-z0-9_-]+",case["name"]), "invalid case name")
        require(case["name"] not in names, "duplicate case name")
        names.add(case["name"])
        integer(case.get("n"), "n", 1)
        require(case["n"] <= 255, "acceptance is limited to n<=255; use separate performance tools for large grids")
        require(case.get("problem") in PROBLEMS, "unknown problem")
        require(case["problem"] != "discrete-mixed" or case["n"] >= 3, "discrete-mixed requires n>=3")
        require(case.get("mode") in ("fixed","converge"), "unknown mode")
        integer(case.get("iterations"), "iterations", 1 if case["mode"] == "converge" else 0)
        case.setdefault("tol", 1e-10)
        finite(case["tol"], "tol", True)
        case.setdefault("check_every", 1)
        integer(case["check_every"], "check_every", 1)
        case.setdefault("expected_exit", 0)
        integer(case["expected_exit"], "expected_exit")
        require(case["expected_exit"] in ((0,) if case["mode"] == "fixed" else (0,2)), "invalid expected_exit")
    return config


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False)+"\n")


def invoke(command, env, timeout):
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", env=env,
                                   start_new_session=(os.name == "posix"))
    except OSError as exc:
        return None, "", str(exc), "launch_error"
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr, None
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        stdout, stderr = process.communicate()
        return process.returncode, stdout, stderr, "timeout"


def validate_result(result, case, launch):
    require(isinstance(result,dict), "stdout must contain exactly one JSON object")
    for key, expected in (("schema_version",1),("n",case["n"]),("requested_iterations",case["iterations"]),
                          ("check_every",case["check_every"]),("ranks",launch["expected_ranks"]),
                          ("threads_per_rank",launch["expected_threads"])):
        require(type(result.get(key)) is int and result[key] == expected, "result metadata mismatch: " + key)
    for key in ("mode","problem"):
        require(result.get(key) == case[key], "result metadata mismatch: " + key)
    finite(result.get("tolerance"), "result.tolerance", True)
    require(result["tolerance"] == case["tol"], "tolerance mismatch")
    k = result.get("actual_iterations")
    integer(k, "actual_iterations")
    require(k <= case["iterations"], "iteration count exceeds limit")
    if case["mode"] == "fixed":
        require(k == case["iterations"], "fixed mode did not execute requested count")
        require(result.get("stop_reason") == "fixed_iterations", "wrong fixed stop reason")
    else:
        require(k == case["iterations"] or k % case["check_every"] == 0, "stopped outside a check point")
        require(result.get("stop_reason") == ("tolerance" if case["expected_exit"] == 0 else "max_iterations"), "wrong convergence stop reason")
        require(case["expected_exit"] != 2 or k == case["iterations"], "nonconvergence before iteration limit")
    require(type(result.get("converged")) is bool, "converged must be boolean")
    for key in ("final_relative_residual","final_absolute_residual","rhs_l2","solve_seconds_max","seconds_per_iteration"):
        finite(result.get(key), key)
    expected_checks = k//case["check_every"] + int(k % case["check_every"] != 0) + int(case["mode"] == "converge")
    require(type(result.get("timed_residual_checks")) is int and result["timed_residual_checks"] == expected_checks,
            "wrong residual-check count")
    require(result["converged"] == (result["final_relative_residual"] <= case["tol"]), "inconsistent converged flag")
    if case["mode"] == "converge":
        require(result["converged"] == (case["expected_exit"] == 0), "convergence outcome mismatch")
    return k


def run_case(exe, case, config, output):
    folder = output/case["name"]
    folder.mkdir()
    candidate = folder/"candidate.csv"
    launch = config["launch"]
    command = [*launch["prefix"], str(exe), *launch["extra_args"],
               "--n", str(case["n"]), "--mode", case["mode"], "--problem", case["problem"],
               "--iterations", str(case["iterations"]), "--tol", str(case["tol"]),
               "--check-every", str(case["check_every"]), "--solution", str(candidate)]
    env = os.environ.copy()
    env.update(launch["env"])
    dump(folder/"command.json", {"argv":command, "cwd":os.getcwd(), "env_overrides":launch["env"],
                                "thread_environment":{k:env.get(k) for k in ("OMP_NUM_THREADS","OMP_PLACES","OMP_PROC_BIND")},
                                "timeout_seconds":config["timeout_seconds"]})
    code, stdout, stderr, error = invoke(command, env, config["timeout_seconds"])
    (folder/"stdout.log").write_text(stdout)
    (folder/"stderr.log").write_text(stderr)
    record = {"name":case["name"], "status":"FAIL", "exit_code":code, "expected_exit":case["expected_exit"]}
    try:
        require(error is None, "process " + str(error))
        require(code == case["expected_exit"], "unexpected process exit code")
        result = parse_json(stdout)
        dump(folder/"result.json", result)
        k = validate_result(result, case, launch)
        reference = folder/"reference.csv"
        write_grid(reference, field_at_step(case["n"], case["problem"], k))
        comparison = compare_files(reference,candidate,case["n"],**config["comparison"])
        dump(folder/"comparison.json", comparison)
        require(comparison["status"] == "PASS", "grid comparison " + comparison["status"] + ": " + comparison.get("error","numerical mismatch"))
        field = load_grid(candidate,case["n"],config["comparison"]["boundary_atol"])
        residual = residual_metrics(field,case["n"],case["problem"])
        dump(folder/"independent_residual.json",residual)
        require(result.get("residual_kind") == residual["kind"], "wrong residual normalization")
        for actual, expected in ((result["rhs_l2"],residual["rhs_l2"]),
                                 (result["final_absolute_residual"],residual["absolute"]),
                                 (result["final_relative_residual"],residual["relative"])):
            require(math.isclose(actual,expected,rel_tol=1e-6,abs_tol=1e-12), "reported residual differs from independent recomputation")
        margin = max(1e-13,case["tol"]*1e-6)
        if result["converged"]:
            require(residual["relative"] <= case["tol"]+margin, "independent residual exceeds tolerance")
        if case["mode"] == "converge" and k > 0:
            previous = ((k-1)//case["check_every"])*case["check_every"]
            previous_field = field_at_step(case["n"],case["problem"],previous)
            previous_residual = residual_metrics(previous_field,case["n"],case["problem"])["relative"]
            require(previous_residual >= case["tol"]-margin, "solver missed an earlier convergence check")
        record.update(status="PASS", actual_iterations=k, max_abs_error=comparison["max_abs_error"],
                      relative_l2_error=comparison["relative_l2_error"], independent_relative_residual=residual["relative"])
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        record["error"] = str(exc)
    dump(folder/"verdict.json",record)
    return record


def run_suite(exe, config_path, output):
    config = validate_config(parse_json(config_path.read_text()))
    require(exe.is_file() and os.access(exe,os.X_OK), "executable missing or not executable")
    require(not output.exists(), "output directory already exists; choose a new path to prevent stale results")
    output.mkdir(parents=True)
    dump(output/"config.json",config)
    try:
        commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True))
    except (OSError,subprocess.CalledProcessError):
        commit,dirty = None,None
    dump(output/"run_manifest.json", {"started_utc":datetime.now(timezone.utc).isoformat(),
         "python":sys.version, "executable":str(exe), "executable_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
         "config_sha256":hashlib.sha256(config_path.read_bytes()).hexdigest(),
         "validation_tools_sha256":{name:hashlib.sha256((ROOT/"scripts"/name).read_bytes()).hexdigest()
                                    for name in ("run_acceptance.py","compare_grids.py","validation_oracle.py")},
         "git_commit":commit,
         "working_tree_dirty":dirty, "scope":"correctness_only; platform and parallel execution are not certified by this runner"})
    records = [run_case(exe,case,config,output) for case in config["cases"]]
    failures = sum(row["status"] != "PASS" for row in records)
    summary = {"schema_version":1,"status":"PASS" if not failures else "FAIL", "cases":len(records),
               "passed":len(records)-failures,"failed":failures,"results":records}
    dump(output/"summary.json",summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT/"configs/acceptance_serial.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run_suite(args.exe.resolve(),args.config.resolve(),args.output.resolve())
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({"status":"ERROR","error":str(exc)}),file=sys.stderr)
        return 2
    print(json.dumps({k:v for k,v in summary.items() if k != "results"},indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
