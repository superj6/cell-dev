"""Verify the terminal archive and exact stored rows without importing simulation code."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent/'.git').is_dir())
PROTOCOL_SHA = '2941610e25eb55f5e3b4ca2f0be91db46931573b24788bb85709c5b8464d9345'
REVISION = '968bb81f2e146e2e729bca43004628d78a6e9b99'
ROLES = ('AM_reference','AO_start','mixed8','mixed24')
WORLDS = ('match85','pool','persistent','blink80_20','match1024','short_blank','transfer')
MAX_MEMBER = 32*1024**2
MAX_RAW = 256*1024**2


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2),b''):
            digest.update(chunk)
    return digest.hexdigest()


def checked_path(base, name):
    relative = PurePosixPath(name)
    require(relative.parts and not relative.is_absolute() and str(relative) == name
            and all(part not in ('','.','..') for part in relative.parts),'unsafe path: '+name)
    path = base
    for part in relative.parts:
        path /= part
        require(not path.is_symlink(),'symlink: '+name)
    require(path.resolve().is_relative_to(base.resolve()),'escaped path: '+name)
    return path


def confirmation_files(index):
    expected = {f'raw/{world}/row_{i:02d}.npz' for world in WORLDS for i in range(4)}
    require(set(index) == expected,'exact28 confirmation batches')
    files = {}
    for world in WORLDS:
        for i,role in enumerate(ROLES):
            raw = f'raw/{world}/row_{i:02d}.npz'
            scored = f'scored/{world}/row_{i:02d}.npz'
            row = index[raw]
            require(row['status'] == 'validated' and row['lives'] == row['requested_lives'] == 512
                    and row['role'] == role and row['world'] == world and row['abi'] == 5,'row identity')
            require(row['scored_path'] == scored,'scored path')
            files[raw],files[scored] = row['sha256'],row['scored_sha256']
    return files


def verify_rows(archive, files, destination=None):
    """Validate and optionally stream regular members; never use tar.extractall."""
    seen,previous,total = set(),'',0
    with tarfile.open(archive/'raw_scored.tar.gz','r:gz') as stream:
        for member in stream:
            name = member.name
            require(name in files and name not in seen and name > previous,'unexpected/duplicate/unsorted tar member')
            require(member.type == tarfile.REGTYPE and not member.issparse(),'nonregular tar member')
            require(0 < member.size <= MAX_MEMBER,'tar member size')
            require(member.mode == 0o644 and member.uid == member.gid == member.mtime == 0
                    and member.uname == member.gname == '' and not member.pax_headers,'tar metadata')
            total += member.size
            require(total <= MAX_RAW,'tar expanded byte limit')
            source = stream.extractfile(member)
            require(source is not None,'missing member stream')
            output = None
            if destination is not None:
                path = checked_path(destination,name)
                path.parent.mkdir(parents=True,exist_ok=True)
                output = path.open('xb')
            digest,count = hashlib.sha256(),0
            try:
                with source:
                    for chunk in iter(lambda source=source: source.read(1024**2),b''):
                        digest.update(chunk)
                        count += len(chunk)
                        if output is not None:
                            output.write(chunk)
            finally:
                if output is not None:
                    output.close()
            require(count == member.size and digest.hexdigest() == files[name],'member digest: '+name)
            seen.add(name)
            previous = name
    require(seen == set(files) and len(seen) == 56,'exact56 native/scored members')
    return dict(raw_scored_members=len(seen),raw_scored_uncompressed_bytes=total)


def terminal_bindings(base, summary='summary.json'):
    protocol = read(base/'protocol.json')
    require(sha(base/'protocol.json') == PROTOCOL_SHA and protocol['source_revision'] == REVISION,'fixed protocol')
    require(tuple(protocol['roles']) == ROLES and tuple(protocol['worlds']) == WORLDS,'four-role/seven-world scope')
    require(protocol['seeds'] == list(range(52460000,52460512)) and protocol['native_seed'] == 53233,'seed scope')
    require(read(base/'READY.json')['protocol_sha256'] == PROTOCOL_SHA,'READY binding')
    release = read(base/'release.json')
    require(release['status'] == 'released' and release['protocol_sha256'] == PROTOCOL_SHA,'release binding')
    review = read(base/'reviews/actual_input_review.json')
    require(review['status'] == 'passed' and review['protocol_sha256'] == PROTOCOL_SHA,'input review binding')
    for category in ('source_pins','input_pins'):
        for name,digest in protocol[category].items():
            require(sha(checked_path(base,name)) == digest,'frozen '+name)
    for field,name in (('seed_audit_sha256','namespace/seed_audit.json'),('reservation_sha256','reservation.json')):
        require(sha(base/name) == protocol[field],'namespace binding')
    budget,whole,measured = [read(base/name) for name in ('budget.json','study_complete.json','measurement_complete.json')]
    require(all(item['status'] == 'complete' and item['protocol_sha256'] == PROTOCOL_SHA
                for item in (budget,whole,measured)),'three complete markers')
    require((whole['research_lives'],whole['startup_lives'],whole['total_calls']) == (75894,8,75902),'total calls')
    require((measured['research_lives'],measured['startup_lives'],measured['rows']) == (14336,4,28),'confirmation calls')
    require(whole['measurement_complete_sha256'] == sha(base/'measurement_complete.json'),'measurement binding')
    require(measured['row_index_sha256'] == sha(base/'row_index.json')
            and measured['endpoints_sha256'] == sha(base/'endpoints.json'),'row/endpoint binding')
    require(budget['release_sha256'] == sha(base/'release.json')
            and budget['attempt_sha256'] == sha(base/'attempt.json'),'ownership binding')
    require(budget['cpu_seconds'] < 10680 and budget['wall_seconds'] < 7080
            and budget['search_cpu_seconds'] < 8280 and budget['confirmation_cpu_seconds'] < 2400,'runtime caps')
    for item in (budget,*[read(base/meta['path']) for meta in budget['phase_records'].values()]):
        require(item['exit_code'] == item['worker_exit_code'] == 0 and not item['running'] and not item['queued'],
                'cleared worker status')
        cleanup = item['terminal_cleanup']
        require(cleanup['same_pid_namespace'] and cleanup['all_owned_groups_exited']
                and cleanup['all_worker_identities_exited'] and not cleanup['remaining_descendants'],'owned cleanup')
    for meta in budget['phase_records'].values():
        path = checked_path(base,meta['path'])
        require(sha(path) == meta['sha256'],'phase budget digest')
        value = read(path)
        require(value['status'] == 'complete' and value['protocol_sha256'] == PROTOCOL_SHA,'phase completion')
        require(value['attempt_sha256'] == sha(path.parent/'attempt.json'),'phase attempt binding')
        require(value['peak_owned_rss_bytes'] < value['cap_rss_bytes'] == 4*1024**3
                and value['available_memory_bytes'] >= value['minimum_available_bytes'] == 4*1024**3
                and value['worker_address_space_bytes'] == 8*1024**3,'phase memory bounds')
    require(set(whole['search_complete_pins']) == {'mixed'},'one search')
    folder = base/'runs/mixed'
    marker = read(folder/'search_complete.json')
    require(whole['search_complete_pins']['mixed'] == sha(folder/'search_complete.json'),'search marker binding')
    require(marker['status'] == 'complete' and marker['research_lives'] == 61558 and marker['startup_lives'] == 4
            and marker['protocol_sha256'] == PROTOCOL_SHA and marker['release_sha256'] == sha(base/'release.json'),
            'search scope')
    for name,digest in marker['output_pins'].items():
        require(sha(checked_path(folder,name)) == digest,'search evidence '+name)
    for name,pin in marker['checkpoint_log_pins'].items():
        path = checked_path(folder,name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'],'checkpoint log '+name)
    for name in ('startup.json','runs/mixed/search_startup.json'):
        startup = read(base/name)
        require(startup['startup_lives'] == 4 and startup['protocol_sha256'] == PROTOCOL_SHA
                and startup['identity'] == protocol['expected_numerical_identity'],'startup identity')
        matched = startup['matching']
        callpath = checked_path(base,matched['calls_path'])
        require(matched['lives'] == 2 and matched['calls_sha256'] == sha(callpath),'matching startup binding')
        calls = read(callpath)
        require([item['backend'] for item in calls] == ['C_full','C_fast'],'two startup matching calls')
        for item,name in zip(calls,('full.npz','fast.npz')):
            require(item['status'] == 'validated' and item['seed'] == 42000000
                    and item['raw_sha256'] == sha(callpath.parent/name),'startup raw binding')
    endpoints = read(base/'endpoints.json')
    require(endpoints['roles'] == list(ROLES) and endpoints['protocol_sha256'] == PROTOCOL_SHA,'endpoint scope')
    for row,role in zip(endpoints['genomes'],ROLES):
        require(row['role'] == role and sha(checked_path(base,row['path'])) == row['file_sha256'],'endpoint genotype')
    result = read(base/summary)
    require(result['status'] == 'complete' and result['protocol_sha256'] == PROTOCOL_SHA
            and result['row_index_sha256'] == sha(base/'row_index.json'),'summary binding')
    require((result['research_lives'],result['startup_lives'],result['paired_life_clusters']) == (14336,4,512),
            'summary scope')
    return protocol,confirmation_files(read(base/'row_index.json'))


def verify(archive=HERE):
    archive = Path(archive).resolve()
    manifest = read(archive/'manifest.json')
    require(manifest['status'] == 'complete' and manifest['total_calls'] == 75902,'terminal manifest')
    require(not any(path.is_symlink() for path in archive.rglob('*')),'archive symlink')
    actual = {str(path.relative_to(archive)) for path in archive.rglob('*') if path.is_file()
              and path != archive/'manifest.json' and '__pycache__' not in path.parts}
    require(actual == set(manifest['files']),'manifest file set')
    for name,pin in manifest['files'].items():
        path = checked_path(archive,name)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'],'manifest '+name)
    historical = read(archive/'registration_history/manifest.json')
    for name,pin in historical['files'].items():
        kept = 'registration_history/'+name if name in ('README.md','verify.py') else name
        path = checked_path(archive,kept)
        require(sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'],'prospective bytes '+name)
    protocol,files = terminal_bindings(archive)
    require(manifest['protocol_sha256'] == PROTOCOL_SHA,'manifest protocol')
    for name,digest in protocol['production_pins'].items():
        source = subprocess.check_output(['git','show',REVISION+':'+name],cwd=ROOT)
        require(hashlib.sha256(source).hexdigest() == digest,'committed dependency '+name)
    for row in read(archive/'namespace_references.json'):
        require(sha(checked_path(ROOT,row['public_path'])) == row['sha256'],'historical namespace pin')
    audit = read(archive/'terminal_audit/audit_receipt.json')
    require(audit['status'] == 'passed' and audit['pins']['protocol.json'] == PROTOCOL_SHA
            and audit['pins']['summary'] == sha(archive/'summary.json')
            and audit['pins']['row_index.json'] == sha(archive/'row_index.json'),'independent audit binding')
    native = read(archive/'native_replay_result.json')
    require(native['status'] == 'passed' and native['protocol_sha256'] == PROTOCOL_SHA
            and native['offspring_replayed'] == 5376 and native['point_additions_replayed'] == 10752
            and native['simulated_lives'] == native['random_draws'] == 0,'native replay receipt')
    data = verify_rows(archive,files)
    return dict(status='passed',archive_files=len(actual),protocol_sha256=PROTOCOL_SHA,
        summary_sha256=sha(archive/'summary.json'),row_index_sha256=sha(archive/'row_index.json'),
        raw_scored_tar_sha256=sha(archive/'raw_scored.tar.gz'),completed_calls=75902,
        verifier_simulator_calls=0,verifier_builds=0,**data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=HERE)
    print(json.dumps(verify(parser.parse_args().archive),indent=2))
