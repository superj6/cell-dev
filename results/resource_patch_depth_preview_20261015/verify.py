"""Verify saved preview bytes and four ledger comparisons; never execute a simulator."""
import hashlib
import json
import struct
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROLES = ('AO', 'G8_joint', 'Pareto4_joint', 'depth8_joint')


def read(name):
    return json.loads((HERE / name).read_text())


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def bits(values):
    return [struct.pack('<d', float(value)) for value in values]


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.values = False, []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            assert 'src' not in dict(attrs), 'external script dependency'
            self.active = True
            self.values.append('')

    def handle_data(self, text):
        if self.active:
            self.values[-1] += text

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False


def verify(*, check_budget=True):
    record, validation = read('execution_record.json'), read('validation.json')
    assert record['seed'] == 52530000 and record['roles'] == list(ROLES)
    assert validation['status'] == 'passed' and validation['JS_replays'] == 4
    assert validation['ledger_bits_checked'] == 428 and validation['ledger_values_per_role'] == 107
    assert validation['full_hashes_checked'] == 0 and not validation['real_browser_tested']
    assert validation['new_C_lives'] == validation['new_Python_lives'] == validation['builds'] == 0
    assert validation['record_sha256'] == sha('execution_record.json')
    assert validation['html_sha256'] == sha('resource_patch_depth.html')
    assert validation['replay_result_sha256'] == sha('replay_result.json')
    for key in ('source_pins', 'input_pins'):
        for name, digest in record[key].items():
            assert sha(name) == digest, name
    fixture, replay = read('inputs/fixture.json'), read('replay_result.json')
    assert fixture['seed'] == replay['seed'] == 52530000
    assert replay['status'] == 'passed' and replay['JS_replays'] == len(replay['cases']) == 4
    for i, role in enumerate(ROLES):
        case, returned = fixture['cases'][i], replay['cases'][i]
        assert case['role'] == returned['role'] == role and returned['status'] == 'passed'
        assert case['seed'] == returned['seed'] == 52530000 and case['body'] == returned['body'] == i
        assert case['native_row'] == i*512 and case['seed_row'] == 0
        packed = np.asarray(fixture['doc']['bodies'][i]['genome'], dtype=np.float64)
        pins = record['genome_pins'][role]
        assert packed.shape == (875,) and hashlib.sha256(packed.tobytes()).hexdigest() == pins['packed_sha256']
        assert fixture['doc']['bodies'][i]['genotype_sha256'] == pins['raw_sha256']
        assert sha(case['native_file']) == case['native_sha256']
        with np.load(HERE / case['native_file'], allow_pickle=False) as native:
            assert native['ledger'].shape == (2048, 107) and int(native['seeds'][0]) == 52530000
            assert native['row_ids'].tolist() == list(range(4))
            assert native['genome_raw_sha256'][i] == pins['raw_sha256']
            assert native['protocol_sha256'].item() == record['scientific_protocol_sha256']
            assert native['stage'].item() == 'confirmation' and native['world_name'].item() == 'patch'
            assert np.all(native['hashes'] == np.uint64(0x243F6A8885A308D3))
            assert bits(case['ledger']) == bits(returned['ledger']) == bits(native['ledger'][i*512])
    parsed = Scripts()
    parsed.feed((HERE / 'resource_patch_depth.html').read_text())
    assert len(parsed.values) == 4
    assert json.loads(parsed.values[0]) == {key: fixture[key] for key in ('seed', 'doc', 'roles')}
    for i, name in enumerate(('inputs/lifesim.js', 'inputs/resource_patches_view.js', 'page.js'), 1):
        assert parsed.values[i] == (HERE / name).read_text()
    if check_budget:
        budget = read('execution/budget.json')
        assert budget['status'] == 'complete' and budget['protocol_sha256'] == sha('execution_record.json')
        assert budget['attempt_sha256'] == sha('execution/attempt.json')
        assert not budget['running'] and not budget['queued']
        assert budget['terminal_cleanup']['all_owned_groups_exited']
        assert budget['terminal_cleanup']['all_worker_identities_exited']
        assert not budget['terminal_cleanup']['remaining_descendants']
        assert budget['package_cpu_seconds_allocated'] < 15 and budget['package_wall_seconds_allocated'] < 60
        assert budget['cap_rss_bytes'] == 1024**3 and budget['worker_address_space_bytes'] == 2*1024**3
    return dict(status='passed', html_sha256=sha('resource_patch_depth.html'), saved_ledger_bits=428,
                saved_full_hashes=0, embedded_sources_exact=True, embedded_fixture_exact=True,
                new_lives=0, builds=0, real_browser_tested=False)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
