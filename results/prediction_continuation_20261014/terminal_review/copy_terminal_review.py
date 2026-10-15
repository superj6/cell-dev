"""Copy only reviewed AF terminal evidence; never edit a frozen release file."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_prediction_continuation_20261014'
NAMES = (
    'review_terminal.py', 'terminal_verifier_preparation.json', 'terminal_verifier_dry_run.json',
    'independent_terminal_raw_review.json', 'terminal_execution_review.json',
    'terminal_raw_review.stdout.json', 'terminal_raw_review.stderr.txt',
    'frozen_reanalysis.stdout.json', 'frozen_reanalysis.stderr.txt',
    'frozen_reader_reanalysis/summary.json', 'frozen_reader_reanalysis/paired_vectors.npz',
    'release_prerequisites.json', 'root_release_receipt.json',
    'history/root_release_prerequisite_initial_error.json',
    'release_study.py', 'clear_terminal.py', 'terminal_clearance_console.json',
    'analysis_stdout.json', 'analysis_stderr.txt', 'run_console.log',
    'all_archive_files.txt', 'force_add_paths.txt',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    pins = {
        'independent_terminal_raw_review.json': '890ebc035442d608fd065f38c834fe10fad875901a66d288d228732b1b84fcc7',
        'terminal_execution_review.json': 'b2fed83d56834280393f8f34fcb93958fbc4b9957c1ec581f9df796311803b47',
        'frozen_reader_reanalysis/summary.json': 'b544f4c337389566ed386df8d0453f7f6ca6e7ab6453a682599d844dc9d7be61',
        'frozen_reader_reanalysis/paired_vectors.npz': '24cb5984a41e3dc51ce2a80dbe5369673c398a4989d308b6141889dea5ea5ad8',
    }
    for name, digest in pins.items():
        assert sha(AUDIT / name) == digest, name
    copied = {}
    sources = [(AUDIT / name, STUDY / 'terminal_review' / name) for name in NAMES]
    sources += [(AUDIT / 'figures' / name, STUDY / 'figures' / name)
                for name in ('generate.py', 'capture_and_economy.png', 'capture_and_economy.svg')]
    sources.append((Path(__file__), STUDY / 'terminal_review/copy_terminal_review.py'))
    for source, target in sources:
        data = source.read_bytes()
        if target.exists():
            assert target.read_bytes() == data, target
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        copied[str(target.relative_to(STUDY))] = {'sha256': sha(target), 'source': str(source.relative_to(ROOT))}
    receipt = {'status': 'exact_terminal_copies', 'files': copied,
               'simulation_calls': 0, 'compilation_calls': 0, 'frozen_files_modified': False}
    (AUDIT / 'terminal_copy_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'files_copied': len(copied), 'receipt_sha256': sha(AUDIT / 'terminal_copy_receipt.json')}))


if __name__ == '__main__':
    main()
