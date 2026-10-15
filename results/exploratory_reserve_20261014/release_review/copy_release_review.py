"""Curate exact AH preparation evidence; never include synthetic fixture trees."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
STUDY = ROOT / 'outputs/autonomous_exploratory_reserve_20261014'
FILES = (
    'archive.py', 'check_public_preparation.py', 'copy_release_review.py',
    'producer_source_review.json', 'historical_cost_review.json', 'source_origins.json',
    'review_source.py', 'review_source_stdout.json', 'review_source_stderr.txt',
    'source_tests.xml', 'source_tests.log', 'source_tests_final.xml', 'source_tests_final.log',
    'ruff_initial.log', 'ruff_final.log', 'check_independent_source_design.py',
    'independent_source_design_review.json', 'independent_source_review.stdout.json', 'independent_source_review.stderr.txt',
    'check_actual_inputs.py', 'independent_actual_input_review.json',
    'independent_actual_input_review.stdout.json', 'independent_actual_input_review.stderr.txt',
    'actual_preparation_review.json', 'preparation_command.json', 'preparation_stdout.json',
    'preparation_stderr.txt', 'preparation_execution_review.json', 'review_preparation.py',
    'review_preparation_stdout.json', 'review_preparation_stderr.txt',
    'register_study.py', 'release_study.py', 'clear_terminal.py', 'root_helper_origins.json',
    'root_helper_source_review.json', 'registration_review_acceptance.json', 'registration_prerequisites.json',
    'registration_console.json', 'preregister_text_draft.md', 'preregister_text.md', 'update_preregister_docs.py',
    'history/check_independent_source_design_initial.py.txt',
    'history/independent_source_review_initial_error.txt', 'history/root_review_acceptance_initial_error.json',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = [AUDIT / name for name in FILES]
    sources += sorted(path for path in (AUDIT / 'source_history').rglob('*') if path.is_file())
    record = {}
    for source in sources:
        relative = source.relative_to(AUDIT)
        target = STUDY / 'release_review' / relative
        assert source.is_file() and not any(part.startswith('test_tmp') for part in relative.parts)
        if target.exists():
            assert target.read_bytes() == source.read_bytes(), relative
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        record[str(target.relative_to(STUDY))] = {'origin': str(source.relative_to(ROOT)), 'sha256': sha(target)}
    (AUDIT / 'release_review_copy.json').write_text(json.dumps({'status': 'copied_exact', 'files': record,
        'simulation_calls': 0, 'compiled_libraries': 0}, indent=2) + '\n')
    print(json.dumps({'status': 'copied_exact', 'files': len(record)}))


if __name__ == '__main__':
    main()
