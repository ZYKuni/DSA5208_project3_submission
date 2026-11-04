#!/usr/bin/env python3
"""Prepare a matched CPU experiment matrix from completed Vanda pilot evidence.

Run inside the formal PBS allocation; this writes configuration only.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess


def load(path):
    return json.loads(path.read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if (args.pilot/'exit_code.txt').read_text().strip()!='0':
        raise ValueError('completed successful pilot required')
    summary=load(args.pilot/'parallel_summary.json')
    if summary.get('status')!='PASS' or summary.get('passed')!=294:
        raise ValueError('complete mixed correctness matrix required')
    assigned=set(os.sched_getaffinity(0))
    topology=subprocess.check_output(['lscpu','-p=CPU,CORE,SOCKET'],text=True)
    physical={(int(core),int(socket)) for line in topology.splitlines() if not line.startswith('#')
              for cpu,core,socket in [line.split(',')] if int(cpu) in assigned}
    maximum=2**int(math.log2(min(16,len(physical))))
    if maximum<4: raise ValueError('at least four assigned physical cores required')
    powers=[2**i for i in range(int(math.log2(maximum))+1)]
    info={}
    for line in subprocess.check_output(['lscpu'],text=True,env=dict(os.environ,LC_ALL='C')).splitlines():
        if ':' in line:
            key,value=line.split(':',1);info[key.strip()]=value.strip()
    calibration=load(args.pilot/'calibration-serial-n2048.json')
    elapsed=calibration['solve_seconds_max']
    if not math.isfinite(elapsed) or elapsed<=0: raise ValueError('invalid calibration')
    iterations=max(1000,math.ceil(15/elapsed*1000/100)*100)
    if iterations>50000: raise ValueError('unexpected calibration: review workload manually')
    def case(label,variant,n,ranks,threads,communication='sendrecv'):
        result=dict(label=label,variant=variant,n=n,ranks=ranks,threads=threads,ranks_per_node=ranks)
        if variant in ('mpi','mpi_openmp'): result['communication']=communication
        return result
    strong=[case('serial','serial',2048,1,1)]
    strong += [case('mpi'+str(p),'mpi',2048,p,1) for p in powers]
    layouts=[(maximum//t,t) for t in powers]
    strong += [case(f'r{r}t{t}','mpi_openmp',2048,r,t) for r,t in layouts if t>1]
    strong += [case('openmp'+str(maximum),'openmp',2048,1,maximum)]
    weak=[case('mpi'+str(p),'mpi',round(512*math.sqrt(p)),p,1) for p in powers]
    weak += [case('hybrid'+str(p),'mpi_openmp',round(512*math.sqrt(p)),p//2,2) for p in powers if p>=4]
    ratio=[case(f'r{r}t{t}','mpi' if t==1 else 'mpi_openmp',2048,r,t) for r,t in layouts]
    r=max(1,maximum//4);t=maximum//r
    communication=[case(comm,'mpi_openmp',2048,r,t,comm) for comm in ('sendrecv','overlap')]
    solution=[case('serial','serial',127,1,1),case('mpi'+str(maximum),'mpi',127,maximum,1),
              case(f'r{r}t{t}','mpi_openmp',127,r,t),case('openmp'+str(maximum),'openmp',127,1,maximum)]
    studies=[]
    for ident,kind,baseline,cases in [('strong_vanda','strong','serial',strong),
            ('weak_vanda','weak','mpi1',weak),('ratio_vanda','ratio',ratio[0]['label'],ratio),
            ('communication_vanda','ratio','sendrecv',communication)]:
        studies.append(dict(id=ident,kind=kind,baseline=baseline,iterations=iterations,check_every=10,cases=cases))
    studies.append(dict(id='solution_vanda',kind='solution',baseline='serial',mode='converge',
                         iterations=200000,tol=1e-8,check_every=20,cases=solution))
    cpu_to_core={int(cpu):(int(core),int(socket)) for line in topology.splitlines() if not line.startswith('#')
                 for cpu,core,socket in [line.split(',')]}
    probes=[]
    combinations=sorted({(c['ranks'],c['threads']) for study in studies for c in study['cases'] if c['variant'] in ('mpi','mpi_openmp')})
    for ranks,threads in combinations:
        code='import os,json; print(json.dumps({"rank":int(os.environ["OMPI_COMM_WORLD_RANK"]),"cpus":sorted(os.sched_getaffinity(0)))}))'
        command=['mpiexec','--map-by',f'slot:PE={threads}','--bind-to','core','--report-bindings','-n',str(ranks),'python3','-c',code]
        proc=subprocess.run(command,text=True,capture_output=True,timeout=60,check=True)
        members=[json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        if len(members)!=ranks or {m['rank'] for m in members}!=set(range(ranks)):
            raise ValueError('affinity probe rank mismatch')
        occupied=set()
        for member in members:
            cpus=set(member['cpus'])
            cores={cpu_to_core[cpu] for cpu in cpus}
            if not cpus<=assigned or len(cores)!=threads or occupied & cores:
                raise ValueError('rank affinity escaped allocation or overlapped physical cores')
            occupied |= cores
        probes.append(dict(ranks=ranks,threads=threads,argv=command,members=members,stderr=proc.stderr))
    config=dict(schema_version=1,scope='cluster',cluster='Vanda',node_count=1,
        cpu_model=info.get('Model name','unknown'),physical_cores_per_node=int(info['Core(s) per socket'])*int(info['Socket(s)']),
        assigned_cpu_ids=sorted(assigned),assigned_physical_cores=len(physical),maximum_test_cores=maximum,binding_probes=probes,
        ranks_per_node=maximum,rank_binding='OpenMPI slot:PE=threads, bind-to core; standalone baseline within PBS cpuset',
        platform_verified=True,binding_verified=True,launcher_verified=True,workload_calibrated=True,
        validation_evidence=str(args.pilot),calibration_seconds=elapsed,calibrated_iterations=iterations,
        warmups=1,repeats=5,timeout_seconds=300,
        launcher=['mpiexec','--map-by','slot:PE={threads}','--bind-to','core','--report-bindings','-n','{ranks}'],
        env={'OMP_DYNAMIC':'FALSE','OMP_PLACES':'cores','OMP_PROC_BIND':'close','OMP_WAIT_POLICY':'ACTIVE'},studies=studies)
    args.output.write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps({'cases':sum(len(s['cases']) for s in studies),'iterations':iterations,
                      'max_cores':maximum,'assigned_cpu_ids':sorted(assigned)},indent=2))


if __name__=='__main__':main()
