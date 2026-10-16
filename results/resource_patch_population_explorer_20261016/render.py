"""Render a completed saved-data population panel; stdlib only, no simulator or build."""
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'results/resource_patch_population_20261015'
PINS = {
    'population_rows.csv': 'a39c5d27ef45c8428bff95448126891d819eb1362058064ec839154304a949fe',
    'summary.json': 'bc83c4bde878b319316f7d3f2af13db2d851be729f5ce6c5aa7cd00bbf76f607',
    'inputs/rows.json': '1940813099dbda45292c896ef8ac94f310eba4d877dc49e73940e753b14be778',
    'study_complete.json': 'c67531cb783956400ef8aefccfcf24421396cbb0422beedf87d899b9f7a4500e',
    'tables_receipt.json': '656c464753b9c4c269a5ced91ef669512f68e02c576290b664b57970e8fce155',
    'terminal_tables/report_tables.py': '258ab80c691761847e3818f54c80fc94035546cf55f761f0fb40f0309e5b3b8f',
}
WORLDS = ['patch', 'pool', 'persistent', 'blink80_20', 'transfer']
METRICS = ['captures', 'total_patch_refill_harvest', 'F', 'cost']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    for name, digest in PINS.items():
        assert sha(SOURCE / name) == digest, name
    summary, manifest, terminal, tables = [read(SOURCE / name) for name in
        ('summary.json', 'inputs/rows.json', 'study_complete.json', 'tables_receipt.json')]
    assert summary['status'] == terminal['status'] == tables['status'] == 'complete'
    assert terminal['summary_sha256'] == tables['summary_sha256'] == PINS['summary.json']
    assert tables['files']['population_rows.csv'] == PINS['population_rows.csv']
    assert tables['source_sha256'] == PINS['terminal_tables/report_tables.py']
    assert summary['rows_manifest_sha256'] == PINS['inputs/rows.json']
    assert summary['row_manifest'] == manifest['rows'] and summary['paired_life_clusters'] == 32
    with (SOURCE / 'population_rows.csv').open(newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == 485 and len(manifest['rows']) == 97
    lookup = {(r['group'], int(r['local_row']), r['world']): r for r in csv_rows}
    assert len(lookup) == 485
    rows, numeric_checks = [], 0
    for index, item in enumerate(manifest['rows']):
        assert item['index'] == index
        order = next(r for r in summary['descriptive_orders'][item['group']]['rows'] if r['index'] == index)
        assert order['label'] == item['label'] and order['native_id'] == item['native_id']
        assert order['reported_endpoint'] == item['reported_endpoint']
        values = {}
        for world in WORLDS:
            row = lookup[(item['group'], item['row'], world)]
            assert int(row['native_id']) == item['native_id'] and row['raw_sha256'] == item['raw_sha256']
            assert row['reported_endpoint'] == str(item['reported_endpoint'])
            values[world] = {}
            for metric in METRICS:
                stat = summary['absolute'][world][item['label']][metric]
                assert stat['n'] == 32
                values[world][metric] = {key: stat[key] for key in ('mean', 'se')}
                for key in ('mean', 'se'):
                    assert math.isfinite(stat[key]) and float(row[f'{metric}_{key}']) == stat[key]
                    numeric_checks += 1
        rows.append(dict(item, values=values, fresh_rank=order['fresh_descriptive_rank']+1,
                         cached_rank=None if 'cached16_rank' not in order else order['cached16_rank']+1,
                         fresh_joint_minimum=order['fresh_joint_minimum']))
    assert {g: sum(r['group'] == g for r in rows) for g in ('G8', 'mean4', 'pareto4', 'AO')} == {
        'G8': 32, 'mean4': 32, 'pareto4': 32, 'AO': 1}
    assert sum(r['reported_endpoint'] for r in rows) == 4
    document = dict(rows=rows, worlds=WORLDS, seeds_per_world=32, source_pins=PINS,
                    scientific_protocol_sha256=summary['protocol_sha256'])
    payload = json.dumps(document, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    script = (HERE / 'client.js').read_text()
    assert '</script' not in script.lower()
    html = (HERE / 'template.html').read_text().replace('__DATA__', payload).replace('__CLIENT__', script)
    target = HERE / 'population_explorer.html'
    target.write_text(html)
    # Verify the exact embedded payload and script, not a second calculation from derived values.
    embedded = html.split('<script type="application/json" id="data">', 1)[1].split('</script>', 1)[0]
    assert json.loads(embedded) == document and html.count(script) == 1
    receipt = dict(status='passed', source_archive=str(SOURCE.relative_to(ROOT)), source_pins=PINS,
        renderer_sha256=sha(Path(__file__)), client_sha256=sha(HERE / 'client.js'),
        template_sha256=sha(HERE / 'template.html'), html_sha256=sha(target), html_bytes=target.stat().st_size,
        rows=97, worlds=5, CSV_rows_checked=485, exact_numeric_checks=numeric_checks,
        linked_scatter_points=388, historical_endpoint_rows=4, embedded_data_exact=True,
        simulations=0, builds=0, random_draws=0, real_browser_tested=False,
        limitation='Development means and descriptive ranks only; no endpoint replacement or winner certification.')
    (HERE / 'verification.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
