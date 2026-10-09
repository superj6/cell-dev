"""Assemble atlas.html from template.html, the verified organism exports and charts.json."""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
D = HERE / "data"

SPECIMENS = [
    {
        "id": "context", "short": "Cue switch",
        "taskLabel": "context task",
        "taskLine": "Task: face the light, unless a small cue spot appeared first, then face away. Most cells never feel the cue.",
        "title": "A cue switches on a ring of relay cells",
        "headline": "A brief cue turns on a band of 27 relay cells that keep re-lighting each other through the dark wait. That 'on' state keeps the cells that would face the light silent, so the body faces away.",
        "mechanism": (
            "The body grew a closed band of 27 relay cells (type A) around a small middle, with 22 slow light-sensing cells "
            "(type B) around the outside and in the middle. With no cue, a few type B cells on the brightest edge charge up and "
            "fire, so the body points at the light, usually with just 2 or 3 spikes. A resting relay cell sits halfway to firing, "
            "so the cue spot sets off the relay cells under it, and one spike from a relay neighbour fires the next. The signal "
            "spreads along the band one cell per tick until all 27 fire on every tick, re-lighting each other through the dark "
            "wait: that steady 'on' state is the memory of the cue. Relay spikes also hold the nearby type B cells far below "
            "firing, so they stay silent when the light comes on. Light switches relay cells off, starting on the bright side, "
            "and the quiet creeps toward the dark side over a few ticks. Scoring catches the last relay spikes, all on the dark "
            "side, so the body faces away."),
        "evidence": (
            "Checked on 240 held-out trials. Whenever the cue touches a relay cell (113 of 113 such trials), all 27 relay cells "
            "fire on every tick from 6 to 8 ticks after the cue until the light comes on. Silencing the band for a single tick "
            "before the light means it never restarts, and the cued score drops to about -0.05. Adding 80 or 300 extra dark "
            "ticks changes nothing in the shown trials. Messages off: 0.00. Types shuffled: 0.29. All one type: 0.41."),
        "caveats": (
            "The 'face the light' answer rests on very few spikes, because one well-placed spike already counts as fully "
            "decisive. The memory is expensive: a cued trial uses about 435 spikes, against about 2 for an uncued one. About 6% "
            "of cued trials fail, when the cue spot lands only on type B cells. The run log reports 0.81 held-out for this "
            "organism; the 0.93 shown comes from the exporter's own 48 trials."),
    },
    {
        "id": "withdraw", "short": "Withdraw wave",
        "taskLabel": "withdraw task",
        "taskLine": "Task: a brief poke lands on one side of the body; the firing has to end up on the opposite side.",
        "title": "A poke starts a wave around a horseshoe",
        "headline": "Ten relay cells grew into a horseshoe. A poke starts a wave that runs along it one cell per tick, and by the time the response is scored, the front still going is on the far side.",
        "mechanism": (
            "The 10 type B cells form a horseshoe-shaped ring around the middle of the body, with a gap on the lower left. The "
            "38 type A cells fill the space around it. While waiting, each ring cell charges up to 80-90% of the way to firing, "
            "so one spike from a ring neighbour fires it, and so does a nudge from a poked type A cell next to it. Type A cells "
            "ignore each other, so they never pass a signal on. From the first ring cell to fire, a wave runs along the ring one "
            "cell per tick, both ways if it starts partway along. A ring cell that has just fired ignores input for a few ticks, "
            "so the wave only moves forward and stops when it runs off an end. Scoring starts 4 ticks after the poke. By then "
            "the front on the shorter arm has usually run off its end, so the front still going is on the far side. Shuffle the "
            "same cells into random places and the ring breaks into islands, and the score falls to about 0."),
        "evidence": (
            "Checked on the 48 held-out trials shown here. In 41 of them only one wave front is firing while the response is "
            "scored, and every scored spike sits on the far half of the body. Removing one ring cell costs 0.09 to 0.68 for 8 of "
            "the 10, because it cuts the path, while no type A cell costs more than 0.016. Cutting the ring cells' rest after "
            "firing from 3 ticks to 1 drops the score to 0.40; to 0, the wave bounces and the score is about 0. Messages off: "
            "0.00. Types shuffled: about 0.03 over 200 shuffles."),
        "caveats": (
            "2 of 48 held-out trials score 0: the poke lands far out, touches only outer type A cells, and no wave starts. For "
            "pokes from one direction the far point falls in the horseshoe's gap, so the best the wave can do is about 0.69."),
    },
    {
        "id": "jump", "short": "Jump detector",
        "taskLabel": "jump task",
        "taskLine": "Task: a flash at spot A, then the same flash at spot B a few ticks later; point the way it jumped.",
        "title": "A central hub that warns the far side",
        "headline": "A 4-cell hub in the middle carries a brief nudge from the first flash to the cells of the second, so only the second spot fires in time to be counted.",
        "mechanism": (
            "The body has 46 ordinary cells (type A) and a 4-cell hub in the middle (type B); both kinds sense light. An "
            "ordinary cell needs two ticks of light to fire, so a flash on its own makes its spot fire one tick late, on a tick "
            "the scorer never reads. When the first flash fires its cells, the hub passes the signal across the middle within a "
            "tick or two, and each hub spike gives the ordinary cells touching it a small, short-lived nudge. If the second flash "
            "lands on nudged cells, light plus nudge fires them on the very first tick, which is counted. So almost all of the "
            "counted firing sits on the spot the flash jumped to. It works as a timing detector: the trip through the hub sets "
            "the delay, and a cell fires early only when the second flash and the nudge arrive together."),
        "evidence": (
            "Over 96 held-out trials, 161 of the 167 counted spikes sit on spot B at its first tick, and none come before the "
            "flashes or at A's first tick. Either flash alone gives only 5 counted spikes. Removing the hub's 4 cells gives "
            "0.00, cutting the hub's contacts to ordinary cells gives -0.01, and cutting contacts between ordinary cells leaves "
            "0.73. Messages off: 0.00, with every trial silent on the counted ticks."),
        "caveats": (
            "The saved 0.80 was a lucky 48-trial draw; 0.73-0.74 over many trial sets is the better estimate. The trick relies "
            "on jumps always crossing the middle of the body, where the hub sits: if jumps may be centred up to 3 sites from the "
            "middle, it scores about 0.20. "
            "Answers are tiny, usually 1-3 spikes per trial."),
    },
    {
        "id": "memory4", "short": "4-cell memory",
        "taskLabel": "memory task",
        "taskLine": "Task: a flash, a dark wait of random length, then a uniform 'go' signal; point where the flash was.",
        "title": "Four cells that remember a flash",
        "headline": "The smallest solution found: four identical cells store where a flash came from as a voltage head start, held in place by the spikes they send each other.",
        "mechanism": (
            "The four cells sit in a 2x2 block, each touching the other three, and every spike pushes the other three cells' "
            "voltage down by 2. When the flash arrives they usually fire together once and knock each other far below firing "
            "level. The flash keeps shining for three more ticks, and the cell on the side the light came from takes in the "
            "most, so it ends up the least far down. That head start is the memory. In the dark all four climb back at the same "
            "pace, so the order holds even as the lead slowly shrinks. The leader fires first, either on its own 10-19 ticks "
            "into the dark or when the go signal pushes every cell up, and its spike knocks the other three down again, so from "
            "then on it fires alone. In about 1 trial in 5 the go signal lifts the runner-up over the line on the same tick, and "
            "the pair keeps firing together, which lowers that trial's score from about 0.87 to 0.68. With messages off, all "
            "four fire in lock-step and point nowhere."),
        "evidence": (
            "All 84 possible held-out trials (12 directions x 7 wait lengths) were run: 0.871 overall, where 0.911 is the best "
            "this 4-cell body can score. The 18 trials where two cells fire together account for the whole gap. Weakening the "
            "push-down from -2 to -0.5 gives -0.14, and a faster leak (1/4) leaves every trial silent. Waits of 20 to 100 dark "
            "ticks score the full 0.911, because the leader has already fired alone before the go signal. Messages off: 0.00."),
        "caveats": "It grew on a square lattice with diagonal neighbours (8 per cell), so all four cells touch each other.",
    },
    {
        "id": "motion_cheat", "short": "Motion, no messages",
        "taskLabel": "motion task",
        "taskLine": "Task: a spot of light drifts across the body; point the way it is moving.",
        "title": "Motion without messages",
        "headline": "A cautionary specimen. This body seems to track a moving spot, but its cells never need to talk: four touchy tips each react only to their own light.",
        "mechanism": (
            "The body is an X of 28 cells, but only the 4 tip cells (type B) ever fire. The other 24 (type A) are too "
            "insensitive to fire and just hold the tips out. Each tip slowly charges up in the dark without quite reaching its "
            "firing point, so the longer it waits, the less light sets it off. The spot crosses the body in a straight line and "
            "only the middle of its trip is scored. A tip on the side the spot is heading toward waits the longest and fires when "
            "the light reaches it late in the trip; that one spike, from a cell that lies in the direction of motion, earns "
            "almost full marks. It fails when the starting tip also fires inside the scored stretch and cancels the answer "
            "(about 1 trial in 4), and when the spot passes between the arms and nothing fires (about 1 in 3). Messages change "
            "nothing here, which is why the project built the jump task to force cells to talk."),
        "evidence": (
            "With messages off the spike pattern is identical tick for tick, on held-out and training trials alike. Removing all "
            "24 type A cells leaves the score exactly the same. Over 960 held-out trials, 42% have spikes only on the side the "
            "spot is heading, 34% are silent while scoring is on, and in 24% a starting-side tip cancels the answer."),
        "caveats": "Held-out score 0.41 on the exporter's 48 trials; 0.37 on a larger set of 960.",
    },
]

