"""Freeze the reviewed, collision-audited development panel; no lives or builds."""
from __future__ import annotations

import argparse
import json

from prepare_inputs import materialize_inputs

from common import STUDY, save, sha

SOURCE_FILES = ('common.py', 'monitor_core.py', 'run.py', 'prepare.py', 'prepare_inputs.py',
                'measure.py', 'analyze.py', 'PROTOCOL.md')
REVISION = '5d556443e91d558de8de27ab2e5dc7ae11a51415'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    if args.source_revision != REVISION:
        raise ValueError('fixed completed scientific milestone required')
    if any((STUDY / name).exists() for name in ('protocol.json', 'reservation.json', 'READY.json', 'inputs')):
        raise ValueError('first preparation refuses existing frozen artifacts')
    for name in SOURCE_FILES:
        if not (STUDY / name).is_file():
            raise ValueError('source preparation incomplete: ' + name)
    inputs = materialize_inputs(args.source_revision)
    reservation = dict(status='reserved', study='resource_patch_population_20261015',
        development_seeds=list(range(52510000, 52510032)), whole_block_half_open=[52510000, 52520000],
        genetic_seed=None, role='One fixed whole-population development panel; not fresh winner confirmation.',
        seed_audit_sha256=sha(STUDY / 'namespace/seed_audit.json'), simulated_lives=0)
    save(STUDY / 'reservation.json', reservation, exclusive=True)
    runtime = dict(cpu_seconds=2640, wall_seconds=1740, threads=2, workers=1, cleanup_margin_seconds=10,
                   rss_bytes=4 * 1024**3, address_space_bytes=8 * 1024**3,
                   minimum_available_bytes=4 * 1024**3)
    protocol = dict(inputs, study='Whole-population acquisition development diagnostic',
        research_lives=15520, startup_lives=4, total_calls=15524, batches=20, genomes=97,
        genome_world_rows=485, lives_per_genome_world=32,
        runtime_budget=runtime,
        package_budget=dict(cpu_seconds=2700, wall_seconds=1800, preparation_terminal_cpu_reserve=60,
                            preparation_terminal_wall_reserve=60),
        source_pins={name: sha(STUDY / name) for name in SOURCE_FILES},
        reservation_sha256=sha(STUDY / 'reservation.json'),
        scientific_scope='Development-only, all rows retained, no mutation or replacement endpoint.',
        joint_diagnostic=dict(worlds=['patch', 'pool', 'persistent'],
            capture_scales=[19.046875, 16.029296875, 5.919921875], fitness_weights=[.5, .25, .25],
            order=['minimum_capture_fraction_descending', 'weighted_production_F_descending', 'native_id_ascending'],
            certified_winner=False))
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared_not_released', protocol_sha256=sha(STUDY / 'protocol.json'),
        source_revision=REVISION, planned_calls=15524, new_lives=0, builds=0, random_draws=0), exclusive=True)
    print(json.dumps(dict(status='prepared', protocol_sha256=sha(STUDY / 'protocol.json'), planned_calls=15524,
                         simulator_calls=0, builds=0)))


if __name__ == '__main__':
    main()
