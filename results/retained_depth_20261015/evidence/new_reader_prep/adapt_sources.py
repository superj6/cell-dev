"""Source-only AN→AO retention-depth matrix adaptation; no inputs, genetics or lives."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OLD=ROOT/'outputs/autonomous_occlusion_acquisition_20261015'
NEW=ROOT/'outputs/autonomous_retained_depth_20261015'

def get(text,name):
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])
def put(text,name,value):
    return text.replace(get(text,name),value.strip())

m=(OLD/'measure.py').read_text()
m=m.replace('AN fixed start, midpoint and final confirmation after one search', 'AO fixed references, midpoint and final confirmation after two searches')
m=m.replace('ARMS = ("acquisition",)','ARMS = ("unchanged", "balanced")')
m=m.replace('ROLES = ("AM_current_start", "generation4", "generation8")','ROLES = ("AM_reference", "AN_start", "unchanged8", "unchanged24", "balanced8", "balanced24")')
m=m.replace('generation not in (4, 8)','generation not in (8, 24)')
f=get(m,'freeze_endpoints')
start=f.index('    reference = protocol["reference"]')
body_start=f.index('    folder = STUDY / "runs/acquisition"')
body_end=f.index('    loaded = [Layout.load(path) for path in paths]')
body=f[body_start:body_end]
body=body.replace('folder = STUDY / "runs/acquisition"','folder = STUDY / "runs" / arm').replace('protocol["configs"]["acquisition"]','protocol["configs"][arm]').replace('selection_config("acquisition",','selection_config(arm,')
body=body.replace('    paths = [STUDY / reference["path"]]\n','')
body=body.replace('((4, folder / "generation4"), (8, folder))','((8, folder / "generation8"), (24, folder))')
body=body.replace('generation == 8','generation == 24').replace('generation == 4','generation == 8').replace('"generation": 4','"generation": 8')
body='\n'.join('    '+line if line else '' for line in body.rstrip().splitlines())+'\n'
header='''    references = (protocol["ancestral_reference"], protocol["reference"])
    for role, reference in zip(ROLES[:2], references):
        if reference["role"] != role or sha(STUDY / reference["path"]) != reference["file_sha256"]:
            raise ValueError("fixed starting reference differs")
    paths = [STUDY / reference["path"] for reference in references]
    searches, midpoints = {}, {}
    for arm in ARMS:
'''
f=f[:start]+header+body+'        searches[arm], midpoints[arm] = records[24], records[8]\n'+f[body_end:]
f=f.replace('genomes.shape != (3, 875)','genomes.shape != (6, 875)').replace('three exact BODY-1','six exact BODY-1')
f=f.replace('if raw_sha(genomes[0]) != reference["raw_sha256"]:', 'if any(raw_sha(genomes[i]) != reference["raw_sha256"] for i, reference in enumerate(references)):')
f=f.replace('"searches": {"acquisition": records[8]}, "midpoint": records[4]', '"searches": searches, "midpoints": midpoints')
f=f.replace('Generation4 and generation8 population rank0 endpoints fixed before confirmation; final is never replaced by midpoint.', 'Both generation8 and generation24 rank0 endpoints from both24-generation searches fixed before confirmation; no outcome-based replacement.')
m=put(m,'freeze_endpoints',f)
m=m.replace('"research_lives": 7680','"research_lives": 15360').replace('"rows": 15','"rows": 30').replace('3 fixed genomes x 5 worlds','6 fixed genomes x 5 worlds')
(NEW/'measure.py').write_text(m)

a=(OLD/'analyze.py').read_text()
a=a.replace('ROLES = ("AM_current_start", "generation4", "generation8")','ROLES = ("AM_reference", "AN_start", "unchanged8", "unchanged24", "balanced8", "balanced24")')
a=a.replace('ARMS = ("acquisition",)','ARMS = ("unchanged", "balanced")')
a=a.replace('PAIRS = ((1, 0), (2, 0), (2, 1))','PAIRS = tuple((a, b) for b in range(6) for a in range(b + 1, 6))')
a=a.replace('RETENTION = ((1, 0, "pool"), (1, 0, "persistent"), (2, 0, "pool"), (2, 0, "persistent"))','RETENTION = tuple((candidate, reference, world) for candidate in range(2, 6)\n                  for reference, worlds in ((1, ("pool", "persistent", "blink80_20")),\n                                            (0, ("pool", "persistent"))) for world in worlds) + ((5, 3, "blink80_20"),)')
a=a.replace('28214','138476').replace('28222','138488').replace('7680','15360').replace('20534','61558').replace('2933','11967')
a=a.replace('"startup_lives"] != 8','"startup_lives"] != 12').replace('"startup_lives": 8','"startup_lives": 12')
a=a.replace('"raw_rows": 15','"raw_rows": 30').replace('"rows": 15','"rows": 30').replace('exact 15-row','exact 30-row')
a=a.replace('"native_search_lives": 61558','"native_search_lives": 123116')
# Search one-arm count stays61558, but scope now24generations.
f=get(a,'verify_protocol').replace('"generations": 8','"generations": 24')
f=f.replace('"cpu_seconds": 10800','"cpu_seconds": 28800').replace('"wall_seconds": 5400','"wall_seconds": 14400').replace('"search_cpu_seconds": 7200','"search_cpu_seconds": 24000').replace('"confirmation_cpu_seconds": 3600','"confirmation_cpu_seconds": 4800')
f=f.replace('expected_primary = [{"world": "blink80_20", "new": ROLES[2], "old": ROLES[0], "metric": "captures"}]', 'expected_primary = [{"world": world, "new": ROLES[5], "old": ROLES[3], "metric": "captures"}\n                        for world in ("pool", "blink80_20")]')
f=f.replace('if protocol["primary"] != expected_primary:', 'if (protocol["primary"] != expected_primary or protocol["primary_noninferiority"] != {\n            "world": "blink80_20", "new": ROLES[5], "old": ROLES[3], "metric": "captures", "retained_fraction": .9}):')
start=f.index('    reference = protocol["reference"]')
end=f.index('    record = protocol["population_start"]')
oldref=f[start:end]
newref='    for index, name in enumerate(("ancestral_reference", "reference")):\n'+ '\n'.join('    '+line for line in oldref.rstrip().splitlines())+'\n'
newref=newref.replace('reference = protocol["reference"]','reference = protocol[name]').replace('reference["role"] != ROLES[0]','reference["role"] != ROLES[index]')
f=f[:start]+newref+f[end:]
f=f.replace('one native config/fresh seed required','two paired native configs/fresh shared seed required')
a=put(a,'verify_protocol',f)
# Restore three-phase resource schema from completed AM, changing only caps and total counts.
am=(ROOT/'outputs/autonomous_capture_value_selection_20261015/analyze.py').read_text()
f=get(am,'verify_terminal')
f=f.replace('10800','28800').replace('5400','14400').replace('7200','24000').replace('3600','4800')
f=f.replace('28748','138476').replace('28756','138488').replace('"startup_lives": 8','"startup_lives": 12')
a=put(a,'verify_terminal',f)
# Each direct child independently performs four startup lives.
f=get(a,'verify_startup')
f=f.replace('(("confirmation", "startup.json"), ("acquisition", "runs/acquisition/search_startup.json"))', '(("confirmation", "startup.json"), *[(arm, f"runs/{arm}/search_startup.json") for arm in ARMS])')
f=f.replace('"search_startup": receipts["acquisition"], "total_startup_lives": 8', '"search_startups": {arm: receipts[arm] for arm in ARMS}, "total_startup_lives": 12')
a=put(a,'verify_startup',f)
# Arm-specific endpoint checker is the AN checker with one shared structural extraction.
f=get(a,'verify_endpoints')
start=f.index('    arm = "acquisition"')
stop=f.index('    proof = read(base / "first_cohort_replay.json")')
armbody=f[start:stop].replace('    arm = "acquisition"\n','')
armbody=armbody.replace('list(range(8))','list(range(24))').replace('[0, 4, 7]','[0, 4, 8, 12, 16, 20, 23]').replace('len(lineage) != 9','len(lineage) != 25')
armbody=armbody.replace('record["generation"] != 8','record["generation"] != 24').replace('eight-generation','twenty-four-generation')
armbody=armbody.replace('manifest["genomes"][2]','manifest["genomes"][final_index]').replace('manifest["genomes"][1]','manifest["genomes"][midpoint_index]')
armbody=armbody.replace('"gen fixed 2pool/2persistent/4blink80_20 per8 repeated for recheck; diagnostics=persistent neutral; R_cap500"','"gen fixed per-arm allocation per8 repeated for recheck; unchanged2/2/4 balanced4/2/2; diagnostics=persistent neutral; R_cap500"')
armbody=armbody.replace('"pattern": ["pool", "persistent", "blink80_20", "blink80_20"] * 2,','"pattern": (["pool", "persistent", "blink80_20", "blink80_20"] if arm == "unchanged"\n                    else ["pool", "persistent", "pool", "blink80_20"]) * 2,')
armbody=armbody.replace('generation4/','generation8/').replace('"selection": 20480, "valid": 48','"selection": 61440, "valid": 112').replace('"native_evals": 2560, "generations": 8','"native_evals": 7680, "generations": 24')
armbody=armbody.replace('"generations": 8, "evals": 2560','"generations": 24, "evals": 7680')
armbody=armbody.replace('manifest["midpoint"]','manifest["midpoints"][arm]').replace('"generation": 4','"generation": 8').replace('lineage[4]','lineage[8]').replace('curves[:4]','curves[:8]').replace('lineage[:5]','lineage[:9]').replace('generation4 passive','generation8 passive')
armbody+='    return {"generation": 24, "rank": 0, "health": health,\n            "guards_retained": marker["health"]["pop_guard"], "count_proof": marker["count_proof"]}, lineage\n'
helper='def verify_search_endpoint(base, protocol, identity, manifest, arm, midpoint_index, final_index):\n'+armbody
prefix=f[:start]
prefix=prefix.replace('len(manifest["genomes"]) != 3','len(manifest["genomes"]) != 6').replace('or set(manifest["searches"]) != set(ARMS)', 'or set(manifest["searches"]) != set(ARMS) or set(manifest["midpoints"]) != set(ARMS)')
prefix=prefix.replace('Generation4 and generation8 population rank0 endpoints fixed before confirmation; final is never replaced by midpoint.', 'Both generation8 and generation24 rank0 endpoints from both24-generation searches fixed before confirmation; no outcome-based replacement.')
oldpaths='expected_paths = [protocol["reference"]["path"], "runs/acquisition/generation4/best_genome.json",\n                      "runs/acquisition/best_genome.json"]'
newpaths='expected_paths = [protocol["ancestral_reference"]["path"], protocol["reference"]["path"],\n                      *[path for arm in ARMS for path in (f"runs/{arm}/generation8/best_genome.json",\n                                                          f"runs/{arm}/best_genome.json")]]'
prefix=prefix.replace(oldpaths,newpaths)
prefix=prefix.replace('if manifest["genomes"][0]["raw_sha256"] != protocol["reference"]["raw_sha256"]:', 'if any(manifest["genomes"][i]["raw_sha256"] != protocol[key]["raw_sha256"]\n           for i, key in enumerate(("ancestral_reference", "reference"))):')
prefix+='    reviews, lineages = {}, {}\n    for arm, mid_index in zip(ARMS, (2, 4)):\n        reviews[arm], lineages[arm] = verify_search_endpoint(base, protocol, identity, manifest, arm, mid_index, mid_index + 1)\n'
suffix=f[stop:]
suffix=suffix.replace('or proof["recorded_first_256_replayed"] is not True','or proof["all_256_candidate_bytes_equal"] is not True\n            or proof["recorded_genetic_signatures_equal"] is not True')
sig_start=suffix.index('    signature =')
sig_end=suffix.index('    return manifest,')
sig=suffix[sig_start:sig_end].replace('for child in lineage[1]["children"]','for child in lineages[arm][1]["children"]').replace('sha(folder / "lineage.jsonl")','sha(base / "runs" / arm / "lineage.jsonl")')
suffix=suffix[:sig_start]+'    for arm in ARMS:\n'+'\n'.join('    '+line if line else '' for line in sig.rstrip().splitlines())+'\n'+'''    for key in ("candidate_raw_sha256", "candidate_row_sha256", "genetic_signature_sha256"):
        if proof["runs"][ARMS[0]][key] != proof["runs"][ARMS[1]][key]:
            raise ValueError("paired first-cohort bytes or recorded operations differ")
    return manifest, {"searches": reviews, "midpoint_generation": 8, "midpoint_added_lives": 0,
                      "first_256_raw_rows_replayed_before_confirmation": True,
                      "limitation": "NumPy reader binds midpoint/final checkpoint hashes, JSON rank0 bytes and native log prefixes. Full checkpoint population/genetic/ranking replay is separate; raw search ledgers are not complete."}
'''
a=put(a,'verify_endpoints',helper+'\n\n'+prefix+suffix)
a=put(a,'verdicts','''
def verdicts(rows):
    pool = describe(rows["pool"][ROLES[5]]["captures"] - rows["pool"][ROLES[3]]["captures"])
    blink_difference = describe(rows["blink80_20"][ROLES[5]]["captures"] - rows["blink80_20"][ROLES[3]]["captures"])
    blink_margin = describe(rows["blink80_20"][ROLES[5]]["captures"] - .9 * rows["blink80_20"][ROLES[3]]["captures"])
    own_start = {role: {world: describe(rows[world][role]["captures"] - rows[world][ROLES[1]]["captures"])
                        for world in WORLDS} for role in ROLES[2:]}
    return {"primary_balanced24_minus_unchanged24_pool_captures": pool,
            "primary_blink80_20_actual_capture_difference": blink_difference,
            "primary_blink80_20_ninety_percent_noninferiority": blink_margin,
            "joint_primary_passes": pool["lower_3se"] > 0 and blink_margin["lower_3se"] > 0,
            "checkpoint_minus_AN_start_captures": own_start,
            "confirmation_capture_value": 500, "matched_evolutionary_pairs": 1,
            "interpretation": "One matched pair of deliberately chosen full populations. Allocation is an objective intervention; deeper endpoints are not independent evolutionary replicates. The conventional90% margin permits some loss and is not broad retention or optimal-weight evidence."}
''')
(NEW/'analyze.py').write_text(a)
