#!/usr/bin/env python3
"""Pin one MPI rank to disjoint physical cores within the PBS CPU allowance."""
import argparse
import json
import os
from pathlib import Path
import socket

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--threads', type=int, required=True)
p.add_argument('--record-dir', type=Path, required=True)
p.add_argument('command', nargs=argparse.REMAINDER)
a = p.parse_args()
local = int(os.environ.get('OMPI_COMM_WORLD_LOCAL_RANK', '0'))
rank = int(os.environ.get('OMPI_COMM_WORLD_RANK', '0'))
physical = {}
for cpu in sorted(os.sched_getaffinity(0)):
    top = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
    key = tuple(int((top / x).read_text()) for x in ('physical_package_id', 'core_id'))
    physical.setdefault(key, cpu)  # Never assign both SMT siblings as different cores.
cores = sorted(physical.items())
chosen = cores[local*a.threads:(local+1)*a.threads]
if a.threads < 1 or len(chosen) != a.threads:
    raise RuntimeError('insufficient allowed physical cores; refuse oversubscription')
cpus = [cpu for key, cpu in chosen]
os.sched_setaffinity(0, cpus)
os.environ.update(OMP_NUM_THREADS=str(a.threads), OMP_DYNAMIC='FALSE',
                  OMP_PLACES=','.join('{'+str(c)+'}' for c in cpus),
                  OMP_PROC_BIND='close', OMP_WAIT_POLICY='ACTIVE')
a.record_dir.mkdir(parents=True, exist_ok=True)
(a.record_dir / f'rank-{rank}.json').write_text(json.dumps({
    'rank': rank, 'local_rank': local, 'host': socket.gethostname(),
    'cpus': cpus, 'physical_cores': [key for key, cpu in chosen],
    'affinity': sorted(os.sched_getaffinity(0)), 'threads': a.threads,
})+'\n')
os.execvp(a.command[0], a.command)
