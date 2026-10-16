"""Source-only configuration, file checks and owned-worker identity checks."""
from pathlib import Path
import hashlib,json,os

STUDY=Path(__file__).resolve().parent
ROOT=STUDY.parents[2]
ROLES=('I','E','P','N','B','R0','R1','D0','D1','D2','D3')
PRIOR_CPU=50.93  # engineering22.32 + audit20.82 + materialization2.66 + reducer5.03 + allowance0.10
PRIOR_WALL=46.38 # engineering22.38 + audit16.19 + materialization2.67 + reducer5.04 + allowance0.10

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value,*,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path if exclusive else path.with_suffix(path.suffix+'.tmp')
    with temp.open('xb' if exclusive else 'wb') as f:
        f.write((json.dumps(value,indent=2,allow_nan=False)+'\n').encode());f.flush();os.fsync(f.fileno())
    if not exclusive:temp.replace(path)

def checked_protocol():
    p=read(STUDY/'protocol.json')
    for label,base in (('source_pins',STUDY),('input_pins',STUDY),('production_pins',ROOT)):
        for name,digest in p[label].items():
            file=(base/name).resolve()
            if not file.is_relative_to(base.resolve()) or sha(file)!=digest:raise ValueError('changed pin '+name)
    if sha(STUDY.parent/'seed_audit.json')!=p['seed_audit_sha256']:raise ValueError('seed audit changed')
    if sha(STUDY/'reservation.json')!=p['reservation_sha256']:raise ValueError('reservation changed')
    return p

def checked_release():
    p=checked_protocol();r=read(STUDY/'release.json')
    if r.get('status')!='released' or r.get('protocol_sha256')!=sha(STUDY/'protocol.json'):
        raise ValueError('root release must bind this exact protocol')
    return p

def parent_check():
    parent=int(os.environ.get('CELLDEV_MONITOR_PID','0'))
    if parent<=1 or os.getppid()!=parent or os.getpgrp()!=os.getpid():raise ValueError('not an owned monitor worker')
    attempt=read(STUDY/'attempt.json')
    fields=Path(f'/proc/{parent}/stat').read_text().rsplit(')',1)[1].split()
    actual=dict(pid=parent,ppid=int(fields[1]),pgid=int(fields[2]),start_ticks=int(fields[19]))
    if actual!=attempt['monitor'] or os.readlink('/proc/self/ns/pid')!=attempt['pid_namespace']:
        raise ValueError('monitor identity changed')
    if (os.environ.get('CELLDEV_ATTEMPT_SHA256')!=sha(STUDY/'attempt.json') or
        attempt['protocol_sha256']!=sha(STUDY/'protocol.json') or
        attempt['release_sha256']!=sha(STUDY/'release.json')):raise ValueError('release identity changed')
