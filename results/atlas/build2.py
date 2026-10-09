"""Assemble atlas.html (2026-10-09): part 1, the BODY-1 pilot bodies (data/life_*.json, data/curves.json), plus
part 2, the 2026-10-06 task-ladder atlas unchanged (build.py's specimens, organism exports and charts)."""
import json
import re
from pathlib import Path

import numpy as np

import build

HERE = Path(__file__).parent
D = HERE / "data"
SIGMA = {"catch_speck_l4": 0.6, "catch_v1_l4": 1.5}
RHO = 1.0

LIVES = {  # key -> (file stem, short picker label, long label)
    "s5": ("speck_lmax4_hexprism_sex_s5", "Speck s5", "Speck task, seed 5, the best evolved body"),
    "s4": ("speck_lmax4_hexprism_sex_s4", "Speck s4", "Speck task, seed 4"),
    "s2": ("speck_lmax4_hexprism_sex_s2", "Speck s2", "Speck task, seed 2"),
    "s6": ("speck_lmax4_hexprism_sex_s6", "Speck s6", "Speck task, seed 6: loses its whole score when neighbour messages stop"),
    "s7": ("speck_lmax4_hexprism_sex_s7", "Speck s7", "Speck task, seed 7"),
    "v1s5": ("lmax4_hexprism_sex_s5", "Original s5", "Original task, seed 5"),
    "reflex": ("reflex_at_hollow3", "Hand reflex", "The hand-built reflex (designed and tuned, not evolved)"),
    "router": ("router_at_ring4", "Hand router", "The hand-built router (designed and tuned, not evolved)"),
}
PICKER = ["s5", "s4", "s2", "s6", "s7", "v1s5", "reflex", "router"]
STOPS = {4, 5, 6, 7, 8}  # SPECK L4 seeds whose final best stops growing within its life (analysis.md, GB11)
GREW_V1 = {5, 6, 8, 9}

