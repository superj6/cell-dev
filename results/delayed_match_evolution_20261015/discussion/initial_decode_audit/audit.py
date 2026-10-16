#!/usr/bin/env python3
"""Static readout bounds for the frozen inherited population; no engine import or RNG."""
import resource
import signal
import time

START_WALL = time.perf_counter()
START_CPU = time.process_time()
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
# A stricter address-space bound also bounds resident memory, unlike advisory RLIMIT_RSS on Linux.
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
resource.setrlimit(resource.RLIMIT_RSS, (512 * 1024**2, 512 * 1024**2))
signal.alarm(60)

import ast
import csv
import hashlib
import itertools
import json
import math
import os
from collections import Counter
from fractions import Fraction
from pathlib import Path
import struct
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
ROOT = HERE.parents[3]
INPUT_SHA = '56f81eaf0418a6589cca6505d33215c3e1448893d5285b7e909875217a7a6d19'
PINS = {
    'src/genome.py': '788a3d4465e006ad10e5c67ed2e464cb248066fa5d730e5afb31f4131edfaa4a',
    'src/evolve.py': '26929ca024c0ff2a395cab2898cf4f3f24eaae632fabb778d27cb7fb38fd647f',
    'src/life/spec.py': '8a74b75aa7c06be2f25fd3a012f56fe78c112354bc8311e0075f4db41ee5fbb8',
    'src/life/kernel.c': '20f7d3ee288e62bd3b65bc8c8c151866f60cfe86b46facc317a6695433d7861d',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def f32(x):
    return float(struct.unpack('<f', struct.pack('<f', x))[0])


def main():
    for name in ('audit.json', 'readout_bounds.csv', 'REPORT.md', 'resources.json'):
        if (HERE / name).exists():
            raise FileExistsError('Refusing to overwrite prior result: ' + name)
    protocol = json.loads((STUDY / 'protocol.json').read_text())
    for name, expected in PINS.items():
        assert sha(ROOT / name) == expected == protocol['production_pins'][name], name
    input_path = STUDY / 'inputs/input_population.json'
    assert sha(input_path) == INPUT_SHA
    population = json.loads(input_path.read_text())
    assert len(population['genomes']) == 32

    # Compile only these exact scalar functions/constants and two exact methods from pinned spec.py.
    # No imports from spec/lattice/Torch, no simulation, packing backend, or generated random values.
    tree = ast.parse((ROOT / 'src/life/spec.py').read_text())
    functions = {'sigmoid', 'clip', 'rint', 'q8', '_level', '_fate', '_decode21'}
    constants = {'G_MAX', 'KNOBS_V2', 'KNOBS_V3', 'DELTA', 'KAPPA', 'PHI', 'TAU_TR'}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
            nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == 'Abi':
            nodes.extend(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in ('readout', 'decode_knobs'))
    assert len(nodes) == len(functions) + len(constants) + 2
    scalar_source = ast.unparse(ast.Module(body=nodes, type_ignores=[])) + '\n'
    env = {'math': math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'pinned_spec_scalar_subset', 'exec'), env)
    # The extracted readout only needs these two slices; its own 16-column accumulation is unchanged.
    abi = SimpleNamespace(P=23, version=5, GENOME_SLICES={'A': (0, 368), 'a0': (368, 391)})
    readout = lambda packed, g: env['readout'](abi, packed, g)
    decode = lambda y: env['decode_knobs'](abi, y)
    knobs = list(env['KNOBS_V3'])
    continuous = {'asym', 'sec0', 'sec1'}
    rows, genomes = [], []
    corners_checked = 0

    for index, genome in enumerate(population['genomes']):
        active = [k for k, value in enumerate(genome['act']) if f32(value) > .5]
        assert active == list(range(8))
        assert len(genome['A']) == 23 and all(len(row) == 16 for row in genome['A'])
        A = [[f32(x) + 0.0 if k in active else 0.0 for k, x in enumerate(row)] for row in genome['A']]
        bias = [f32(x) + 0.0 for x in genome['a0']]
        assert all(math.isfinite(x) for row in A for x in row) and all(map(math.isfinite, bias))
        packed = [x for row in A for x in row] + bias
        initial_g = [env['sigmoid'](f32(x)) + 0.0 if k in active else 0.0 for k, x in enumerate(genome['s0'])]
        initial_y = readout(packed, initial_g)
        initial_theta = decode(initial_y)

        # Independent finite corner enumeration checks every reported extremum. Monotonicity of each
        # signed multiplication and ordered sum establishes extrema over the entire continuous box.
        corner_min = [math.inf] * 23
        corner_max = [-math.inf] * 23
        for bits in itertools.product((0.0, 1.0), repeat=len(active)):
            g = list(bits) + [0.0] * 8
            y = readout(packed, g)
            corner_min = [min(a, b) for a, b in zip(corner_min, y)]
            corner_max = [max(a, b) for a, b in zip(corner_max, y)]
            corners_checked += 1

        for p, knob in enumerate(knobs):
            low_g = [1.0 if x < 0 else 0.0 for x in A[p]]
            high_g = [1.0 if x > 0 else 0.0 for x in A[p]]
            low = readout(packed, low_g)[p]
            high = readout(packed, high_g)[p]
            assert low == corner_min[p] and high == corner_max[p] and low <= initial_y[p] <= high
            low_exact = Fraction(bias[p]) + sum((Fraction(x) for x in A[p] if x < 0), Fraction())
            high_exact = Fraction(bias[p]) + sum((Fraction(x) for x in A[p] if x > 0), Fraction())
            yl, yh = [0.0] * 23, [0.0] * 23
            yl[p], yh[p] = low, high
            dl, dh = decode(yl)[p], decode(yh)[p]
            assert dl <= initial_theta[p] <= dh
            coefficient_constant = all(x == 0 for x in A[p])
            # Strictly monotone continuous mathematical decoders: equal rounded endpoint values
            # alone are not taken as a proof of constancy. Discrete documented maps are nondecreasing.
            constant = coefficient_constant or (knob not in continuous and dl == dh)
            reason = ('all active readout coefficients zero' if coefficient_constant else
                      'monotone discrete decode endpoints equal' if constant else
                      'nonzero affine range under strictly monotone continuous decode' if knob in continuous else
                      'different decoded extrema; distinct abstract-box corners witness variation')
            rows.append(dict(genome_row=index, knob=knob, readout_row=p,
                             active_coefficients_nonzero=sum(x != 0 for x in A[p]),
                             exact_affine_lower=str(low_exact), exact_affine_upper=str(high_exact),
                             native_order_lower=low, native_order_upper=high,
                             decoded_lower=dl, decoded_upper=dh,
                             initial_readout=initial_y[p], initial_decoded=initial_theta[p],
                             proven_constant=constant, constant_value=dl if constant else None,
                             proof=reason))
        genomes.append(dict(row=index, old_id=population['ids'][index], active_slots=active,
                            initial_gene_state=initial_g, initial_readout=initial_y, initial_decoded=initial_theta))

    summary = []
    for knob in knobs:
        rr = [r for r in rows if r['knob'] == knob]
        cv = Counter(r['constant_value'] for r in rr if r['proven_constant'])
        summary.append(dict(knob=knob, constant_genomes=sum(r['proven_constant'] for r in rr),
                            constant_values=[dict(value=k, genomes=v) for k, v in sorted(cv.items())],
                            decoded_lower=min(r['decoded_lower'] for r in rr),
                            decoded_upper=max(r['decoded_upper'] for r in rr),
                            initial_values=sorted(set(r['initial_decoded'] for r in rr))))
    result = dict(status='complete', population_file=str(input_path.relative_to(ROOT)), population_sha256=INPUT_SHA,
                  protocol_sha256=sha(STUDY / 'protocol.json'), production_pins=PINS,
                  script_sha256=sha(Path(__file__)), scalar_subset_sha256=hashlib.sha256(scalar_source.encode()).hexdigest(),
                  abi=5, genomes=32, active_genes_per_genome=8, readouts_per_genome=23,
                  total_readout_intervals=len(rows), exhaustive_corners_checked=corners_checked,
                  method='Exact rational affine bounds plus native ordered float64 corner bounds; pinned monotone decoders.',
                  constant_test='Discrete endpoint equality, or identically zero active coefficients. Continuous sigmoid rows require identically zero coefficients.',
                  scope='Abstract independent gene-state box [0,1]^8, inactive states zero; no state reachability, cellular role, or whole-life neutrality claim.',
                  limits=['Bounds are marginal per readout; their extrema need not be simultaneously attainable.',
                          'Initial states are zygote before plane cues, activity, chemistry or division, not adult states.',
                          'A constant base channel weight need not make directional effective weights constant.',
                          'A variable knob need not change on any feasible trajectory or carry sensory information.',
                          'A constant knob does not make the body or membrane dynamics constant.'],
                  simulator_calls=0, builds=0, genetic_random_draws=0, scientific_random_draws=0,
                  summary=summary, genomes_initial=genomes, intervals=rows)
    (HERE / 'audit.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    with (HERE / 'readout_bounds.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (HERE / 'pinned_scalar_subset.py').write_text(scalar_source)
    report = [
        'Static decode accessibility of the 32 frozen inherited genomes. No lives, builds or random draws.', '',
        f'Input SHA256: `{INPUT_SHA}`. Script/source pins and all 736 intervals are in [audit.json](audit.json); '
        'the same intervals and initial outputs are in [readout_bounds.csv](readout_bounds.csv).', '',
        'Each active gene varies independently over [0,1] for this bound; inactive slots remain zero. '
        'The script uses exact scalar methods extracted from pinned spec.py, preserves float32 genome values and '
        'ordered float64 readouts, and independently verifies all extrema at 8,192 cube vertices. '
        'Exact rational affine bounds are retained as well. Equal endpoint values prove constancy for the documented '
        'nondecreasing discrete decoders. Continuous sigmoid readouts are declared constant only when every active '
        'coefficient is zero; floating saturation is not treated as a proof.', '',
        '| Knob | Genomes proved constant /32 | Constant values (genomes) | Decoded range across all boxes | Initial decoded values |',
        '|---|---:|---|---|---|'
    ]
    fmt = lambda x: f'{x:.8g}'
    for s in summary:
        values = ', '.join(f"{fmt(v['value'])} ({v['genomes']})" for v in s['constant_values']) or '—'
        initial = ', '.join(fmt(x) for x in s['initial_values'])
        if len(s['initial_values']) > 8:
            initial = f"{fmt(min(s['initial_values']))}…{fmt(max(s['initial_values']))}; {len(s['initial_values'])} values"
        report.append(f"| {s['knob']} | {s['constant_genomes']} | {values} | {fmt(s['decoded_lower'])}…{fmt(s['decoded_upper'])} | {initial} |")
    report += ['', 'These are marginal bounds, not reachable-state measurements. Different readout extrema can require '
               'different gene states. Initial outputs describe the zygote before local cues and activity, not the developed '
               'tissue. Nonconstant bounds establish available decoded variation in the abstract box, not a functioning '
               'sensory pathway. Constant base channel weights can coexist with chemically varying directional gains. '
               'Membrane activity, message timing, chemistry, gene recurrence and morphology can retain information even '
               'when individual phenotype knobs are constant. This does not test memory lifetime or whole-life neutrality.', '',
               'No gate, selection change or cell redesign follows. Resource caps are 30 CPU seconds, 60 wall seconds '
               'and 512 MiB RSS. A stricter 512 MiB address-space limit was applied, below the authorized 2 GiB ceiling; '
               'the process is single-threaded and imports no native simulation/numerical library. Full process usage '
               'is recorded externally in resources.txt, with internal accounting in resources.json.', '']
    (HERE / 'REPORT.md').write_text('\n'.join(report))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    resources = dict(cpu_seconds=time.process_time() - START_CPU, wall_seconds=time.perf_counter() - START_WALL,
                     peak_rss_bytes=usage.ru_maxrss * 1024, cpu_cap_seconds=30, wall_cap_seconds=60,
                     rss_cap_bytes=512 * 1024**2, applied_address_space_cap_bytes=512 * 1024**2,
                     authorized_address_space_ceiling_bytes=2 * 1024**3,
                     thread_count=len(list(Path('/proc/self/task').iterdir())), pid=os.getpid(),
                     note='Internal timing through output creation; external resources.txt covers whole process.')
    assert resources['thread_count'] == 1 and resources['peak_rss_bytes'] <= resources['rss_cap_bytes']
    (HERE / 'resources.json').write_text(json.dumps(resources, indent=2) + '\n')
    print(json.dumps({'status': 'complete', 'summary': summary, 'resources': resources}, indent=2))


if __name__ == '__main__':
    main()
