"""Freeze the reviewed eight-generation continuation; no builds, lives or random draws."""
from __future__ import annotations

import argparse
import json
import sys

sys.dont_write_bytecode = True

from prepare_inputs import materialize_inputs  # noqa: E402

from common import STUDY, save, sha  # noqa: E402

REVISION = '1a7f38bd3222bacf27367fd99998d87776c34ec5'
SOURCE_FILES = ('common.py', 'monitor_core.py', 'run.py', 'prepare.py', 'prepare_inputs.py',
                'search.py', 'selection.py', 'pareto.py', 'population_loader.py',
                'measure.py', 'analyze.py', 'PROTOCOL.md',
                'namespace/audit_namespace.py', 'namespace/classify_namespace.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-revision', required=True)
    args = parser.parse_args()
    if args.source_revision != REVISION:
        raise ValueError('fixed completed scientific milestone required')
    if any((STUDY / name).exists() for name in
           ('protocol.json', 'reservation.json', 'READY.json', 'inputs', 'configs')):
        raise ValueError('first preparation refuses existing frozen artifacts')
    for name in SOURCE_FILES:
        if not (STUDY / name).is_file():
            raise ValueError('source preparation incomplete: ' + name)
    inputs = materialize_inputs(args.source_revision)
    from omegaconf import OmegaConf
    from population_loader import loader_identity
    from selection import selection_identity

    cfg = OmegaConf.load(STUDY / 'inputs/input_config.yaml')
    cfg.seed = inputs['native_seed']
    cfg.evolve.generations = 8
    cfg.evolve.recheck_lives = 32
    cfg.life.lives = 32
    cfg.life.control = 'resource_patch_depth_continuation'
    cfg.evolve.seed_genome = str(STUDY / inputs['population_start']['population_file'])
    cfg.logging.output_dir = str(STUDY / 'runs/pareto')
    cfg.population_start = loader_identity(inputs['population_start'])
    cfg.retention_selection = selection_identity('pareto', inputs['selection_worlds'])
    if (cfg.threads != 2 or cfg.evolve.mu != 32 or cfg.evolve.lam != 224
            or cfg.evolve.recheck_k != 64 or cfg.evolve.n_mut != 2
            or cfg.evolve.dup_rate != 0 or cfg.evolve.del_rate != 0
            or cfg.evolve.heldout_every != 4 or cfg.life.valid_lives != 16
            or cfg.life.final_lives != 2 or cfg.life.final_top != 1
            or cfg.life.abi != 6 or cfg.life.T != 1024 or not cfg.life.extinct_charge):
        raise ValueError('inherited native genetics, diagnostics, prices or resource configuration differs')
    folder = STUDY / 'configs'
    folder.mkdir(exist_ok=False)
    config_path = folder / 'pareto.yaml'
    with config_path.open('x') as stream:
        stream.write(OmegaConf.to_yaml(cfg, resolve=True))
    relative = str(config_path.relative_to(STUDY))
    inputs['input_pins'][relative] = sha(config_path)
    reservation = dict(status='reserved', study='resource_patch_depth_20261015',
        native_seed=inputs['native_seed'], native_life_seeds=inputs['native_life_seeds'],
        endpoint_seeds=inputs['endpoint_seeds'], confirmation_seeds=inputs['confirmation_seeds'],
        seed_blocks=[[52520000, 52530000], [52530000, 52540000]],
        role='One continuation, one all-survivor endpoint panel, then fixed fresh confirmation; no retry.',
        seed_audit_sha256=inputs['seed_audit_sha256'], simulated_lives=0)
    save(STUDY / 'reservation.json', reservation, exclusive=True)
    runtime = dict(cpu_seconds=10620, wall_seconds=7020, threads=2, workers=1, cleanup_margin_seconds=10,
                   rss_bytes=4 * 1024**3, address_space_bytes=8 * 1024**3,
                   minimum_available_bytes=4 * 1024**3)
    protocol = dict(inputs, study='Deeper acquisition-aware continuation with denser evaluation',
        research_lives=97334, startup_lives=8, total_calls=97342,
        search=dict(generations=8, parents=32, children=224, shortlist=64, base_lives=32, recheck_lives=32,
            selection_lives=81920, validation_generations=[0, 4, 7], validation_lives=48, final_lives=6,
            research_lives=81974, startup_lives=4, total_calls=81978),
        measurement=dict(endpoint_genomes=32, endpoint_worlds=3, endpoint_lives_per_genome_world=32,
            endpoint_lives=3072, confirmation_genomes=4, confirmation_worlds=6,
            confirmation_lives_per_genome_world=512, confirmation_lives=12288,
            research_lives=15360, startup_lives=4, total_calls=15364),
        configs=dict(pareto=dict(path=relative, sha256=sha(config_path))),
        runtime_budget=runtime,
        phase_budgets=dict(pareto=dict(cpu_seconds=8700, wall_seconds=5400),
                           measurement=dict(cpu_seconds=1920, wall_seconds=1620)),
        package_budget=dict(cpu_seconds=10800, wall_seconds=7200, preparation_terminal_cpu_reserve=180,
                            preparation_terminal_wall_reserve=180),
        source_pins={name: sha(STUDY / name) for name in SOURCE_FILES},
        reservation_sha256=sha(STUDY / 'reservation.json'),
        confirmation_roles=[*inputs['reference_roles'], 'depth8_joint'],
        primary_contrast=['depth8_joint', 'Pareto4_joint'],
        scientific_scope='Exploratory combined depth and denser evaluation; no causal policy comparison.',
        endpoint_rule=dict(worlds=['patch', 'pool', 'persistent'],
            capture_scales=[19.046875, 16.029296875, 5.919921875], fitness_weights=[.5, .25, .25],
            order=['minimum_capture_fraction_descending', 'weighted_production_F_descending', 'native_id_ascending'],
            frozen_before_confirmation=True, replaces_historical_endpoint=False))
    save(STUDY / 'protocol.json', protocol, exclusive=True)
    save(STUDY / 'READY.json', dict(status='prepared_not_released', protocol_sha256=sha(STUDY / 'protocol.json'),
        source_revision=REVISION, planned_calls=97342, new_lives=0, builds=0, random_draws=0), exclusive=True)
    print(json.dumps(dict(status='prepared', protocol_sha256=sha(STUDY / 'protocol.json'), planned_calls=97342,
                         simulator_calls=0, builds=0)))


if __name__ == '__main__':
    main()
