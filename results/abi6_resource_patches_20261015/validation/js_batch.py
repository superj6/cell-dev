"""Fixed serial JS regression commands; run only under the engineering monitor."""
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PLAY = ROOT / 'results/atlas/play'
COMMANDS = [
    ('patches', ['test_resource_patches.js', '--truth', str(HERE/'truth/truth.json')]),
    ('patch_view', ['test_resource_patches_view.js']),
    ('legacy_wounds', ['test_lifesim.js']),
    ('visibility', ['test_visibility.js', '--truth',
                    str(ROOT/'results/abi4_visibility_20261014/final_truth/truth.json')]),
    ('matching', ['test_delayed_match.js', '--truth',
                  str(ROOT/'results/abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json')]),
    ('matching_trial64', ['test_delayed_match_trial64.js']),
    ('matching_view', ['test_delayed_match_view.js']),
]


def main():
    output = HERE/'js_logs'
    output.mkdir()
    rows = []
    for name, args in COMMANDS:
        command = ['node', '--max-old-space-size=2048', '--require', str(HERE/'count_js_calls.cjs'),
                   str(PLAY/args[0]), *args[1:]]
        env = dict(os.environ, LIFE_JS_CALL_LOG=str(output/(name+'_calls.json')))
        with (output/(name+'.stdout.log')).open('x') as stdout:
            with (output/(name+'.stderr.log')).open('x') as stderr:
                completed = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        rows.append(dict(name=name, command=command, exit_code=completed.returncode))
        (output/'commands.json').write_text(json.dumps(rows, indent=2)+'\n')
        print(name, completed.returncode, flush=True)
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
