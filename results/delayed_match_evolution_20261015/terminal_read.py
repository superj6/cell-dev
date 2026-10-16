"""Run the frozen saved-row reader and recorded-genetics replay after full completion."""
import json
import sys
from pathlib import Path

STUDY = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDY / 'terminal_package'))
from replay import bounded  # noqa: E402


def main():
    for name in ('budget.json', 'study_complete.json', 'measurement_complete.json'):
        if json.loads((STUDY / name).read_text())['status'] != 'complete':
            raise ValueError('full completion required: ' + name)
    for name in ('summary.json', 'native_replay_result.json', 'terminal_read_receipt.json'):
        if (STUDY / name).exists():
            raise ValueError('refuse existing saved-data result: ' + name)
    sys.path.insert(0, str(STUDY))
    import analyze
    import native_replay
    import numpy as np
    import torch

    import common

    torch.set_num_threads(1)
    protocol = common.checked_protocol()
    expected = protocol['expected_numerical_identity']
    if (str(torch.__version__) != expected['torch'] or np.__version__ != expected['numpy']
            or sys.version.split()[0] != expected['python']
            or torch.backends.cpu.get_cpu_capability() != expected['torch_cpu_capability']):
        raise ValueError('saved-data dependency identity differs')
    summary = analyze.analyze(STUDY)
    common.save(STUDY / 'summary.json', summary, exclusive=True)
    genetics = native_replay.complete_replay(STUDY, protocol)
    common.save(STUDY / 'native_replay_result.json', genetics, exclusive=True)
    if any(name in sys.modules for name in ('src.life.build', 'src.life.evaluate', 'src.run')):
        raise ValueError('saved-data read imported execution code')
    receipt = dict(status='passed', simulator_calls=0, builds=0, random_draws=0,
                   script_sha256=common.sha(__file__), protocol_sha256=common.sha(STUDY / 'protocol.json'),
                   summary_sha256=common.sha(STUDY / 'summary.json'),
                   native_replay_sha256=common.sha(STUDY / 'native_replay_result.json'),
                   offspring_replayed=genetics['offspring_replayed'],
                   point_additions_replayed=genetics['point_additions_replayed'])
    common.save(STUDY / 'terminal_read_receipt.json', receipt, exclusive=True)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    with bounded():
        main()
