"""Root check of artifact bytes in the working tree and actual Git index."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
public = root / sys.argv[1]
manifest = json.loads((public / 'manifest.json').read_text())
entries = manifest['artifacts']
for name, item in entries.items():
    data = (public / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == item['sha256'], name
    assert len(data) == item['bytes'], name
paths = sorted(p for p in public.rglob('*') if p.is_file())
for path in paths:
    rel = str(path.relative_to(root))
    indexed = subprocess.check_output(['git', 'show', ':' + rel], cwd=root)
    assert indexed == path.read_bytes(), rel
print(json.dumps({'status': 'passed', 'artifacts': len(entries),
                  'actual_index_files_checked': len(paths),
                  'manifest_sha256': hashlib.sha256((public / 'manifest.json').read_bytes()).hexdigest()}))
