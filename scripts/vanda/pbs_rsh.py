#!/usr/bin/env python3
"""Launch an Open MPI remote daemon through PBS/TM, preserving job GPU limits."""
import os
import json
from pathlib import Path
import sys

hosts=Path(os.environ['PBS_NODEFILE']).read_text().split()
target=sys.argv[1].split('.')[0].lower()
index=next(i for i,h in enumerate(hosts) if h.split('.')[0].lower()==target)
args=sys.argv[2:]
if not args:
    raise RuntimeError('missing remote daemon command')
# Open MPI supplies a shell prefix and already-quoted tokens, as for ssh.
command=' '.join(args)
record=Path(os.environ['PCG_DAEMON_LOG_DIR'])
record.mkdir(parents=True,exist_ok=True)
(record/('daemon-'+target+'.json')).write_text(json.dumps({'index':index,'args':args,'command':command})+'\n')
os.execv('/opt/pbs/bin/pbsdsh',['pbsdsh','-n',str(index),'--','/usr/bin/env',
         'PATH='+os.environ['PATH'],'LD_LIBRARY_PATH='+os.environ.get('LD_LIBRARY_PATH',''),
         '/bin/bash','-c',command])