BODIES = [
    {
        "id": "b-s5", "short": "Catch together", "lives": ["s5"],
        "eyebrow": "body 1 · speck task, seed 5 · the best evolved body · about 122 cells",
        "title": "Catch together, then hush",
        "headline": "Sensing cells fire only when two pieces of evidence arrive close together, and neighbours lend each other "
                    "evidence. Each moving cell then sends a brief hush back to the sensor that fired it, which keeps the "
                    "whole sheet from setting itself off.",
        "taskLine": "Speck task: a small target (halo 0.6) that pays 500 per catch; a missed click costs 10.",
        "mechanism": (
            "Each column is a sensing cell with a moving cell grown straight above it. A sensing cell rests well below its "
            "firing point, so one receptor event almost never fires it. Two events within about 5 time units do, and so "
            "does one event plus a few spikes from neighbouring sensors. The target's halo covers a patch of about seven "
            "sensors at once, so the sensors under it confirm each other and fire, while stray background events mostly "
            "die out. Each sensor spike fires the moving cell above it one time unit later, and a moving cell on the rim "
            "pulls the dot outward on its side, toward the target. About one time unit after twitching, the moving cell "
            "sends inhibition back down to its own sensor. That hush keeps the weakly linked sensing sheet from setting "
            "itself off: without it, off-target spikes triple and the pulls lose their aim. Interior moving cells cannot "
            "pull at all, but they still deliver the hush."),
        "chips": [["score, 1,024 lives", "+7.06", False], ["neighbour messages off", "+2.65", True],
                  ["hush removed (after growth)", "−5.6", True], ["catches / missed clicks", "20 / 20", False],
                  ["cells (screen · pull · hidden)", "56 · 50 · 15", False], ["hidden layers off", "+0.04", False]],
        "evidence": (
            "Six fully logged lives, each checked bit for bit against the fast simulator, then lesions applied only after "
            "the body had grown, on 128-1,024 fresh lives. Blocking neighbour messages after growth costs 4.3 to 4.9, all "
            "of it lost catches (every cost changes by 0.05 or less). Seven ways of making the sensors uniformly more "
            "sensitive never recover that loss, so the messages do more than raise sensitivity. A second agent re-tested "
            "the account on lives the first never saw: the two-event rule, the lateral help, the hush and the inert "
            "hidden layers were confirmed."),
        "caveats": (
            "The skeptic refuted two finer claims: that the hush lands exactly in time to cancel a sensor's post-spike "
            "priming, and that one chemistry knob alone makes the sense-to-move link work. This body scores below the "
            "hand-built reflex (+8.69) because of cost, not skill: it catches as many targets with half the wasted "
            "clicks, but keeps about twice as many cells alive."),
    },
    {
        "id": "b-s4", "short": "Neighbours vote", "lives": ["s4"],
        "eyebrow": "body 2 · speck task, seed 4 · about 95 cells",
        "title": "Neighbours vote, and the fringe listens",
        "headline": "A sensing cell fires on two votes: its own receptor event counts double and a neighbour's spike counts "
                    "once. Sensors with nothing above them became an antenna that only talks inward.",
        "taskLine": "Speck task: a small target (halo 0.6) that pays 500 per catch; a missed click costs 10.",
        "mechanism": (
            "A sensing cell counts votes. Its own receptor event is worth two, a spike from a neighbouring sensor about "
            "one, and it fires at two votes within about 2 time units. So it fires on two events of its own, or on one "
            "event that a neighbour agrees with, and almost never on one stray event (4% of the time). Cells under the "
            "target confirm each other, and lone background events die out. The body grows its moving cells straight up "
            "from the sensors, so the sensing disk ends up wider than the moving disk. The roughly 20 sensors with nothing "
            "above them became an antenna: they excite their inner neighbours strongly and barely signal outward, so a "
            "target beyond the moving cells still recruits the right side. After firing, a sensor restarts above its "
            "resting level, so for a moment one event re-fires it: a detection is hard to start and easy to keep."),
        "chips": [["score, 1,024 lives", "+5.21", False], ["neighbour messages off", "+2.75", True],
                  ["same messages, scrambled targets", "−4.15", True], ["antenna fringe silenced", "−1.42", True],
                  ["post-spike latch worth", "0.9–1.4", False], ["catches / missed clicks", "15 / 35", False]],
        "evidence": (
            "Confirmed in full by an independent skeptic on fresh lives. After growth (the network is fixed by about t = "
            "512), neighbour messages carry about 55% of the score, all through catches. Delivering the same amount of "
            "lateral drive to random sensors is worse than delivering none (−4.15 ± 0.39), and shifting every sensor's "
            "sensitivity recovers at most +0.64 of the 3.3 lost, so where a message lands is what matters. The firing "
            "probabilities above were measured on rested sensors in fresh lives."),
        "caveats": "Hidden cells exist (0–13 per body) but never fire.",
    },
    {
        "id": "b-s2", "short": "Crowding sets gain", "lives": ["s2"],
        "eyebrow": "body 3 · speck task, seed 2 · grows to about 108 cells",
        "title": "Crowded cells turn their volume down",
        "headline": "The sensing layer is a plain retina. The moving layer does the work: each cell sets its own gain from how "
                    "crowded it is, and adjusts it during life when a neighbour dies.",
        "taskLine": "Speck task: a small target (halo 0.6) that pays 500 per catch; a missed click costs 10.",
        "mechanism": (
            "Here the sensing layer does no computing: each sensor fires on every receptor event it gets, like a pixel. "
            "The work happens in the moving layer, where each cell sets its own volume from how many neighbours it has. "
            "A cell on the rim, which can pull, has few neighbours and relays every spike. A crowded interior cell, which "
            "cannot pull, needs two inputs close together, so stray events die there, and it passes activity outward to "
            "the rim. A target over the middle of the body then recruits the rim cells on its side. The setting adapts "
            "during life: when a neighbour dies, the cells around it turn their volume up over the next 10 to 100 time "
            "units. The outward relay only pays once the body has about 70 cells, and this body keeps growing, so it "
            "crosses that line during its life."),
        "chips": [["score, 1,024 lives", "+4.09", False], ["neighbour messages off", "+3.78", True],
                  ["relay removed at 91 cells", "−1.50", True], ["messages removed at 47 cells", "+0.4–0.5", False],
                  ["catches / missed clicks", "13 / 30", False], ["cells at the end", "≈108", False]],
        "evidence": (
            "The gain switch is causal: when a neighbour is removed the cells around it drift to high gain, but not if "
            "their neighbour-count input is held fixed. In bodies frozen at a given size, removing the act-layer relay "
            "costs 20% of catches at 91 cells, while removing neighbour messages helps a 47-cell body, whatever its age: size "
            "sets the sign."),
        "caveats": (
            "The skeptic confirmed the gain map, the outward relay and the size crossover, but refuted a predicted "
            "speed of the gain change after a neighbour's death and that every life grows an interior hole."),
    },
    {
        "id": "b-v1s5", "short": "Reflex regrown", "lives": ["v1s5"],
        "eyebrow": "body 4 · original task, seed 5 · about 87 cells",
        "title": "The reflex, regrown from one cell",
        "headline": "On the original task, with its wide target, evolution rebuilt the hand-designed reflex, with one "
                    "refinement: the clicking cell waits for two pieces of evidence.",
        "taskLine": "Original task: a wide target (halo 1.5) that pays 100 per catch; a missed click costs 2.",
        "mechanism": (
            "This body rebuilt the hand-designed reflex. Each sensing cell drives the moving cell above it with one strong "
            "kick, and rim cells pull the dot toward the side the target's wide halo covers. Sensors on the rim fire on a "
            "single event; sensors in the middle need two. The centre sensor, which drives the clicking cell, also needs "
            "two events within about one time unit, which keeps clicks precise. A centre that fires on single events "
            "would waste about 28 more clicks per life. Neighbour messages add little here, about 0.3 of its score. As in "
            "every body, the messages' direction comes from chemistry: moving cells secrete about four times more of one "
            "chemical, and that difference turns the same spike into excitation going up and inhibition coming down."),
        "chips": [["score, 256 lives", "+2.83", False], ["neighbour messages off", "−0.3", False],
                  ["single-event centre", "+28 misses", True], ["secretion swapped", "wrecked", True],
                  ["catches / missed clicks", "50 / 61", False], ["cells", "≈87", False]],
        "evidence": (
            "Swapping which layer secretes more flips the up and down signs and wrecks the score. Silencing the centre "
            "sensor leaves the dot sitting on the target but removes about 90% of catches."),
        "caveats": (
            "The skeptic could not rule out a plain reflex for the steering sensors: giving the interior sensors "
            "single-event settings changed neither the score nor the share of target-driven spikes."),
    },
    {
        "id": "b-ref", "short": "Hand-built references", "lives": ["reflex", "router"],
        "eyebrow": "references · designed by hand, tuned, not evolved",
        "title": "What evolution was measured against",
        "headline": "The reflex never talks sideways. The router relays coincident events from the middle of the body to the "
                    "rim. No evolved body has beaten the reflex yet.",
        "taskLine": "Speck task, the same world as bodies 1–3. Use the buttons above the replay to switch body.",
        "mechanism": (
            "In the reflex, a rim sensor fires on any single receptor event and drives the moving cell above it. No cell "
            "ever talks to its side neighbours, and switching neighbour messages off changes nothing. The router adds "
            "interior sensors that detect coincident events and relay them sideways to the rim, so a target over the "
            "middle of the body pulls the rim on its side. In the router, 38% of rim twitches start in another column, "
            "and switching neighbour messages off after growth costs 9.3 of its 11. The best evolved body catches as "
            "many targets as the reflex, with half the wasted clicks, but it pays to keep about twice as many cells "
            "alive."),
        "chips": [["reflex score", "+8.69", False], ["reflex, messages off", "±0.00", False],
                  ["router score", "+10.96", False], ["router, messages off", "−9.3", True],
                  ["reflex cells", "56", False], ["router cells", "122", False]],
        "evidence": (
            "Both scored on the same 1,024 fresh lives as the evolved bodies. These two bodies were also used to check "
            "the probe toolkit: it must find 0 relayed chains in the reflex and a large share in the router, with "
            "latency stepping by one time unit per hop."),
        "caveats": None,
    },
]


