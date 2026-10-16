"""Single serial engineering batch; stop on first failure and retain all output."""
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = HERE.parents[2]
PLAY = ROOT / 'results/atlas/play'
PYTHON = ROOT / '.venv/bin/python'


def main():
    output = HERE / 'js_continuation' / 'stages'
    output.mkdir()
    truth = HERE / 'truth'
    commands = []
    js = [
        ('contact', STUDY/'test_contact_resources.js', ['--truth', str(truth/'truth.json')]),
        ('contact_view', STUDY/'test_contact_resources_view.js', []),
        ('patches', PLAY/'test_resource_patches.js', ['--truth', str(STUDY/'abi6_truth/truth.json')]),
        ('patch_view', PLAY/'test_resource_patches_view.js', []),
        ('legacy_wounds', PLAY/'test_lifesim.js', []),
        ('visibility', PLAY/'test_visibility.js', ['--truth',
          str(ROOT/'results/abi4_visibility_20261014/final_truth/truth.json')]),
        ('matching', PLAY/'test_delayed_match.js', ['--truth',
          str(ROOT/'results/abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json')]),
        ('matching_trial64', PLAY/'test_delayed_match_trial64.js', []),
        ('matching_view', PLAY/'test_delayed_match_view.js', []),
    ]
    commands.extend((name, ['node', '--single-threaded', '--single-threaded-gc', '--max-old-space-size=2048',
                            '--require', str(HERE/'count_js_calls.cjs'),
                            str(script), *args]) for name, script, args in js)
    rows = []
    for name, command in commands:
        env = dict(os.environ, LIFE_JS_CALL_LOG=str(output/(name+'_calls.json')))
        with (output/(name+'.stdout.log')).open('x') as stdout:
            with (output/(name+'.stderr.log')).open('x') as stderr:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        rows.append(dict(name=name, command=command, exit_code=result.returncode))
        (output/'commands.json').write_text(json.dumps(rows, indent=2)+'\n')
        print(name, result.returncode, flush=True)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
