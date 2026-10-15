"""Draft standalone AN viewer build; requires completed export, bounded replay and mock UI check."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.build:
        print(json.dumps({'status': 'source_only_unreleased', 'simulated_lives': 0}))
        return
    if args.output is None:
        parser.error('--output is required with --build')
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = json.loads((HERE / 'export_receipt.json').read_text())
    for name, digest in receipt['source_pins'].items():
        assert sha(Path(name)) == digest, name
    for name, digest in receipt['draft_source_pins'].items():
        assert sha(HERE / name) == digest, name
    budget = json.loads((HERE / 'validation_budget.json').read_text())
    assert budget['status'] == 'complete' and budget['js_replay_lives'] == 6 and budget['all_processes_exited']
    assert sha(HERE / 'replay_stdout.json') == budget['stdout_sha256']
    assert json.loads((HERE / 'replay_stdout.json').read_text())['status'] == 'complete'
    assert json.loads((HERE / 'ui_check.json').read_text())['status'] == 'passed'
    for name, digest in budget['source_pins'].items():
        assert sha(HERE / name) == digest
    engine = ROOT / 'results/atlas/play/lifesim.js'
    assert sha(engine) == budget['engine_sha256']
    parts = {'__DATA__': (HERE / 'bodies.json').read_text().strip(), '__ENGINE__': engine.read_text(),
             '__UI__': (HERE / 'viewer.js').read_text(),
             '__VALIDATION_NOTE__': 'Six Node engineering replays matched all 345 retained fast-C ledger values. This checks these fixed lives, not every browser or possible life. Controls were tested with a mock. Browser rendering and playback have not been validated.'}
    assert all('</script' not in text.lower() for text in parts.values())
    text = (HERE / 'template.html').read_text()
    for marker, value in parts.items():
        text = text.replace(marker, value)
    assert all(marker not in text for marker in parts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(text)
    print(json.dumps({'status': 'built_local_only', 'sha256': sha(args.output), 'simulated_lives': 0}))


if __name__ == '__main__':
    main()
