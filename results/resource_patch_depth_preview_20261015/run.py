"""Four owned JS replays and paused HTML assembly; no native simulation or build."""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import monitor_core  # noqa: E402

from common import sha  # noqa: E402

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'execution_record.json'
    record = json.loads(path.read_text())
    assert record['JS_replays'] == 4 and record['seed'] == 52530000
    assert record['new_C_lives'] == record['new_Python_lives'] == record['builds'] == 0
    for key in ('source_pins', 'input_pins'):
        for name, digest in record[key].items():
            assert sha(HERE / name) == digest, name
    execution = HERE / 'execution'
    execution.mkdir(exist_ok=False)

    def complete_check():
        from verify import verify
        # The watchdog checks its terminal resource/cleanup receipt after this callback.
        result = verify(check_budget=False)
        assert result['status'] == 'passed' and result['saved_ledger_bits'] == 428

    result = monitor_core.run_worker(execution,
        ['node', '--single-threaded', '--max-old-space-size=256', str(HERE / 'replay.js')],
        record['runtime_budget'], sha(path), sha(path), complete_check)
    print(json.dumps(result, indent=2))
    if result['status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    if parser.parse_args().run:
        main()
    else:
        print(json.dumps({'status': 'source_only', 'JS_replays': 0}))
