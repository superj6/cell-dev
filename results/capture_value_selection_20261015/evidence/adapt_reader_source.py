"""Source-only AL→AM adaptation; no data imports, simulation or genetics."""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'outputs/autonomous_retention_selection_20261015'
NEW = ROOT / 'outputs/autonomous_capture_value_selection_20261015'
NEW.mkdir(exist_ok=True)
for name in ('measure.py', 'analyze.py', 'native_replay.py'):
    text = (OLD/name).read_text()
    text = text.replace('persistent_control_final', 'current_value_final').replace('mixture_final', 'high_value_final')
    text = text.replace('persistent_control', 'current_value').replace('balanced_mixture', 'high_value')
    text = text.replace('"AI_control_start", "current_value_final", "high_value_final"',
                        '"AI_control_start", "AL_mixture_start", "current_value_final", "high_value_final"')
    if name == 'native_replay.py':
        text = text.replace('AL_recorded_ops', 'AM_recorded_ops')
    elif name == 'measure.py':
        text = text.replace('AL frozen three-role', 'AM frozen four-role')
        start = text.index('    reference = protocol["reference"]')
        end = text.index('    searches = {}', start)
        text = text[:start] + '''    references = (protocol["ancestral_reference"], protocol["reference"])
    for role, reference in zip(ROLES[:2], references):
        if reference["role"] != role or sha(STUDY / reference["path"]) != reference["file_sha256"]:
            raise ValueError("fixed starting reference differs")
    paths = [STUDY / reference["path"] for reference in references]
''' + text[end:]
        text = text.replace('genomes.shape != (3, 875)', 'genomes.shape != (4, 875)').replace('three exact BODY-1', 'four exact BODY-1')
        text = text.replace('if raw_sha(genomes[0]) != reference["raw_sha256"]:',
            'if any(raw_sha(genomes[i]) != reference["raw_sha256"] for i, reference in enumerate(references)):')
        text = text.replace('"research_lives": 3072', '"research_lives": 8192').replace('"rows": 12', '"rows": 16')
        text = text.replace('3 fixed genomes x 4 worlds x 256', '4 fixed genomes x 4 worlds x 512')
    else:
        text = text.replace('AL ', 'AM ')
        text = text.replace('PAIRS = ((1, 0), (2, 0), (2, 1))', 'PAIRS = ((1, 0), (2, 0), (3, 0), (2, 1), (3, 1), (3, 2))')
        text = text.replace('fixed 3-genome by 4-world', 'fixed 4-genome by 4-world')
        start = text.index('def retention_diagnostics(rows):')
        end = text.index('\ndef local(base, name):', start)
        text = text[:start] + '''RETENTION = ((1, 0, "persistent"), (2, 0, "persistent"), (3, 0, "persistent"),
             (2, 1, "pool"), (2, 1, "persistent"), (3, 1, "pool"), (3, 1, "persistent"))


def retention_diagnostics(rows):
    reports, arrays = {}, {}
    for candidate, reference, world in RETENTION:
        role, ancestor = ROLES[candidate], ROLES[reference]
        new, old = rows[world][role]["captures"], rows[world][ancestor]["captures"]
        key = f"{role}_vs_{ancestor}__{world}"
        difference, conventional = new - old, new - .9 * old
        reports[key] = {
            "capture_difference": describe(difference),
            "retained_90_percent_vector": describe(conventional),
            "passes_conventional_10_percent_diagnostic": describe(conventional)["lower_3se"] > 0,
            "reference_mean_captures": float(old.mean()), "candidate_mean_captures": float(new.mean()),
            "mean_capture_ratio": float(new.mean() / old.mean()) if old.mean() > 0 else None,
            "interpretation": "Conventional 10% diagnostic; a null difference is not established retention.",
        }
        arrays["retention__" + key + "__capture_difference"] = difference
        arrays["retention__" + key + "__ninety_percent_reference"] = conventional
    return reports, arrays


def verdicts(rows):
    def gain(world, new, old):
        return describe(rows[world][new]["captures"] - rows[world][old]["captures"])
    primary = {world: gain(world, ROLES[3], ROLES[2]) for world in ("pool", "persistent")}
    own_start = {role: {world: gain(world, role, ROLES[1]) for world in ("pool", "persistent")}
                 for role in ROLES[2:]}
    return {"primary_high_minus_current_captures": primary,
            "joint_primary_capture_advantage": all(v["lower_3se"] > 0 for v in primary.values()),
            "endpoint_minus_AL_start_captures": own_start,
            "strict_simultaneous_capture_gain_over_AL_start": {
                role: all(v["lower_3se"] > 0 for v in worlds.values()) for role, worlds in own_start.items()},
            "confirmation_capture_value": 500,
            "ancestral_L92_restoration_tested": False,
            "evolutionary_replicate_pairs": 1,
            "interpretation": "One paired selection comparison, not evolutionary replication or a proof of richer computation."}

''' + text[end:]
        # Exact changed scope/caps, without editing ledger or scientific accounting functions.
        for a,b in [('13388','28748'),('13396','28756'),('3072','8192'),('10316','20556'),('5158','10278'),('5120','10240'),('2254','4064')]:
            text = text.replace(a,b)
        text = text.replace('"cpu_seconds": 5400, "wall_seconds": 3600', '"cpu_seconds": 10800, "wall_seconds": 5400')
        text = text.replace('"search_cpu_seconds": 3600, "confirmation_cpu_seconds": 1800', '"search_cpu_seconds": 7200, "confirmation_cpu_seconds": 3600')
        text = text.replace('"initial_lives": 4, "recheck_lives": 4', '"initial_lives": 8, "recheck_lives": 8')
        text = text.replace('len(seeds) != 256 or len(set(seeds)) != 256', 'len(seeds) != 512 or len(set(seeds)) != 512')
        text = text.replace('expected 256 unique research seeds', 'expected 512 unique research seeds')
        text = text.replace('expected_primary = [{"world": "pool", "new": ROLES[2], "old": ROLES[1], "metric": "captures"}]',
            'expected_primary = [{"world": world, "new": ROLES[3], "old": ROLES[2], "metric": "captures"}\n                        for world in ("pool", "persistent")]')
        start = text.index('    reference = protocol["reference"]')
        end = text.index('    record = protocol["population_start"]', start)
        text = text[:start] + '''    for role, reference in zip(ROLES[:2], (protocol["ancestral_reference"], protocol["reference"])):
        path = local(base, reference["path"])
        if (reference["role"] != role or sha(path) != reference["file_sha256"]
                or protocol["original_input_pins"][reference["source"]] != sha(path)
                or hashlib.sha256(json_genome(path).tobytes()).hexdigest() != reference["raw_sha256"]):
            raise ValueError("retained reference bytes or origin differs")
''' + text[end:]
        text = text.replace('if (persistent["v_t"], persistent["tau_turn"], persistent["d0"], persistent["d_min"]) != (.3, 200, 1, .5):',
            'if (persistent["v_t"], persistent["tau_turn"], persistent["d0"], persistent["d_min"], persistent["R_cap"]) != (.3, 200, 1, .5, 500):')
        text = text.replace('len(manifest["genomes"]) != 3', 'len(manifest["genomes"]) != 4')
        text = text.replace('expected_paths = [protocol["reference"]["path"],',
            'expected_paths = [protocol["ancestral_reference"]["path"], protocol["reference"]["path"],')
        text = text.replace('if manifest["genomes"][0]["raw_sha256"] != protocol["reference"]["raw_sha256"]:',
            'if any(manifest["genomes"][i]["raw_sha256"] != protocol[key]["raw_sha256"]\n           for i, key in enumerate(("ancestral_reference", "reference"))):')
        text = text.replace('enumerate(ARMS, 1)', 'enumerate(ARMS, 2)')
        text = text.replace('"rule": "gen indices even=pool odd=persistent; control and diagnostics=persistent",',
            '"rule": "gen indices even=pool odd=persistent; gen R_cap by arm; diagnostics=persistent R_cap500",\n            "selection_capture_value": 500. if arm == "current_value" else 2000.,')
        text = text.replace('len(line["seeds"]) != 4', 'len(line["seeds"]) != 8').replace('len(line["recheck"]["seeds"]) != 4','len(line["recheck"]["seeds"]) != 8')
        text = text.replace('entry["lives"] != 256', 'entry["lives"] != 512')
        text = text.replace('for i in range(3)}', 'for i in range(len(ROLES))}').replace('complete exact 12-row matrix required', 'complete exact 16-row matrix required')
        text = text.replace('"rows": 12', '"rows": 16').replace('"raw_rows": 12','"raw_rows": 16')
        text = text.replace('budget["cap_cpu_seconds"] != 5400 or budget["cap_wall_seconds"] != 3600', 'budget["cap_cpu_seconds"] != 10800 or budget["cap_wall_seconds"] != 5400')
        text = text.replace('budget["search_cpu_cap"] != 3600 or budget["confirmation_cpu_cap"] != 1800', 'budget["search_cpu_cap"] != 7200 or budget["confirmation_cpu_cap"] != 3600')
        text = text.replace('search_cpu >= 3600 or confirmation_cpu >= 1800', 'search_cpu >= 7200 or confirmation_cpu >= 3600')
        text = text.replace('expected_cap = 3600 if phase in ARMS else min(5400, search_cpu + 1800)', 'expected_cap = 7200 if phase in ARMS else min(10800, search_cpu + 3600)')
        text = text.replace('record["cap_wall_seconds"] <= 3600', 'record["cap_wall_seconds"] <= 5400')
    (NEW/name).write_text(text)
shutil.copyfile(OLD/'replay_ops.py', NEW/'replay_ops.py')
