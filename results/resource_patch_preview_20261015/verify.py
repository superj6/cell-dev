"""Verify the saved preview, embedded sources and exact replay evidence without running a life."""
import hashlib
import json
import struct
from html.parser import HTMLParser
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text())


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.values = []

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


def verify():
    record, validation, budget = read('execution_record.json'), read('validation.json'), read('execution/budget.json')
    assert validation['status'] == 'passed' and budget['status'] == 'complete'
    assert validation['JS_replays'] == 1 and validation['ledger_bits_checked'] == 107
    assert validation['full_hashes_checked'] == 5 and not validation['real_browser_tested']
    assert validation['new_C_lives'] == validation['new_Python_lives'] == validation['builds'] == 0
    assert validation['record_sha256'] == budget['protocol_sha256'] == sha('execution_record.json')
    assert validation['html_sha256'] == sha('resource_patch_AO.html')
    assert validation['replay_result_sha256'] == sha('replay_result.json')
    assert budget['attempt_sha256'] == sha('execution/attempt.json')
    assert not budget['running'] and not budget['queued']
    assert budget['terminal_cleanup']['all_owned_groups_exited']
    assert budget['terminal_cleanup']['all_worker_identities_exited']
    assert not budget['terminal_cleanup']['remaining_descendants']
    assert budget['package_cpu_seconds_allocated'] < 30 and budget['package_wall_seconds_allocated'] < 60
    for key in ('source_pins', 'input_pins'):
        for name, digest in record[key].items():
            assert sha(name) == digest, name
    fixture, replay = read('inputs/fixture.json'), read('replay_result.json')
    assert fixture['seed'] == record['seed'] == replay['seed'] == 42000000
    packed = np.asarray(fixture['doc']['bodies'][0]['genome'], dtype=np.float64)
    assert packed.shape == (875,) and hashlib.sha256(packed.tobytes()).hexdigest() == record['packed_genotype_sha256']
    assert fixture['doc']['bodies'][0]['genotype_sha256'] == record['genotype_sha256']
    with np.load(HERE / 'inputs/saved_C_full.npz', allow_pickle=False) as native:
        expected = [struct.pack('<d', float(value)) for value in native['ledger'][0]]
        assert [struct.pack('<d', float(value)) for value in fixture['truth']['ledger']] == expected
        assert [struct.pack('<d', float(value)) for value in replay['ledger']] == expected
        assert replay['hashes'] == fixture['truth']['hashes'] == [f'{int(value):016x}' for value in native['hashes'][0]]
    parsed = Scripts()
    parsed.feed((HERE / 'resource_patch_AO.html').read_text())
    assert len(parsed.values) == 4
    assert json.loads(parsed.values[0]) == {'seed': fixture['seed'], 'doc': fixture['doc']}
    assert parsed.values[1] == (HERE / 'inputs/lifesim.js').read_text()
    assert parsed.values[2] == (HERE / 'inputs/resource_patches_view.js').read_text()
    return dict(status='passed', html_sha256=sha('resource_patch_AO.html'), saved_ledger_bits=107,
                saved_full_hashes=5, embedded_sources_exact=True, embedded_fixture_exact=True,
                new_lives=0, builds=0, real_browser_tested=False)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
