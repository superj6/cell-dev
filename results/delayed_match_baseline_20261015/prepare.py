"""Freeze six public AO endpoints and exact preset worlds; no builds, lives, or random draws."""
from __future__ import annotations

import ast
import hashlib
import shutil
import subprocess
import sys
from dataclasses import asdict

from common import ROLES, ROOT, STUDY, read, save, sha

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))


def seed_review():
    inventory = read(STUDY / 'candidate_seed_inventory.json')
    if inventory['NPZ_matches'] or inventory['NPZ_errors'] or inventory['JSON_errors']:
        raise ValueError('unresolved namespace overlap/errors')
    classes = []
    for row in inventory['JSON_hits']:
        if row['value'] != 52430000 or row['field'] != 'whole_block_half_open.1' or 'retained_depth_20261015' not in row['path']:
            raise ValueError('unclassified namespace value: ' + str(row))
        classes.append(dict(row, classification='Excluded upper endpoint of AO block 142'))
    text_classes = []
    for line in (STUDY / 'candidate_text_matches.txt').read_text().splitlines():
        path, number, text = line.split(':', 2)
        if '5d6d561cda5f7ac66479097d328af9fbfd2449f0fbb39f52435b9605bc341f2e' in text:
            category = 'Substring of source SHA256, not a seed'
        elif 'openhr/switching/' in path:
            category = 'Older block 143 at base 43 million, disjoint'
        elif 'retained_depth_20261015' in path and '52430000' in text:
            category = 'AO block 142 excluded upper endpoint in audit source'
        else:
            raise ValueError('unclassified seed literal: ' + line)
        text_classes.append(dict(path=path, line=int(number), classification=category))
    switching = ROOT / 'outputs/openhr/harness/harness.py'
    tree = ast.parse(switching.read_text())
    base = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'SEED_BASE' for t in node.targets))
    if base != 43000000 or 'seed0=SEED_BASE + 10_000 * block, first=first' not in switching.read_text():
        raise ValueError('older switching namespace changed')
    registrations = []
    for folder in sorted((ROOT / 'outputs').glob('autonomous_*')):
        path = folder / 'registration.json'
        if not path.exists():
            continue
        row = read(path)
        ranges = row.get('seed_blocks') or []
        if isinstance(ranges, dict):
            if row['study'] != 'Y ordinary visibility gradient':
                raise ValueError('unknown seed block map')
            ranges = [[51000000 + 10000*b, 51000000 + 10000*(b+1)] for b in ranges.values()]
        if len(ranges) == 2 and all(isinstance(v, int) for v in ranges):
            ranges = [ranges]
        if any(max(lo, 52430000) < min(hi, 52440000) for lo, hi in ranges):
            raise ValueError('registered block overlap')
        registrations.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), seed_blocks=ranges))
    audit = dict(status='passed', block=143, whole_block_half_open=[52430000, 52440000],
        actual_development_seeds=list(range(52430000, 52430032)), numeric_overlap_count=0,
        coverage={k: inventory[k] for k in ('current_npz_paths', 'unchanged_npz_paths',
            'unchanged_seed_members_covered', 'distinct_unchanged_payloads_reopened')},
        JSON_classification=classes, text_classification=text_classes, registration_pins=registrations,
        switching_source_sha256=sha(switching), inventory_sha256=sha(STUDY / 'candidate_seed_inventory.json'),
        limitations=inventory['limitations'], simulation_calls=0, engine_builds=0)
    save(STUDY / 'seed_audit.json', audit, exclusive=True)
    save(STUDY / 'reservation.json', dict(study='Delayed-match frozen-endpoint developmental baseline',
        status='reserved_development_only', seed_blocks=[[52430000, 52440000]],
        seeds=list(range(52430000, 52430032)), confirmation_eligible=False,
        actual_lives=390, scientific_fast_lives=384, predetermined_full_repeat_lives=6,
        intentional_reuse='All six roles and both durations share 32 seeds; first seed T85 repeated in full mode.',
        seed_audit_sha256=sha(STUDY / 'seed_audit.json')), exclusive=True)


