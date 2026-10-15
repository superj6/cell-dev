"""Source-only AM→AN base adaptation; never imports scientific inputs or engines."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'outputs/autonomous_capture_value_selection_20261015'
NEW=ROOT/'outputs/autonomous_occlusion_acquisition_20261015'
for name in ('measure.py','analyze.py'):
    s=(OLD/name).read_text()
    s=s.replace('ARMS = ("current_value", "high_value")','ARMS = ("acquisition",)')
    s=s.replace('ROLES = ("AI_control_start", "AL_mixture_start", "current_value_final", "high_value_final")',
                'ROLES = ("AM_current_start", "generation4", "generation8")')
    if name=='measure.py':
        s=s.replace('AM frozen four-role confirmation after both searches','AN fixed start, midpoint and final confirmation after one search')
        s=s.replace('def validate_search_state(state):','def validate_search_state(state, generation):')
        s=s.replace('if state["generation"] != 4 or [r["gen"] for r in state["curves"]] != list(range(4)):',
                    'if generation not in (4, 8) or state["generation"] != generation or [r["gen"] for r in state["curves"]] != list(range(generation)):')
        s=s.replace('both complete four-generation endpoints are required','the declared midpoint or final checkpoint is required')
        s=s.replace('"research_lives": 8192','"research_lives": 7680').replace('"rows": 16','"rows": 15')
        s=s.replace('4 fixed genomes x 4 worlds x 512','3 fixed genomes x 5 worlds x 512')
    else:
        s=s.replace('WORLDS = ("pool", "persistent", "blink80_5", "turn100_blink80_5")',
                    'WORLDS = ("pool", "persistent", "blink80_5", "blink80_20", "turn100_blink80_20")')
        s=s.replace('PAIRS = ((1, 0), (2, 0), (3, 0), (2, 1), (3, 1), (3, 2))',
                    'PAIRS = ((1, 0), (2, 0), (2, 1))')
        s=s.replace('fixed 4-genome by 4-world','fixed 3-genome by 5-world')
        s=s.replace('("pool", "blink80_5", "turn100_blink80_5")','("pool", "blink80_5", "blink80_20", "turn100_blink80_20")')
        s=s.replace('RETENTION = ((1, 0, "persistent"), (2, 0, "persistent"), (3, 0, "persistent"),\n             (2, 1, "pool"), (2, 1, "persistent"), (3, 1, "pool"), (3, 1, "persistent"))',
                    'RETENTION = ((1, 0, "pool"), (1, 0, "persistent"), (2, 0, "pool"), (2, 0, "persistent"))')
        for a,b in [('28748','28214'),('28756','28222'),('8192','7680'),('20556','20534'),('10278','20534'),('10240','20480'),('4064','2933')]:
            s=s.replace(a,b)
        s=s.replace('"rows": 16','"rows": 15').replace('"raw_rows": 16','"raw_rows": 15').replace('complete exact 16-row','complete exact 15-row')
        s=s.replace('"arms": list(ARMS), "generations": 4','"arms": list(ARMS), "generations": 8')
        s=s.replace('"research_lives_per_arm": 20534, "startup_lives_per_arm": 2','"research_lives_per_arm": 20534, "startup_lives_per_arm": 4')
        s=s.replace('expected_primary = [{"world": world, "new": ROLES[3], "old": ROLES[2], "metric": "captures"}\n                        for world in ("pool", "persistent")]',
                    'expected_primary = [{"world": "blink80_20", "new": ROLES[2], "old": ROLES[0], "metric": "captures"}]')
        start=s.index('    for role, reference in zip(ROLES[:2],')
        end=s.index('    record = protocol["population_start"]',start)
        s=s[:start]+'''    reference = protocol["reference"]
    path = local(base, reference["path"])
    if (reference["role"] != ROLES[0] or sha(path) != reference["file_sha256"]
            or protocol["original_input_pins"][reference["source"]] != sha(path)
            or hashlib.sha256(json_genome(path).tobytes()).hexdigest() != reference["raw_sha256"]):
        raise ValueError("retained reference bytes or origin differs")
''' + s[end:]
        s=s.replace('two native configs/shared seed required','one native config/fresh seed required')
        s=s.replace('"blink80_5": blink, "turn100_blink80_5": dict(blink, tau_turn=100.)}',
                    '"blink80_5": blink, "blink80_20": dict(blink, visibility_off=20.),\n                "turn100_blink80_20": dict(blink, visibility_off=20., tau_turn=100.)}')
        s=s.replace('for k in ("pool", "persistent")}', 'for k in ("pool", "persistent", "blink80_20")}')
        s=s.replace('fixed two-context selection physics differs','fixed three-context acquisition physics differs')
        s=s.replace('abi = 4 if name in ("blink80_5", "turn100_blink80_5") else 3',
                    'abi = 3 if name in ("pool", "persistent") else 4')
        s=s.replace('if len(identities) != 4', 'if len(identities) != 3')
        s=s.replace('one monitor and three sequential leaders required','one monitor and two sequential leaders required')
        s=s.replace('len({r["pid"] for r in workers}) != 3','len({r["pid"] for r in workers}) != 2')
        s=s.replace('not cumulative[0] <= cumulative[1] <= search_cpu <= cumulative[2] <= budget["cpu_seconds"]',
                    'not cumulative[0] <= search_cpu <= cumulative[1] <= budget["cpu_seconds"]')
    (NEW/name).write_text(s)
s=(OLD/'native_replay.py').read_text().replace('AM_recorded_ops','AN_recorded_ops')
s=s.replace("for arm in ('current_value', 'high_value'):","for arm in ('acquisition',):")
start=s.index("    for key in ('candidate_raw_sha256', 'candidate_row_sha256', 'genetic_signature_sha256'):")
end=s.index("    return {'status':",start)
s=s[:start]+s[end:]
s=s.replace("'all_256_candidate_bytes_equal': True, 'recorded_genetic_signatures_equal': True,", "'recorded_first_256_replayed': True,")
s=s.replace("'First-cohort fitness, survival and later genomes may differ between worlds.'", "'No paired search is present; this proof covers only recorded first-generation bytes.'")
(NEW/'native_replay.py').write_text(s)
shutil.copyfile(OLD/'replay_ops.py',NEW/'replay_ops.py')
