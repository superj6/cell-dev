"""Read recorded world metadata for AN's declared cue-gap contexts; no engine calls."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

import yaml

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
STUDY = ROOT / 'outputs/autonomous_occlusion_acquisition_20261015'
AUDIT = OUT.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / 'src/life/spec.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'World')
    meta = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '_META' for t in n.targets))
    keys = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and n.target.id not in meta]
    assert len(keys) == 70
    prior_path = ROOT / 'results/capture_value_selection_20261015/protocol.json'
    prior = json.loads(prior_path.read_text())['worlds']
    targets = {'blink80_20': {**prior['blink80_5']['world'], 'visibility_off': 20.},
               'turn100_blink80_20': {**prior['blink80_5']['world'], 'visibility_off': 20., 'tau_turn': 100.}}
    expected = {name: [world[key] for key in keys] for name, world in targets.items()}
    query = subprocess.run(['rg', '--no-ignore', '-l', '-0', '--glob', '*.json', '--glob', '*.yaml',
        '--glob', '!**/test_*/**', '--glob', '!**/__pycache__/**',
        'visibility_on|blink_on|world_vector|packed_world', 'results', 'outputs'],
        cwd=ROOT, capture_output=True, check=False)
    assert query.returncode in (0, 1)
    pins, exact, partial, settings, errors = {}, [], [], {}, []
    full_worlds = packed_vectors = scratch_worlds = 0

    def walk(value, trail, path):
        nonlocal full_worlds, packed_vectors, scratch_worlds
        if isinstance(value, dict):
            if set(keys) <= value.keys():
                full_worlds += 1
                vector = [value[key] for key in keys]
                for name, target in expected.items():
                    if vector == target:
                        exact.append({'path': path, 'field': trail, 'target': name, 'kind': '70 physical fields'})
            if {'visibility_mode', 'visibility_on', 'visibility_off', 'visibility_low'} <= value.keys():
                setting = tuple(value[k] for k in ('visibility_mode', 'visibility_on', 'visibility_off', 'visibility_low'))
                settings[str(setting)] = settings.get(str(setting), 0) + 1
                if setting == (2, 80, 20, 0) and not set(keys) <= value.keys():
                    partial.append({'path': path, 'field': trail, 'kind': 'partial ABI4 80/20 declaration'})
            if 'blink_on' in value and 'blink_off' in value:
                scratch_worlds += 1
                if value['blink_on'] == 80 and value['blink_off'] == 20:
                    partial.append({'path': path, 'field': trail, 'kind': 'scratch 80/20 declaration'})
            for key, child in value.items():
                if key in ('genomes', 'genome', 'population', 'program', 'cells', 'hashes', 'ledger'):
                    continue
                walk(child, trail + [str(key)], path)
        elif isinstance(value, list):
            if len(value) == 70 and all(isinstance(x, (int, float)) for x in value):
                packed_vectors += 1
                for name, target in expected.items():
                    if value == target:
                        exact.append({'path': path, 'field': trail, 'target': name, 'kind': 'packed 70-vector'})
            else:
                for index, child in enumerate(value):
                    if isinstance(child, (dict, list)):
                        walk(child, trail + [str(index)], path)

    for raw in sorted(set(query.stdout.split(b'\0')) - {b''}):
        name = raw.decode()
        path = ROOT / name
        if path.is_relative_to(STUDY) or path.is_relative_to(AUDIT):
            continue
        pins[name] = sha(path)
        try:
            value = json.loads(path.read_text()) if path.suffix == '.json' else yaml.safe_load(path.read_text())
            walk(value, [], name)
        except (ValueError, yaml.YAMLError) as error:
            errors.append({'path': name, 'error': str(error)})
    text = subprocess.run(['rg', '-n', '--glob', '*.py', '--glob', '*.md', '--glob', '*.yaml',
        '--glob', '!**/test_*/**', '--glob', '!**/__pycache__/**',
        r'blink.?80.?20|on.{0,8}80.{0,40}off.{0,8}20|off.{0,8}20.{0,40}on.{0,8}80',
        'results', 'outputs', 'docs'], cwd=ROOT, capture_output=True, check=False)
    assert text.returncode in (0, 1)
    lines = [line for line in text.stdout.decode().splitlines()
             if not (ROOT / line.split(':', 1)[0]).is_relative_to(STUDY)
             and not (ROOT / line.split(':', 1)[0]).is_relative_to(AUDIT)]
    (OUT / 'exposure_text_matches.txt').write_text('\n'.join(lines) + '\n')
    result = {'status': 'recorded_metadata_review_complete', 'exact_prior_physical_world_matches': exact,
        'partial_or_scratch_80_20_declarations': partial, 'parse_errors': errors,
        'world_keys': keys, 'targets': expected, 'metadata_files': len(pins),
        'complete_world_dicts': full_worlds, 'packed_70_vectors': packed_vectors,
        'scratch_visibility_dicts': scratch_worlds, 'observed_visibility_settings': settings,
        'metadata_source_pins': pins, 'text_matches_sha256': sha(OUT / 'exposure_text_matches.txt'),
        'source_pins': {str(path.relative_to(ROOT)): sha(path) for path in (source, prior_path, Path(__file__))},
        'classification': 'No prior recorded exact 80-on/20-off context found; current AN discussion is prospective.',
        'interpretation': ['blink80_20 becomes a training context in AN and must not be called held out.',
            'turn100_blink80_20 is a predeclared untrained combination in AN. Its factors and nearby contexts were already explored.',
            'This is limited transfer evidence, not a broad unseen-environment or memory claim.'],
        'limitations': ['Scan covers retained named visibility dictionaries, scratch blink slots, packed world vectors and source declarations under outputs/results/docs.',
            'It does not prove that no undocumented or unretained run ever used equivalent physics.',
            'Synthetic test directories and the current unexecuted AN source/audit are excluded.',
            'No genotype, outcome or trajectory arrays are inspected.'],
        'simulation_calls': 0, 'genetic_draws': 0, 'registered': False}
    assert not exact and not partial and not errors
    (OUT / 'exposure_review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'metadata_files', 'complete_world_dicts',
        'packed_70_vectors', 'scratch_visibility_dicts', 'exact_prior_physical_world_matches')}, indent=2))


if __name__ == '__main__':
    main()
