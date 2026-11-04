#!/usr/bin/env python3
"""Aggregate complete repeated runs; preserve missing/failed cases in CSV."""
import argparse
import csv
import json
from pathlib import Path
import statistics

def summarize(root):
    config=json.loads((root/"config.json").read_text())
    runs=json.loads((root/"runs.json").read_text())
    rows=[]
    for study in config["studies"]:
        local=[]
        for case in study["cases"]:
            samples=[r for r in runs if r["study"]==study["id"] and r["label"]==case["label"] and not r["warmup"]]
            good=[r for r in samples if r["status"]=="PASS"]
            times=[r["result"]["solve_seconds_max"] for r in good]
            full=len(samples)==config["repeats"] and len(good)==len(samples)
            if any(r["status"]!="PASS" for r in runs if r["study"]==study["id"] and r["label"]==case["label"] and r["warmup"]):
                full=False
            local.append({"study":study["id"],"kind":study["kind"],"scope":config["scope"],**case,
                "cores":case["ranks"]*case["threads"],"samples":len(times),"status":"PASS" if full else "INCOMPLETE",
                "median_seconds":statistics.median(times) if full else None,
                "min_seconds":min(times) if full else None,"max_seconds":max(times) if full else None,
                "iterations":study["iterations"],"check_every":study.get("check_every",1),
                "baseline":study["baseline"],"speedup":None,"efficiency":None,"work_per_core":case["n"]**2/(case["ranks"]*case["threads"])})
        base=next(r for r in local if r["label"]==study["baseline"])
        for row in local:
            if row["status"]==base["status"]=="PASS":
                ratio=base["median_seconds"]/row["median_seconds"]
                if study["kind"]=="weak":
                    row["efficiency"]=ratio
                else:
                    row["speedup"]=ratio
                    row["efficiency"]=ratio/(row["cores"]/base["cores"])
                row["work_per_core_ratio"]=row["work_per_core"]/base["work_per_core"]
            else: row["work_per_core_ratio"]=None
        rows+=local
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    rows=summarize(a.input)
    (a.output/"summary.json").write_text(json.dumps(rows,indent=2)+"\n")
    with (a.output/"summary.csv").open("w",newline="") as f:
        fields=list(dict.fromkeys(key for row in rows for key in row))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    return 0 if all(r["status"]=="PASS" for r in rows) else 1
if __name__=="__main__":raise SystemExit(main())
