"""Assemble a local standalone HTML only after complete bounded replay and supplied-state UI checks."""
import argparse
import json
from pathlib import Path

from export import ARTIFACT, HERE, ROOT, checked_record, read, sha


def assemble(record, output):
    checked_record(record)
    budget = read(HERE/"validation_budget.json")
    exported = read(ARTIFACT/"export_receipt.json")
    replay = read(ARTIFACT/"replay_receipt.json")
    ui = read(ARTIFACT/"ui_smoke.json")
    if (budget["status"] != "complete" or budget["C_full_lives"] != 12 or budget["JS_replay_lives"] != 12
            or budget["record_sha256"] != sha(record) or budget["cpu_seconds"] > 60
            or budget["wall_seconds"] > 180 or not budget["all_processes_exited"]
            or budget["export_receipt_sha256"] != sha(ARTIFACT/"export_receipt.json")
            or budget["replay_receipt_sha256"] != sha(ARTIFACT/"replay_receipt.json")
            or budget["ui_smoke_sha256"] != sha(ARTIFACT/"ui_smoke.json")
            or exported["status"] != "complete" or exported["C_full_lives"] != 12
            or exported["record_sha256"] != sha(record)
            or replay["status"] != "complete" or ui["status"] != "passed"):
        raise ValueError("complete bounded replay and UI evidence required")
    for name, key in (("bodies.json", "bodies_sha256"), ("truth.json", "truth_sha256"),
                      ("C_calls.json", "C_calls_sha256")):
        if sha(ARTIFACT/name) != exported[key]:
            raise ValueError("validated export changed before assembly: "+name)
    parts = {
        "__DATA__": (ARTIFACT/"bodies.json").read_text(),
        "__ENGINE__": (ROOT/"results/atlas/play/lifesim.js").read_text(),
        "__DELAYED_VIEW__": (HERE/"delayed_match_view.js").read_text(),
        "__VIEWER__": (HERE/"viewer.js").read_text(),
        "__VALIDATION_NOTE__": "Twelve fixed C-full replays matched their retained confirmation ledgers. "
            "Twelve stepped Node replays matched all 840 ledger values, 60 full hash families and spike rasters. "
            "Controls were checked using supplied state. Browser rendering and playback have not been tested.",
    }
    if any("</script" in value.lower() for value in parts.values()):
        raise ValueError("unsafe embedded script delimiter")
    text = (HERE/"template.html").read_text()
    for marker, value in parts.items():
        text = text.replace(marker, value)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(text)
    print(json.dumps(dict(status="assembled_local_only", sha256=sha(output), simulator_calls=0)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assemble", action="store_true")
    parser.add_argument("--record", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.assemble:
        if args.record is None or args.output is None:
            parser.error("--record and --output are required")
        assemble(args.record.resolve(), args.output.resolve())
    else:
        print(json.dumps(dict(status="source_only", simulator_calls=0)))
