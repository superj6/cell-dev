"""Export unchanged published AE genomes and first-seed truth, without simulation."""
from pathlib import Path
import hashlib
import json
import numpy as np
from src.life import spec

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
AE = ROOT / 'results/prediction_gradient_20261014'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(AE/'analysis_result/summary.json') == 'e269cab21b720053fcb0ae14febfd62b76a86c7a91bb49cc0a7cedc536721628'
summary = json.loads((AE/'analysis_result/summary.json').read_text())
protocol = json.loads((AE/'protocol.json').read_text())
roles = json.loads((AE/'confirmation_roles.json').read_text())
with np.load(AE/'confirmation_genotypes.npz', allow_pickle=False) as data:
    raw = data['genomes'].copy()
assert raw.shape == (4,875) and raw.dtype == np.float32
atlas = json.loads((ROOT/'results/atlas/play/bodies.json').read_text())
assert protocol['world']['drag_exp'] == atlas['drag']['drag_exp']
seed = protocol['seeds']['confirm'][0]
assert seed == 52300000
pins = {str(p.relative_to(ROOT)):sha(p) for p in [AE/'protocol.json', AE/'analysis_result/summary.json',
        AE/'confirmation_roles.json', AE/'confirmation_genotypes.npz',
        ROOT/'src/life/spec.py', ROOT/'results/atlas/play/lifesim.js', ROOT/'results/atlas/play/bodies.json']}
world = {k:protocol['world'][k] for k in spec.V3.WORLD_KEYS}
packed = spec.V3.pack_genomes(raw, 'hexprism')
bodies = []
truth = []
for i,role in enumerate(roles['roles']):
    assert hashlib.sha256(raw[i].tobytes()).hexdigest() == roles['genotype_sha256'][role]
    bodies.append({'name':role,'abi':3,'mode':'grn','world':world,'genome':packed[i].tolist(),
                   'genotype_sha256':roles['genotype_sha256'][role]})
    p=AE/f'measurement/confirm/persistent/confirm/row_{i:04d}.npz'
    pins[str(p.relative_to(ROOT))]=sha(p)
    with np.load(p,allow_pickle=False) as data:
        assert int(data['seeds'][0]) == seed
        truth.append({'role':role,'seed':seed,'ledger_hex':[float(v).hex() for v in data['ledger'][0]],
                      'ledger':[float(v) for v in data['ledger'][0]],'source_sha256':sha(p)})
doc={'abi':3,'seed':seed,'bodies':bodies,'drag':atlas['drag'],
     'lattice':atlas['lattice'],'genome_slices':atlas['genome_slices'],
     'summary':{b:summary['contrasts'][f'H_{b}_minus_P_{b}'] for b in ['D90','L92']},
     'source_summary_sha256':sha(AE/'analysis_result/summary.json')}
for name,value in [('bodies.json',doc),('truth.json',{'seed':seed,'cases':truth,'ledger':list(spec.V3.LEDGER)}),
                   ('export_receipt.json',{'status':'exported_without_simulation','source_pins':pins,
                    'seed_policy':'First already-published AE confirmation seed; illustrative, not selected for outcome.',
                    'new_genetic_draws':0,'new_simulated_lives':0,'compiled_libraries':0})]:
    with (HERE/name).open('x') as f:f.write(json.dumps(value,separators=(',',':'))+'\n')
print(json.dumps({'status':'exported','roles':roles['roles'],'seed':seed,'new_lives':0}))
