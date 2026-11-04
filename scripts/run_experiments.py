#!/usr/bin/env python3
"""Sequential, traceable performance collection; no full-field CSV in timing runs."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
from run_acceptance import invoke, parse_json, validate_result

ROOT=Path(__file__).resolve().parents[1]

def write(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+"\n")

def capture(argv):
    try:
        p=subprocess.run(argv,text=True,capture_output=True,timeout=15)
        return {"argv":argv,"exit_code":p.returncode,"stdout":p.stdout,"stderr":p.stderr}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"argv":argv,"error":str(e)}

def source_snapshot():
    files=[]
    for name in ("include","src","scripts","configs","tests"):
        files += [p for p in (ROOT/name).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [ROOT/"CMakeLists.txt"]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def check_config(c):
    if c.get("schema_version")!=1 or c.get("scope") not in ("local-container","local-native","cluster"):
        raise ValueError("invalid experiment schema/scope")
    if type(c.get("repeats")) is not int or c["repeats"]<3:
        raise ValueError("at least 3 measured repetitions required")
    if type(c.get("warmups")) is not int or c["warmups"]<1:
        raise ValueError("at least one warmup required")
    if not isinstance(c.get("launcher"),list) or not all(isinstance(x,str) for x in c["launcher"]):
        raise ValueError("launcher must be argv array")
    if not c.get("studies"): raise ValueError("no studies")
    seen=set()
    for study in c["studies"]:
        if study["id"] in seen or study["kind"] not in ("strong","weak","ratio","solution"):
            raise ValueError("invalid/duplicate study")
        seen.add(study["id"])
        labels=set()
        for case in study["cases"]:
            if case["label"] in labels: raise ValueError("duplicate case label")
            labels.add(case["label"])
            for key in ("n","ranks","threads"):
                if type(case[key]) is not int or case[key]<1: raise ValueError("invalid "+key)
            if case["ranks"]>case["n"]: raise ValueError("ranks>N")
            if case["variant"] not in ("serial","mpi","openmp","mpi_openmp"): raise ValueError("invalid variant")
            if case["variant"] in ("serial","openmp") and case["ranks"]!=1: raise ValueError("non-MPI ranks must equal 1")
            if case["variant"] in ("serial","mpi") and case["threads"]!=1: raise ValueError("serial kernels need one thread")
            communication=case.get("communication","sendrecv")
            if communication not in ("sendrecv","overlap"): raise ValueError("invalid communication")
            if case["variant"] in ("serial","openmp") and communication!="sendrecv":
                raise ValueError("communication choice requires MPI")
        if study["baseline"] not in labels: raise ValueError("missing baseline")
        if study["kind"]!="solution" and study.get("mode","fixed")!="fixed": raise ValueError("scaling studies require fixed K")
        if type(study["iterations"]) is not int or study["iterations"]<1: raise ValueError("positive K required")
        if study["kind"] in ("strong","ratio","solution") and len({x["n"] for x in study["cases"]})!=1:
            raise ValueError("same N required for strong/ratio/solution studies")
        if study["kind"]=="ratio" and len({x["ranks"]*x["threads"] for x in study["cases"]})!=1:
            raise ValueError("ratio study requires fixed total cores")
    return c

def build_command(config, study, case, bindir):
    """Use B's MPI executable and shared CLI; retain legacy launcher lists."""
    variant=case["variant"]
    executable={"serial":"poisson_serial","mpi":"poisson_mpi",
                "openmp":"poisson_openmp","mpi_openmp":"poisson_hybrid"}[variant]
    command=[]
    if variant in ("mpi","mpi_openmp"):
        values={"ranks":case["ranks"],"threads":case["threads"],
                "ranks_per_node":case.get("ranks_per_node",config.get("ranks_per_node"))}
        command=[x.format(**values) for x in config["launcher"]]
        if not any("{ranks}" in x for x in config["launcher"]):
            command += ["-n",str(case["ranks"])]
    command += [str(bindir/executable)]
    if variant in ("openmp","mpi_openmp"): command += ["--kernel","openmp"]
    if variant in ("mpi","mpi_openmp"):
        command += ["--communication",case.get("communication","sendrecv")]
    command += ["--n",str(case["n"]),"--mode",study.get("mode","fixed"),
                "--problem",study.get("problem","continuous-sine"),
                "--iterations",str(study["iterations"]),
                "--check-every",str(study.get("check_every",1)),"--tol",str(study.get("tol",1e-10))]
    return command

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--bin-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    config=check_config(parse_json(a.config.read_text()))
    if a.output.exists(): raise ValueError("choose a new output directory")
    job=os.environ.get("SLURM_JOB_ID") or os.environ.get("PBS_JOBID") or os.environ.get("LSB_JOBID")
    if config["scope"]=="cluster":
        if config.get("cluster") not in ("Atlas","Vanda") or not job:
            raise ValueError("cluster scope requires Atlas/Vanda and a real scheduler job ID")
        if not all(config.get(key) for key in ("platform_verified","binding_verified","launcher_verified","workload_calibrated")):
            raise ValueError("verify cluster resources, launcher, binding and workload calibration before formal measurement")
        required=("node_count","cpu_model","ranks_per_node","rank_binding","validation_evidence")
        if any(not config.get(k) for k in required): raise ValueError("missing verified cluster metadata")
        cores=config.get("physical_cores_per_node")
        if type(cores) is not int or cores<1: raise ValueError("verified physical_cores_per_node required")
        for study in config["studies"]:
            for case in study["cases"]:
                rpn=case.get("ranks_per_node",config["ranks_per_node"])
                if type(rpn) is not int or rpn<1 or case["ranks"]>config["node_count"]*rpn:
                    raise ValueError("rank layout exceeds allocated nodes")
                if min(case["ranks"],rpn)*case["threads"]>cores:
                    raise ValueError("rank/thread layout exceeds physical cores per node")
    a.output.mkdir(parents=True)
    bindir=a.bin_dir.resolve()
    env=os.environ.copy();env.update(config.get("env",{}))
    snapshot=source_snapshot()
    manifest={"schema_version":1,"started_utc":datetime.now(timezone.utc).isoformat(),
        "scope":config["scope"],"cluster":config.get("cluster"),"job_id":job,
        "node_count":config.get("node_count",1),"platform":platform.platform(),"python":sys.version,
        "cpu_model":config.get("cpu_model"),"ranks_per_node":config.get("ranks_per_node"),
        "rank_binding":config.get("rank_binding"),"env_overrides":config.get("env",{}),
        "git":capture(["git","-C",str(ROOT),"rev-parse","HEAD"]),
        "git_status":capture(["git","-C",str(ROOT),"status","--porcelain"]),
        "compiler":capture(["c++","--version"]),"mpi":capture(["mpiexec","--version"]),
        "lscpu":capture(["lscpu"]),"cmake":capture(["cmake","--version"]),
        "source_sha256":snapshot,"binaries":{},
        "timing":"max rank solve wall time; update, halo, scheduled residuals; excludes init/export/final diagnostics",
        "validation":"performance samples check metadata and finite diagnostics; full-field correctness is separate"}
    for path in sorted(bindir.glob("poisson_*")):
        if path.is_file(): manifest["binaries"][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    flags=bindir/"compile_commands.json"
    if flags.exists(): (a.output/"compile_commands.json").write_bytes(flags.read_bytes())
    write(a.output/"manifest.json",manifest);write(a.output/"config.json",config)
    records=[]
    for study in config["studies"]:
        for case in study["cases"]:
            variant=case["variant"]
            command=build_command(config,study,case,bindir)
            mode=study.get("mode","fixed"); problem=study.get("problem","continuous-sine")
            tol=study.get("tol",1e-10);check=study.get("check_every",1)
            runenv=env.copy();runenv["OMP_NUM_THREADS"]=str(case["threads"])
            for repeat in range(-config["warmups"],config["repeats"]):
                run_id=f"run-{len(records):04d}";folder=a.output/run_id;folder.mkdir()
                record={"run_id":run_id,"study":study["id"],"study_kind":study["kind"],"baseline":study["baseline"],
                    **case,"repeat":repeat,"warmup":repeat<0,"scope":config["scope"],"job_id":job,"status":"FAIL"}
                write(folder/"command.json",{"argv":command,"env_overrides":{**config.get("env",{}),"OMP_NUM_THREADS":str(case["threads"])}})
                code,stdout,stderr,error=invoke(command,runenv,config.get("timeout_seconds",180))
                (folder/"stdout.log").write_text(stdout);(folder/"stderr.log").write_text(stderr)
                record["exit_code"]=code
                try:
                    if error or code!=0: raise ValueError(error or "nonzero exit code")
                    result=parse_json(stdout)
                    validate_result(result,{"n":case["n"],"iterations":study["iterations"],"check_every":check,"mode":mode,
                        "problem":problem,"tol":tol,"expected_exit":0},{"expected_ranks":case["ranks"],"expected_threads":case["threads"]})
                    expected_variant="mpi-"+case.get("communication","sendrecv") if variant=="mpi" else variant
                    if result["variant"]!=expected_variant: raise ValueError("variant mismatch")
                    expected_comm=case.get("communication","sendrecv") if variant in ("mpi","mpi_openmp") else "none"
                    if result.get("communication")!=expected_comm: raise ValueError("communication mismatch")
                    if variant in ("mpi","mpi_openmp") and result.get("driver")!="b-mpi":
                        raise ValueError("MPI driver mismatch")
                    if result["solve_seconds_max"]<=0: raise ValueError("nonpositive performance time")
                    record.update(status="PASS",result=result)
                    write(folder/"result.json",result)
                except (ValueError,KeyError,TypeError) as e:
                    record["error"]=str(e)
                write(folder/"verdict.json",record);records.append(record)
                write(a.output/"runs.json",records)
            print(study["id"],case["label"],flush=True)
    failures=sum(r["status"]!="PASS" for r in records)
    write(a.output/"collection_summary.json",{"status":"PASS" if not failures else "FAIL","runs":len(records),"failed":failures})
    return bool(failures)
if __name__=="__main__":
    raise SystemExit(main())