def lives():
    out = {}
    for key, (stem, short, label) in LIVES.items():
        d = json.loads((D / f"life_{stem}.json").read_text())
        d.update(short=short, label=label, sigma=SIGMA[d["preset"]], rho=RHO)
        out[key] = d
    return out


def curves():
    C = json.loads((D / "curves.json").read_text())

    def rows(prefix, group):
        out = []
        for s in range(10):
            r = C[f"{prefix}_hexprism_sex_s{s}"]
            sm = [float(np.median(r["cells"][max(0, i - 4):i + 5])) for i in range(len(r["cells"]))]  # 9-gen median
            out.append(dict(label=f"seed {s}", group=group(s), valid=r["valid"],
                            cells=[[g, round(c, 1)] for g, c in zip(r["gen"], sm) if g % 5 == 0 or g == r["gen"][-1]]))
        return out

    return dict(speck=rows("speck_lmax4", lambda s: "stops" if s in STOPS else "grows"),
                v1=rows("lmax4", lambda s: "grew" if s in GREW_V1 else "stuck"))


def main():
    organisms = {}
    for s in build.SPECIMENS:
        d = json.loads((D / f"{s['id']}.json").read_text())
        letters = {r["type"]: "ABCD"[i] for i, r in enumerate(sorted(d["rules"], key=lambda r: r["type"]))}
        for t in d["trials"]:
            t["label"] = re.sub(r"type-(\d)", lambda m: f"type {letters.get(int(m.group(1)), m.group(1))}", t["label"])
        d["title"] = s["title"]
        organisms[s["id"]] = d
    footer = [
        "Part 1: BODY-1 pilot, cell-dev commit 622fd5b (RESULTS.md, 2026-10-09). Replays are one life per body, chosen "
        "as the life whose score is nearest the median of 24 fresh lives (seeds from 38,000,000), traced in the "
        "reference simulator and checked bit for bit against the kernel. Mechanism accounts were each re-tested by an "
        "independent skeptic on fresh lives (results/catch_pilot/mechanisms.json).",
    ] + build.FOOTER
    data = {"organisms": organisms, "specimens": build.SPECIMENS, "charts": json.loads((D / "charts.json").read_text()),
            "footer": footer, "body1": {"lives": lives(), "curves": curves(), "specimens": BODIES, "picker": PICKER}}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = (HERE / "template2.html").read_text().replace("/*__DATA__*/", blob)
    (HERE / "atlas.html").write_text(html)
    print(f"atlas.html {len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
