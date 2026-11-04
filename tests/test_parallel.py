#!/usr/bin/env python3
"""Real OpenMP/MPI acceptance. Output contains each invocation and oracle result."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from run_acceptance import run_suite

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bin-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--mpiexec",default="")
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix="run-",dir=a.output.resolve()))
    base=json.loads((ROOT/"configs/acceptance_serial.json").read_text())
    records=[]
    metadata_failures=[]
    scenarios=[("openmp",1,t,"openmp","none") for t in (1,2,4)]
    if a.mpiexec:
        scenarios += [("hybrid",r,t,k,comm) for comm in ("sendrecv","overlap")
                      for r,t,k in ((1,1,"serial"),(3,1,"serial"),(1,1,"openmp"),
                                    (1,2,"openmp"),(1,4,"openmp"),(2,1,"openmp"),
                                    (3,1,"openmp"),(2,2,"openmp"),(3,2,"openmp"),
                                    (3,4,"openmp"),(4,2,"openmp"))]
    for exe_name,ranks,threads,kernel,communication in scenarios:
        config=copy.deepcopy(base)
        config["cases"]=[c for c in config["cases"] if c["n"]>=ranks]
        if exe_name=="hybrid":
            for n in (ranks,2*ranks,127):
                config["cases"].append({"name":f"slab_n{n}","n":n,"problem":"discrete-sine",
                    "mode":"fixed","iterations":5,"check_every":3})
        extra=["--kernel",kernel]
        if exe_name=="hybrid": extra += ["--communication",communication]
        config["launch"]={"prefix":([a.mpiexec,"-n",str(ranks)] if exe_name=="hybrid" else []),
            "extra_args":extra,"expected_ranks":ranks,"expected_threads":threads,
            "env":{"OMP_NUM_THREADS":str(threads),"OMP_DYNAMIC":"FALSE",
                   "OMPI_MCA_rmaps_base_oversubscribe":"1","OMPI_MCA_hwloc_base_binding_policy":"none"}}
        label=f"{exe_name}-r{ranks}-t{threads}-{kernel}-{communication}"
        path=folder/(label+".json");path.write_text(json.dumps(config,indent=2)+"\n")
        result=run_suite((a.bin_dir/("poisson_"+exe_name)).resolve(),path,folder/label)
        for case in config["cases"]:
            result_path=folder/label/case["name"]/"result.json"
            if not result_path.is_file():
                metadata_failures.append(label+"/"+case["name"]+": no result JSON; see verdict/stdout/stderr")
                continue
            actual=json.loads(result_path.read_text())
            expected_variant=("mpi_openmp" if kernel=="openmp" else "mpi-"+communication) if exe_name=="hybrid" else "openmp"
            expected={"communication":communication,"kernel":kernel,"variant":expected_variant,
                      "driver":"b-mpi" if exe_name=="hybrid" else "openmp"}
            for key,value in expected.items():
                if actual.get(key)!=value: metadata_failures.append(f"{label}/{case['name']}: mismatched {key}")
            if exe_name=="hybrid" and actual.get("mpi_thread_provided",0)<1:
                metadata_failures.append(label+"/"+case["name"]+": missing MPI thread support evidence")
        records.append({"configuration":label,**{k:v for k,v in result.items() if k!="results"}})
        print(label,result["status"],result["passed"],flush=True)
    negatives=[]
    if a.mpiexec:
        for extra,message in ((["--n","2"],"ranks <= n"),
                (["--n","7","--kernel","invalid"],"unknown kernel"),
                (["--n","7","--communication","invalid"],"unknown communication"),
                (["--n","0"],"must be positive"),
                (["--n","7","--solution",str(folder/"missing"/"field.csv")],"cannot open solution file")):
            command=[a.mpiexec,"-n","3",str((a.bin_dir/"poisson_hybrid").resolve()),"--iterations","1",*extra]
            env=os.environ.copy();env.update(OMPI_MCA_rmaps_base_oversubscribe="1",OMPI_MCA_hwloc_base_binding_policy="none",OMP_NUM_THREADS="2")
            proc=subprocess.run(command,env=env,text=True,capture_output=True,timeout=30)
            passed=proc.returncode!=0 and message in proc.stderr
            negatives.append({"argv":command,"exit_code":proc.returncode,"stdout":proc.stdout,"stderr":proc.stderr,"passed":passed})
            if not passed: raise RuntimeError("negative test failed: "+message)
        (folder/"negative_tests.json").write_text(json.dumps(negatives,indent=2)+"\n")
    summary={"status":"PASS" if all(r["status"]=="PASS" for r in records) and not metadata_failures else "FAIL",
             "scope":"local real parallel correctness; not cluster performance",
             "configurations":records,"oracle_cases":sum(r["cases"] for r in records),
             "passed":sum(r["passed"] for r in records),"negative_cases":len(negatives),"metadata_failures":metadata_failures}
    (folder/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (a.output/"latest.json").write_text(json.dumps({"folder":str(folder),**summary},indent=2)+"\n")
    return summary["status"]!="PASS"
if __name__=="__main__":
    raise SystemExit(main())
