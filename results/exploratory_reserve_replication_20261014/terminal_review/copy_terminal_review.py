"""Copy frozen AI terminal evidence after final root review; no simulation."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
A = Path(__file__).resolve().parent
S = ROOT / 'outputs/autonomous_exploratory_reserve_replication_20261014'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


NAMES = [
    'review_terminal.py', 'build_terminal_verifier.py',
    'terminal_verifier_preparation.json', 'terminal_verifier_dryrun.json',
    'terminal_verifier_dryrun.stderr.txt', 'terminal_verifier_dryrun_review.json',
    'execute_terminal_review.py', 'terminal_execution_command.json',
    'independent_raw_terminal_stdout.json', 'independent_raw_terminal_stderr.txt',
    'frozen_reader_terminal_stdout.json', 'frozen_reader_terminal_stderr.txt',
    'independent_terminal_raw_review.json', 'terminal_execution_review.json',
    'terminal_result_details.json', 'frozen_reader_reanalysis/summary.json',
    'frozen_reader_reanalysis/paired_vectors.npz',
    'release_prerequisites.json', 'release_console.json',
    'prospective_index_verification.json', 'prospective_whitespace_check.txt',
    'prospective_whitespace_exceptions.json', 'clear_terminal.py',
    'clear_terminal_console.json', 'analysis_stdout.json', 'analysis_stderr.txt',
    'monitor_console.txt', 'terminal_text.md', 'update_terminal_docs.py',
    'figure_stdout.txt', 'figure_stderr.txt', 'all_archive_files.txt',
    'force_add_paths.txt', 'doc_claim_review.stdout.json',
    'doc_claim_review.stderr.txt', 'terminal_preflight.stdout.json',
    'terminal_preflight.stderr.txt', 'terminal_completed_pins.json',
]
# Bind after final root prose/figure freeze and independent review; never infer
# approval from the mere existence of an artifact.
PINS = {'review_terminal.py': '7e4f91360ffc685eeed6170a087732a507513f62f9d3fb1935606ffc32241ffe', 'build_terminal_verifier.py': 'd600f0862da928501b0f40fbfb42e5be41b13b023a0869c4cb29449ceb21ab98', 'terminal_verifier_preparation.json': '5789fd63479c089a46cde37b5ab515fdb801b3f1e8194f47c89e25556d63fc8f', 'terminal_verifier_dryrun.json': 'b0e0b3ac276de9f45b70275ec700fb11bdcfd533cc24cd2623a7dd7af795efde', 'terminal_verifier_dryrun.stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'terminal_verifier_dryrun_review.json': 'da4ff0c6d92847a3b528c2a29fcf9d1a0796e2b001e8a49255511705debeda74', 'execute_terminal_review.py': 'fcbd357633d98ebd353668d31e61fdb81852240810dca9f6a3c11ca16982806b', 'terminal_execution_command.json': '2e0b58d7e227c789d927e4842529b0b683ede5896c2e93c7c13bc82978177521', 'independent_raw_terminal_stdout.json': 'f0fdbe0652c9028be271fcab03abb3239236b7f653bd00f4039615d2782ca36e', 'independent_raw_terminal_stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'frozen_reader_terminal_stdout.json': 'a070f5b95edd37d95fc8d6cc9a5a87203cac3edc65baf6f18105dc36ccc3f2f9', 'frozen_reader_terminal_stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'independent_terminal_raw_review.json': '77ac1e9e46398c5268cac225d745d886c80480cd821803fa694e1d1db54c8867', 'terminal_execution_review.json': 'e7497ae9d75ab7e7f45c4ff3a66f3924a58679d68ce54cce20d0c715ebb27c15', 'terminal_result_details.json': 'f0d01fbaf8afe6b9c9cabbd29e0b78d8f91553d3f61f00d9e23c8dcb787f4446', 'frozen_reader_reanalysis/summary.json': 'a070f5b95edd37d95fc8d6cc9a5a87203cac3edc65baf6f18105dc36ccc3f2f9', 'frozen_reader_reanalysis/paired_vectors.npz': 'c92030a04349348cb95a4c5deccda09f966a1d5c960b84b2e14061b64464edf1', 'release_prerequisites.json': '97c84a27c6fc9cecbe48fcfdabe026d85cb9b5fdf359f21ad74ab4137b5249af', 'release_console.json': '17c5499f1e29d19feefda3210bfec96bf3bd5c48fb0ceeb30ac7b03590c5bc03', 'prospective_index_verification.json': 'f912deba7914834059f205a7f4aef077644a00aba5132bb95ed777b3ec2dfa9c', 'prospective_whitespace_check.txt': 'ed4902064176f15c79f70b2b25aa7e4591b440364b1817d25b223038ef57547e', 'prospective_whitespace_exceptions.json': '97f7fe98f32c098fb93800d86e46b5deb3c7ff3f22ccae3f4c34524872c868b0', 'clear_terminal.py': '8c9a7d43470f67edfef3d7ab73c200b159a6a55325a161726021de0f664d066f', 'clear_terminal_console.json': '00c971a86ce1f9e6c87fa0ed7ae250ec264c2d00225b7a7b1c9e2619009fa03c', 'analysis_stdout.json': 'a070f5b95edd37d95fc8d6cc9a5a87203cac3edc65baf6f18105dc36ccc3f2f9', 'analysis_stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'monitor_console.txt': 'c4e55be76718b4f46cc91a505ca3e04e1c1b97f94e9bb46f3a6191e03665dc6e', 'terminal_text.md': 'e87d6d454cb4edda0701a43ff33379a3a2bb5483ea5e0a28a0dc31e7e31e4546', 'update_terminal_docs.py': '9ebf0a81cb0c06e5ab65ef9c832adf1055da3414894e348a26e7ee42e780476a', 'figure_stdout.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'figure_stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'all_archive_files.txt': '176887b3620e6d5b3e760c80924539525596675a3371c3bd6d0cb49baa210642', 'force_add_paths.txt': '6957d2024584d17c73039a00c78f5c69a7bbf67a4b012c624505f6792e01833b', 'doc_claim_review.stdout.json': 'b10885f51307fcee50ed0d8f2bb21f91e80a874b37696c37c51719bc10870c17', 'doc_claim_review.stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'terminal_preflight.stdout.json': 'f075df16bb21049d9715b30eef720cec85ee233b70f498ad0eb54e034b686321', 'terminal_preflight.stderr.txt': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'terminal_completed_pins.json': '1c6779acf1d16eabf469dd3d7423faf01127f68e26a9aec18c4b5efdac83ddc3', 'figures/generate.py': 'e61d8b180293bbb13ab5fc04ba153b92916f9f8d3df6cd0b50ceb33b5bdedbc3', 'figures/capture_and_economy.png': '69a5cd838a0b66d3e7379e3117c9b32c65ba216e68293e730f8c358c58a5e947', 'figures/capture_and_economy.svg': '36e898d93925742056d471df40048d94955977723cae5da70b0b575350fac1dd'}


def main():
    if not PINS:
        raise ValueError('final terminal copy pins are not set')
    figures = [f'figures/{name}' for name in (
        'generate.py', 'capture_and_economy.png', 'capture_and_economy.svg')]
    if set(PINS) != set(NAMES + figures):
        raise ValueError('terminal copy coverage differs')
    for name, digest in PINS.items():
        if sha(A / name) != digest:
            raise ValueError('terminal source changed: ' + name)
    sources = [(A / name, S / 'terminal_review' / name) for name in NAMES]
    sources += [(A / name, S / name) for name in figures]
    sources.append((Path(__file__), S / 'terminal_review/copy_terminal_review.py'))
    # Check every destination before the first write.
    for source, destination in sources:
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError('immutable terminal destination differs: ' + str(destination))
    copied = {}
    for source, destination in sources:
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
        copied[str(destination.relative_to(S))] = {
            'sha256': sha(destination), 'source': str(source.relative_to(ROOT))}
    receipt = {'status': 'exact_terminal_copies', 'files': copied,
               'simulation_calls': 0, 'compiled_libraries': 0,
               'frozen_files_modified': False}
    (A / 'terminal_copy_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'copied': len(copied),
                      'receipt_sha256': sha(A / 'terminal_copy_receipt.json')}))


if __name__ == '__main__':
    main()
