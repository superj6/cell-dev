"""Independent packed-graph and completed-endpoint checks; never simulate scientific lives."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'outputs/copy_connectivity_20261014/analyze.py'
SUMMARY = SOURCE.with_name('summary.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def graph(active, w, a, slot):
    """Boolean transitive closure, source first; independent of the reviewed DFS."""
    edge = (w.T != 0) & active[:, None] & active[None, :]
    closure = edge | (np.eye(len(active), dtype=bool) & active[:, None])
    for intermediate in range(len(active)):
        closure |= closure[:, intermediate, None] & closure[None, intermediate, :]
    reached = closure[slot]
    direct = np.flatnonzero(a[:, slot] != 0).tolist()
    others = np.flatnonzero(edge[slot] & (np.arange(len(active)) != slot)).tolist()
    readouts = np.flatnonzero(np.any(a[:, reached] != 0, axis=1)).tolist()
    return {'direct_readout_rows': direct, 'other_gene_targets': others,
            'reachable_active_genes': np.flatnonzero(reached).tolist(),
            'reachable_readout_rows': readouts, 'has_readout_path': bool(readouts)}


def check_selected_artifacts(folder, relatives):
    provenance = folder / 'provenance.json'
    saved = json.loads(provenance.read_text())
    for relative in relatives:
        path, record = folder / relative, saved['artifacts'][relative]
        assert sha(path) == record['sha256'] and path.stat().st_size == record['bytes']
    return sha(provenance)


def main():
    loader = importlib.util.spec_from_file_location('reviewed_copy_connectivity', SOURCE)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    helper = module.load_helper()
    original = module.observe
    counters = {'observed_genomes_checked': 0, 'copied_gene_records_checked': 0}

    def checked_observe(helper, genome, origins, generation, individual, retained):
        rows = original(helper, genome, origins, generation, individual, retained)
        packed = helper.pack(genome)
        active = helper.view(packed, 'act') > .5
        w, a = helper.view(packed, 'W')[:, :16], helper.view(packed, 'A')
        for row in rows:
            expected = graph(active, w, a, row['slot'])
            assert {key: row[key] for key in expected} == expected
        counters['observed_genomes_checked'] += 1
        counters['copied_gene_records_checked'] += len(rows)
        return rows

    module.observe = checked_observe
    generator, graph_cases = np.random.default_rng(0), 0
    for _ in range(100):
        active = generator.random(16) > .4
        w = (generator.random((16, 16)) > .8).astype(float)
        a = (generator.random((23, 16)) > .95).astype(float)
        for slot in np.flatnonzero(active):
            assert module.connectivity(active, w, a, slot) == graph(active, w, a, slot)
            graph_cases += 1
    archive = ROOT / 'results/structural_20261013'
    provenance = json.loads((archive / 'provenance.json').read_text())
    assert sha(archive / 'provenance.json') == module.ARCHIVE_SHA
    check_selected_artifacts(archive, list(provenance['artifacts']))
    saved = json.loads(SUMMARY.read_text())
    rerun = [module.run_archive(archive, run, helper) for run in (51089, 51090)]
    assert rerun == saved['runs']
    j = ROOT / 'results/duplicate_use_20261014'
    m = ROOT / 'results/gene_interaction_20261014'
    pins = {str(folder.relative_to(ROOT)): check_selected_artifacts(folder, names) for folder, names in (
        (j, ['measurement/genotypes.npz', 'measurement/manifest.json']),
        (m, ['genotypes.npy', 'measurement/manifest.json', 'analytical_proof/PROOF.md']))}
    jrows = np.load(j / 'measurement/genotypes.npz', allow_pickle=False)['genomes']
    mrows = np.load(m / 'genotypes.npy', allow_pickle=False)
    jmanifest = json.loads((j / 'measurement/manifest.json').read_text())
    endpoints = {}
    for run, jrow in ((51089, 0), (51090, 2)):
        population = json.loads((archive / f'runs/s{run}/population.json').read_text())
        raw = helper.from_json({'dims': population['dims'], 'params': population['genomes'][0]})
        assert helper.same(raw, jrows[jrow])
        assert helper.raw_sha(raw) == jmanifest['genome_raw_sha256'][jrow]
        assert population['origins'][0] == jmanifest['branches'][str(run)]['origins']
        if run == 51090:
            assert helper.same(raw, mrows[0])
        endpoints[str(run)] = {'raw_sha256': helper.raw_sha(raw),
                               'copy_connectivity': rerun[(run - 51089)]['final_rank0']}
    receipt = {'status': 'passed', 'simulated_lives': 0, 'active_study_outcomes_read': False,
        'reviewed_analyzer_sha256': sha(SOURCE), 'reviewed_summary_sha256': sha(SUMMARY),
        'review_script_sha256': sha(Path(__file__)), 'helper_sha256': sha(module.HELPER),
        'G_archive_provenance_sha256': sha(archive / 'provenance.json'), 'endpoint_archive_provenance': pins,
        'synthetic_graph_cases': graph_cases, **counters, 'complete_summary_replay_identical': True,
        'endpoints': endpoints,
        'source_semantics': ['W[target,source] feeds the target gene update; A[readout,gene] feeds phenotype.',
            'Independent Boolean transitive closure checks every observed copy on packed, '
            'inactive-masked coefficients.',
            'Whole-gene crossover precedes point mutation and structural operations; '
            'point mutations cannot target act.',
            'Copy origin follows its gene unit; outgoing W rows belong to regulated genes and may cross separately.',
            'Mutation opportunities count post-crossover carriers before structural operations, '
            'including later deletions.'],
        'limitations': ['Nonzero graph paths are potential coupling, '
            'not reachable activation, phenotype change or fitness.',
            'Repeated related genotypes/carriers are not independent samples; '
            'no probability or evolutionary SE inferred.',
            'Retention and connectivity alone do not show positive selection or expanded computation.',
            'Origins label copied gene units, not the ancestry of each outgoing edge.']}
    (OUT / 'independent_review.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({key: receipt[key] for key in ['status', 'synthetic_graph_cases',
        'observed_genomes_checked', 'copied_gene_records_checked', 'complete_summary_replay_identical']}, indent=2))


if __name__ == '__main__':
    main()
