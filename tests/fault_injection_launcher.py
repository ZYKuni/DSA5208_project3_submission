#!/usr/bin/env python3
"""TEST FIXTURE ONLY: intentionally corrupt real output to test the validator."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time

mode=os.environ.get("ACCEPTANCE_TEST_FAULT")
if mode=="timeout":
    time.sleep(60)
if mode=="environment":
    assert os.environ["TEST_MARKER"]=="present"
proc=subprocess.run(sys.argv[1:],text=True,capture_output=True)
sys.stderr.write(proc.stderr)
if sys.argv[sys.argv.index("--n")+1]!="7":
    sys.stdout.write(proc.stdout)
    raise SystemExit(proc.returncode)
if mode=="wrong_exit":
    raise SystemExit(9)
if mode=="bad_json":
    print("not-json")
    raise SystemExit(0)
result=json.loads(proc.stdout)
path=Path(sys.argv[sys.argv.index("--solution")+1])
if mode=="missing_file":
    path.unlink()
elif mode=="transpose":
    with path.open(newline="") as stream:
        rows=list(csv.DictReader(stream))
    values={(r["global_i"],r["global_j"]):r["u"] for r in rows}
    with path.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["global_i","global_j","u"],lineterminator="\n")
        writer.writeheader()
        for row in rows:
            row["u"]=values[row["global_j"],row["global_i"]]
            writer.writerow(row)
elif mode=="bad_metadata":
    result["n"]+=1
elif mode=="bad_residual":
    result["final_relative_residual"]+=0.1
elif mode=="bad_iterations":
    result["actual_iterations"]-=1
elif mode=="extra_stdout":
    print("debug output")
print(json.dumps(result))
raise SystemExit(proc.returncode)
