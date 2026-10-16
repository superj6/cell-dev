"""Bounded engineering commands; no automatic retries or scientific searches."""
import argparse
import json
import os
import sys

from support import ROOT, STUDY, save, sha
from monitor import run_worker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--cpu', type=float, default=600)
    parser.add_argument('--wall', type=float, default=900)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or '/' in args.label:
        raise ValueError('named command required')
    spent = [json.loads(p.read_text()) for p in STUDY.glob('*/budget.json')]
    cpu_used = sum(x['cpu_seconds'] for x in spent)
    wall_used = sum(x['wall_seconds'] for x in spent)
    if args.cpu + cpu_used > 1800 or args.wall + wall_used > 3600:
        raise ValueError('engineering package allocation exceeded')
    folder = STUDY / args.label
    folder.mkdir()
    paths = sorted([*ROOT.glob('src/**/*.py'), ROOT/'src/life/kernel.c', *ROOT.glob('tests/*.py'),
                    *ROOT.glob('results/atlas/play/*.js'), ROOT/'results/atlas/play/bodies.json',
                    STUDY.parent/'export_truth.py', *STUDY.glob('*.py'), *STUDY.glob('*.cjs')])
    pins = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    save(folder/'source_pins.json', pins, exclusive=True)
    budget = dict(cpu_seconds=args.cpu, wall_seconds=args.wall, cleanup_margin_seconds=5,
                  threads=2, workers=1, rss_bytes=4*1024**3, address_space_bytes=8*1024**3,
                  minimum_available_bytes=4*1024**3)
    save(folder/'command.json', dict(command=command, budget=budget, prior_cpu_seconds=cpu_used,
                                   prior_wall_seconds=wall_used), exclusive=True)
    (folder/'counts').mkdir()
    env = dict(os.environ, PYTHONPATH=str(STUDY/'instrumentation')+os.pathsep+str(ROOT),
               ABI6_COUNT_DIR=str(folder/'counts'), TMPDIR=str(STUDY), NUMEXPR_NUM_THREADS='1')

    def complete_check():
        changed = [name for name, digest in pins.items() if sha(ROOT/name) != digest]
        save(folder/'source_check.json', dict(unchanged=not changed, changed=changed), exclusive=True)
        if changed:
            raise ValueError('source changed during validation: '+str(changed))

    result = run_worker(folder, command, budget, sha(STUDY.parent/'DRAFT_CONTRACT.md'),
                        sha(folder/'command.json'), complete_check, environment=env)
    print(json.dumps({k: result[k] for k in ('status','worker_exit_code','cpu_seconds','wall_seconds',
                                            'peak_owned_rss_bytes','reason','error','terminal_cleanup')}))
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    sys.exit(main())
