"""Assemble a fixed-case standalone HTML without importing or executing any simulator."""
from __future__ import annotations

import copy
import hashlib
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = "grn_count3_preset"
BODY_INDEX, SEED = 0, 42000002
PATCH_WORLD = dict(
    T=128.0, t0=0.0, t_open=0.0, task_mode=0.0, sample_min=0.0, sample_max=0.0,
    blank_min=0.0, blank_max=0.0, choice_T=0.0, reset_T=0.0,
    visibility_mode=0.0, visibility_on=0.0, visibility_off=0.0, visibility_low=1.0,
    patch_count=3.0, patch_capacity=2.0, patch_refill_fast=80.0, patch_refill_slow=160.0,
    patch_landmark=0.1, v_t=0.0, tau_turn=0.0, t_resp=0.0, b2_amp=0.0, b2_value=0.0,
    b2_mode=0.0, b2_p=1.0, sigma=0.6, rho_c=1.0, R_min=2.0, R_max=4.0,
    R_cap=500.0, c_miss=10.0,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble():
    atlas_path = ROOT/"results/atlas/play/bodies.json"
    engine_path = ROOT/"results/atlas/play/lifesim.js"
    view_path = ROOT/"results/atlas/play/resource_patches_view.js"
    prepared = json.loads((HERE/"JS_PREPARATION.json").read_text())
    for path in (engine_path, view_path):
        assert digest(path) == prepared["source_pins"][str(path.relative_to(ROOT))]
    atlas = json.loads(atlas_path.read_text())
    body = copy.deepcopy(atlas["bodies"][BODY_INDEX])
    assert body["name"] == "speck_lmax4_hexprism_sex_s5" and body["mode"] == "grn"
    body.pop("world_vec", None)
    body["world"].update(PATCH_WORLD)
    body.update(abi=6, lattice=atlas["lattice"], genome_slices=atlas["genome_slices"], drag=atlas["drag"])
    sources = {str(path.relative_to(ROOT)): digest(path) for path in (
        atlas_path, engine_path, view_path, Path(__file__), HERE/"DRAFT_CONTRACT.md", HERE/"export_truth.py")}
    payload = json.dumps(dict(body=body, seed=SEED, case=CASE), separators=(",", ":"), allow_nan=False)
    payload = payload.replace("<", "\\u003c").replace("&", "\\u0026")
    engine, view = engine_path.read_text(), view_path.read_text()
    assert "</script" not in engine.lower() and "</script" not in view.lower()
    title = html.escape(body["name"])
    page = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Resource patches · fixed engineering preview</title>
<style>
  :root { color-scheme:dark; font:16px/1.5 system-ui,sans-serif; background:#0a111b; color:#e1e8f2 }
  body { max-width:1050px; margin:32px auto; padding:0 20px }
  h1,h2 { line-height:1.15; font-weight:600 }
  p { max-width:94ch; color:#c3d0df }
  button { font:inherit; cursor:pointer; padding:7px 12px; margin:0 8px 8px 0;
    border:1px solid #526477; border-radius:6px; color:inherit; background:#1a2b3e }
  button:disabled { opacity:.5; cursor:default }
  table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; margin:20px 0 }
  th,td { text-align:right; padding:8px; border-bottom:1px solid #314153 }
  th:first-child,td:first-child { text-align:left }
  caption { text-align:left; padding-bottom:8px; color:#aebed1 }
  details { overflow-wrap:anywhere; margin-top:24px }
  #error { color:#ffc6ab }
  @media(max-width:700px) { table { font-size:11px } th,td { padding:3px } }
</style>
<h1>Persistent resource patches</h1>
<p>This fixed engineering illustration uses the historical GRN fixture <strong>__BODY__</strong>.
  It was not evolved on resource patches. No success or information-payoff claim is attached to this example.</p>
<p>Case <code>grn_count3_preset</code>, seed <code>42000002</code>, duration 128: three stationary patches,
  capacity two packets each, source periods 80 or 160, and the original food and energy prices.
  This is the preset geometry in a shortened engineering life. Playback starts paused; replay uses the same case.</p>
<p>Sources arrive on fixed world schedules independently of the organism. Cells receive local scalar receptor pings;
  the labels below do not provide patch identity, stock, period, a clock, or a map to cells.</p>
<p id="error" role="alert"></p>
<main id="viewer"></main>
<details><summary>Embedded source provenance</summary><pre>__PINS__</pre></details>
<script type="application/json" id="fixture">__PAYLOAD__</script>
<script>__ENGINE__</script>
<script>__VIEW__</script>
<script>
'use strict';
try {
  const fixture = JSON.parse(document.getElementById('fixture').textContent);
  ResourcePatchesView.mount(document.getElementById('viewer'), fixture.body,
    { seed:fixture.seed, hashes:true, speed:8 });
} catch (cause) { document.getElementById('error').textContent = cause.message; }
</script>
</html>
"""
    for token, value in (("__BODY__", title), ("__PINS__", html.escape(json.dumps(sources, indent=2))),
                         ("__PAYLOAD__", payload), ("__ENGINE__", engine), ("__VIEW__", view)):
        page = page.replace(token, value)
    output = HERE/"resource_patches_preview.html"
    output.write_text(page)
    receipt = dict(status="assembled_without_simulation", case=CASE, source_body=BODY_INDEX, seed=SEED,
                   world_overrides=PATCH_WORLD, source_pins=sources, html_sha256=digest(output),
                   html_bytes=output.stat().st_size, new_lives=0, new_builds=0, new_random_draws=0,
                   runtime_checks_executed=False, real_browser_tested=False,
                   purpose="Fixed engineering illustration; no evolved patch behavior or payoff claim.")
    (HERE/"PREVIEW_PREPARATION.json").write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps(dict(path=str(output), sha256=receipt["html_sha256"], bytes=receipt["html_bytes"])))


if __name__ == "__main__":
    assemble()
