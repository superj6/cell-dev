"""Regeneration positive control v7: the GS5 GRN router (handbuilt.router_genome) plus four genes that refill holes.

  router gene 7 INNER (n_view/D >= 7/8) is made slow (lambda 1/16): a cell that was interior remembers it for ~30 units.
  12 GATE = sigma(100 (timer - 0.5))      development is over (lineage timer, gene 5, inherited); lambda 1/2
  13 MAT  target 1, lambda 1/16, Q -1     a daughter starts immature (0); mothers are already mature after development
  14 FULL = sigma(80 (n_view/D - 13/16))  all 7 contacts present; lambda 1/2
  15 LOSS = sigma(20 INNER - 20 FULL + 20 GATE + 20 MAT - 50)   lambda 1/2
       a mature cell that was interior and now misses a contact, after development
  p_div readout += 1.75 LOSS (only sense cells reach the threshold). The cell divides into its best open slot: up if
  its act cell died (zeta 2), else a hole (flanks). A refill daughter is immature, so it cannot trigger while it
  inherits INNER; its 'fresh' division regrows its act cell (up) or, at the rim, buds once outward.
  K.w1 = 1: the hotspot also listens to channel 1, so a relay-type (J) cell that refills the centre still drives the
  click (the founder's lineage role cannot come back). In the intact body nothing below K emits channel 1.
Router gene 12 (quiet) is freed: interior act cells sit above channel-1-only J cells and never fire either way.
"""
from common import *
LAM, X3 = hb.LAM_X, hb.X3
GATE, MAT, FULL, LOSS = 12, 13, 14, 15
LAMX = {2: -3.0, 4: -2.0, 8: -1.0, 16: 0.0, 32: 1.0, 64: 2.0, 128: 4.0}

def regen_genome(base_knobs, window=0.2, gain=1.75, t_gate=0.5, inner_lam=16, enable=True):
    g = hb.router_genome(base_knobs, window=window).astype(np.float64)
    W, b, lam, s0, Q, act = (V3.genome_view(g, n) for n in ("W", "b", "lam", "s0", "Q", "act"))
    A = V3.genome_view(g, "A")
    W[GATE, :] = 0.0; W[:, GATE] = 0.0; A[:, GATE] = 0.0; b[GATE] = 0.0; act[GATE] = 0.0   # free 'quiet'
    if not enable:
        return g.astype(np.float32)
    lam[hb.RG_INNER] = LAMX[inner_lam]
    for k in (GATE, MAT, FULL, LOSS):
        act[k], s0[k], Q[k] = 1.0, -12.0, 0.0
        W[k, :] = 0.0
    lam[GATE], lam[MAT], lam[FULL], lam[LOSS] = LAMX[2], LAMX[16], LAMX[2], LAMX[2]
    W[GATE, hb.CG_TIMER], b[GATE] = 100.0, -100.0 * t_gate
    b[MAT], Q[MAT] = 12.0, -1.0
    W[FULL, X3["n_view"]], b[FULL] = 80.0, -80.0 * 13 / 16
    W[LOSS, hb.RG_INNER], W[LOSS, FULL], W[LOSS, GATE], W[LOSS, MAT], b[LOSS] = 20.0, -20.0, 20.0, 20.0, -50.0
    A[V3.K["p_div"], LOSS] = gain
    return g.astype(np.float32)

def router_knobs(k_w1=1.0):
    k = dict(hb.SPECK_TUNED["router@ring4"], **hb.ROUTER_FIXED)
    if k_w1:
        k["K.w1"] = k_w1
    return k

if __name__ == "__main__":
    from xbuild import xrun
    sd = seeds(256, 4)
    base = hb.GrnBody("grn-router", hb.router_genome(router_knobs(0.0), window=0.2))
    basek = hb.GrnBody("grn-router K.w1", hb.router_genome(router_knobs(), window=0.2))
    reg = hb.GrnBody("grn-router+regen", regen_genome(router_knobs()))
    refl = P.hand("reflex@hollow3")[0]
    def late(r): return r.ledger[:, 22]
    rows = []
    for kw in (dict(), dict(kill_t=512.0, kill_frac=0.25), dict(kill_t=512.0, kill_frac=0.5), dict(kill_t=300.0, kill_frac=0.25)):
        out = {}
        for name, org in (("reflex@hollow3", refl), ("grn-router", base), ("grn-router K.w1", basek), ("grn-router+regen", reg)):
            r = xrun(org, "catch_speck_l4", sd, **kw)
            out[name] = r
            print(f"{str(kw):45s} {name:18s} F={F(r).mean():+.2f}±{F(r).std()/16:.2f} n_end={r['n_end'].mean():.0f}±{r['n_end'].std():.0f} "
                  f"births={r['births'].mean():.0f} late_caps={late(r).mean():.1f} zero_late={(late(r)==0).mean():.2f}", flush=True)
            rows.append(dict(world=str(kw), body=name, F=float(F(r).mean()), se=float(F(r).std()/16), n_end=float(r['n_end'].mean()),
                             births=float(r['births'].mean()), late_caps=float(late(r).mean()), zero_late=float((late(r)==0).mean())))
        d = paired(out["grn-router+regen"], out["grn-router K.w1"]); d2 = paired(out["grn-router+regen"], out["reflex@hollow3"])
        print(f"   regen - router(K.w1) {d['mean']:+.2f}±{d['se']:.2f};  regen - reflex {d2['mean']:+.2f}±{d2['se']:.2f}", flush=True)
        rows.append(dict(world=str(kw), regen_minus_router=d, regen_minus_reflex=d2))
    json.dump(rows, open(f"{OUT}/regen7.json", "w"), indent=1)