def prepare():
    import numpy as np

    from src.life import spec

    if any((STUDY / n).exists() for n in ('protocol.json', 'release.json', 'attempt.json', 'raw')):
        raise ValueError('preparation is first-attempt only')
    (STUDY / 'inputs').mkdir(parents=True, exist_ok=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not revision.startswith('968bb81'):
        raise ValueError('ABI5 milestone revision required')
    source = ROOT / 'results/retained_depth_20261015'
    endpoints = read(source / 'endpoints.json')
    if tuple(endpoints['roles']) != ROLES or tuple(row['role'] for row in endpoints['genomes']) != ROLES:
        raise ValueError('the public six-role order differs')
    genomes, references = [], []
    for item in endpoints['genomes']:
        path = source / item['path']
        if sha(path) != item['file_sha256']:
            raise ValueError('public endpoint bytes differ')
        value = read(path)
        raw = np.concatenate([np.asarray(value['params'][f.name], dtype=np.float32).reshape(-1)
                              for f in spec.V5.GENOME_FIELDS])
        if raw.shape != (875,) or not np.isfinite(raw).all() or hashlib.sha256(raw.tobytes()).hexdigest() != item['raw_sha256']:
            raise ValueError('public raw genome differs')
        target = STUDY / 'inputs' / (item['role'] + '.json')
        shutil.copyfile(path, target)
        genomes.append(raw)
        references.append(dict(item, public_path=str(path.relative_to(ROOT)), path=str(target.relative_to(STUDY))))
    raw = np.stack(genomes)
    np.save(STUDY / 'inputs/raw_genomes.npy', raw, allow_pickle=False)
    packed = spec.V5.pack_genomes(raw, 'hexprism')
    np.save(STUDY / 'inputs/packed_genomes.npy', packed, allow_pickle=False)
    save(STUDY / 'inputs/endpoints.json', dict(roles=ROLES, genomes=references,
        public_manifest=str((source / 'endpoints.json').relative_to(ROOT)),
        public_manifest_sha256=sha(source / 'endpoints.json')), exclusive=True)
    seed_review()
    worlds = {}
    for duration in (85, 1024):
        w = spec.world('catch_delayed_match_l4', T=float(duration))
        worlds[str(duration)] = dict(abi=5, world=asdict(w), world_vector=spec.V5.pack_world(w).tolist())
    schedule = []
    for duration in (85, 1024):
        for role_index, role in enumerate(ROLES):
            for seed in range(52430000, 52430032):
                schedule.append(dict(role=role, role_index=role_index, T=duration, seed=seed, fast=True,
                    path=f'raw/fast/T{duration}/{role}/{seed}.npz'))
    for role_index, role in enumerate(ROLES):
        schedule.append(dict(role=role, role_index=role_index, T=85, seed=52430000, fast=False,
            path=f'raw/full/T85/{role}/52430000.npz'))
    interpretation = [
        'Developmental/accessibility diagnostic only: 32 shared fresh seeds are not the plan0.4 512-seed admission or an information-payoff test.',
        'Every scheduled endpoint and outcome is retained. Guards, numerical status, truncated fates, or full/fast disagreement limit interpretation; no replacement or outcome-based exclusion is permitted.',
        'F is ABI5 physical net reward per task duration, including the default guard charge. No extra selection extinction surcharge, repricing, or behavioral intervention is added.',
        'Positive F or capture counts cannot establish conditional matching: sample-blind random resolved choices earn +225 gross on average before physical costs. Inspect both sample classes, choice coverage, timeouts, and unfinished trials.',
        'T14/15/25 development comes from the single predeclared first seed per endpoint at T85. Off-center means z=0 and (a,b)!=(0,0) relative to the body lattice; this describes potential spatial sensing, not current receptor gain, body displacement, or effective cue discrimination.',
        'Snapshots include births and deaths at the stated cutoff and count rejected placements separately in raw logs. Sample duration is 15–25; t14 is before its earliest end, t15 the earliest boundary, and t25 the latest boundary. Actual scalar cue exposure also depends on motion.',
        'Durations share seeds, but T85 need not be a strict observable prefix of T1024 because terminal scheduling/accounting can differ. No neural-memory or prediction claim follows from this baseline; retained body state is legitimate embodied memory.',
        'A stopped attempt retains its available rows and counts; missing planned rows remain missing. No automatic retry, top-up, selection, evolution, or extra startup life is allowed.',
    ]
    protocol = dict(study='Frozen AO endpoints on delayed matching: developmental baseline',
        source_revision=revision, abi=5, roles=ROLES, seeds=list(range(52430000, 52430032)),
        seed_partition='development only', worlds=worlds, schedule=schedule, fate_cap=65536,
        scientific_fast_lives=384, predetermined_full_repeat_lives=6, backend_calls=390, startup_lives=0,
        budget=dict(cpu_seconds=600, wall_seconds=900, workers=1, threads=1, cleanup_margin_seconds=5,
                    rss_bytes=2*1024**3, address_space_bytes=8*1024**3, minimum_available_bytes=4*1024**3),
        interpretation=interpretation,
        production_pins={str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src').rglob('*'))
                         if p.suffix in ('.py', '.c')},
        input_pins={str(p.relative_to(STUDY)): sha(p) for p in sorted((STUDY / 'inputs').iterdir())},
        source_pins={p.name: sha(p) for p in sorted(STUDY.glob('*.py'))},
        seed_audit_sha256=sha(STUDY / 'seed_audit.json'), reservation_sha256=sha(STUDY / 'reservation.json'),
        ownership_pattern_source=dict(path='results/retained_depth_20261015/monitor.py',
                                      sha256=sha(ROOT / 'results/retained_depth_20261015/monitor.py')))
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared_not_launched', protocol_sha256=sha(STUDY / 'protocol.json'),
        source_revision=revision, builds=0, simulation_calls=0, backend_calls_planned=390,
        source_only_check='Python syntax, exact input/world packing, seed audit; no engine build/run'), exclusive=True)
    print('Prepared 390 planned calls; zero builds or lives launched.')


if __name__ == '__main__':
    prepare()
