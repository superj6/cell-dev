"""One fixed world worker, 13 complete raw-ledger checkpoints. Default dry run; first attempt only."""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from common import ROLES, STUDY, WORLDS, canonical, parent_check, protocol, read, require_release, save, sha


def identity(value,world,candidate):
    return {'protocol_sha256':sha(STUDY/'protocol.json'),'world':world,'candidate':candidate,'seeds':value['seeds']}


def run_world(world,expected_parent):
    parent_check(expected_parent,phase="research")
    value = require_release()
    report, budget = read(STUDY/'validation/report.json'),read(STUDY/'validation_budget.json')
    if report.get('status') != 'complete' or report.get('protocol_sha256') != sha(STUDY/'protocol.json'):
        raise ValueError('validation not complete for this protocol')
    if budget.get('report_sha256') != sha(STUDY/'validation/report.json'):
        raise ValueError('validation budget not bound to report')
    directory = STUDY/'rows'/world
    if directory.exists():
        raise ValueError('first attempt only: world output already exists')
    directory.mkdir(parents=True)
    from raw import run
    entry = value['worlds'][world]
    library = report['libraries']['fast']
    checkpoints = {}
    for candidate in entry['candidates']:
        parent_check(expected_parent,phase="research")
        protocol()
        role = candidate['role']
        pending = directory/(role+'.pending')
        pending.mkdir()
        ident = identity(value,world,candidate)
        c0,w0 = time.process_time(),time.monotonic()
        try:
            arrays = run(candidate,entry,value['seeds'],STUDY/library['path'],library['sha256'])
            arrays.update(identity=np.asarray(canonical(ident)),cpu_seconds=np.asarray(time.process_time()-c0),
                          wall_seconds=np.asarray(time.monotonic()-w0))
            target = pending/'row.npz'
            with target.open('wb') as stream:
                np.savez_compressed(stream,**arrays)
                stream.flush()
                os.fsync(stream.fileno())
            parent_check(expected_parent,phase="research")
            protocol()
            save(pending/'checkpoint.json',{'identity':ident,'row_sha256':sha(target)})
            pending.rename(directory/role)
            checkpoints[role+'/checkpoint.json'] = sha(directory/role/'checkpoint.json')
        except BaseException as error:
            save(pending/'failure.json',{'status':'incomplete','error':type(error).__name__+': '+str(error),'identity':ident})
            raise
    save(directory/'complete.json',{'status':'complete','protocol_sha256':sha(STUDY/'protocol.json'),
        'world':world,'roles':ROLES,'simulation_calls':6656,'checkpoint_pins':checkpoints})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--world',choices=WORLDS)
    parser.add_argument('--expected-parent',type=int)
    args = parser.parse_args()
    if args.run:
        if args.world is None:
            parser.error('--world required')
        run_world(args.world,args.expected_parent)
    else:
        print(json.dumps({'status':'dry_run','research_lives':6656,'worlds':WORLDS,'roles':ROLES,'threads_per_worker':2}))
