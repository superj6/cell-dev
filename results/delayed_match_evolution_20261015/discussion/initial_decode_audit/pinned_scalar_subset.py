G_MAX = 16

def sigmoid(x: float) -> float:
    """1 / (1 + exp(-x)) as C evaluates it: where exp(-x) overflows to inf (x < about -709.78) the result is 0.0;
    Python's math.exp raises there instead, so that case is mirrored explicitly."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0

def clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x

def rint(x: float) -> float:
    """Round half to even keeping the sign of x, exactly as C ``nearbyint`` (so rint(-0.4) is -0.0)."""
    return math.copysign(float(round(x)), x)

def q8(x: float) -> float:
    """Clip to [-2, 2] and round to the 1/8 grid."""
    return rint(clip(x, -2.0, 2.0) * 8.0) / 8.0
KNOBS_V2 = ('w0', 'w1', 'b', 'tau_m', 't_ref', 'emit0', 'emit1', 'delta', 'kappa', 'p_div', 'asym', 'p_die', 'phi', 'sec0', 'sec1', 'pol0', 'pol1', 'tau_tr', 'a0', 'a1', 'chi')
KNOBS_V3 = KNOBS_V2 + ('zeta', 'g_r')
DELTA = (0.0, 0.5, 1.0, 2.0)
KAPPA = (0.0, 0.25, 0.5, 1.0)
PHI = (0.0, 0.5, 1.0, 2.0)
TAU_TR = (2.0, 4.0, 8.0, 16.0)

def _level(table, y: float) -> float:
    return table[int(clip(rint(2.0 * y), 0.0, 3.0))]

def _fate(y: float) -> float:
    k = int(clip(rint(4.0 * y), 0.0, 8.0))
    return 0.0 if k == 0 else 2.0 ** (k - 8)

def _decode21(y: list[float]) -> list[float]:
    """The 21 knobs of ABI 2 (LIFE_ABI.md section 8, rows 0-20)."""
    return [q8(y[0]), q8(y[1]), q8(y[2]), 2.0 ** clip(rint(y[3] + 2.0), 0.0, 4.0), 0.5 * clip(rint(2.0 * y[4] + 4.0), 1.0, 8.0), 1.0 if y[5] > 0.0 else 0.0, 1.0 if y[6] > 0.0 else 0.0, _level(DELTA, y[7]), _level(KAPPA, y[8]), _fate(y[9]), sigmoid(y[10]), _fate(y[11]), _level(PHI, y[12]), 0.5 * sigmoid(y[13]), 0.5 * sigmoid(y[14]), q8(2.0 * math.tanh(y[15])), q8(2.0 * math.tanh(y[16])), TAU_TR[int(clip(rint(y[17] + 1.5), 0.0, 3.0))], q8(y[18]), q8(y[19]), q8(y[20])]

def decode_knobs(self, y) -> list[float]:
    """theta = decode(y) for the readout values y = A.g + a0 (LIFE_ABI.md section 8)."""
    y = [float(v) for v in y]
    out = _decode21(y)
    if self.version >= 3:
        out += [q8(y[21]), q8(y[22])]
    return out

def readout(self, gt_row, g) -> list[float]:
    """y_p = a0[p] + sum_k A[p][k] g[k], accumulated left to right over k = 0..15 (packed genome table row)."""
    A = gt_row[self.GENOME_SLICES['A'][0]:self.GENOME_SLICES['A'][1]]
    a0 = gt_row[self.GENOME_SLICES['a0'][0]:self.GENOME_SLICES['a0'][1]]
    out = []
    for p in range(self.P):
        y = float(a0[p])
        for k in range(G_MAX):
            y = y + float(A[p * G_MAX + k]) * float(g[k])
        out.append(y)
    return out
