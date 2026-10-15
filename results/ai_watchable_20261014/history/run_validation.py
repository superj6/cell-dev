"""Four JS replays of published C lives; 120 CPU-second hard child ceiling."""
from pathlib import Path
import datetime,hashlib,json,os,resource,subprocess,time
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (HERE/'validation_attempt.json').exists()
pins={p.name:sha(p) for p in [HERE/'check_replay.js',HERE/'bodies.json',HERE/'truth.json']}
value={'scope':'four JS replays, existing AE first confirmation seed52300000; no new research or C lives',
       'status':'registered','cpu_cap_seconds':120,'wall_cap_seconds':180,'source_pins':pins,
       'engine_sha256':sha(HERE.parents[1]/'results/atlas/play/lifesim.js'),
       'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(HERE/'validation_attempt.json').write_text(json.dumps(value,indent=2)+'\n')
start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
def limit():resource.setrlimit(resource.RLIMIT_CPU,(120,120))
with (HERE/'replay_stdout.json').open('x') as out,(HERE/'replay_stderr.txt').open('x') as err:
    proc=subprocess.Popen(['node',str(HERE/'check_replay.js')],stdout=out,stderr=err,preexec_fn=limit,start_new_session=True)
    fields=Path(f'/proc/{proc.pid}/stat').read_text().rsplit(')',1)[1].split()
    identity={'pid':proc.pid,'pgid':proc.pid,'ppid':os.getpid(),'start_ticks':int(fields[19])}
    try:code=proc.wait(timeout=180)
    except subprocess.TimeoutExpired:proc.kill();code=proc.wait()
after=resource.getrusage(resource.RUSAGE_CHILDREN);cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
receipt={'status':'complete' if code==0 else 'incomplete','exit_code':code,'cpu_seconds':cpu,
         'wall_seconds':time.monotonic()-start,'cap_cpu_seconds':120,'processes':[identity],
         'process_groups':[identity['pgid']],'running':[],'queued':[],'cleanup_error':None,
         'all_processes_exited':not Path(f'/proc/{proc.pid}').exists(),'source_pins':pins,
         'stdout_sha256':sha(HERE/'replay_stdout.json'),'stderr_sha256':sha(HERE/'replay_stderr.txt'),
         'js_replay_lives':4 if code==0 else None,'new_C_lives':0,'new_research_lives':0}
(HERE/'validation_budget.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2));raise SystemExit(code)
