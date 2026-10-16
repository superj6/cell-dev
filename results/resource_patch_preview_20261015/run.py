"""One owned JS replay and static HTML assembly under the declared separate preview cap."""
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import monitor_core  # noqa: E402

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record_path = HERE / 'execution_record.json'
    record = json.loads(record_path.read_text())
    assert record['JS_replays'] == 1 and record['new_C_lives'] == record['new_Python_lives'] == record['builds'] == 0
    for key in ('source_pins', 'input_pins'):
        for name, digest in record[key].items():
            assert sha(HERE / name) == digest, name
    execution = HERE / 'execution'
    execution.mkdir(exist_ok=False)

    def complete_check():
        receipt = json.loads((HERE / 'validation.json').read_text())
        assert receipt['status'] == 'passed' and receipt['JS_replays'] == 1
        assert receipt['ledger_bits_checked'] == 107 and receipt['full_hashes_checked'] == 5
        assert receipt['record_sha256'] == sha(record_path)
        assert receipt['html_sha256'] == sha(HERE / 'resource_patch_AO.html')
        for key in ('source_pins', 'input_pins'):
            for name, digest in record[key].items():
                assert sha(HERE / name) == digest, name

    result = monitor_core.run_worker(execution, ['node', '--single-threaded', str(HERE / 'replay.js')],
        record['runtime_budget'], sha(record_path), sha(record_path), complete_check)
    print(json.dumps(result, indent=2))
    if result['status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
