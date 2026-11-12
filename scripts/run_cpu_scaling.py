#!/usr/bin/env python3
"""Run and validate CPU experiments inside a four-node PBS allocation.

Keep every independent sample. Select the fastest complete row per group only
when producing the final summary; retain median/CV as variability evidence.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time


def weak_cases(dim, base, ranks):
    return [(p, round(base*p**(1/dim))) for p in ranks]


def serial_sizes(dim):
    if dim == 2:
        return [128,256,512,1024,2048]
    return sorted({32,64,128,192,288} | {n for p,n in weak_cases(3,32,[1,8,64,216,256])})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--suite', choices=['pilot', 'full', 'weak3d'], default='full')
    a = p.parse_args()
    if not os.environ.get('PBS_JOBID'):
        p.error('run within PBS, not on a login node')
    a.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parent.parent
    a.bin_dir = a.bin_dir.resolve()
    hosts = list(dict.fromkeys(Path(os.environ['PBS_NODEFILE']).read_text().split()))
    if len(hosts) != 4:
        raise ValueError('exactly four physical hosts are required')
    meta = dict(job_id=os.environ['PBS_JOBID'], hosts=hosts, suite=a.suite,
                timing='CG loop only, initialisation/allocation/validation excluded; end barrier included',
                stopping_tolerance=5e-9, acceptance_true_residual=1e-8,
                repeats=3, warmups=1, selection='minimum entire row; all samples retained',
                mpi='HPC-X; explicit PBS host subset; ppr placement; rank-local physical-core pinning',
                source_hashes={str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
                               for pattern in ['include/*.hpp', 'src/common/*.cpp', 'src/mpi/*.cpp',
                                               'src/mpi/*.hpp', 'src/serial/*pp', 'src/hybrid_omp/*pp',
                                               'scripts/run_cpu_scaling.py', 'scripts/vanda/pin_rank.py']
                               for f in root.glob(pattern)},
                binary_hashes={k: hashlib.sha256((a.bin_dir/('poisson_'+k)).read_bytes()).hexdigest()
                               for k in ['serial', 'mpi', 'omp']})
    (a.output/'manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    samples, references, summaries = [], {}, []

    def launch(impl, ranks, threads, record):
        nodes = min(4, max(1, math.ceil(ranks*threads/72)))
        if ranks % nodes:
            raise ValueError('rank count must divide selected host count')
        record.parent.mkdir(parents=True, exist_ok=True)
        hostfile = record.parent / (record.name+'.hosts')
        hostfile.write_text(''.join(f'{h} slots=72\n' for h in hosts[:nodes]))
        return ['mpiexec', '--mca', 'coll_hcoll_enable', '0', '--mca', 'coll_ucc_enable', '0',
                '--mca', 'pml', 'ob1', '--mca', 'btl', 'self,vader,tcp',
                '--hostfile', str(hostfile.resolve()), '-n', str(ranks),
                '--map-by', f'ppr:{ranks//nodes}:node', '--bind-to', 'none',
                'python3', str(root/'scripts/vanda/pin_rank.py'), '--threads', str(threads),
                '--record-dir', str(record.resolve())]

    def check_placement(record, ranks, threads):
        rows = [json.loads(f.read_text()) for f in record.glob('rank-*.json')]
        if len(rows) != ranks:
            raise ValueError('missing rank placement record')
        occupied = set()
        for r in rows:
            if len(r['cpus']) != threads or r['affinity'] != sorted(r['cpus']):
                raise ValueError('affinity not enforced')
            for core in r['physical_cores']:
                k = (r['host'], *core)
                if k in occupied:
                    raise ValueError('physical-core overlap')
                occupied.add(k)
        return len({r['host'] for r in rows}), len(occupied)

    def run_group(experiment, impl, dim, n, ranks=1, threads=1,
                  decomp='cart', halo='block', cg='std'):
        gid = f'{experiment}-{impl}-{dim}d-n{n}-p{ranks}-t{threads}-{decomp}-{halo}-{cg}'
        rows = []
        for rep in range(-1, 3):
            rid = gid+('-warmup' if rep < 0 else '-r'+str(rep))
            dest = a.output/rid
            record = a.output/'placement'/rid
            command = launch(impl, ranks, threads, record)
            command += [str(a.bin_dir/('poisson_'+impl)), '--dim', str(dim), '--n', str(n),
                        '--tol', '5e-9', '--maxit', '20000', '--repeat', '1',
                        '--decomp', decomp, '--halo', halo, '--cg', cg,
                        '--csv', str(dest.with_suffix('.csv').resolve())]
            dest.with_suffix('.command.json').write_text(json.dumps(command)+'\n')
            start = time.monotonic()
            with dest.with_suffix('.stdout.log').open('w') as out, dest.with_suffix('.stderr.log').open('w') as err:
                subprocess.run(command, stdout=out, stderr=err, check=True, timeout=900)
            row, = csv.DictReader(dest.with_suffix('.csv').open())
            actual_nodes, actual_cores = check_placement(record, ranks, threads)
            for k, v in dict(impl=impl, dim=dim, n=n, ranks=ranks, threads=threads, gpus=0, cg=cg).items():
                if (row[k] if isinstance(v, str) else int(row[k])) != v:
                    raise ValueError(f'{rid}: {k} mismatch')
            if impl != 'serial' and (row['decomp'] != decomp or row['halo'] != halo):
                raise ValueError('variant labels mismatch')
            numbers = [float(row[k]) for k in ['rel_res', 'err_l2', 't_total', 't_stencil', 't_halo', 't_reduce']]
            if not all(math.isfinite(x) and x >= 0 for x in numbers) or not (
                    1 < int(row['iters']) < 20000 and float(row['rel_res']) < 1e-8 and float(row['t_total']) > 0):
                raise ValueError(f'{rid}: invalid/unconverged result')
            key = (dim, n)
            if impl != 'serial':
                ref = references[key]
                if abs(int(row['iters'])-int(ref['iters'])) > 1 or not math.isclose(
                        float(row['err_l2']), float(ref['err_l2']), rel_tol=1e-6):
                    raise ValueError(f'{rid}: serial comparison failed')
            row.update(experiment=experiment, repeat=rep, job_id=os.environ['PBS_JOBID'],
                       group=gid, nodes=actual_nodes, physical_cores=actual_cores,
                       seconds_per_iteration=float(row['t_total'])/int(row['iters']),
                       points_per_core=n**dim/(ranks*threads),
                       process_seconds=time.monotonic()-start)
            if rep >= 0:
                rows.append(row)
                samples.append(row)
                write_csv(a.output/'samples.csv', samples)
            print('SAMPLE', rid, 'iters='+row['iters'], 'solve='+row['t_total'],
                  'cores='+str(actual_cores), 'nodes='+str(actual_nodes), flush=True)
        best = min(rows, key=lambda r: float(r['t_total']))
        times = [float(r['t_total']) for r in rows]
        result = dict(best, seconds_min=min(times), seconds_median=statistics.median(times),
                      seconds_max=max(times), cv=statistics.pstdev(times)/statistics.mean(times),
                      iters_min=min(int(r['iters']) for r in rows),
                      iters_max=max(int(r['iters']) for r in rows),
                      max_true_rel_res=max(float(r['rel_res']) for r in rows),
                      repeats=len(rows), shortest_at_least_one_second=min(times) >= 1)
        summaries.append(result)
        write_csv(a.output/'summary.csv', summaries)
        if impl == 'serial':
            references[dim, n] = best
        print('GROUP_PASS', gid, 'min=',min(times), 'CV=',result['cv'], flush=True)

    # Validate 256 and 288 distinct physical cores, then a 4-rank x 72-thread split.
    for ranks, threads in [(256, 1), (288, 1), (4, 72)]:
        rid = f'probe-p{ranks}-t{threads}'
        record = a.output/'placement'/rid
        command = launch('mpi', ranks, threads, record) + [str(a.bin_dir/'cluster_cpu_smoke'), '4', str(threads)]
        with (a.output/(rid+'.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
        assert check_placement(record, ranks, threads) == (4, ranks*threads)
        print('PLACEMENT_PASS',ranks,threads,flush=True)
    if a.suite == 'pilot':
        for dim, n in [(2, 31), (3, 15)]:
            run_group('pilot', 'serial', dim, n)
            for impl, ranks, threads in [('mpi',256,1), ('mpi',288,1), ('omp',32,9)]:
                for cg in ['std', 'pipe']:
                    run_group('pilot',impl,dim,n,ranks,threads,cg=cg)
    elif a.suite == 'weak3d':
        cases=weak_cases(3,32,[1,8,64,216,256])
        for n in sorted({n for ranks,n in cases}):
            run_group('serial','serial',3,n)
        for ranks,n in cases:
            run_group('weak','mpi',3,n,ranks)
    else:
        for dim, n in [(2,31),(3,15)]:
            run_group('preflight', 'serial', dim, n)
            run_group('preflight', 'mpi', dim, n, 256)
            run_group('preflight', 'mpi', dim, n, 288)
            run_group('preflight', 'omp', dim, n, 32, 9)
        for dim in [2,3]:
            for n in serial_sizes(dim):
                run_group('serial', 'serial', dim, n)
        for dim,n in [(2,2048),(3,288)]:
            for ranks in [1,2,4,8,16,32,64,128,256,288]:
                for dec in ['cart','slab']:
                    run_group('strong','mpi',dim,n,ranks,decomp=dec)
            for ranks in [64,256]:
                for halo,cg in [('overlap','std'),('block','pipe'),('overlap','pipe')]:
                    run_group('variants','mpi',dim,n,ranks,halo=halo,cg=cg)
            for ranks,threads in [(288,1),(144,2),(72,4),(32,9),(16,18),(4,72)]:
                run_group('hybrid','omp',dim,n,ranks,threads)
        for dim, base, ranks_list in [(2,128,[1,4,16,64,256]), (3,32,[1,8,64,216,256])]:
            for ranks in ranks_list:
                n = weak_cases(dim,base,[ranks])[0][1]
                run_group('weak','mpi',dim,n,ranks)
    print('CPU_SCALING_VALIDATION=PASS',len(samples),'accepted samples',flush=True)


def write_csv(path, rows):
    with path.open('w',newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


if __name__ == '__main__':
    main()
