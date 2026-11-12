#!/usr/bin/env python3
"""Validate inter-GPU halos, then retain independent 1/2-GPU measurements."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    if not os.environ.get('PBS_JOBID'):
        p.error('run inside PBS')
    a.output.mkdir(parents=True,exist_ok=False)
    os.environ['PCG_DAEMON_LOG_DIR']=str(a.output.resolve())
    root = Path(__file__).resolve().parent.parent
    a.bin_dir = a.bin_dir.resolve()
    hosts = list(dict.fromkeys(Path(os.environ['PBS_NODEFILE']).read_text().split()))
    assert len(hosts) == 2
    meta = dict(job_id=os.environ['PBS_JOBID'],hosts=hosts, gpus_per_host=1,
                stopping_tolerance=5e-9, acceptance_true_residual=1e-8,
                cuda_cli_true_tolerance=1e-8, cuda_recursive_stop_tolerance=5e-9,
                repeats=3,warmups=1,selection='minimum entire row; retain all samples',
                timing='CG loop only, exclude setup and validation; end barrier included',
                binary_hashes={k:hashlib.sha256((a.bin_dir/('poisson_'+k)).read_bytes()).hexdigest()
                               for k in ['serial','cuda']},
                source_hashes={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest()
                               for folder in ['include','src','scripts'] for f in (root/folder).rglob('*')
                               if f.is_file() and f.suffix in ['.cpp','.cu','.cuh','.hpp','.py','.pbs','.sh']})
    meta['source_hashes']['CMakeLists.txt']=hashlib.sha256((root/'CMakeLists.txt').read_bytes()).hexdigest()
    (a.output/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    samples, summaries, references = [], [], {}
    # PBS/TM launches remote daemons into this job's device limits, rather than
    # relying on an SSH session's device visibility on a shared GPU host.
    hf=a.output/'gpu-probe.hosts'
    hf.write_text(''.join(f'{h} slots=1\n' for h in hosts))
    env=dict(os.environ,PCG_EXPECT_GPU_COUNT='1',PCG_SMOKE_DEVICE_MPI='1',
             UCX_TLS='tcp,sm,self,cuda_copy,cuda_ipc',UCX_NET_DEVICES='all')
    command=['mpiexec','--mca','coll_hcoll_enable','0','--mca','coll_ucc_enable','0',
             '--mca','plm_rsh_agent',str(root/'scripts/vanda/pbs_rsh.py'),
             '--mca','pml','ucx','--mca','pml_ucx_tls','any',
             '-x','PCG_EXPECT_GPU_COUNT','-x','PCG_SMOKE_DEVICE_MPI',
             '-x','UCX_TLS','-x','UCX_NET_DEVICES','--hostfile',str(hf.resolve()),'-n','2',
             '--map-by','ppr:1:node','--bind-to','none',str(a.bin_dir/'cluster_gpu_smoke')]
    with (a.output/'gpu-allocation-probe.log').open('w') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    print('GPU_ALLOCATION_DEVICE_MPI=PASS',flush=True)

    def group(experiment,impl,dim,n,g=1,mode='staged'):
        gid=f'{experiment}-{impl}-{dim}d-n{n}-g{g}-{mode}'
        rows=[]
        for rep in range(-1,3):
            rid=gid+('-warmup' if rep<0 else '-r'+str(rep))
            dest=a.output/rid
            hf=dest.with_suffix('.hosts')
            nodes=g
            hf.write_text(''.join(f'{h} slots=1\n' for h in hosts[:nodes]))
            command=['mpiexec','--mca','coll_hcoll_enable','0','--mca','coll_ucc_enable','0',
                     '--mca','plm_rsh_agent',str(root/'scripts/vanda/pbs_rsh.py'),
                     '--mca','pml','ucx','--mca','pml_ucx_tls','any',
                     '-x','PCG_CUDA_HALO','-x','PCG_CUDA_STOP_TOL',
                     '-x','UCX_TLS','-x','UCX_NET_DEVICES','--hostfile',str(hf.resolve()),'-n',str(g),
                     '--map-by',f'ppr:{g//nodes}:node','--bind-to','none',
                     'python3',str(root/'scripts/vanda/pin_rank.py'),'--threads','1',
                     '--record-dir',str((a.output/'placement'/rid).resolve()),
                     str(a.bin_dir/('poisson_'+impl)), '--dim',str(dim),'--n',str(n),
                     '--tol','1e-8' if impl=='cuda' else '5e-9',
                     '--maxit','20000','--repeat','1','--decomp','cart',
                     '--halo','block','--cg','std','--csv',str(dest.with_suffix('.csv').resolve())]
            dest.with_suffix('.command.json').write_text(json.dumps(command)+'\n')
            with dest.with_suffix('.stdout.log').open('w') as out,dest.with_suffix('.stderr.log').open('w') as err:
                env=dict(os.environ,PCG_CUDA_HALO=mode,UCX_TLS='tcp,sm,self,cuda_copy,cuda_ipc',
                         UCX_NET_DEVICES='all',PCG_CUDA_STOP_TOL='5e-9')
                subprocess.run(command,env=env,
                               stdout=out,stderr=err,check=True,timeout=900)
            row,=csv.DictReader(dest.with_suffix('.csv').open())
            assert row['impl']==impl and int(row['dim'])==dim and int(row['n'])==n
            assert int(row['ranks'])==g and int(row['threads'])==1
            assert int(row['gpus'])==(g if impl=='cuda' else 0)
            assert 1<int(row['iters'])<20000 and 0<=float(row['rel_res'])<1e-8
            assert all(math.isfinite(float(row[k])) and float(row[k])>=0
                       for k in ['rel_res','err_l2','t_total','t_stencil','t_halo','t_reduce'])
            assert float(row['t_total'])>0
            if impl!='serial':
                ref=references[dim,n]
                assert abs(int(row['iters'])-int(ref['iters']))<=1
                assert math.isclose(float(row['err_l2']),float(ref['err_l2']),rel_tol=1e-6)
            row.update(experiment=experiment,transport=mode,repeat=rep,group=gid,
                       job_id=os.environ['PBS_JOBID'],nodes=nodes,
                       seconds_per_iteration=float(row['t_total'])/int(row['iters']))
            if rep>=0:
                rows.append(row);samples.append(row);write(a.output/'samples.csv',samples)
            print('SAMPLE',rid,'iters='+row['iters'],'solve='+row['t_total'],flush=True)
        times=[float(r['t_total']) for r in rows]
        best=min(rows,key=lambda r:float(r['t_total']))
        summaries.append(dict(best,seconds_min=min(times),seconds_median=statistics.median(times),
                              seconds_max=max(times),cv=statistics.pstdev(times)/statistics.mean(times),
                              repeats=len(rows),max_true_rel_res=max(float(r['rel_res']) for r in rows),
                              shortest_at_least_one_second=min(times)>=1))
        write(a.output/'summary.csv',summaries)
        if impl=='serial':references[dim,n]=best
        print('GROUP_PASS',gid,'min=',min(times),flush=True)

    # All transports/counts must pass small 2D and 3D serial comparisons first.
    for dim,n in [(2,31),(3,15)]:
        group('preflight','serial',dim,n)
        for mode in ['staged','device']:
            for g in [1,2]:group('preflight','cuda',dim,n,g,mode)
    for dim,n in [(2,2048),(3,256)]:
        group('reference','serial',dim,n)
        for mode in ['staged','device']:
            for g in [1,2]:group('strong','cuda',dim,n,g,mode)
    print('GPU_SCALING_VALIDATION=PASS',len(samples),'accepted samples',flush=True)


def write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        w.writeheader();w.writerows(rows)


if __name__=='__main__':main()
