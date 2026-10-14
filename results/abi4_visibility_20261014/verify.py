"""Verify the archived engineering evidence and its repository sources without simulation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
manifest = json.loads((HERE / 'manifest.json').read_text())
for base, entries in ((HERE, manifest['artifacts']), (ROOT, manifest['source_files'])):
    for name, expected in entries.items():
        actual = hashlib.sha256((base / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'changed artifact: {base / name}')
print(json.dumps(dict(status='verified', artifacts=len(manifest['artifacts']),
                      sources=len(manifest['source_files']), scientific_lives=0)))
