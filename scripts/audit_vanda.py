#!/usr/bin/env python3
"""Independent archive/per-run/statistics audit; standard library only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
def load(p):
    return json.loads(p.read_text())
def require(condition, message):
    if not condition:
        raise ValueError(message)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a, b):
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
def audit(base):
    measure=base/'measure_1514382'; pilot=base/'pilot_1514325'
    cfg=load(measure/'collection/config.json'); manifest=load(measure/'collection/manifest.json')
    source=load(measure/'source_archive.json')
    for folder in (measure,pilot):
        require((folder/'exit_code.txt').read_text().strip()=='0', 'job failed')
    require(manifest['job_id']=='1514382.stdct-mgmt-02','unexpected measurement job')
    archives=load(base/'archives.json')
    raw_files_verified=0
    for name,record in archives.items():
        require(digest(base/name)==record['sha256'],'archive hash: '+name)
        with tarfile.open(base/name) as archive:
            for member in archive.getmembers():
                parts=Path(member.name).parts
                if not member.isfile() or len(parts)<4:continue
                dirname=parts[2]
                mapping={'vanda-pilot-1514292.stdct-mgmt-02':'pilot_1514292',
                         'vanda-pilot-1514325.stdct-mgmt-02':'pilot_1514325',
                         'vanda-measure-1514382.stdct-mgmt-02':'measure_1514382'}
                if dirname not in mapping:continue
                local=base/mapping[dirname]/Path(*parts[3:])
                if local.is_file():
                    require(local.read_bytes()==archive.extractfile(member).read(),'raw archive mismatch: '+str(local))
                    raw_files_verified+=1
    for line in (measure/'job_sources.sha256').read_text().splitlines():
        expected,name=line.split(maxsplit=1)
        require(digest(measure/Path(name).name)==expected,'job script hash: '+name)
    binaries={Path(line.split(maxsplit=1)[1]).name:line.split()[0]
              for line in (pilot/'binaries.sha256').read_text().splitlines()}
    require(binaries==manifest['binaries'],'pilot/measurement binary identity')
    current_changes=[]
    for name,h in manifest['source_sha256'].items():
        if not (ROOT/name).is_file() or digest(ROOT/name)!=h:
            current_changes.append(name)
    require(not any(p.startswith(('src/','include/')) or p=='CMakeLists.txt'
                    for p in current_changes),'solver differs from measured version')
    # Historical commit check is optional in exported packages without .git.
    historical='unavailable in exported source'
    if (ROOT/'.git').exists():
        for name,h in manifest['source_sha256'].items():
            data=subprocess.check_output(['git','show',source['revision']+':'+name],cwd=ROOT)
            require(hashlib.sha256(data).hexdigest()==h,'historical source hash: '+name)
        historical='verified all '+str(len(manifest['source_sha256']))+' recorded files'
    runs=load(measure/'collection/runs.json'); stored=load(measure/'summary/summary.json')
    require(len({r['run_id'] for r in runs})==len(runs),'duplicate run IDs')
    require(len(runs)==sum(len(s['cases']) for s in cfg['studies'])*(cfg['warmups']+cfg['repeats']),'run count')
    for run in runs:
        folder=measure/'collection'/run['run_id']
        result=load(folder/'result.json'); verdict=load(folder/'verdict.json')
        require(result==json.loads((folder/'stdout.log').read_text()),'stdout mismatch')
        require(verdict==run and run['result']==result,'run index mismatch')
        require(run['status']=='PASS' and run['exit_code']==0,'failed sample')
        require(run['job_id']==manifest['job_id'],'run job identity')
        command=load(folder/'command.json')['argv']
        require(Path(next(x for x in command if Path(x).name.startswith('poisson_'))).name in binaries,'unknown executable')
        for flag,key in [('--n','n'),('--iterations','requested_iterations'),('--check-every','check_every')]:
            require(int(command[command.index(flag)+1])==result[key],'command mismatch: '+flag)
    output=[]
    for study in cfg['studies']:
        rows=[]
        for case in study['cases']:
            group=[r for r in runs if r['study']==study['id'] and r['label']==case['label']]
            require(sorted(r['repeat'] for r in group)==list(range(-cfg['warmups'],cfg['repeats'])),'repetition coverage')
            for r in group:
                require(r['warmup']==(r['repeat']<0),'warmup identity')
                result=r['result']
                require(result['n']==case['n'] and result['ranks']==case['ranks'] and result['threads_per_rank']==case['threads'],'layout mismatch')
                require(result['check_every']==study.get('check_every',1),'residual interval mismatch')
                if study.get('mode','fixed')=='converge':
                    require(result['converged'] and result['actual_iterations']==61160,'convergence work mismatch')
            samples=[r for r in group if not r['warmup']]
            times=[r['result']['solve_seconds_max'] for r in samples]
            require(all(math.isfinite(t) and t>0 for t in times),'invalid timing')
            rows.append(dict(study=study['id'],label=case['label'],cores=case['ranks']*case['threads'],
                             median_seconds=statistics.median(times),min_seconds=min(times),max_seconds=max(times),
                             work_per_core=case['n']**2/(case['ranks']*case['threads']),
                             sample_run_ids=[r['run_id'] for r in samples]))
        baseline=next(r for r in rows if r['label']==study['baseline'])
        for row in rows:
            ratio=baseline['median_seconds']/row['median_seconds']
            row['speedup']=None if study['kind']=='weak' else ratio
            row['efficiency']=ratio if study['kind']=='weak' else ratio/(row['cores']/baseline['cores'])
            row['work_per_core_ratio']=row['work_per_core']/baseline['work_per_core']
            old=next(r for r in stored if r['study']==row['study'] and r['label']==row['label'])
            for key in ('median_seconds','min_seconds','max_seconds','speedup','efficiency','work_per_core','work_per_core_ratio'):
                require(old[key] is None if row[key] is None else close(old[key],row[key]),'summary mismatch: '+row['label']+'/'+key)
        output+=rows
    require(len(stored)==len(output),'summary extra rows')
    return dict(status='PASS',raw_files_verified=raw_files_verified,archives_verified=len(archives),job_id=manifest['job_id'],source_revision=source['revision'],
                historical_source=historical,measured_solver_matches_current=True,current_non_solver_changes=current_changes,
                launches=len(runs),measured_samples=sum(not r['warmup'] for r in runs),configurations=len(output),
                binaries_match_pilot=True,rows=output,
                limits='Archive integrity and consistency, not a new Vanda run or team human sign-off.')
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,default=ROOT/'docs/C/results/Vanda_1103');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=audit(a.evidence);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
