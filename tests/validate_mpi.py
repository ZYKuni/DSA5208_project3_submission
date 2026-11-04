#!/usr/bin/env python3
"""Real MPI processes, A's independent oracle, and direct V0 comparison."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_acceptance import run_suite, invoke
from compare_grids import compare_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--serial", type=Path, required=True)
    parser.add_argument("--mpiexec", type=Path, required=True)
    parser.add_argument("--numproc-flag", default="-n")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=args.output.resolve()))
    base = json.loads((ROOT / "configs/acceptance_serial.json").read_text())
    records, suites, failures = [], [], []
    for ranks in (1, 2, 3, 4):
        for communication in ("sendrecv", "overlap"):
            label = "%s-r%d" % (communication, ranks)
            config = copy.deepcopy(base)
            config["cases"] = [c for c in config["cases"] if c["n"] >= ranks]
            # Explicit one/two-row slabs, larger messages, all built-in RHS types.
            for n in (ranks, 2 * ranks, 127):
                config["cases"].append(dict(name="slab_n%d" % n, n=n, problem="discrete-sine",
                    mode="fixed", iterations=5, check_every=3))
            config["launch"] = dict(prefix=[str(args.mpiexec.resolve()), args.numproc_flag, str(ranks)],
                extra_args=["--communication", communication], env={"OMP_NUM_THREADS": "1"},
                expected_ranks=ranks, expected_threads=1)
            config_path = output / (label + ".json")
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            folder = output / label
            suite = run_suite(args.exe.resolve(), config_path, folder)
            suites.append(dict(name=label, summary=suite,
                               manifest=json.loads((folder / "run_manifest.json").read_text())))
            for case in config["cases"]:
                case_folder = folder / case["name"]
                record = dict(suite=label, case=case, artifacts={})
                for filename in ("command.json", "result.json", "verdict.json", "comparison.json", "independent_residual.json"):
                    path = case_folder / filename
                    if path.exists(): record["artifacts"][filename] = json.loads(path.read_text())
                record["stdout"] = (case_folder / "stdout.log").read_text()
                record["stderr"] = (case_folder / "stderr.log").read_text()
                if record["artifacts"]["verdict.json"]["status"] == "PASS":
                    command = [str(args.serial.resolve()), "--n", str(case["n"]), "--problem", case["problem"],
                        "--mode", case["mode"], "--iterations", str(case["iterations"]),
                        "--tol", str(case.get("tol", 1e-10)), "--check-every", str(case.get("check_every", 1)),
                        "--solution", str(case_folder / "serial.csv")]
                    code, stdout, stderr, error = invoke(command, os.environ.copy(), 30)
                    record["serial"] = dict(command=command, exit_code=code, stdout=stdout, stderr=stderr, error=error)
                    comparison = compare_files(case_folder / "serial.csv", case_folder / "candidate.csv", case["n"])
                    record["serial_comparison"] = comparison
                    if error or code != case.get("expected_exit", 0) or comparison["status"] != "PASS":
                        failures.append(label + "/" + case["name"] + ": V0 comparison failed")
                else:
                    failures.append(label + "/" + case["name"] + ": oracle failed")
                records.append(record)
            print(label, suite["status"], suite["passed"], "/", suite["cases"], flush=True)
    negatives = []
    for extra, message in ((["--n", "1"], "ranks <= n"),
                           (["--n", "7", "--communication", "invalid"], "unknown communication"),
                           (["--n", "0"], "must be positive"),
                           (["--n", "7", "--solution", str(output / "missing" / "field.csv")], "cannot open solution file")):
        command = [str(args.mpiexec.resolve()), args.numproc_flag, "2", str(args.exe.resolve()), "--iterations", "1", *extra]
        code, stdout, stderr, error = invoke(command, os.environ.copy(), 20)
        passed = error is None and code not in (None, 0) and message in stderr
        negatives.append(dict(command=command, exit_code=code, stdout=stdout, stderr=stderr, error=error, passed=passed))
        if not passed: failures.append("negative test: " + message)
    evidence = dict(scope="local correctness only; no cluster performance claims", suites=suites,
                    cases=records, negative_tests=negatives, failures=failures)
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    summary = dict(status="FAIL" if failures else "PASS", numerical_cases=len(records),
                   negative_cases=len(negatives), failures=failures, evidence=str(output / "evidence.json"))
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return bool(failures)


if __name__ == "__main__":
    sys.exit(main())
