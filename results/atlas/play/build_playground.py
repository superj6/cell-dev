"""Assemble atlas_play.html: the Spiking Tissue Atlas (../atlas.html, built by ../build2.py) plus the live playground.

Inserted right after the part-1 header (before <div id="evo-charts">):
  1. <script type="application/json" id="pg-data">: {"doc": bodies.json verbatim, "ui": body labels, notes, seeds}
  2. <script>lifesim.js</script> (defines window.LifeSim)
  3. playground.html (a <section id="play"> with its own <style> and <script>)
The atlas footer gets one line about the simulator, and one CSS rule fixes a sideways scroll of the atlas at
phone width. Run (from the repo root, for the seeds):
  PYTHONPATH=. nice -n 10 .venv/bin/python <play>/build_playground.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # viz/play
VIZ = HERE.parent
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from src.life import analysis  # noqa: E402

SEED0 = 39_000_000 + 100_000 * 6  # this page's lives (the 39.1M and 39.2M blocks went to the engine's validation)
N_SEEDS = 16
SKIP_T = 300
ANCHOR = '    <div id="evo-charts"'

# bodies.json order; short labels as in build2.LIVES, notes from the mechanism accounts (build2.BODIES) and the
# engine's validation (s7 nearly still on an empty screen, s2 reaching the 1,024-cell guard at t 7,330-8,642);
# cell counts are medians over the 16 page seeds (play/tmp/cells_check.js)
BODIES = [
    ("speck_lmax4_hexprism_sex_s5", "Speck s5", "Speck task, seed 5, the best evolved body",
     "The best evolved body. Its sensors fire on two events close together, with help from neighbours. "
     "With neighbour messages off it still chases, but more slowly and with more missed clicks."),
    ("speck_lmax4_hexprism_sex_s4", "Speck s4", "Speck task, seed 4",
     "Sensors vote: a sensor's own event counts double and a neighbour's spike once. A fringe of sensors with "
     "nothing above them works as an antenna. It grows slowly (about 65 cells at t 300), and neighbour messages "
     "carry about half of its score."),
    ("speck_lmax4_hexprism_sex_s2", "Speck s2", "Speck task, seed 2",
     "A plain retina below, and a relay above whose cells turn their gain down when crowded. It is small at t 300 "
     "(about 50 cells) and never stops growing: a long session ends when it reaches 1,024 cells, at around t 7,000 "
     "to 9,000."),
    ("speck_lmax4_hexprism_sex_s6", "Speck s6", "Speck task, seed 6",
     "The largest body, about 170 cells. It loses its whole score when neighbour messages stop."),
    ("speck_lmax4_hexprism_sex_s7", "Speck s7", "Speck task, seed 7",
     "Grows to about 100 cells within 50 time units, then mostly holds. On an empty screen it barely moves."),
    ("lmax4_hexprism_sex_s5", "Original s5", "Original task, seed 5",
     "Evolved on the original task, with a wide target. Evolution rebuilt the hand-designed reflex here, "
     "and its clicking cell waits for two pieces of evidence."),
    ("reflex@hollow3", "Hand reflex", "The hand-built reflex (designed and tuned, not evolved)",
     "Designed and tuned by hand, not evolved. Its cells ignore messages from neighbours in the same layer, so "
     "switching neighbour messages off changes nothing: the same spikes, bit for bit."),
    ("router@ring4", "Hand router", "The hand-built router (designed and tuned, not evolved)",
     "Designed by hand. Interior sensors relay coincident events to the rim; switching neighbour messages off "
     "costs most of its score."),
]
FOOTER = ("Try it: the playground runs lifesim.js, a JavaScript transcription of the reference simulator "
          "(LIFE_ABI 3) with ports of glibc's exp, log, sin, cos and tanh. In the standard world it matched the C "
          "kernel bit for bit on 64 test lives in every ledger column and log hash, and on 256 more in score, "
          "catches and spikes, across the 8 bodies. Placed targets sum their halos into the receptor rate. Page "
          "lives use seeds from 39,600,000.")


def safe_script(src: str, what: str) -> str:
    low = src.lower()
    assert "</script" not in low and "<!--" not in low, f"{what} cannot be inlined as is"
    return src


def main():
    atlas = (VIZ / "atlas.html").read_text()
    lifesim = safe_script((HERE / "lifesim.js").read_text(), "lifesim.js")
    frag = (HERE / "playground.html").read_text()
    doc_text = (HERE / "bodies.json").read_text().strip()
    doc = json.loads(doc_text)
    assert [b["name"] for b in doc["bodies"]] == [b[0] for b in BODIES], "bodies.json order changed"
    for m in re.finditer(r"<script>(.*?)</script>", frag, re.S):
        safe_script(m.group(1), "playground script")

    seeds = [int(s) for s in analysis.fresh_seeds(N_SEEDS, seed0=SEED0)]
    ui = {"bodies": [{"name": n, "short": s, "label": lab, "note": note} for n, s, lab, note in BODIES],
          "seeds": seeds, "skipTo": SKIP_T}
    blob = ('{"doc":' + doc_text + ',"ui":' + json.dumps(ui, ensure_ascii=False, separators=(",", ":")) + "}")
    blob = blob.replace("</", "<\\/")
    json.loads(blob)  # still one valid JSON document

    insert = (f'    <script type="application/json" id="pg-data">{blob}</script>\n'
              f"    <script>\n{lifesim}\n</script>\n{frag.rstrip()}\n")
    assert atlas.count(ANCHOR) == 1, "part-1 anchor not found exactly once"
    assert 'id="play"' not in atlas, "atlas.html already has a playground"
    out = atlas.replace(ANCHOR, insert + ANCHOR, 1)
    # phone-width fix for the atlas itself: the evolution charts' svg (min-width 380px) scrolls inside .chart, but
    # the grid items around it kept min-width:auto and held the whole column at 380px (6-22px of sideways scroll)
    assert "</style>" in out
    out = out.replace("</style>", "</style>\n<style>.chart-card > *, .small-multiples > * { min-width: 0 }</style>", 1)

    # one footer line (the footer paragraphs live in the atlas-data JSON blob)
    m = re.search(r'(<script type="application/json" id="atlas-data">)(.*?)(</script>)', out, re.S)
    data = json.loads(m.group(2))
    rest = [p for p in data["footer"] if not p.startswith("Try it:")]
    data["footer"] = rest[:1] + [FOOTER] + rest[1:]  # after the part-1 line
    new_blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    out = out[:m.start(2)] + new_blob + out[m.end(2):]

    dest = VIZ / "atlas_play.html"
    dest.write_text(out)
    print(f"{dest} {len(out) / 1024:.0f} KB (atlas {len(atlas) / 1024:.0f} KB, lifesim {len(lifesim) / 1024:.0f} KB, "
          f"bodies {len(doc_text) / 1024:.0f} KB, fragment {len(frag) / 1024:.0f} KB); seeds {seeds[0]}-{seeds[-1]}")


if __name__ == "__main__":
    main()
