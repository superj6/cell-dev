"""Build a standalone viewer from frozen exports; no simulations or network access."""
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'results/atlas/persistent_target.html')
args=parser.parse_args()
data=(HERE/'bodies.json').read_text().strip()
engine=(ROOT/'results/atlas/play/lifesim.js').read_text()
ui=(HERE/'viewer.js').read_text()
assert '</script' not in data.lower() and '</script' not in engine.lower() and '</script' not in ui.lower()
export=json.loads((HERE/'export_receipt.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in export['source_pins'].items():assert sha(ROOT/name)==digest,name
assert json.loads((HERE/'replay_stdout.json').read_text())['status']=='complete'
assert json.loads((HERE/'ui_check.json').read_text())['status']=='passed'
text=(HERE/'template.html').read_text().replace('__DATA__',data).replace('__ENGINE__',engine).replace('__UI__',ui)
assert all(marker not in text for marker in ['__DATA__','__ENGINE__','__UI__'])
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(text)
print(json.dumps({'status':'built','html':str(args.output),'sha256':sha(args.output),'bytes':args.output.stat().st_size,'simulated_lives':0}))
