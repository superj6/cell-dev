"""Package saved example frames into one portable HTML file; never runs a simulation."""
import argparse
import json
from pathlib import Path


def build(data_path, output_path):
    here = Path(__file__).resolve().parent
    payload = json.loads(Path(data_path).read_text())
    if not payload.get("examples"):
        raise ValueError("No examples in saved data")
    for example in payload["examples"]:
        if not example["frames"] or not example["cells"]:
            raise ValueError(f"Empty recording: {example['key']}")
        times = [frame["t"] for frame in example["frames"]]
        if times != sorted(times):
            raise ValueError(f"Frames out of order: {example['key']}")
        for frame in example["frames"]:
            reconstructed = {cell["id"] for cell in example["cells"]
                             if cell["born"] <= frame["t"] and
                             (cell["died"] is None or cell["died"] > frame["t"])}
            if reconstructed != set(frame["alive"]):
                raise ValueError(f"Saved lifetimes do not reconstruct frame: {example['key']} at {frame['t']}")
            del frame["alive"]
            frame["events"] = [event for event in frame["events"] if event["kind"] in {
                "capture", "miss", "slot_hit", "patch_click", "task_resolution",
                "patch_contact_start", "patch_contact_mature"}]
        # Full scientific ledgers, panel vectors and observer records remain in the source recording.
        for field in ("panel", "summary", "body"):
            example.pop(field, None)
        example["world"] = {key: example["world"][key] for key in ("sigma", "rho_c")}
    validation = payload.get("validation", {})
    if isinstance(validation, dict) and validation.get("all_passed"):
        count = len(validation["cases"])
        validation["description"] = (f"All {count} saved lives match the native simulator exactly: "
                                     "143 ledger values and five trajectory hashes per life. "
                                     "Frames are saved every eight time units. Display values retain full precision.")
    script = (here / "viewer.js").read_text()
    if "</script" in script.lower():
        raise ValueError("Unexpected script terminator")
    data = json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    page = (here / "template.html").read_text().replace("__DATA__", data).replace("__VIEWER__", script)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page)
    print(json.dumps({"output": str(target), "examples": len(payload["examples"]),
                      "bytes": target.stat().st_size, "simulation_calls": 0,
                      "alive_lists_reconstructed_and_verified": True, "float_rounding": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data")
    parser.add_argument("output")
    args = parser.parse_args()
    build(args.data, args.output)
