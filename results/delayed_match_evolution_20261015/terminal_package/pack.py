"""Stage a complete terminal archive into a new outputs directory; never modify public results."""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import tarfile
import time
from pathlib import Path

import verify
from replay import bounded, new_output, save

HERE = Path(__file__).resolve().parent


def copy(source,destination):
    verify.require(source.is_file() and not source.is_symlink(),'regular source required: '+str(source))
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        verify.require(verify.sha(source) == verify.sha(destination),'refuse changed existing archive file '+str(destination))
    else:
        shutil.copy2(source,destination)


def tree(source,destination):
    total = 0
    for path in sorted(source.rglob('*')):
        verify.require(not path.is_symlink(),'symlink in evidence tree')
        if path.is_file() and not {'__pycache__','.pytest_cache','build-cache'} & set(path.relative_to(source).parts):
            verify.require(path.suffix not in ('.so','.pyc','.tmp'),'unexpected binary/cache/temp evidence')
            total += path.stat().st_size
            verify.require(total <= 256*1024**2,'evidence tree exceeds256MiB')
            copy(path,destination/path.relative_to(source))


def pack(args):
    started = time.monotonic()
    study = args.study.resolve()
    prospective = verify.ROOT/'results/delayed_match_evolution_20261015'
    out = new_output(args.out)
    # Refuse to inspect results before all required terminal states are complete.
    gates = [verify.read(study/name) for name in ('budget.json','study_complete.json','measurement_complete.json')]
    verify.require(all(value.get('status') == 'complete' for value in gates),'terminal gates incomplete')
    protocol,files = verify.terminal_bindings(study,str(args.summary.resolve()))
    prospective_manifest = verify.read(prospective/'manifest.json')
    verify.require(prospective_manifest['status'] == 'prospective','prospective archive must be untouched')
    for name,pin in prospective_manifest['files'].items():
        path = verify.checked_path(prospective,name)
        verify.require(verify.sha(path) == pin['sha256'] and path.stat().st_size == pin['bytes'],'prospective pin '+name)
    verify.require(verify.sha(study/'protocol.json') == verify.sha(prospective/'protocol.json'),'prospective protocol')
    verify.require(args.readme.read_bytes() != (prospective/'README.md').read_bytes(),'terminal README required')
    shutil.copytree(prospective,out,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    try:
        history = out/'registration_history'
        history.mkdir(exist_ok=False)
        for name in ('README.md','manifest.json','verify.py'):
            shutil.move(out/name,history/name)
        for name in ('release.json','attempt.json','budget.json','study_complete.json','measurement_complete.json',
                     'row_index.json','endpoints.json','startup.json'):
            copy(study/name,out/name)
        for name in ('runs','execution','terminal_audit'):
            tree(study/name,out/name)
        copy(args.summary.resolve(),out/'summary.json')
        copy(args.native_replay.resolve(),out/'native_replay_result.json')
        copy(args.readme.resolve(),out/'README.md')
        copy(args.report.resolve(),out/'TERMINAL_REPORT.md')
        for relative in args.include:
            source = verify.checked_path(study,relative)
            if source.is_dir():
                tree(source,verify.checked_path(out,relative))
            else:
                copy(source,verify.checked_path(out,relative))
        for name in ('verify.py','replay.py'):
            copy(HERE/name,out/name)
        tree(HERE,out/'terminal_package')
        archive_path = out/'raw_scored.tar.gz'
        with archive_path.open('xb') as output:
            with gzip.GzipFile(filename='',mode='wb',fileobj=output,mtime=0,compresslevel=6) as compressed:
                with tarfile.open(fileobj=compressed,mode='w|',format=tarfile.USTAR_FORMAT) as archive:
                    for name,digest in sorted(files.items()):
                        source = verify.checked_path(study,name)
                        verify.require(verify.sha(source) == digest,'raw/scored changed before packing')
                        member = tarfile.TarInfo(name)
                        member.size = source.stat().st_size
                        member.mode,member.uid,member.gid,member.mtime = 0o644,0,0,0
                        member.uname = member.gname = ''
                        with source.open('rb') as stream:
                            archive.addfile(member,stream)
        expanded = verify.verify_rows(out,files)
        save(out/'packaging_receipt.json',dict(status='staged',protocol_sha256=verify.PROTOCOL_SHA,
            source_revision=protocol['source_revision'],summary_sha256=verify.sha(out/'summary.json'),
            raw_scored_tar_sha256=verify.sha(archive_path),raw_scored_tar_bytes=archive_path.stat().st_size,
            prospective_manifest_sha256=verify.sha(history/'manifest.json'),
            helper_sha256=verify.sha(__file__),wall_seconds_before_verification=time.monotonic()-started,
            simulator_calls=0,builds=0,random_draws=0,**expanded))
        manifest = dict(status='complete',protocol_sha256=verify.PROTOCOL_SHA,research_lives=75894,
                        startup_lives=8,total_calls=75902,files={})
        for path in sorted(out.rglob('*')):
            if path.is_file():
                manifest['files'][str(path.relative_to(out))] = dict(sha256=verify.sha(path),bytes=path.stat().st_size)
        save(out/'manifest.json',manifest)
        return verify.verify(out)
    except BaseException as error:
        save(out/'packaging_failure.json',dict(status='failed',error=repr(error),simulator_calls=0,builds=0,random_draws=0))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,required=True)
    parser.add_argument('--summary',type=Path,required=True)
    parser.add_argument('--native-replay',type=Path,required=True)
    parser.add_argument('--readme',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--include',action='append',default=[],help='optional additional study-relative evidence')
    with bounded():
        print(json.dumps(pack(parser.parse_args()),indent=2))
