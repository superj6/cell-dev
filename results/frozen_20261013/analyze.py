"""Independently recompute the fixed-tissue experiment from aggregate ledgers; no simulation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault('ATEN_CPU_CAPABILITY', 'avx2')
ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/life/spec.py').exists())
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

BASE = Path(__file__).resolve().parent / 'sources/accounting_analysis.py'
if not BASE.exists():
    BASE = ROOT / 'results/followthrough_20261013/analyze.py'
loader = importlib.util.spec_from_file_location('frozen_accounting_audit', BASE)
accounting = importlib.util.module_from_spec(loader)
loader.loader.exec_module(accounting)
CONDITIONS = ('normal','freeze','lateral_off','freeze+lateral_off')
STUDY = ROOT / 'outputs/autonomous_frozen_20261013'


def write(path, data):
    accounting.write_json(path, data)


def deltas(fitness):
    arrays = {key: np.asarray(fitness[key]) for key in CONDITIONS}
    shape = arrays['normal'].shape
    if len(shape) != 2 or shape[0] != 2 or shape[1] < 2:
        raise ValueError('require paired parent/winner matrices')
    if any(value.shape != shape or not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError('all condition arrays must be finite and paired')
    gains = {key: value[1] - value[0] for key, value in arrays.items()}
    result = {'unfrozen_gain': gains['normal'], 'frozen_gain': gains['freeze'],
              'unfrozen_lateral_off_gain': gains['lateral_off'],
              'frozen_lateral_off_gain': gains['freeze+lateral_off'],
              'unfrozen_lateral_interaction': gains['normal'] - gains['lateral_off'],
              'frozen_lateral_interaction': gains['freeze'] - gains['freeze+lateral_off'],
              'gain_lost_under_freeze': gains['normal'] - gains['freeze']}
    result['interaction_change_under_freeze'] = result['unfrozen_lateral_interaction'] - result['frozen_lateral_interaction']
    for i, name in enumerate(('parent','winner')):
        for prefix, normal, lesion in (('frozen','freeze','freeze+lateral_off'),('unfrozen','normal','lateral_off')):
            result[f'{name}_{prefix}_lateral_loss'] = arrays[normal][i] - arrays[lesion][i]
    return result


def analyze(study, smoke=False):
    if (study/'provenance.json').exists():
        for relative, value in accounting.read_json(study/'provenance.json')['artifacts'].items():
            if accounting.digest(study/relative)!=value['sha256']:
                raise ValueError(f'archived artifact differs: {relative}')
    folder = study / ('validation_smoke' if smoke else 'measurement')
    if not folder.exists():
        folder = study / ('validation/smoke' if smoke else 'measurement')
    manifest = accounting.read_json(folder / 'manifest.json')
    report = accounting.read_json(folder / 'report.json')
    if report['status'] != 'complete':
        raise ValueError('scientific measurement is incomplete')
    source = study / 'sources/taskvar_frozen_gain.py'
    if not source.exists():
        source = ROOT / 'scripts/taskvar_frozen_gain.py'
    if accounting.digest(source) != manifest['runner_sha256']:
        raise ValueError('frozen scientific runner differs')
    for name, expected in manifest['helpers'].items():
        candidate = study / 'sources' / name
        if not candidate.exists():
            candidate = ROOT / 'scripts' / name
        if accounting.digest(candidate) != expected:
            raise ValueError(f'frozen helper differs: {name}')
    prior = study / 'inputs/prior'
    if not prior.exists():
        prior = ROOT / 'results/pool_mutants_20261013'
    for name, expected in manifest['prior_artifacts'].items():
        if accounting.digest(prior / name) != expected:
            raise ValueError(f'prior input differs: {name}')
    if manifest['numerical_identity'] != accounting.read_json(prior / 'provenance.json')['numerical_identity']:
        raise ValueError('numerical identity differs from original discovery')
    block, count = (8,2) if smoke else (92,512)
    seeds = list(range(51_000_000 + block*10000,51_000_000 + block*10000 + count))
    if manifest['seeds'] != seeds or manifest['seed_block'] != block:
        raise ValueError('seed block differs from fixed protocol')
    data_genomes = accounting.read_npz(folder / 'genotypes.npz')['genomes']
    original = np.load(prior / 'genomes/s5_pool.npy', allow_pickle=False)[[0,38]]
    if data_genomes.tobytes() != original.tobytes():
        raise ValueError('measurement is not the fixed parent/row38 pair')
    if [hashlib.sha256(g.tobytes()).hexdigest() for g in data_genomes] != manifest['genome_sha256']:
        raise ValueError('genotype SHA differs from manifest')
    data, pairs, terms = {}, {}, {}
    for condition in CONDITIONS:
        flags = 0 if condition == 'normal' else accounting.spec.V3.flags(*condition.split('+'))
        world = accounting.spec.world('catch_speck_l4', T=1536,t_fork=768,t_open=800,d0=.5,d_min=.25,
                                      sigma=.4,lam_s=4,fork_flags=flags)
        if asdict(world) != manifest['worlds'][condition]:
            raise ValueError(f'fixed world differs: {condition}')
        data[condition] = accounting.read_npz(folder / condition / 'scores.npz')
        accounting.check_scores(data[condition], seeds, [0,1], world)
        index_path = folder / condition / 'row_index.json'
        if index_path.exists():
            row_index = accounting.read_json(index_path)
            if set(row_index) != {f'rows/row_{i:04d}.npz' for i in (0,1)}:
                raise ValueError('raw row index differs')
            for i in (0,1):
                relative = f'rows/row_{i:04d}.npz'
                path = folder / condition / relative
                if path.exists():
                    if accounting.digest(path) != row_index[relative]['sha256']:
                        raise ValueError('raw row hash differs')
                    row = accounting.read_npz(path)
                    if not np.array_equal(row['seeds'],seeds):
                        raise ValueError('raw row seed order differs')
                    for column in accounting.LEDGER_COLS:
                        if not np.array_equal(row[column],data[condition][column][i]):
                            raise ValueError('aggregate differs from raw row')
                elif not (study/'provenance.json').exists():
                    raise ValueError('local raw row missing')
        elif not smoke:
            raise ValueError('scientific row index missing')
        pairs[condition] = accounting.pair_report(data[condition],1,0,world,
                              report['conditions'][condition]['winner_minus_parent'])
        terms[condition] = accounting.pair_terms(data[condition],1,0,world)
    effects = deltas({key:value['F'] for key,value in data.items()})
    summaries = {key:accounting.stats(value) for key,value in effects.items()}
    for key, value in summaries.items():
        accounting.check_summary(value,report['contrasts'][key],key)
    intact, lesion = data['freeze'], data['freeze+lateral_off']
    paired = []
    for index in (0,1):
        good = (intact['status'][index] == 0) & (lesion['status'][index] == 0)
        paired.append(int(good.sum()))
        for arm in (intact,lesion):
            if np.any(arm['births'][index]) or np.any(arm['deaths'][index]) or np.any(arm['last_birth'][index] >= 800):
                raise ValueError('frozen tissue changes during measurement')
            if not np.allclose(arm['live_time'][index,good],736*arm['n_end'][index,good],rtol=1e-10,atol=1e-8):
                raise ValueError('frozen cell-time is inconsistent with fixed population')
        if not np.array_equal(intact['n_end'][index,good],lesion['n_end'][index,good]):
            raise ValueError('frozen arms do not preserve the same population')
    if paired != report['frozen_tissue_validation']['paired_complete_lives_by_genotype']:
        raise ValueError('fixed-tissue validation count differs')
    contributions = {key:accounting.stats(terms['freeze'][key]-terms['freeze+lateral_off'][key])
                     for key in terms['freeze']}
    primary = summaries['frozen_lateral_interaction']
    summary = {'status':'validation_only' if smoke else 'complete','scientific_genome_lives':0 if smoke else 4096,
        'validation_genome_lives':16 if smoke else 0,'source_sha256':manifest['runner_sha256'],
        'accounting_analysis_sha256':accounting.digest(BASE),'seed_block':block,'seeds_per_arm':count,
        'window':[800,1536],'conditions':pairs,'contrasts':summaries,
        'primary':{**primary,'positive_above_3se':primary['mean']>3*primary['se'],
                   'negative_below_minus_3se':primary['mean'] < -3*primary['se']},
        'primary_fitness_contributions':contributions,'frozen_complete_pairs':paired,
        'cpu_seconds':report['cpu_seconds'],
        'limits':report['limitations'],
        'ledger_windows':'F, income, cost and captures use 800..1536; end counts/path/last_birth cover whole life.'}
    return summary,effects


def export(study,out,summary,effects):
    if summary['status'] != 'complete':
        raise ValueError('only completed scientific measurements may be exported')
    budget_path=study/'budget.json'
    if not budget_path.exists():
        budget_path=study/'operations/budget.json'
    budget=accounting.read_json(budget_path)
    if budget['status']!='complete' or budget['exit_code']!=0 or budget['cpu_seconds']>3600:
        raise ValueError('measurement did not complete inside the registered monitor budget')
    out.mkdir(parents=True,exist_ok=True)
    def keep(source,relative):
        target=out/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if source.resolve()!=target.resolve():
            shutil.copy2(source,target)
    prepared=study if (study/'provenance.json').exists() else ROOT/'results/frozen_20261013'
    for relative,value in accounting.read_json(prepared/'provenance.json')['artifacts'].items():
        if '__pycache__' in Path(relative).parts or Path(relative).suffix == '.pyc':
            continue
        if accounting.digest(prepared/relative)!=value['sha256']:
            raise ValueError(f'preparation artifact differs: {relative}')
        keep(prepared/relative,relative)
    if (out/'README.md').exists() and not (out/'PREPARATION.md').exists():
        keep(out/'README.md','PREPARATION.md')
    for path in (study/'measurement').rglob('*'):
        if path.is_file() and path.name in ('manifest.json','report.json','genotypes.npz','scores.npz','row_index.json'):
            keep(path,path.relative_to(study))
    for name in ('budget.json','ready.json'):
        source=study/name if (study/name).exists() else study/'operations'/name
        keep(source,Path('operations')/name)
    keep(BASE,Path('sources/accounting_analysis.py'))
    keep(Path(__file__),Path('analyze.py'))
    write(out/'summary.json',summary)
    np.savez_compressed(out/'independent_contrasts.npz',seeds=np.arange(51_920_000,51_920_512,dtype=np.uint64),**effects)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    groups=((('unfrozen_gain','frozen_gain','unfrozen_lateral_off_gain','frozen_lateral_off_gain'),
             ('Normal','Frozen','Lateral off','Frozen + lateral off'),'Winner minus parent'),
            (('unfrozen_lateral_interaction','frozen_lateral_interaction','interaction_change_under_freeze'),
             ('Lateral dependence: normal','Lateral dependence: frozen','Normal − frozen dependence'),
             'Paired interaction contrasts'))
    for ax,(keys,labels,title) in zip(axes,groups):
        values=[summary['contrasts'][key] for key in keys]
        ax.errorbar([v['mean'] for v in values],np.arange(len(keys)),xerr=[3*v['se'] for v in values],
                    fmt='o',capsize=4,color='#386d96')
        ax.set_yticks(np.arange(len(keys)),labels)
        ax.invert_yaxis()
        ax.axvline(0,color='.5',lw=1)
        ax.set_title(title)
        ax.set_xlabel('Paired ΔF, ±3 SE')
        ax.grid(axis='x',color='.92')
    fig.suptitle('Fixed parent/row38; 512 shared seeds; fitness counted over 800–1536')
    for suffix in ('png','svg'):
        fig.savefig(out/f'frozen_lateral.{suffix}',dpi=180)
    plt.close(fig)
    primary=summary['primary']
    decision=('Positive added lateral dependence in the frozen descendant tissue.' if primary['positive_above_3se']
              else 'Negative added lateral dependence in the frozen descendant tissue.'
              if primary['negative_below_minus_3se'] else 'The primary interaction is unresolved at three SE.')
    lines=['# Lateral dependence with tissue held fixed','',decision,'',
           f"Primary interaction: **{primary['mean']:+.4f} ± {primary['se']:.4f} F** (512 paired lives).",'',
           '| Contrast | Mean ± SE |','|---|---:|']
    for key,value in summary['contrasts'].items():
        lines.append(f"| {key.replace('_',' ')} | {value['mean']:+.4f} ± {value['se']:.4f} |")
    lines+=['',f"Scientific genome-lives: 4,096. Monitored CPU: {budget['cpu_seconds']:.3f} seconds. "
        'The separate 16-life preparation validation is not included in these estimates.','',
        'Both genotypes retain their own frozen tissue footprints. Freeze changes gene regulation as well as '
        'development. These comparisons do not establish a new algorithm, mature tissue, or matched-footprint '
        'information use. A small or unresolved interaction is not evidence of exact zero.','',
        'All four arms use the same 736-unit accounting window. Production guard/extinction charges remain in '
        'fitness; constant-tissue integration checks use only complete guard-free pairs. Whole-life end counts, '
        'path and last-birth descriptors are labelled separately from windowed fitness/captures/costs.','',
        'At t=768, the lateral lesion suppresses creation of new in-plane spike arrival messages; '
        'already scheduled messages, vertical spikes and chemical transport continue. The accounting window '
        'starts at 800 after pending structural claims and messages have settled. Prior dynamic state is retained.','',
        '[Preparation and validation](PREPARATION.md) · [Frozen protocol](protocol_excerpt.md)','',
        '```bash','.venv/bin/python results/frozen_20261013/analyze.py --study results/frozen_20261013',
        '```','']
    (out/'README.md').write_text('\n'.join(lines))
    files={str(path.relative_to(out)):{'sha256':accounting.digest(path),'bytes':path.stat().st_size}
           for path in sorted(out.rglob('*')) if path.is_file() and path.name!='provenance.json'
           and '__pycache__' not in path.parts and path.suffix != '.pyc'}
    write(out/'provenance.json',{'status':'complete','artifacts':files,'analysis_sha256':accounting.digest(Path(__file__)),
         'accounting_analysis_sha256':accounting.digest(BASE),'simulated_lives_by_analysis':0})


def self_check():
    background=np.array([100.,-200.,300.,-400.])
    matrix={key:np.stack([background,background]) for key in CONDITIONS}
    matrix['freeze'][1]+=[3,4,5,6]
    matrix['freeze+lateral_off'][1]+=[1,2,3,4]
    result=deltas(matrix)
    assert accounting.stats(result['frozen_lateral_interaction'])=={'mean':2.,'se':0.,'n':4}
    assert accounting.stats(result['interaction_change_under_freeze'])=={'mean':-2.,'se':0.,'n':4}
    print(json.dumps({'paired_covariance_self_check':'passed','simulated_lives':0}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=STUDY)
    parser.add_argument('--out',type=Path,default=ROOT/'results/frozen_20261013')
    parser.add_argument('--validate-smoke',action='store_true')
    parser.add_argument('--self-check',action='store_true')
    parser.add_argument('--export',action='store_true')
    args=parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not args.validate_smoke and not (args.study/'measurement/report.json').exists():
        print(json.dumps({'status':'awaiting_measurement','simulated_lives':0}))
        return
    summary,effects=analyze(args.study,args.validate_smoke)
    if args.export:
        if args.validate_smoke:
            raise ValueError('validation-only lives cannot be exported as scientific results')
        export(args.study,args.out,summary,effects)
    print(json.dumps({'status':summary['status'],'primary':summary['primary'],'simulated_lives':0},indent=2))


if __name__=='__main__':
    main()