FOOTER = [
    "How to read the scores: each trial scores how decisively the firing during the scoring window sits on the correct side "
    "of the body, from -1 (wrong side) through 0 (no lean, or silence) to 1. Held-out trials use directions, distances, "
    "waits or speeds the organism never trained on. One well-placed spike already counts as fully decisive, so several "
    "specimens answer with only a few spikes.",
    "Chart caveats: the runs used three versions of the code that picks a run's starting genomes (the early one could "
    "start from a dead single cell; see RESULTS.md). The 8-founder bars mix them: withdraw used the fixed version, context "
    "the partly fixed one, jump the old one. Everything else used the old version. Three seeds per condition, so small "
    "differences are within noise.",
    "Source: the cell-dev repository on this machine (outputs/, results/ and RESULTS.md). Each organism was replayed with "
    "the repository's own simulator; its explanation was checked by targeted simulations and challenged by two independent "
    "reviewers, and corrected where they found problems.",
]


def main():
    organisms = {}
    for s in SPECIMENS:
        d = json.loads((D / f"{s['id']}.json").read_text())
        letters = {r["type"]: "ABCD"[i] for i, r in enumerate(sorted(d["rules"], key=lambda r: r["type"]))}
        for t in d["trials"]:  # labels written with raw type numbers -> page letters
            t["label"] = re.sub(r"type-(\d)", lambda m: f"type {letters.get(int(m.group(1)), m.group(1))}", t["label"])
        d["title"] = s["title"]
        organisms[s["id"]] = d
    data = {"organisms": organisms, "specimens": SPECIMENS, "hero": "context",
            "charts": json.loads((D / "charts.json").read_text()), "footer": FOOTER}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = (HERE / "template.html").read_text().replace("/*__DATA__*/", blob)
    (HERE / "atlas.html").write_text(html)
    print(f"atlas.html {len(html) / 1024:.0f} KB")
    for s in SPECIMENS:
        for t in organisms[s["id"]]["trials"]:
            print(f"  {s['id']:13s} {t['label']}")


if __name__ == "__main__":
    main()
