"""First block121 NPZ check. Read seed members only; retain a targeted delta baseline.

No engine imports, outcome-array reads, namespace reservation, or study mutation.
The baseline records filesystem identity and seed-member hashes, not full NPZ hashes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import time
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
LOW, HIGH = 52_210_000, 52_220_000
SKIP = {'.git', '.venv', '__pycache__', 'node_modules'}


def stat_record(path):
    value = path.stat()
    return {key: getattr(value, 'st_' + key) for key in
            ('size', 'mtime_ns', 'ctime_ns', 'dev', 'ino')}


def main():
    started = time.monotonic()
    records, matches, errors = {}, [], []
    arrays = 0
    for top in (ROOT / 'results', ROOT / 'outputs'):
        for folder, dirs, names in os.walk(top, followlinks=False):
            base = Path(folder)
            dirs[:] = sorted(name for name in dirs if name not in SKIP
                              and not (base / name).is_relative_to(OUT)
                              and not (base / name).is_relative_to(ROOT / 'outputs/autonomous_visibility_lateral_20261014'))
            for name in sorted(names):
                if not name.endswith('.npz'):
                    continue
                path = base / name
                relative = str(path.relative_to(ROOT))
                synthetic = any(part.startswith('test_') for part in path.parts)
                record = {'synthetic_fixture': synthetic, 'seed_members': {}}
                records[relative] = record
                try:
                    record['stat'] = stat_record(path)
                    with zipfile.ZipFile(path) as archive:
                        names_seen = set()
                        for info in archive.infolist():
                            if not info.filename.endswith('.npy') or 'seed' not in info.filename.lower():
                                continue
                            if info.filename in names_seen:
                                raise ValueError('duplicate seed member')
                            names_seen.add(info.filename)
                            raw = archive.read(info)  # ZIP validates this seed member CRC.
                            array = np.load(io.BytesIO(raw), allow_pickle=False)
                            if not isinstance(array, np.ndarray) or not np.issubdtype(array.dtype, np.number):
                                raise ValueError('non-numeric seed member')
                            if not np.isfinite(array).all():
                                raise ValueError('non-finite seed member')
                            if not np.issubdtype(array.dtype, np.integer):
                                if not np.issubdtype(array.dtype, np.floating) or np.any(array != np.floor(array)):
                                    raise ValueError('non-integral seed member')
                            arrays += 1
                            record['seed_members'][info.filename] = {
                                'npy_sha256': hashlib.sha256(raw).hexdigest(),
                                'dtype': str(array.dtype), 'shape': list(array.shape),
                                'crc32': info.CRC, 'uncompressed_bytes': info.file_size,
                                'compressed_bytes': info.compress_size,
                            }
                            for value in array[(array >= LOW) & (array < HIGH)].flat:
                                matches.append({'path': relative, 'member': info.filename,
                                                'value': int(value), 'synthetic_fixture': synthetic})
                    if stat_record(path) != record['stat']:
                        raise ValueError('NPZ changed while reading seed members')
                except (OSError, ValueError, zipfile.BadZipFile, EOFError) as error:
                    record['error'] = type(error).__name__ + ': ' + str(error)
                    errors.append({'path': relative, 'error': record['error'], 'synthetic_fixture': synthetic})
                if len(records) % 10000 == 0:
                    print(json.dumps({'npz_files': len(records), 'seed_members': arrays,
                                      'elapsed_seconds': time.monotonic() - started}), flush=True)
    baseline = {'format': 1, 'block_half_open': [LOW, HIGH], 'records': records,
                'delta_rule': 'Enumerate current NPZ paths; reread additions and every file whose size/mtime_ns/ctime_ns/dev/ino differs. Preserve unchanged published archives. This is a filesystem-change baseline, not a full-NPZ cryptographic identity proof.'}
    target = OUT / 'npz_seed_baseline.json'
    target.write_text(json.dumps(baseline, indent=2) + '\n')
    result = {'status': 'completed_pending_match_error_classification', 'reserved': False,
              'whole_block_half_open': [LOW, HIGH], 'actual_seeds_half_open': [LOW, LOW + 128],
              'npz_files_checked': len(records), 'seed_members_checked': arrays,
              'numeric_matches': matches, 'errors': errors,
              'nonfixture_errors': [x for x in errors if not x['synthetic_fixture']],
              'baseline_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'wall_seconds': time.monotonic() - started,
              'scope': 'First single-range block121 check across results/ and outputs/ NPZ seed-named members only; own AA audit/study excluded. Outcome arrays are not opened. Names/ZIP metadata for other members may be inspected.',
              'simulation_calls': 0, 'compilation_calls': 0,
              'source_modules_imported': sorted(n for n in __import__('sys').modules if n == 'src' or n.startswith('src.'))}
    (OUT / 'npz_seed_review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'npz_files_checked', 'seed_members_checked',
          'numeric_matches', 'nonfixture_errors', 'wall_seconds', 'baseline_sha256')}, indent=2))


if __name__ == '__main__':
    main()
