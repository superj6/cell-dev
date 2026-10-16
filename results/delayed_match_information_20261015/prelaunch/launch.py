"""Root-released single-worker monitor. Default describes only; never auto-releases."""
import argparse,json
from common import STUDY,ROOT,PRIOR_CPU,checked_release,read,sha
from monitor_core import run_worker

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args()
    if not a.run:
        print(json.dumps(dict(status='unreleased source preparation',new_simulator_calls=0)));return
    protocol=checked_release()
    def complete():
        m=read(STUDY/'measurement_complete.json')
        assert m['status']=='complete' and m['backend_calls']==6656 and m['total_package_calls']==6696
        assert m['protocol_sha256']==sha(STUDY/'protocol.json')
        assert m['row_index_sha256']==sha(STUDY/'row_index.json') and m['summary_sha256']==sha(STUDY/'summary.json')
        checked_release()
    result=run_worker(STUDY,[str(ROOT/'.venv/bin/python'),'-u',str(STUDY/'worker.py'),'--run-child'],
        protocol['remaining_monitored_budget'],sha(STUDY/'protocol.json'),sha(STUDY/'release.json'),complete)
    result['cumulative_cpu_seconds']=PRIOR_CPU+result['cpu_seconds']
    print(json.dumps(result));raise SystemExit(0 if result['status']=='complete' else 1)

if __name__=='__main__':main()
