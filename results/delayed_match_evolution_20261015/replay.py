"""Replay frozen saved-row analysis and recorded genetics; no simulation, build, or new draws."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import verify


def save(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


@contextmanager
def bounded():
    """One-thread saved-data work, bounded independently of the finished research worker."""
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['ATEN_CPU_CAPABILITY'] = 'avx2'
    sys.dont_write_bytecode = True
    resource.setrlimit(resource.RLIMIT_CPU,(58,60))
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    stopped = threading.Event()
    reason = ['saved-data resource limit']

    def interrupt(signum,frame):
        raise RuntimeError(reason[0]+' signal '+str(signum))

    for sig in (signal.SIGALRM,signal.SIGXCPU,signal.SIGUSR1):
        signal.signal(sig,interrupt)
    signal.alarm(120)

    def monitor():
        while not stopped.is_set():
            available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))
            rss = next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines()
                       if line.startswith('VmRSS:'))
            own,children = resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = own.ru_utime+own.ru_stime+children.ru_utime+children.ru_stime
            if available < 4*1024**3 or rss > 512*1024**2 or cpu >= 58:
                reason[0] = 'saved-data host floor, RSS, or cumulative CPU limit'
                os.kill(os.getpid(),signal.SIGUSR1)
                return
            stopped.wait(.1)

    thread = threading.Thread(target=monitor,daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1.)
        signal.alarm(0)


def new_output(value):
    path = Path(value)
    path = path if path.is_absolute() else Path.cwd()/path
    verify.require(not path.exists() and not path.is_symlink(),'--out must be absent')
    out = path.resolve()
    verify.require(out.parent == (verify.ROOT/'outputs').resolve()
                   and not (verify.ROOT/'outputs').is_symlink(),'--out must be one direct outputs/<name>')
    return out


def replay(archive,out):
    start = time.monotonic()
    archive = Path(archive).resolve()
    out = new_output(out)
    out.mkdir()
    receipt = dict(status='started',simulator_calls=0,builds=0,random_draws=0,
                   replay_source_sha256=verify.sha(__file__),archive=str(archive))
    save(out/'replay_started.json',receipt)
    try:
        validated = verify.verify(archive)
        verify.require(shutil.disk_usage(out).free >= validated['raw_scored_uncompressed_bytes']+256*1024**2,
                       'insufficient replay storage')
        checkout = out/'checkout'
        study = checkout/'outputs/saved_evolution'
        shutil.copytree(archive,study,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        protocol = verify.read(study/'protocol.json')
        for name,digest in protocol['production_pins'].items():
            data = subprocess.check_output(['git','show',verify.REVISION+':'+name],cwd=verify.ROOT)
            verify.require(hashlib.sha256(data).hexdigest() == digest,'production pin '+name)
            destination = verify.checked_path(checkout,name)
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(data)
        for name in ('raw','scored'):
            verify.require(not (study/name).exists(),'archive unexpectedly has unpacked '+name)
        extracted = verify.verify_rows(archive,verify.confirmation_files(verify.read(study/'row_index.json')),study)
        sys.path[:0] = [str(study),str(checkout)]
        for name in ('common','analyze','native_replay','src'):
            verify.require(name not in sys.modules,'unexpected preloaded module '+name)
        common = importlib.import_module('common')
        common.checked_protocol()
        reader = importlib.import_module('analyze')
        reconstructed = reader.analyze(study)
        common.save(out/'summary.json',reconstructed,exclusive=True)
        verify.require((out/'summary.json').read_bytes() == (archive/'summary.json').read_bytes(),
                       'frozen summary did not replay bytewise')
        native = importlib.import_module('native_replay')
        import numpy as np
        import torch

        torch.set_num_threads(1)
        expected = protocol['expected_numerical_identity']
        verify.require(str(torch.__version__) == expected['torch'] and np.__version__ == expected['numpy']
                       and sys.version.split()[0] == expected['python'],'replay dependency versions')
        verify.require(torch.backends.cpu.get_cpu_capability() == expected['torch_cpu_capability'],
                       'replay CPU arithmetic capability')
        genetics = native.complete_replay(study,protocol)
        common.save(out/'native_replay_result.json',genetics,exclusive=True)
        verify.require(genetics == verify.read(archive/'native_replay_result.json'),'native replay receipt differs')
        verify.require(not any(name in sys.modules for name in ('src.life.build','src.life.evaluate','src.run')),
                       'execution module was imported by saved-data replay')
        receipt.update(status='passed',protocol_sha256=verify.PROTOCOL_SHA,source_revision=verify.REVISION,
            archive_manifest_sha256=verify.sha(archive/'manifest.json'),summary_sha256=verify.sha(out/'summary.json'),
            native_replay_sha256=verify.sha(out/'native_replay_result.json'),offspring_replayed=5376,
            point_additions_replayed=10752,raw_scored_tar_sha256=validated['raw_scored_tar_sha256'],**extracted)
    except BaseException as error:
        receipt.update(status='failed',error=repr(error))
        raise
    finally:
        own,children = resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt.update(cpu_seconds_before_shutdown=own.ru_utime+own.ru_stime+children.ru_utime+children.ru_stime,
                       wall_seconds_before_shutdown=time.monotonic()-start,peak_rss_kib=own.ru_maxrss)
        save(out/'replay_receipt.json',receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    with bounded():
        print(json.dumps(replay(args.archive,args.out),indent=2))
