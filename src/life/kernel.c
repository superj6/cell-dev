// One-life event kernel, ABI v1. The contract is docs/LIFE_ABI.md; section numbers below refer to it.
//
// One continuous, clockless life per genome (GRN mode) or phenotype program (program mode) on a sparse, unbounded
// lattice fabric (or a dense disk). Sites process their own events in time-ordered batches (6.2); every cross-site
// effect is a message delayed by at least d_min (6.3). Handlers emit records that one sequential accountant consumes
// in canonical (t, sitekey, seq) order (9.1), so floating-point sums are identical under every scheduler. The heap
// scheduler (production) and the window scheduler (tests) share every handler (11). Lives run in parallel with
// OpenMP and are independent of thread count and batch composition.
//
// Build: gcc -O3 -fopenmp -ffp-contract=off -fPIC -shared -std=c11 (no -ffast-math, no -march): see build.py.
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define ABI_VERSION 1
#define NG 16          // gene slots
#define NIN 23         // regulatory inputs
#define NK 21          // phenotype knobs
#define DMAX 8         // largest lattice degree
#define GENOME_SIZE 809
#define PROGRAM_SIZE 119
#define WORLD_SIZE 41
#define LEDGER_SIZE 35
#define HASH_SIZE 4
#define MAX_INIT 64
#define FATE_I 6
#define FATE_F 18
// world ranges (4.7): time stays resolvable at 2^-21 or finer, and no period or delay is shorter than STEP_MIN
#define TIME_MAX 1073741824.0  // 2^30: bound on T and |t0|
#define STEP_MIN 0.0009765625  // 2^-10: smallest d_min and smallest possible tick period
#define SD_MAX 1.0             // frozen log-normal spreads (delay_sd, clock_sd)
#define NOISE_MAX 1024.0       // membrane-noise kicks per cell per unit
#define NMAX_MAX 1048576.0     // 2^20 live cells
#define INT_FIELD_MAX 1073741824.0  // 2^30: fabric_R, oracle_cap, |stuck_a|, |stuck_b|

// knobs (section 8)
enum { K_W0, K_W1, K_B, K_TAUM, K_TREF, K_EMIT0, K_EMIT1, K_DELTA, K_KAPPA, K_PDIV, K_ASYM, K_PDIE, K_PHI, K_SEC0,
       K_SEC1, K_POL0, K_POL1, K_TAUTR, K_A0, K_A1, K_CHI };
// packed genome offsets (4.4)
enum { GO_W = 0, GO_B = 368, GO_LAM = 384, GO_G0 = 400, GO_Q = 416, GO_ACT = 432, GO_A = 448, GO_A0 = 784,
       GO_DM = 805, GO_KM = 807 };
// program table (4.5)
enum { PR_JUV = 105, PR_NVRIM, PR_ZYGROW, PR_FLANKGATE, PR_PDIVLO, PR_KGROW, PR_TIMERSTEP, PR_PRUNE, PR_KKEEP,
       PR_KDIE, PR_DM0, PR_DM1, PR_KM0, PR_KM1 };
enum { ROW_ALONE, ROW_CONTACT, ROW_JUVENILE, ROW_RIM, ROW_ZYGOTE, N_ROWS };
// world vector (4.7)
enum { W_T, W_T0, W_TOPEN, W_TFORK, W_FLAGS, W_FORKFLAGS, W_DMIN, W_D0, W_DELAYSD, W_JIT, W_TAUMIS, W_P0, W_CLOCKSD,
       W_TICKJIT, W_TAUZ, W_TH, W_THLO, W_TAUR, W_TAUE, W_HINC, W_CLIVE, W_CSPIKE, W_CTW, W_CMSG, W_CDIV, W_CSEC,
       W_NMAX, W_EMAX, W_FABRICR, W_ORACLE, W_WINDOWH, W_DROPP, W_NOISE, W_KILLT, W_KILLFRAC, W_STUCKT, W_STUCKA,
       W_STUCKB, W_KILLRATE, W_WOUNDRATE, W_DRIFTTAU };
// ledger columns (4.9)
enum { L_INCOME, L_LIVE, L_SECINT, L_SPIKES, L_KAPPA, L_CONTACT, L_CLAIMS, L_BIRTHS, L_REJECTS, L_REJWALL, L_DEATHS,
       L_KILLS, L_COST, L_GUARD, L_NET, L_F, L_NEND, L_NPEAK, L_TEND, L_STATUS, L_EVENTS, L_BEATS, L_PINT,
       L_ARRIVALS, L_ARRDROP, L_PACKETS, L_MSEC, L_MDEC, L_MLOST, L_MCONTENT, L_MINFLIGHT, L_CLAMPS, L_LASTBIRTH,
       L_TICKS, L_TEXT };
// flags (12)
enum { F_CONTACTS_OFF = 1 << 0, F_CHEM_OFF = 1 << 1, F_APOPTOSIS_OFF = 1 << 2, F_DIVISION_OFF = 1 << 3,
       F_FREEZE = 1 << 4, F_GENES_BLIND = 1 << 5, F_IDENTITY_CLAMP = 1 << 6, F_PHENO_FIXED = 1 << 7,
       F_LOCKSTEP = 1 << 8, F_PROGRAM = 1 << 9, F_INTEGER_TWIN = 1 << 10 };
#define F_ALL ((1 << 11) - 1)
#define F_BASE_ONLY (F_LOCKSTEP | F_PROGRAM | F_INTEGER_TWIN)
// status bits (4.12)
enum { ST_EXTINCT = 1, ST_GUARD_CELLS = 2, ST_GUARD_EVENTS = 4, ST_RASTER_OVF = 8, ST_FATE_OVF = 16,
       ST_CHEM_CLAMP = 32, ST_MISMATCH = 64, ST_CAPACITY = 128, ST_WALL = 256 };
// draw streams (3)
enum { S_ZYG = 1, S_UID, S_TAU, S_CLK, S_PHASE, S_DC, S_JIT, S_DROP, S_TICK, S_DIE, S_DIV, S_PLACE, S_NOISE, S_NSIGN,
       S_KILL, S_TIE, S_ORDER };
// event groups and kinds (6.1)
enum { G_CLAIM, G_NOTICE, G_PACKET, G_MEMB, G_TICK, G_EXO };
enum { N_BORN, N_PRESENT, N_ACK, N_REJECT, N_DIED };
enum { M_ARRIVAL, M_THRESHOLD, M_NOISE };
enum { X_KILL, X_STUCK };
// records (9.1)
enum { R_BIRTH, R_SPIKE, R_TICK, R_CHEM, R_PACKET, R_LOST, R_CLAIM, R_RESOLVE, R_DEATH };
// hash families (9.6)
enum { H_ALL, H_SPIKES, H_FATE, H_CHEM };
// internal failures (the life is invalid: capacity bit)
enum { FAIL_ALLOC = 1, FAIL_LIMIT = 2, FAIL_CAUSAL = 4 };

static const uint64_t HASH_INIT = 0x243F6A8885A308D3ULL;
static const double TWO_M53 = 1.0 / 9007199254740992.0;
static const double TAU_M_T[5] = {1.0, 2.0, 4.0, 8.0, 16.0};
static const double DELTA_T[4] = {0.0, 0.5, 1.0, 2.0};
static const double KAPPA_T[4] = {0.0, 0.25, 0.5, 1.0};
static const double PHI_T[4] = {0.0, 0.5, 1.0, 2.0};
static const double TAU_TR_T[4] = {2.0, 4.0, 8.0, 16.0};

// ------------------------------------------------------------------------------------------- arithmetic (2, 3)
static inline uint64_t splitmix64(uint64_t x) {
  uint64_t z = x + 0x9E3779B97F4A7C15ULL;
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
  return z ^ (z >> 31);
}
static inline uint64_t hash_start(uint64_t seed, uint64_t stream) { return splitmix64(seed ^ splitmix64(stream)); }
static inline uint64_t hash1(uint64_t seed, uint64_t s, uint64_t k1) { return splitmix64(hash_start(seed, s) ^ k1); }
static inline uint64_t hash2(uint64_t seed, uint64_t s, uint64_t k1, uint64_t k2) {
  return splitmix64(splitmix64(hash_start(seed, s) ^ k1) ^ k2);
}
static inline uint64_t hash3(uint64_t seed, uint64_t s, uint64_t k1, uint64_t k2, uint64_t k3) {
  return splitmix64(splitmix64(splitmix64(hash_start(seed, s) ^ k1) ^ k2) ^ k3);
}
static inline double u01(uint64_t h) { return (double)((h >> 11) | 1ULL) * TWO_M53; }
static inline double draw1(uint64_t seed, uint64_t s, uint64_t k1) { return u01(hash1(seed, s, k1)); }
static inline double draw2(uint64_t seed, uint64_t s, uint64_t k1, uint64_t k2) { return u01(hash2(seed, s, k1, k2)); }
static inline double draw3(uint64_t seed, uint64_t s, uint64_t k1, uint64_t k2, uint64_t k3) {
  return u01(hash3(seed, s, k1, k2, k3));
}
// Irwin-Hall(12) - 6 over hash64(seed, stream, keys..., j), j = 0..11; the prefix hash is shared by the 12 terms.
static double normal_n(uint64_t seed, uint64_t stream, int n, const uint64_t *keys) {
  uint64_t h = hash_start(seed, stream);
  for (int i = 0; i < n; i++) h = splitmix64(h ^ keys[i]);
  uint64_t s = 0;
  for (uint64_t j = 0; j < 12; j++) s += splitmix64(h ^ j) >> 11;
  return (double)s * TWO_M53 - 6.0;
}
static inline uint64_t sitekey(int32_t a, int32_t b) { return ((uint64_t)(uint32_t)a << 32) | (uint64_t)(uint32_t)b; }
static inline uint64_t dbits(double x) { uint64_t u; memcpy(&u, &x, sizeof u); return u; }
static inline double sigma(double x) { return 1.0 / (1.0 + exp(-x)); }
static inline double clipd(double x, double lo, double hi) { return x < lo ? lo : (x > hi ? hi : x); }
static inline double q8(double x) { return nearbyint(clipd(x, -2.0, 2.0) * 8.0) / 8.0; }
static inline double q10(double v) { return nearbyint((v < -2.0 ? -2.0 : v) * 1024.0) / 1024.0; }
// int(clip(x, 0, hi)) for an integer-valued x; NaN maps to 0, so no input can index outside a knob table
static inline int level_index(double x, int hi) { return x >= 0.0 ? (x < (double)hi ? (int)x : hi) : 0; }
static inline int level4(double y) { return level_index(nearbyint(2.0 * y), 3); }
static inline double fate_p(double y) {
  int k = level_index(nearbyint(4.0 * y), 8);
  return k == 0 ? 0.0 : ldexp(1.0, k - 8);
}

static void decode(const double *y, double *th) {  // section 8
  th[K_W0] = q8(y[0]); th[K_W1] = q8(y[1]); th[K_B] = q8(y[2]);
  th[K_TAUM] = TAU_M_T[level_index(nearbyint(y[3] + 2.0), 4)];
  th[K_TREF] = 0.5 * clipd(nearbyint(2.0 * y[4] + 4.0), 1.0, 8.0);
  th[K_EMIT0] = y[5] > 0.0 ? 1.0 : 0.0; th[K_EMIT1] = y[6] > 0.0 ? 1.0 : 0.0;
  th[K_DELTA] = DELTA_T[level4(y[7])]; th[K_KAPPA] = KAPPA_T[level4(y[8])];
  th[K_PDIV] = fate_p(y[9]); th[K_ASYM] = sigma(y[10]); th[K_PDIE] = fate_p(y[11]);
  th[K_PHI] = PHI_T[level4(y[12])];
  th[K_SEC0] = 0.5 * sigma(y[13]); th[K_SEC1] = 0.5 * sigma(y[14]);
  th[K_POL0] = q8(2.0 * tanh(y[15])); th[K_POL1] = q8(2.0 * tanh(y[16]));
  th[K_TAUTR] = TAU_TR_T[level_index(nearbyint(y[17] + 1.5), 3)];
  th[K_A0] = q8(y[18]); th[K_A1] = q8(y[19]); th[K_CHI] = q8(y[20]);
}

static void readout(const double *gt, const double *g, double *y) {
  const double *A = gt + GO_A, *a0 = gt + GO_A0;
  for (int p = 0; p < NK; p++) {
    double v = a0[p];
    for (int k = 0; k < NG; k++) v = v + A[p * NG + k] * g[k];
    y[p] = v;
  }
}

// --------------------------------------------------------------------------------------------- structures
typedef struct { double t; uint64_t tie, sk; int32_t ev, pad; } HEnt;
typedef struct { HEnt *a; int64_t n, cap; } Heap;

typedef struct {
  double t;
  int32_t site, blob;    // target site; claim gene payload (-1 none)
  uint8_t group, sub, slot, mask;
  int32_t next;          // free list
  uint64_t uid;          // target uid (0 = the site occupant, or the site itself for claims)
  uint64_t u2, u3;       // sender uid / daughter uid / ver / noise j; sender k / mother uid
  double x[2];           // lost packet amt[2]; claim timer (program mode)
} Ev;

typedef struct { double t_arr; uint64_t sender; int32_t slot, pad; double amt[2], conc[2]; } Pkt;

typedef struct {
  uint64_t uid, mother, ver;
  int64_t k, n_spike, n_tick, n_div;  // birth index and the cell's own counters
  int32_t site, alive, init_index, fixed_row, claim_pending, stuck, next_free, n_inbox, cap_inbox, pad;
  double t_birth, va, ta, tr, f, r[2], ttr, z, tz, t_prev, taumis, Pn, tau, timer, timer_birth;
  uint64_t view[DMAX];
  double dc[DMAX], inc[DMAX][2], sd[DMAX], weff[DMAX][2];
  double g[NG], m[2], th[NK];
  Pkt *inbox;
} Cell;

typedef struct {
  uint64_t sk, tie;
  int64_t births;
  int32_t a, b, cell, exists;
  int32_t nbr[DMAX];
} Site;

typedef struct {
  double t;
  uint64_t sk;
  int32_t seq, kind, site, pad;
  uint64_t u1, u2, u3;
  int64_t i1, g;         // integer payload; offset of a g[16] snapshot (-1 none)
  double x[3];
} Rec;

typedef struct { double t_send, t_arr; uint64_t tsk, sender; double amt[2]; } Flight;
typedef struct { uint64_t key, sk; double t; int32_t ev, pad; } WEnt;  // window visit key, site, time, event

typedef struct {
  // configuration
  const double *w, *gt, *pg, *unit;
  int D, code, prog, window;
  int32_t off_a[DMAX], off_b[DMAX], back[DMAX], prv[DMAX], nxt[DMAX];
  uint64_t seed, tie_seed, order_seed, salt;
  int64_t flags, fork_flags, fl;
  double T, t0, t1, t_open_abs, t_fork_abs, d_min, d0, delay_sd, jit, tau_mis, P0, clock_sd, tick_jit, tau_z, th,
      th_lo, tau_R, tau_e, h_inc, c_live, c_spike, c_tw, c_msg, c_div, c_sec, n_max, e_max, oracle_cap, window_h,
      drop_p, noise_rate, kill_t, kill_frac, stuck_t;
  int32_t fabric_R, stuck_a, stuck_b;
  int64_t cap_cells;
  // fabric
  Site *sites; int64_t n_sites, cap_sites;
  int32_t *map; int64_t map_cap;
  Cell *cells; int64_t cap_cell_pool; int32_t cell_free;
  // events
  Ev *ev; int64_t cap_ev; int32_t ev_free;
  double *blobs; int32_t *blob_next; int64_t cap_blob; int32_t blob_free;
  Heap heap, local;
  WEnt *wbuf; int64_t cap_wbuf;
  int32_t *bbuf; int64_t cap_bbuf;
  // batch
  int32_t cur_site, seq, in_window;
  double cur_t, wend;
  int32_t *grp[6]; int64_t ngrp[6], capgrp[6];
  // records
  Rec *rec; int64_t n_rec, cap_rec;
  double *gsnap; int64_t n_gsnap, cap_gsnap;
  int64_t *ridx; int64_t cap_ridx;
  int want_g;
  // simulator counts (site-level, order-free) and oracle-cap counts; cap_count is n_alive + n_inflight at cap_t-
  int64_t n_alive_sim, n_inflight_sim, events, c_arrivals, c_arrdrop, c_ticks, cap_count;
  double cap_t;
  // accountant (5.3, 9)
  double A, R, tw; int above;
  int64_t n, inflight, n_peak;
  double income, live_time, sec_int, kappa_sum, cost, P_int, m_sec, m_dec, m_lost, m_content, m_inflight;
  int64_t spikes, contact, claims, births, rejects, rejwall, deaths, kills, beats, packets, clamps;
  double last_birth, t_ext, t_end;
  int extinct, guard;
  int64_t status;
  uint64_t H[HASH_SIZE];
  Flight *fl_q; int64_t fl_head, fl_n, fl_cap;
  // logs
  int64_t raster_cap, raster_n; double *raster_t; uint64_t *raster_uid;
  int64_t fate_cap, fate_n; int64_t *fate_i; double *fate_f;
  int fail;
} Ctx;

static int grow(void **p, int64_t *cap, int64_t need, size_t elem, int64_t first) {
  if (need <= *cap) return 0;
  int64_t nc = *cap ? *cap : first;
  while (nc < need) nc *= 2;
  void *q = realloc(*p, (size_t)nc * elem);
  if (!q) return -1;
  *p = q; *cap = nc;
  return 0;
}

// ------------------------------------------------------------------------------------------------- heap
static inline int hless(const HEnt *x, const HEnt *y) {
  if (x->t != y->t) return x->t < y->t;
  if (x->tie != y->tie) return x->tie < y->tie;
  return x->sk < y->sk;
}
static int hpush(Heap *h, HEnt e) {
  if (h->n == h->cap && grow((void **)&h->a, &h->cap, h->n + 1, sizeof(HEnt), 1024)) return -1;
  int64_t i = h->n++;
  while (i > 0) {
    int64_t p = (i - 1) >> 1;
    if (!hless(&e, &h->a[p])) break;
    h->a[i] = h->a[p];
    i = p;
  }
  h->a[i] = e;
  return 0;
}
static HEnt hpop(Heap *h) {
  HEnt top = h->a[0], last = h->a[--h->n];
  int64_t i = 0;
  for (;;) {
    int64_t l = 2 * i + 1, r = l + 1, m = i;
    const HEnt *cand = &last;
    if (l < h->n && hless(&h->a[l], cand)) { m = l; cand = &h->a[l]; }
    if (r < h->n && hless(&h->a[r], cand)) m = r;
    if (m == i) break;
    h->a[i] = h->a[m];
    i = m;
  }
  if (h->n > 0) h->a[i] = last;
  return top;
}

// ------------------------------------------------------------------------------------------------ fabric
static int in_disk(int code, int64_t a, int64_t b, int64_t R) {
  if (code == 0) {
    int64_t s = a + b, m = a < 0 ? -a : a, bb = b < 0 ? -b : b, ss = s < 0 ? -s : s;
    if (bb > m) m = bb;
    if (ss > m) m = ss;
    return m <= R;
  }
  return (double)(a * a + b * b) <= ((double)R + 0.5) * ((double)R + 0.5);
}

static inline uint64_t map_hash(const Ctx *c, uint64_t sk) { return splitmix64(sk ^ c->salt); }

static int map_insert(Ctx *c, int32_t si) {
  uint64_t m = (uint64_t)c->map_cap - 1, i = map_hash(c, c->sites[si].sk) & m;
  while (c->map[i] >= 0) i = (i + 1) & m;
  c->map[i] = si;
  return 0;
}

static int map_rehash(Ctx *c, int64_t ncap) {
  int32_t *nm = malloc((size_t)ncap * sizeof(int32_t));
  if (!nm) return -1;
  for (int64_t i = 0; i < ncap; i++) nm[i] = -1;
  free(c->map);
  c->map = nm; c->map_cap = ncap;
  for (int64_t s = 0; s < c->n_sites; s++) map_insert(c, (int32_t)s);
  return 0;
}

static int32_t site_get(Ctx *c, int32_t a, int32_t b) {
  uint64_t sk = sitekey(a, b), m = (uint64_t)c->map_cap - 1, i = map_hash(c, sk) & m;
  while (c->map[i] >= 0) {
    if (c->sites[c->map[i]].sk == sk) return c->map[i];
    i = (i + 1) & m;
  }
  if (c->n_sites >= INT32_MAX - 1) { c->fail |= FAIL_LIMIT; return -1; }
  if (grow((void **)&c->sites, &c->cap_sites, c->n_sites + 1, sizeof(Site), 256)) { c->fail |= FAIL_ALLOC; return -1; }
  int32_t si = (int32_t)c->n_sites++;
  Site *s = &c->sites[si];
  s->sk = sk; s->tie = hash1(c->tie_seed, S_TIE, sk); s->births = 0; s->a = a; s->b = b; s->cell = -1;
  s->exists = c->fabric_R == 0 || in_disk(c->code, a, b, c->fabric_R);
  for (int d = 0; d < DMAX; d++) s->nbr[d] = -1;
  if (2 * c->n_sites > c->map_cap) {
    if (map_rehash(c, 2 * c->map_cap)) { c->fail |= FAIL_ALLOC; return -1; }
  } else {
    map_insert(c, si);
  }
  return si;
}

static int32_t site_nbr(Ctx *c, int32_t si, int d) {
  int32_t j = c->sites[si].nbr[d];
  if (j >= 0) return j;
  j = site_get(c, c->sites[si].a + c->off_a[d], c->sites[si].b + c->off_b[d]);
  if (j >= 0) c->sites[si].nbr[d] = j;
  return j;
}

// ------------------------------------------------------------------------------------------- pools
static int32_t cell_alloc(Ctx *c) {
  if (c->n_alive_sim >= c->cap_cells) { c->fail |= FAIL_LIMIT; return -1; }
  if (c->cell_free < 0) {
    int64_t old = c->cap_cell_pool;
    if (grow((void **)&c->cells, &c->cap_cell_pool, old + 1, sizeof(Cell), 64)) { c->fail |= FAIL_ALLOC; return -1; }
    int64_t n = c->cap_cell_pool - old, rot = (int64_t)(c->salt % (uint64_t)n);
    for (int64_t j = 0; j < n; j++) {  // the relabel salt permutes the allocation order (test T5)
      int64_t i = old + (c->salt & 1 ? (j + rot) % n : n - 1 - (j + rot) % n);
      c->cells[i].inbox = NULL; c->cells[i].cap_inbox = 0; c->cells[i].alive = 0;
      c->cells[i].next_free = c->cell_free;
      c->cell_free = (int32_t)i;
    }
  }
  int32_t i = c->cell_free;
  c->cell_free = c->cells[i].next_free;
  return i;
}
static void cell_release(Ctx *c, int32_t i) { c->cells[i].next_free = c->cell_free; c->cell_free = i; }

static int32_t ev_new(Ctx *c) {
  if (c->ev_free < 0) {
    int64_t old = c->cap_ev;
    if (old >= INT32_MAX / 2) { c->fail |= FAIL_LIMIT; return -1; }
    if (grow((void **)&c->ev, &c->cap_ev, old + 1, sizeof(Ev), 4096)) { c->fail |= FAIL_ALLOC; return -1; }
    for (int64_t i = c->cap_ev - 1; i >= old; i--) { c->ev[i].next = c->ev_free; c->ev_free = (int32_t)i; }
  }
  int32_t i = c->ev_free;
  c->ev_free = c->ev[i].next;
  c->ev[i].blob = -1;
  return i;
}
static int32_t blob_new(Ctx *c) {  // claim gene payloads (GRN mode)
  if (c->blob_free < 0) {
    int64_t old = c->cap_blob, nc = old ? 2 * old : 64;
    double *nb = realloc(c->blobs, (size_t)nc * NG * sizeof(double));
    if (!nb) { c->fail |= FAIL_ALLOC; return -1; }
    c->blobs = nb;
    int32_t *nn = realloc(c->blob_next, (size_t)nc * sizeof(int32_t));
    if (!nn) { c->fail |= FAIL_ALLOC; return -1; }
    c->blob_next = nn;
    for (int64_t i = nc - 1; i >= old; i--) { c->blob_next[i] = c->blob_free; c->blob_free = (int32_t)i; }
    c->cap_blob = nc;
  }
  int32_t i = c->blob_free;
  c->blob_free = c->blob_next[i];
  return i;
}
static void ev_release(Ctx *c, int32_t i) {
  if (c->ev[i].blob >= 0) { c->blob_next[c->ev[i].blob] = c->blob_free; c->blob_free = c->ev[i].blob; }
  c->ev[i].blob = -1;
  c->ev[i].next = c->ev_free;
  c->ev_free = i;
}

static void push_ev(Ctx *c, int32_t ei) {
  const Ev *e = &c->ev[ei];
  const Site *s = &c->sites[e->site];
  HEnt h = {e->t, s->tie, s->sk, ei, 0};
  Heap *hp = &c->heap;
  if (c->in_window && e->t < c->wend) {  // only self events may land in the current window (11.2)
    if (e->site != c->cur_site) c->fail |= FAIL_CAUSAL;
    hp = &c->local;
  }
  if (hpush(hp, h)) c->fail |= FAIL_ALLOC;
}

static Ev *ev_make(Ctx *c, int32_t *ei, double t, int32_t site, int group, int sub) {
  *ei = ev_new(c);
  if (*ei < 0) return NULL;
  Ev *e = &c->ev[*ei];
  e->t = t; e->site = site; e->group = (uint8_t)group; e->sub = (uint8_t)sub; e->slot = 0; e->mask = 0;
  e->uid = 0; e->u2 = 0; e->u3 = 0; e->x[0] = e->x[1] = 0.0;
  return e;
}

static void self_ev(Ctx *c, int32_t si, double t, int group, int sub, uint64_t uid, uint64_t u2) {
  int32_t ei;
  Ev *e = ev_make(c, &ei, t, si, group, sub);
  if (!e) return;
  e->uid = uid; e->u2 = u2;
  push_ev(c, ei);
}

// a message through slot d of site si; it arrives at the receiver's slot back[d]
static Ev *msg_make(Ctx *c, int32_t *ei, int32_t si, int d, double t, int group, int sub) {
  int32_t ti = site_nbr(c, si, d);
  if (ti < 0) return NULL;
  Ev *e = ev_make(c, ei, t, ti, group, sub);
  if (e) e->slot = (uint8_t)c->back[d];
  return e;
}

static void notice(Ctx *c, int32_t si, int d, double t, int sub, uint64_t target, uint64_t sender, uint64_t k) {
  int32_t ei;
  Ev *e = msg_make(c, &ei, si, d, t, G_NOTICE, sub);
  if (!e) return;
  e->uid = target; e->u2 = sender; e->u3 = k;
  push_ev(c, ei);
}

// -------------------------------------------------------------------------------------------- records
static Rec *emit(Ctx *c, int kind) {
  if (grow((void **)&c->rec, &c->cap_rec, c->n_rec + 1, sizeof(Rec), 1024)) { c->fail |= FAIL_ALLOC; return NULL; }
  Rec *r = &c->rec[c->n_rec++];
  memset(r, 0, sizeof *r);
  r->t = c->cur_t; r->sk = c->sites[c->cur_site].sk; r->seq = c->seq++; r->kind = kind; r->site = c->cur_site;
  r->g = -1;
  return r;
}
static void rec_g(Ctx *c, Rec *r, const double *g) {
  if (!c->want_g || !r) return;
  if (grow((void **)&c->gsnap, &c->cap_gsnap, c->n_gsnap + NG, sizeof(double), 64 * NG)) { c->fail |= FAIL_ALLOC; return; }
  memcpy(c->gsnap + c->n_gsnap, g, NG * sizeof(double));
  r->g = c->n_gsnap;
  c->n_gsnap += NG;
}

// ---------------------------------------------------------------------------------------- cell physics
static inline double vnow(const Cell *X, double t) {  // 7.1
  if (t < X->tr) return 0.0;
  double t0 = X->ta < X->tr ? X->tr : X->ta, v0 = X->ta >= X->tr ? X->va : 0.0, b = X->th[K_B];
  return b + (v0 - b) * exp(-(t - t0) / X->tau);
}
static inline void traces_to(Cell *X, double t) {
  double e = exp(-(t - X->ttr) / X->th[K_TAUTR]);
  X->f = X->f * e; X->r[0] = X->r[0] * e; X->r[1] = X->r[1] * e; X->ttr = t;
}
static void predict(Ctx *c, int32_t si, Cell *X) {
  X->ver += 1;
  double t0 = X->ta < X->tr ? X->tr : X->ta, v0 = X->ta >= X->tr ? X->va : 0.0, b = X->th[K_B];
  if (b > 1.0 && v0 < 1.0)
    self_ev(c, si, t0 + X->tau * log((b - v0) / (b - 1.0)), G_MEMB, M_THRESHOLD, X->uid, X->ver);
}
static inline int n_view(const Ctx *c, const Cell *X) {
  int n = 0;
  for (int d = 0; d < c->D; d++) n += X->view[d] != 0;
  return n;
}

static void derive(const Ctx *c, Cell *X) {  // section 8: s_d and w_eff
  const double *th = X->th;
  double smax = 0.0;
  for (int d = 0; d < c->D; d++) {
    double s = X->view[d] == 0 ? 0.0
                               : th[K_POL0] * (X->inc[d][0] - X->m[0]) + th[K_POL1] * (X->inc[d][1] - X->m[1]);
    X->sd[d] = s;
    double as = fabs(s);
    smax = smax < as ? as : smax;
  }
  for (int d = 0; d < c->D; d++) {
    double shat = X->sd[d] / (smax + 1e-6);
    X->weff[d][0] = q8(th[K_W0] * (1.0 + th[K_A0] * shat));
    X->weff[d][1] = q8(th[K_W1] * (1.0 + th[K_A1] * shat));
  }
}

static int prog_row(const Ctx *c, const Cell *X, int nv) {  // 7.5 selector
  const double *pg = c->pg;
  if (X->fixed_row >= 0) return X->fixed_row;
  if (pg[PR_ZYGROW] != 0.0 && X->init_index == 0) return ROW_ZYGOTE;
  if (nv == 0) return ROW_ALONE;
  if ((double)X->n_tick < pg[PR_JUV]) return ROW_JUVENILE;
  if (pg[PR_NVRIM] > 0.0 && (double)nv < pg[PR_NVRIM]) return ROW_RIM;
  return ROW_CONTACT;
}

static void set_theta(const Ctx *c, Cell *X, int nv) {
  if (c->prog) {
    memcpy(X->th, c->pg + NK * prog_row(c, X, nv), NK * sizeof(double));
  } else {
    double y[NK];
    readout(c->gt, X->g, y);
    decode(y, X->th);
  }
  X->tau = X->th[K_TAUM] * X->taumis;
}

static void stuck_apply(Cell *X) {  // 7.9: tonic firing that ignores input
  X->th[K_B] = 2.0; X->th[K_TAUM] = 1.0; X->th[K_TREF] = 0.5;
  X->tau = X->th[K_TAUM] * X->taumis;
  for (int d = 0; d < DMAX; d++) X->weff[d][0] = X->weff[d][1] = 0.0;
}

// Inbox-only packets (15.4): a packet whose target is the live occupant when it is sent goes straight into the target's
// inbox, stamped with its arrival time; it becomes a LOST event (group 2 at the target site, at t_arr) only if the
// target is gone when it is sent or dies before t_arr. A packet sent in one window arrives at or after its end, so no
// consumer can see it early, and the records are those of packets-as-events.
static void inbox_sort(Cell *X) {  // (t_arr, sender uid); appends are nearly sorted
  for (int32_t i = 1; i < X->n_inbox; i++) {
    Pkt v = X->inbox[i];
    int32_t j = i - 1;
    while (j >= 0 && (X->inbox[j].t_arr > v.t_arr || (X->inbox[j].t_arr == v.t_arr && X->inbox[j].sender > v.sender))) {
      X->inbox[j + 1] = X->inbox[j];
      j--;
    }
    X->inbox[j + 1] = v;
  }
}
static int inbox_add(Ctx *c, Cell *X, const Pkt *p) {
  if (X->n_inbox == X->cap_inbox) {
    int64_t cap = X->cap_inbox;
    if (grow((void **)&X->inbox, &cap, cap + 1, sizeof(Pkt), 8)) { c->fail |= FAIL_ALLOC; return -1; }
    X->cap_inbox = (int32_t)cap;
  }
  X->inbox[X->n_inbox++] = *p;
  return 0;
}
static void lost_ev(Ctx *c, int32_t si, double t_arr, uint64_t sender, uint64_t target, const double *amt) {
  int32_t ei;
  Ev *e = ev_make(c, &ei, t_arr, si, G_PACKET, 0);
  if (!e) return;
  e->uid = target; e->u2 = sender; e->x[0] = amt[0]; e->x[1] = amt[1];
  push_ev(c, ei);
}

static void fire(Ctx *c, int32_t si, Cell *X, double t) {  // 7.3
  const double *th = X->th;
  X->va = 0.0; X->ta = t; X->tr = t + th[K_TREF];
  traces_to(X, t);
  X->f = X->f + 1.0;
  X->n_spike += 1;
  c->events++;
  int e0 = th[K_EMIT0] != 0.0, e1 = th[K_EMIT1] != 0.0, n_ch = e0 + e1, n_live = n_view(c, X);  // nonzero = on
  int64_t n_out = (int64_t)n_live * n_ch;
  if (n_ch > 0 && !(c->fl & F_CONTACTS_OFF)) {
    uint8_t mask = (uint8_t)(e0 | (e1 << 1));
    double jit = (c->flags & F_LOCKSTEP) ? 0.0 : c->jit;
    for (int d = 0; d < c->D; d++) {
      if (X->view[d] == 0) continue;
      if (c->drop_p > 0.0 && draw3(c->seed, S_DROP, X->uid, (uint64_t)X->n_spike, (uint64_t)d) < c->drop_p) continue;
      double u = draw3(c->seed, S_JIT, X->uid, (uint64_t)X->n_spike, (uint64_t)d);
      double dl = X->dc[d] * (1.0 + jit * (2.0 * u - 1.0)) + th[K_DELTA];
      if (dl < c->d_min) dl = c->d_min;
      int32_t ei;
      Ev *e = msg_make(c, &ei, si, d, t + dl, G_MEMB, M_ARRIVAL);
      if (!e) return;
      e->uid = X->view[d]; e->mask = mask;
      push_ev(c, ei);
    }
  }
  double dz = 0.0, kap = th[K_KAPPA];
  if (kap > 0.0) {
    double zt = X->z * exp(-(t - X->tz) / c->tau_z), zn = zt + kap;
    if (zn > 1.0) zn = 1.0;
    dz = zn - zt; X->z = zn; X->tz = t;
  }
  Rec *r = emit(c, R_SPIKE);
  if (r) { r->u1 = X->uid; r->x[0] = kap; r->i1 = n_out; r->x[1] = dz; }
  predict(c, si, X);
}

static void apoptosis(Ctx *c, int32_t si, int32_t ci, double t, int cause) {  // 7.8
  Cell *X = &c->cells[ci];
  double zt = X->z * exp(-(t - X->tz) / c->tau_z);
  double content = X->m[0] + X->m[1];
  inbox_sort(X);
  for (int32_t i = 0; i < X->n_inbox; i++) {
    const Pkt *p = &X->inbox[i];
    if (p->t_arr <= t) content = content + p->amt[0] + p->amt[1];
    else lost_ev(c, si, p->t_arr, p->sender, X->uid, p->amt);
  }
  Rec *r = emit(c, R_DEATH);
  if (r) {
    r->u1 = X->uid; r->u2 = X->mother; r->i1 = cause; r->x[0] = zt; r->x[1] = content; r->x[2] = t - X->t_birth;
    rec_g(c, r, X->g);
  }
  uint64_t uid = X->uid;
  X->alive = 0; X->n_inbox = 0;
  c->sites[si].cell = -1;
  c->n_alive_sim--;
  cell_release(c, ci);
  for (int d = 0; d < c->D; d++) notice(c, si, d, t + c->d_min, N_DIED, 0, uid, 0);
}

static void birth(Ctx *c, int32_t si, double t, uint64_t uid, uint64_t mother, int bslot, const double *genes,
                  double timer, int init_index, int fixed_row) {  // 7.6
  int32_t ci = cell_alloc(c);
  if (ci < 0) return;
  Site *S = &c->sites[si];
  int64_t k = S->births++;
  uint64_t sk = S->sk;
  Cell *X = &c->cells[ci];
  Pkt *ib = X->inbox;
  int32_t cap = X->cap_inbox;
  memset(X, 0, sizeof *X);
  X->inbox = ib; X->cap_inbox = cap;
  X->uid = uid; X->mother = mother; X->k = k; X->site = si; X->alive = 1; X->init_index = init_index;
  X->fixed_row = fixed_row; X->next_free = -1;
  const int lock = (c->flags & F_LOCKSTEP) != 0;
  if (lock) {
    X->taumis = 1.0; X->Pn = c->P0;
  } else {
    X->taumis = 1.0 + c->tau_mis * (2.0 * draw2(c->seed, S_TAU, sk, (uint64_t)k) - 1.0);
    uint64_t keys[2] = {sk, (uint64_t)k};
    X->Pn = c->P0 * exp(c->clock_sd * normal_n(c->seed, S_CLK, 2, keys));
  }
  double U = draw2(c->seed, S_PHASE, sk, (uint64_t)k);
  X->va = 0.0; X->ta = t; X->tr = t; X->ttr = t; X->tz = t; X->t_prev = t; X->t_birth = t;
  if (c->prog) { X->timer = timer; X->timer_birth = timer; }
  else memcpy(X->g, genes, NG * sizeof(double));
  set_theta(c, X, 0);
  derive(c, X);
  Rec *r = emit(c, R_BIRTH);
  if (r) {
    r->u1 = uid; r->u2 = mother; r->i1 = k; r->u3 = init_index >= 0;
    if (!c->prog) rec_g(c, r, X->g);
  }
  c->sites[si].cell = ci;
  c->n_alive_sim++;
  predict(c, si, X);
  double t1 = lock ? c->t0 + c->P0 * (floor((t - c->t0) / c->P0) + 1.0) : t + U * X->Pn;
  if (t1 <= t) t1 = nextafter(t, INFINITY);
  self_ev(c, si, t1, G_TICK, 0, uid, 0);
  if (c->noise_rate > 0.0) {
    double tn = t - log(draw2(c->seed, S_NOISE, uid, 0)) / c->noise_rate;
    if (tn <= t) tn = nextafter(t, INFINITY);
    self_ev(c, si, tn, G_MEMB, M_NOISE, uid, 0);
  }
  if (c->kill_t >= 0.0 && t < c->t0 + c->kill_t) self_ev(c, si, c->t0 + c->kill_t, G_EXO, X_KILL, uid, 0);
  if (c->stuck_t >= 0.0 && t < c->t0 + c->stuck_t && c->sites[si].a == c->stuck_a && c->sites[si].b == c->stuck_b)
    self_ev(c, si, c->t0 + c->stuck_t, G_EXO, X_STUCK, uid, 0);
  for (int d = 0; d < c->D; d++) notice(c, si, d, t + c->d_min, N_BORN, 0, uid, (uint64_t)k);
  if (mother != 0) notice(c, si, bslot, t + c->d_min, N_ACK, mother, uid, (uint64_t)k);
}

static double contact_delay(const Ctx *c, int32_t si, const Cell *X, int d, uint64_t knb) {  // 7.7 DC
  if (c->flags & F_LOCKSTEP) return c->d0;
  const Site *s = &c->sites[si];
  uint64_t keys[3] = {s->sk, sitekey(s->a + c->off_a[d], s->b + c->off_b[d]), ((uint64_t)X->k << 32) | knb};
  return c->d0 * exp(c->delay_sd * normal_n(c->seed, S_DC, 3, keys));
}

static void tick(Ctx *c, int32_t si, int32_t ci, double t) {  // 7.4 (GRN) and 7.5 (program)
  Cell *X = &c->cells[ci];
  const int64_t fl = c->fl;
  const double dt = t - X->t_prev;
  const int D = c->D;
  // 1. inbox: the packets that have arrived, in (t_arr, sender uid) order
  inbox_sort(X);
  int32_t na = 0;
  for (; na < X->n_inbox && X->inbox[na].t_arr <= t; na++) {
    const Pkt *p = &X->inbox[na];
    X->m[0] = X->m[0] + p->amt[0]; X->m[1] = X->m[1] + p->amt[1];
    if (X->view[p->slot] == p->sender) { X->inc[p->slot][0] = p->conc[0]; X->inc[p->slot][1] = p->conc[1]; }  // 15.9
  }
  if (na > 0) {
    memmove(X->inbox, X->inbox + na, (size_t)(X->n_inbox - na) * sizeof(Pkt));
    X->n_inbox -= na;
  }
  // 2. living cost and secretion of the interval, with the phenotype in force during it
  const double sp0 = X->th[K_SEC0], sp1 = X->th[K_SEC1];
  Rec *r = emit(c, R_TICK);
  if (r) { r->u1 = X->uid; r->x[0] = X->t_prev; r->x[1] = sp0 + sp1; }
  if (t >= c->t_open_abs) c->c_ticks++;
  c->events++;
  // 3. view and inputs
  traces_to(X, t);
  int nv = 0, any_empty = 0, fbest = 0, flank[DMAX];
  for (int d = 0; d < D; d++) nv += X->view[d] != 0;
  for (int e = 0; e < D; e++) {
    flank[e] = (X->view[c->prv[e]] != 0) + (X->view[c->nxt[e]] != 0);
    if (X->view[e] == 0) {
      any_empty = 1;
      if (flank[e] > fbest) fbest = flank[e];
    }
  }
  // 4. genes (GRN) or the program timer
  if (!(fl & (F_IDENTITY_CLAMP | F_FREEZE))) {
    if (c->prog) {
      X->timer = X->timer + c->pg[PR_TIMERSTEP];
    } else {
      double x[NIN], s[NG];
      for (int k = 0; k < NG; k++) x[k] = X->g[k];
      x[16] = X->m[0] / (1.0 + X->m[0]); x[17] = X->m[1] / (1.0 + X->m[1]);
      const double ttr = X->th[K_TAUTR];
      x[18] = X->f / ttr; x[19] = X->r[0] / ttr; x[20] = X->r[1] / ttr;
      x[21] = (double)nv / (double)D; x[22] = (double)fbest / 2.0;
      if (fl & F_GENES_BLIND) x[18] = x[19] = x[20] = x[21] = x[22] = 0.0;
      const double *W = c->gt + GO_W, *bb = c->gt + GO_B, *lam = c->gt + GO_LAM;
      for (int k = 0; k < NG; k++) {
        if (lam[k] == 0.0) { s[k] = 0.0; continue; }  // g + 0 * (s - g) == g exactly: skip the row
        double p = bb[k];
        for (int j = 0; j < NIN; j++) p = p + W[k * NIN + j] * x[j];
        s[k] = sigma(p);
      }
      for (int k = 0; k < NG; k++)
        if (lam[k] != 0.0) X->g[k] = X->g[k] + lam[k] * (s[k] - X->g[k]);
    }
  }
  // 5. membrane re-anchor with the old phenotype, then identity
  if (t >= X->tr) {
    X->va = q10(vnow(X, t)); X->ta = t;
    if (X->va >= 1.0) fire(c, si, X, t);
  }
  if (!(fl & (F_FREEZE | F_PHENO_FIXED))) set_theta(c, X, nv);
  if (!(fl & F_FREEZE)) derive(c, X);
  if (X->stuck) stuck_apply(X);
  predict(c, si, X);
  // 6. death
  if (!(fl & (F_APOPTOSIS_OFF | F_FREEZE))) {
    if (c->prog && c->pg[PR_PRUNE] != 0.0 && X->timer_birth >= c->pg[PR_KKEEP] && X->timer >= c->pg[PR_KDIE]) {
      apoptosis(c, si, ci, t, 2);
      return;
    }
    const double pd = X->th[K_PDIE];
    if (pd > 0.0 && draw2(c->seed, S_DIE, X->uid, (uint64_t)X->n_tick) < pd) {
      apoptosis(c, si, ci, t, 1);
      return;
    }
  }
  // 7. chemistry
  const double *Dm = c->prog ? c->pg + PR_DM0 : c->gt + GO_DM, *km = c->prog ? c->pg + PR_KM0 : c->gt + GO_KM;
  const double md0 = X->m[0] * exp(-km[0] * dt), md1 = X->m[1] * exp(-km[1] * dt);
  const double dec = (X->m[0] - md0) + (X->m[1] - md1);
  X->m[0] = md0 + sp0 * dt; X->m[1] = md1 + sp1 * dt;
  const double sec = sp0 * dt + sp1 * dt;
  int clamp = 0;
  if (nv > 0 && !(fl & F_CHEM_OFF)) {
    const double nvd = (double)nv;
    double amt[2], conc[2];
    for (int i = 0; i < 2; i++) {
      double q = Dm[i] * dt;
      if (nvd * q > 0.9) { q = 0.9 / nvd; clamp = 1; }
      amt[i] = X->m[i] * q; conc[i] = X->m[i];
    }
    for (int d = 0; d < D; d++) {
      if (X->view[d] == 0) continue;
      const int32_t ti = site_nbr(c, si, d);
      if (ti < 0) return;
      const double ta = t + c->d_min;
      const int32_t oc = c->sites[ti].cell;
      if (oc >= 0 && c->cells[oc].uid == X->view[d]) {
        const Pkt pk = {ta, X->uid, c->back[d], 0, {amt[0], amt[1]}, {conc[0], conc[1]}};
        if (inbox_add(c, &c->cells[oc], &pk)) return;
      } else {
        lost_ev(c, ti, ta, X->uid, X->view[d], amt);
      }
      Rec *rp = emit(c, R_PACKET);
      if (rp) {
        rp->u1 = X->uid; rp->u2 = X->view[d]; rp->u3 = c->sites[c->sites[si].nbr[d]].sk;
        rp->x[0] = amt[0]; rp->x[1] = amt[1];
      }
    }
    for (int i = 0; i < 2; i++) X->m[i] = X->m[i] - nvd * amt[i];
  }
  Rec *rc = emit(c, R_CHEM);
  if (rc) { rc->x[0] = sec; rc->x[1] = dec; rc->i1 = clamp; }
  // 8. division
  if (!(fl & (F_DIVISION_OFF | F_FREEZE)) && X->claim_pending == 0 && any_empty) {
    double p = X->th[K_PDIV];
    int ok;
    if (c->prog) {
      if (c->pg[PR_FLANKGATE] > 0.0 && (double)fbest < c->pg[PR_FLANKGATE]) p = c->pg[PR_PDIVLO];
      ok = p > 0.0 && X->timer <= c->pg[PR_KGROW];
    } else {
      ok = p > 0.0;
    }
    if (ok && draw2(c->seed, S_DIV, X->uid, (uint64_t)X->n_tick) < p &&
        (c->oracle_cap == 0.0 || (double)c->cap_count < c->oracle_cap)) {
      double px = 0.0, py = 0.0;
      for (int d = 0; d < D; d++) { px = px + X->sd[d] * c->unit[2 * d]; py = py + X->sd[d] * c->unit[2 * d + 1]; }
      const double chi = X->th[K_CHI], vx = px - chi * py, vy = py + chi * px;
      int best = -1;
      double bs = 0.0;
      for (int e = 0; e < D; e++) {
        if (X->view[e] != 0) continue;
        double sc = c->unit[2 * e] * vx + c->unit[2 * e + 1] * vy + X->th[K_PHI] * (double)flank[e] +
                    1e-3 * draw3(c->seed, S_PLACE, X->uid, (uint64_t)X->n_div, (uint64_t)e);
        if (best < 0 || sc > bs) { best = e; bs = sc; }
      }
      uint64_t dau = hash2(c->seed, S_UID, X->uid, (uint64_t)X->n_div) | 1ULL;
      int32_t ei;
      Ev *e = msg_make(c, &ei, si, best, t + c->d_min, G_CLAIM, 0);
      if (!e) return;
      e->u2 = dau; e->u3 = X->uid;
      if (c->prog) {
        e->x[0] = X->timer;
      } else {
        int32_t bi = blob_new(c);
        if (bi < 0) return;
        e = &c->ev[ei];
        e->blob = bi;
        double *gd = c->blobs + (int64_t)bi * NG;
        const double *Q = c->gt + GO_Q, asym = X->th[K_ASYM];
        if (fl & F_IDENTITY_CLAMP) {  // g frozen: no partition, the daughter starts with her mother's g (15.31)
          for (int k = 0; k < NG; k++) gd[k] = X->g[k];
        } else {
          for (int k = 0; k < NG; k++) {
            double qk = asym * Q[k];
            gd[k] = clipd(X->g[k] + qk, 0.0, 1.0);
            X->g[k] = clipd(X->g[k] - qk, 0.0, 1.0);
          }
        }
      }
      push_ev(c, ei);
      Rec *rl = emit(c, R_CLAIM);
      if (rl) { rl->u1 = X->uid; rl->u2 = dau; rl->u3 = c->sites[c->sites[si].nbr[best]].sk; }
      c->n_inflight_sim++;
      X->n_div += 1;
      X->claim_pending = 1;
    }
  }
  // 9. next tick
  double tj = (c->flags & F_LOCKSTEP) ? 0.0 : c->tick_jit;
  double per = X->Pn * (1.0 + tj * (2.0 * draw2(c->seed, S_TICK, X->uid, (uint64_t)X->n_tick) - 1.0));
  self_ev(c, si, t + per, G_TICK, 0, X->uid, 0);
  X->n_tick += 1;
  X->t_prev = t;
}

// --------------------------------------------------------------------------------------------- batches
static void grp_add(Ctx *c, int g, int32_t ei) {
  if (grow((void **)&c->grp[g], &c->capgrp[g], c->ngrp[g] + 1, sizeof(int32_t), 64)) { c->fail |= FAIL_ALLOC; return; }
  c->grp[g][c->ngrp[g]++] = ei;
}

static int ev_before(const Ctx *c, int g, int32_t a, int32_t b) {  // within-group order (6.2)
  const Ev *x = &c->ev[a], *y = &c->ev[b];
  if (g == G_NOTICE) {
    if (x->slot != y->slot) return x->slot < y->slot;
    if (x->sub != y->sub) return x->sub < y->sub;
    return x->u2 < y->u2;
  }
  if (g == G_MEMB || g == G_EXO) {
    if (x->sub != y->sub) return x->sub < y->sub;
    return x->u2 < y->u2;
  }
  return x->u2 < y->u2;  // claims by daughter uid, packets by sender uid
}
static void grp_sort(Ctx *c, int g) {  // insertion sort: groups are tiny
  int32_t *a = c->grp[g];
  for (int64_t i = 1; i < c->ngrp[g]; i++) {
    int32_t v = a[i];
    int64_t j = i - 1;
    while (j >= 0 && ev_before(c, g, v, a[j])) { a[j + 1] = a[j]; j--; }
    a[j + 1] = v;
  }
}

static void batch(Ctx *c, int32_t si, double t, const int32_t *evs, int64_t n) {  // 6.2
  c->cur_site = si; c->cur_t = t; c->seq = 0;
  c->fl = c->flags | (t >= c->t_fork_abs ? c->fork_flags : 0);
  const int cnt = t >= c->t_open_abs;
  for (int g = 0; g < 6; g++) c->ngrp[g] = 0;
  for (int64_t i = 0; i < n; i++) grp_add(c, c->ev[evs[i]].group, evs[i]);
  for (int g = 0; g < 6; g++) if (c->ngrp[g] > 1) grp_sort(c, g);
  const int32_t occ = c->sites[si].cell;  // the occupant at t-
  // 0. claims
  if (c->ngrp[G_CLAIM]) {
    const int exists = c->sites[si].exists;
    int winner = 0;
    for (int64_t i = 0; i < c->ngrp[G_CLAIM]; i++) {
      const Ev e = c->ev[c->grp[G_CLAIM][i]];
      int res = !exists ? 2 : ((occ >= 0 || winner) ? 1 : 0);
      if (res == 0) winner = 1;
      Rec *r = emit(c, R_RESOLVE);
      if (r) { r->u1 = e.u2; r->u2 = e.u3; r->i1 = res; }
      c->n_inflight_sim--;
      if (res == 0) birth(c, si, t, e.u2, e.u3, e.slot, e.blob >= 0 ? c->blobs + (int64_t)e.blob * NG : NULL, e.x[0], -1, -1);
      else notice(c, si, e.slot, t + c->d_min, N_REJECT, e.u3, 0, 0);
    }
  }
  Cell *X = occ >= 0 ? &c->cells[occ] : NULL;
  // 1. notices
  if (X) {
    for (int64_t i = 0; i < c->ngrp[G_NOTICE]; i++) {
      const Ev *e = &c->ev[c->grp[G_NOTICE][i]];
      const int d = e->slot;
      if (e->sub != N_BORN && e->sub != N_DIED && e->uid != X->uid) continue;
      switch (e->sub) {
        case N_BORN: {
          uint64_t u = e->u2, kk = e->u3;
          X->view[d] = u; X->dc[d] = contact_delay(c, si, X, d, kk);
          notice(c, si, d, t + c->d_min, N_PRESENT, u, X->uid, (uint64_t)X->k);
          break;
        }
        case N_PRESENT: X->view[d] = e->u2; X->dc[d] = contact_delay(c, si, X, d, e->u3); break;
        case N_ACK: X->claim_pending = 0; X->view[d] = e->u2; X->dc[d] = contact_delay(c, si, X, d, e->u3); break;
        case N_REJECT: X->claim_pending = 0; break;
        default: X->view[d] = 0; X->inc[d][0] = X->inc[d][1] = 0.0; break;
      }
    }
  }
  // 2. packets: delivered packets are already in the inbox (inbox_add); the events here are the lost ones
  for (int64_t i = 0; i < c->ngrp[G_PACKET]; i++) {
    const Ev *e = &c->ev[c->grp[G_PACKET][i]];
    Rec *r = emit(c, R_LOST);
    if (r) { r->u1 = e->u2; r->u2 = e->uid; r->x[0] = e->x[0]; r->x[1] = e->x[1]; }
  }
  // 3. membrane step (7.2)
  if (c->ngrp[G_MEMB]) {
    int64_t n_arr = 0, n_del = 0, cnt0 = 0, cnt1 = 0;
    int thr = 0, n_kick = 0;
    double S = 0.0;
    for (int64_t i = 0; i < c->ngrp[G_MEMB]; i++) {
      const Ev *e = &c->ev[c->grp[G_MEMB][i]];
      if (e->sub == M_ARRIVAL) {
        n_arr++;
        if (X && e->uid == X->uid) {
          n_del++;
          if (e->mask & 1) { cnt0++; S += X->weff[e->slot][0]; }
          if (e->mask & 2) { cnt1++; S += X->weff[e->slot][1]; }
        }
      } else if (X && e->uid == X->uid) {
        if (e->sub == M_THRESHOLD) {
          if (e->u2 == X->ver) thr = 1;
        } else {  // NOISE j: this kick, then schedule kick j + 1
          uint64_t j = e->u2;
          S += draw2(c->seed, S_NSIGN, X->uid, j) >= 0.5 ? 0.125 : -0.125;
          n_kick++;
          double tn = e->t - log(draw2(c->seed, S_NOISE, X->uid, j + 1)) / c->noise_rate;
          if (tn <= e->t) tn = nextafter(e->t, INFINITY);
          self_ev(c, si, tn, G_MEMB, M_NOISE, X->uid, j + 1);
        }
      }
    }
    c->events += n_arr;
    if (cnt) { c->c_arrivals += n_del; c->c_arrdrop += n_arr - n_del; }
    if (X && (n_del > 0 || n_kick > 0 || thr)) {
      int go = 1;
      if (n_del > 0) {
        traces_to(X, t);
        X->r[0] = X->r[0] + (double)cnt0; X->r[1] = X->r[1] + (double)cnt1;
      }
      if (t < X->tr) go = 0;  // refractory: input lost, traces already counted
      if (go) {
        double v = (thr ? 1.0 : vnow(X, t)) + S;
        X->va = q10(v); X->ta = t;
        if (X->va >= 1.0) fire(c, si, X, t);
        else predict(c, si, X);
      }
    }
  }
  // 4. tick
  if (X && X->alive) {
    for (int64_t i = 0; i < c->ngrp[G_TICK]; i++)
      if (c->ev[c->grp[G_TICK][i]].uid == X->uid) { tick(c, si, occ, t); break; }
  }
  // 5. exogenous: KILL, then STUCK (7.9)
  for (int64_t i = 0; i < c->ngrp[G_EXO]; i++) {
    const Ev *e = &c->ev[c->grp[G_EXO][i]];
    if (!X || !X->alive || e->uid != X->uid) continue;
    if (e->sub == X_KILL) {
      if (draw1(c->seed, S_KILL, X->uid) < c->kill_frac) {
        Rec *r = emit(c, R_TICK);  // living and secretion cost of [t_prev, t) (7.9)
        if (r) { r->u1 = X->uid; r->x[0] = X->t_prev; r->x[1] = X->th[K_SEC0] + X->th[K_SEC1]; }
        apoptosis(c, si, occ, t, 3);
      }
    } else {
      if (t >= X->tr) {
        X->va = q10(vnow(X, t)); X->ta = t;
        if (X->va >= 1.0) fire(c, si, X, t);
      }
      X->stuck = 1;
      stuck_apply(X);
      predict(c, si, X);
    }
  }
  for (int64_t i = 0; i < n; i++) ev_release(c, evs[i]);
}

// ------------------------------------------------------------------------------------------- accountant
static inline void fold(Ctx *c, int fam, const uint64_t *w, int n) {
  uint64_t h = c->H[fam];
  for (int i = 0; i < n; i++) h = splitmix64(h ^ w[i]);
  c->H[fam] = h;
}

static void adv(Ctx *c, double t, int count) {  // 9.2
  const double dt = t - c->tw;
  if (c->n == 0) { c->tw = t; return; }
  const double nd = (double)c->n, P0 = c->A / nd, e = exp(-dt / c->tau_z);
  if (P0 > c->th) {
    double s1 = c->tau_z * log(P0 / c->th);
    if (s1 > dt) s1 = dt;
    const double I = c->tau_z * P0 * (1.0 - exp(-s1 / c->tau_z)) - c->th * s1;
    const double Rn = c->R * exp(-I / ((1.0 - c->th) * c->tau_e));
    if (count) c->income = c->income + c->h_inc * nd * (c->R - Rn);
    c->R = Rn;
  }
  const double Pend = P0 * e;
  if (Pend < c->th_lo) {
    const double slo = P0 > c->th_lo ? c->tau_z * log(P0 / c->th_lo) : 0.0, dd = dt - slo;
    if (dd > 0) c->R = 1.0 - (1.0 - c->R) * exp(-dd / c->tau_R);
  }
  if (count) c->P_int = c->P_int + c->tau_z * P0 * (1.0 - e);
  if (Pend <= c->th) c->above = 0;
  c->A = c->A * e;
  c->tw = t;
}
static void world_adv(Ctx *c, double t) {
  if (t <= c->tw) return;
  const double to = c->t_open_abs;
  if (c->tw < to && to < t) { adv(c, to, 0); adv(c, t, 1); }
  else adv(c, t, c->tw >= to);
}

static void tick_charge(Ctx *c, double t, double tprev, double sp) {
  const double to = c->t_open_abs;
  if (t > to) {
    const double dl = t - (tprev < to ? to : tprev);
    c->live_time = c->live_time + dl;
    c->sec_int = c->sec_int + sp * dl;
    c->cost = c->cost + c->c_live * dl;
    c->cost = c->cost + c->c_sec * (sp * dl);
  }
}

static void fate_log(Ctx *c, int kind, const Rec *r, uint64_t uid, uint64_t mother, int64_t aux, double age) {
  if (c->fate_cap > 0 && c->fate_n < c->fate_cap) {
    int64_t *fi = c->fate_i + c->fate_n * FATE_I;
    double *ff = c->fate_f + c->fate_n * FATE_F;
    fi[0] = kind; fi[1] = (int64_t)uid; fi[2] = (int64_t)mother;
    fi[3] = c->sites[r->site].a; fi[4] = c->sites[r->site].b; fi[5] = aux;
    ff[0] = r->t; ff[1] = age;
    for (int k = 0; k < NG; k++) ff[2 + k] = r->g >= 0 ? c->gsnap[r->g + k] : 0.0;
  }
  c->fate_n++;
}

static void acc_record(Ctx *c, const Rec *r) {  // 9.1
  const double t = r->t;
  const int cnt = t >= c->t_open_abs;
  while (c->fl_n > 0 && c->fl_q[c->fl_head].t_arr < t) {  // packets whose arrival the accountant has passed
    c->fl_head = (c->fl_head + 1) % c->fl_cap;
    c->fl_n--;
  }
  uint64_t w[6];
  switch (r->kind) {
    case R_BIRTH:
      world_adv(c, t);
      c->n += 1;
      if (!r->u3) {
        if (cnt) c->births++;
        c->last_birth = t;
      }
      fate_log(c, 1, r, r->u1, r->u2, r->i1, 0.0);
      w[0] = 2; w[1] = dbits(t); w[2] = r->u1; w[3] = r->u2; w[4] = r->sk; w[5] = (uint64_t)r->i1;
      fold(c, H_FATE, w, 6); fold(c, H_ALL, w, 6);
      break;
    case R_SPIKE: {
      const double kap = r->x[0];
      if (cnt) {
        c->spikes++; c->kappa_sum = c->kappa_sum + kap; c->contact += r->i1;
        c->cost = c->cost + c->c_spike;
        c->cost = c->cost + c->c_tw * kap;
        c->cost = c->cost + c->c_msg * (double)r->i1;
      }
      if (kap > 0.0) {
        world_adv(c, t);
        c->A = c->A + r->x[1];
        if (c->above == 0 && c->A / (double)c->n > c->th) {
          c->above = 1;
          if (cnt) c->beats++;
        }
      }
      if (c->raster_cap > 0 && c->raster_n < c->raster_cap) {
        c->raster_t[c->raster_n] = t; c->raster_uid[c->raster_n] = r->u1;
      }
      c->raster_n++;
      w[0] = 1; w[1] = dbits(t); w[2] = r->u1; w[3] = dbits(kap); w[4] = (uint64_t)r->i1;
      fold(c, H_SPIKES, w, 5); fold(c, H_ALL, w, 5);
      break;
    }
    case R_TICK:
      tick_charge(c, t, r->x[0], r->x[1]);
      w[0] = 8; w[1] = dbits(t); w[2] = r->u1;
      fold(c, H_ALL, w, 3);
      break;
    case R_CHEM:
      c->m_sec = c->m_sec + r->x[0];
      c->m_dec = c->m_dec + r->x[1];
      if (r->i1) {
        c->status |= ST_CHEM_CLAMP;
        if (cnt) c->clamps += r->i1;
      }
      break;
    case R_PACKET: {
      if (cnt) c->packets++;
      if (c->fl_n == c->fl_cap) {  // grow the ring buffer, keeping FIFO order
        int64_t nc = c->fl_cap ? 2 * c->fl_cap : 1024;
        Flight *q = malloc((size_t)nc * sizeof(Flight));
        if (!q) { c->fail |= FAIL_ALLOC; break; }
        for (int64_t i = 0; i < c->fl_n; i++) q[i] = c->fl_q[(c->fl_head + i) % c->fl_cap];
        free(c->fl_q);
        c->fl_q = q; c->fl_cap = nc; c->fl_head = 0;
      }
      Flight *f = &c->fl_q[(c->fl_head + c->fl_n) % c->fl_cap];
      f->t_send = t; f->t_arr = t + c->d_min; f->tsk = r->u3; f->sender = r->u1; f->amt[0] = r->x[0]; f->amt[1] = r->x[1];
      c->fl_n++;
      w[0] = 6; w[1] = dbits(t); w[2] = r->u1; w[3] = r->u2; w[4] = dbits(r->x[0]); w[5] = dbits(r->x[1]);
      fold(c, H_CHEM, w, 6); fold(c, H_ALL, w, 6);
      break;
    }
    case R_LOST:
      c->m_lost = c->m_lost + r->x[0] + r->x[1];
      w[0] = 7; w[1] = dbits(t); w[2] = r->u1; w[3] = r->u2; w[4] = dbits(r->x[0]); w[5] = dbits(r->x[1]);
      fold(c, H_CHEM, w, 6); fold(c, H_ALL, w, 6);
      break;
    case R_CLAIM:
      c->inflight += 1;
      if (cnt) { c->claims++; c->cost = c->cost + c->c_div; }
      w[0] = 4; w[1] = dbits(t); w[2] = r->u1; w[3] = r->u2; w[4] = r->u3;
      fold(c, H_FATE, w, 5); fold(c, H_ALL, w, 5);
      break;
    case R_RESOLVE:
      c->inflight -= 1;
      if (r->i1 == 2) c->status |= ST_WALL;
      if (cnt) { c->rejects += r->i1 == 1; c->rejwall += r->i1 == 2; }
      if (r->i1 != 0) fate_log(c, 3, r, r->u1, r->u2, r->i1 - 1, 0.0);
      w[0] = 5; w[1] = dbits(t); w[2] = r->u1; w[3] = (uint64_t)r->i1;
      fold(c, H_FATE, w, 4); fold(c, H_ALL, w, 4);
      break;
    case R_DEATH:
      world_adv(c, t);
      c->A = c->A - r->x[0];
      if (c->A < 0) c->A = 0.0;
      c->n -= 1;
      if (c->n == 0) c->A = 0.0;
      if (cnt) {
        if (r->i1 == 3) c->kills++;
        else c->deaths++;
      }
      c->m_lost = c->m_lost + r->x[1];
      fate_log(c, 2, r, r->u1, r->u2, r->i1, r->x[2]);
      w[0] = 3; w[1] = dbits(t); w[2] = r->u1; w[3] = (uint64_t)r->i1;
      fold(c, H_FATE, w, 4); fold(c, H_ALL, w, 4);
      break;
    default: break;
  }
}

static int rec_cmp_ctx(const Ctx *c, int64_t a, int64_t b) {
  const Rec *x = &c->rec[a], *y = &c->rec[b];
  if (x->t != y->t) return x->t < y->t ? -1 : 1;
  if (x->sk != y->sk) return x->sk < y->sk ? -1 : 1;
  return (x->seq > y->seq) - (x->seq < y->seq);
}

static void idx_sort(const Ctx *c, int64_t *a, int64_t n, int64_t *tmp) {  // stable merge sort (no global state)
  if (n < 16) {
    for (int64_t i = 1; i < n; i++) {
      int64_t v = a[i], j = i - 1;
      while (j >= 0 && rec_cmp_ctx(c, v, a[j]) < 0) { a[j + 1] = a[j]; j--; }
      a[j + 1] = v;
    }
    return;
  }
  int64_t h = n / 2;
  idx_sort(c, a, h, tmp);
  idx_sort(c, a + h, n - h, tmp);
  int64_t i = 0, j = h, k = 0;
  while (i < h && j < n) tmp[k++] = rec_cmp_ctx(c, a[j], a[i]) < 0 ? a[j++] : a[i++];
  while (i < h) tmp[k++] = a[i++];
  while (j < n) tmp[k++] = a[j++];
  memcpy(a, tmp, (size_t)n * sizeof(int64_t));
}

static void group_end(Ctx *c, double t) {
  if (c->n > c->n_peak) c->n_peak = c->n;
  if (!c->extinct && c->n == 0 && c->inflight == 0) { c->extinct = 1; c->t_ext = t; c->status |= ST_EXTINCT; }
}

static void flush(Ctx *c) {  // consume pending records in canonical order, time group by time group
  if (c->n_rec == 0) return;
  if (grow((void **)&c->ridx, &c->cap_ridx, 2 * c->n_rec, sizeof(int64_t), 1024)) { c->fail |= FAIL_ALLOC; return; }
  int64_t *idx = c->ridx, *tmp = c->ridx + c->n_rec;
  for (int64_t i = 0; i < c->n_rec; i++) idx[i] = i;
  idx_sort(c, idx, c->n_rec, tmp);
  double tg = c->rec[idx[0]].t;
  for (int64_t i = 0; i < c->n_rec; i++) {
    const Rec *r = &c->rec[idx[i]];
    if (r->t != tg) { group_end(c, tg); tg = r->t; }
    acc_record(c, r);
  }
  group_end(c, tg);
  c->n_rec = 0;
  c->n_gsnap = 0;
}

static int guard_check(Ctx *c, double cg) {  // section 10
  int trip = 0;
  if ((double)c->n >= c->n_max) { c->status |= ST_GUARD_CELLS; trip = 1; }
  if ((double)c->events > c->e_max) { c->status |= ST_GUARD_EVENTS; trip = 1; }
  if (trip) { c->guard = 1; c->t_end = cg; }
  return trip;
}

static int flight_cmp(const void *a, const void *b) {
  const Flight *x = a, *y = b;
  if (x->t_arr != y->t_arr) return x->t_arr < y->t_arr ? -1 : 1;
  if (x->tsk != y->tsk) return x->tsk < y->tsk ? -1 : 1;
  return (x->sender > y->sender) - (x->sender < y->sender);
}
static int site_sk_cmp(const void *a, const void *b) {
  uint64_t x = ((const uint64_t *)a)[0], y = ((const uint64_t *)b)[0];
  return (x > y) - (x < y);
}

static void close_life(Ctx *c, double *L) {  // 9.5
  const double te = c->t_end;
  world_adv(c, te);
  int64_t nl = 0;
  uint64_t *live = malloc((size_t)(c->n_sites > 0 ? c->n_sites : 1) * 2 * sizeof(uint64_t));
  if (!live) { c->fail |= FAIL_ALLOC; }
  else {
    for (int64_t s = 0; s < c->n_sites; s++)
      if (c->sites[s].cell >= 0) { live[2 * nl] = c->sites[s].sk; live[2 * nl + 1] = (uint64_t)s; nl++; }
    if (nl > 1) qsort(live, (size_t)nl, 2 * sizeof(uint64_t), site_sk_cmp);
    for (int64_t i = 0; i < nl; i++) {
      Cell *X = &c->cells[c->sites[live[2 * i + 1]].cell];
      tick_charge(c, te, X->t_prev, X->th[K_SEC0] + X->th[K_SEC1]);
      double content = X->m[0] + X->m[1];
      inbox_sort(X);
      for (int32_t j = 0; j < X->n_inbox && X->inbox[j].t_arr < te; j++)
        content = content + X->inbox[j].amt[0] + X->inbox[j].amt[1];
      c->m_content = c->m_content + content;
    }
    free(live);
  }
  int64_t nf = 0;
  Flight *fq = malloc((size_t)(c->fl_n > 0 ? c->fl_n : 1) * sizeof(Flight));
  if (!fq) { c->fail |= FAIL_ALLOC; }
  else {
    for (int64_t i = 0; i < c->fl_n; i++) {
      const Flight *f = &c->fl_q[(c->fl_head + i) % c->fl_cap];
      if (f->t_send < te && te <= f->t_arr) fq[nf++] = *f;
    }
    if (nf > 1) qsort(fq, (size_t)nf, sizeof(Flight), flight_cmp);
    double s = 0.0;
    for (int64_t i = 0; i < nf; i++) { s = s + fq[i].amt[0]; s = s + fq[i].amt[1]; }
    c->m_inflight = s;
    free(fq);
  }
  const double guard = c->guard ? c->c_live * c->n_max * (c->t1 - te) : 0.0;
  double col = c->c_live * c->live_time;
  col = col + c->c_spike * (double)c->spikes;
  col = col + c->c_tw * c->kappa_sum;
  col = col + c->c_msg * (double)c->contact;
  col = col + c->c_div * (double)c->claims;
  col = col + c->c_sec * c->sec_int;
  const double net = c->income - col - guard;
  const double ac = fabs(col);
  if (fabs(c->cost - col) > 1e-9 * (ac < 1.0 ? 1.0 : ac)) c->status |= ST_MISMATCH;
  if (c->raster_cap > 0 && c->raster_n > c->raster_cap) c->status |= ST_RASTER_OVF;
  if (c->fate_cap > 0 && c->fate_n > c->fate_cap) c->status |= ST_FATE_OVF;
  if (c->fail) c->status |= ST_CAPACITY;
  L[L_INCOME] = c->income; L[L_LIVE] = c->live_time; L[L_SECINT] = c->sec_int; L[L_SPIKES] = (double)c->spikes;
  L[L_KAPPA] = c->kappa_sum; L[L_CONTACT] = (double)c->contact; L[L_CLAIMS] = (double)c->claims;
  L[L_BIRTHS] = (double)c->births; L[L_REJECTS] = (double)c->rejects; L[L_REJWALL] = (double)c->rejwall;
  L[L_DEATHS] = (double)c->deaths; L[L_KILLS] = (double)c->kills; L[L_COST] = c->cost; L[L_GUARD] = guard;
  L[L_NET] = net; L[L_F] = net / (c->T - c->w[W_TOPEN]); L[L_NEND] = (double)c->n; L[L_NPEAK] = (double)c->n_peak;
  L[L_TEND] = te; L[L_STATUS] = (double)c->status; L[L_EVENTS] = (double)c->events; L[L_BEATS] = (double)c->beats;
  L[L_PINT] = c->P_int; L[L_ARRIVALS] = (double)c->c_arrivals; L[L_ARRDROP] = (double)c->c_arrdrop;
  L[L_PACKETS] = (double)c->packets; L[L_MSEC] = c->m_sec; L[L_MDEC] = c->m_dec; L[L_MLOST] = c->m_lost;
  L[L_MCONTENT] = c->m_content; L[L_MINFLIGHT] = c->m_inflight; L[L_CLAMPS] = (double)c->clamps;
  L[L_LASTBIRTH] = c->last_birth; L[L_TICKS] = (double)c->c_ticks; L[L_TEXT] = c->t_ext;
  for (int i = 0; i < LEDGER_SIZE; i++) { uint64_t wv = dbits(L[i]); fold(c, H_ALL, &wv, 1); }
}

// ------------------------------------------------------------------------------------------- schedulers
static void start_life(Ctx *c, const int32_t *init, int32_t n_init) {  // all initial cells are born at t0 (7.6)
  int32_t zero[3] = {0, 0, -1};
  if (n_init <= 0) { init = zero; n_init = 1; }
  for (int32_t j = 0; j < n_init && !c->fail; j++) {
    int32_t si = site_get(c, init[3 * j], init[3 * j + 1]);
    if (si < 0) return;
    c->cur_site = si; c->cur_t = c->t0; c->seq = 0;
    c->fl = c->flags | (c->t0 >= c->t_fork_abs ? c->fork_flags : 0);
    const uint64_t uid = hash1(c->seed, S_ZYG, (uint64_t)j) | 1ULL;
    birth(c, si, c->t0, uid, 0, 0, c->prog ? NULL : c->gt + GO_G0, 0.0, j, c->prog ? init[3 * j + 2] : -1);
  }
  flush(c);
}

static void run_heap(Ctx *c) {  // 11.1
  double next_guard = c->t0 + 1.0;
  int stop = 0;
  while (!stop && !c->fail && c->heap.n > 0) {
    const double t = c->heap.a[0].t;
    if (t >= c->t1) break;
    while (next_guard < c->t1 && next_guard <= t) {
      if (guard_check(c, next_guard)) { stop = 1; break; }
      next_guard += 1.0;
    }
    if (stop) break;
    if (t != c->cap_t) { c->cap_t = t; c->cap_count = c->n_alive_sim + c->n_inflight_sim; }  // 11.3: left limit
    HEnt h0 = hpop(&c->heap);
    int64_t nb = 0;
    if (grow((void **)&c->bbuf, &c->cap_bbuf, 1, sizeof(int32_t), 64)) { c->fail |= FAIL_ALLOC; break; }
    c->bbuf[nb++] = h0.ev;
    while (c->heap.n > 0 && c->heap.a[0].t == t && c->heap.a[0].sk == h0.sk) {
      if (grow((void **)&c->bbuf, &c->cap_bbuf, nb + 1, sizeof(int32_t), 64)) { c->fail |= FAIL_ALLOC; break; }
      c->bbuf[nb++] = hpop(&c->heap).ev;
    }
    batch(c, c->ev[h0.ev].site, t, c->bbuf, nb);
    if (c->heap.n == 0 || c->heap.a[0].t > t) flush(c);
  }
  flush(c);
  if (!stop && !c->fail)
    for (; next_guard < c->t1; next_guard += 1.0)
      if (guard_check(c, next_guard)) break;
}

static int went_cmp(const void *a, const void *b) {
  const WEnt *x = a, *y = b;
  if (x->key != y->key) return x->key < y->key ? -1 : 1;
  if (x->sk != y->sk) return x->sk < y->sk ? -1 : 1;
  if (x->t != y->t) return x->t < y->t ? -1 : 1;
  return (x->ev > y->ev) - (x->ev < y->ev);
}

static void run_window(Ctx *c) {  // 11.2
  const double h = c->window_h;
  const int64_t per_unit = (int64_t)llround(1.0 / h), nwin = (int64_t)llround(c->T) * per_unit;
  for (int64_t k = 0; k < nwin && !c->fail; k++) {
    const double wend = c->t0 + (double)(k + 1) * h;
    int64_t nw = 0;
    while (c->heap.n > 0 && c->heap.a[0].t < wend) {
      if (grow((void **)&c->wbuf, &c->cap_wbuf, nw + 1, sizeof(WEnt), 1024)) { c->fail |= FAIL_ALLOC; return; }
      HEnt e = hpop(&c->heap);
      WEnt *we = &c->wbuf[nw++];
      we->key = hash2(c->order_seed, S_ORDER, (uint64_t)k, e.sk); we->sk = e.sk; we->t = e.t; we->ev = e.ev;
    }
    if (nw > 1) qsort(c->wbuf, (size_t)nw, sizeof(WEnt), went_cmp);
    c->in_window = 1; c->wend = wend;
    for (int64_t i = 0; i < nw && !c->fail;) {
      int64_t j = i;
      c->local.n = 0;
      const int32_t si = c->ev[c->wbuf[i].ev].site;
      for (; j < nw && c->wbuf[j].sk == c->wbuf[i].sk; j++) {
        HEnt he = {c->wbuf[j].t, c->sites[si].tie, c->wbuf[j].sk, c->wbuf[j].ev, 0};
        if (hpush(&c->local, he)) { c->fail |= FAIL_ALLOC; break; }
      }
      c->cur_site = si;
      while (c->local.n > 0 && !c->fail) {
        const double t = c->local.a[0].t;
        int64_t nb = 0;
        while (c->local.n > 0 && c->local.a[0].t == t) {
          if (grow((void **)&c->bbuf, &c->cap_bbuf, nb + 1, sizeof(int32_t), 64)) { c->fail |= FAIL_ALLOC; break; }
          c->bbuf[nb++] = hpop(&c->local).ev;
        }
        batch(c, si, t, c->bbuf, nb);
        c->cur_site = si;
      }
      i = j;
    }
    c->in_window = 0;
    flush(c);
    if ((k + 1) % per_unit == 0 && wend < c->t1 && guard_check(c, wend)) return;
  }
}

// ---------------------------------------------------------------------------------------------- validation
static int is_int(double x) { return isfinite(x) && x == floor(x); }

static int world_ok(const double *w) {  // the rules of spec.validate_world (4.7)
  for (int i = 0; i < WORLD_SIZE; i++) if (!isfinite(w[i])) return 0;
  if (w[W_KILLRATE] != 0.0 || w[W_WOUNDRATE] != 0.0 || w[W_DRIFTTAU] != 0.0) return 0;
  if (!(w[W_T] > 0.0) || !is_int(w[W_T]) || !is_int(w[W_T0])) return 0;
  if (w[W_T] > TIME_MAX || fabs(w[W_T0]) > TIME_MAX) return 0;
  const int ints[6] = {W_NMAX, W_EMAX, W_FABRICR, W_ORACLE, W_STUCKA, W_STUCKB};
  for (int i = 0; i < 6; i++) if (!is_int(w[ints[i]])) return 0;
  if (!(w[W_TOPEN] >= 0.0 && w[W_TOPEN] < w[W_T])) return 0;
  for (int i = W_FLAGS; i <= W_FORKFLAGS; i++) {
    if (!is_int(w[i]) || w[i] < 0.0 || w[i] > (double)F_ALL) return 0;
    int64_t f = (int64_t)w[i];
    if ((f & ~(int64_t)F_ALL) || (f & F_INTEGER_TWIN)) return 0;
  }
  if ((int64_t)w[W_FORKFLAGS] & F_BASE_ONLY) return 0;
  const double h = w[W_WINDOWH];
  if (h != 0.0) {
    int e;
    double m = frexp(h, &e);
    if (!(h > 0.0) || m != 0.5 || e > 0 || h > w[W_DMIN]) return 0;  // h = 2^(e-1) = 2^-k with k >= 1
    if (w[W_ORACLE] > 0.0) return 0;
  }
  // physical ranges: positive time constants, fractions in [0, 1), and a smallest step that time can resolve
  if (!(w[W_DMIN] >= STEP_MIN && w[W_D0] > 0.0)) return 0;
  const int fracs[3] = {W_JIT, W_TAUMIS, W_TICKJIT};
  for (int i = 0; i < 3; i++) if (!(w[fracs[i]] >= 0.0 && w[fracs[i]] < 1.0)) return 0;
  if (!(w[W_DELAYSD] >= 0.0 && w[W_DELAYSD] <= SD_MAX && w[W_CLOCKSD] >= 0.0 && w[W_CLOCKSD] <= SD_MAX)) return 0;
  if (!(w[W_P0] > 0.0) || w[W_P0] * exp(-6.0 * w[W_CLOCKSD]) * (1.0 - w[W_TICKJIT]) < STEP_MIN) return 0;
  if (!(w[W_TAUZ] > 0.0 && w[W_TAUR] > 0.0 && w[W_TAUE] > 0.0)) return 0;
  if (!(w[W_THLO] >= 0.0 && w[W_THLO] < w[W_TH] && w[W_TH] < 1.0)) return 0;
  for (int i = W_HINC; i <= W_CSEC; i++) if (!(w[i] >= 0.0)) return 0;
  if (!(w[W_NMAX] >= 1.0 && w[W_NMAX] <= NMAX_MAX && w[W_EMAX] >= 0.0)) return 0;
  if (!(w[W_FABRICR] >= 0.0 && w[W_FABRICR] <= INT_FIELD_MAX && w[W_ORACLE] >= 0.0 && w[W_ORACLE] <= INT_FIELD_MAX))
    return 0;
  if (!(w[W_DROPP] >= 0.0 && w[W_DROPP] <= 1.0 && w[W_KILLFRAC] >= 0.0 && w[W_KILLFRAC] <= 1.0)) return 0;
  if (!(w[W_NOISE] >= 0.0 && w[W_NOISE] <= NOISE_MAX)) return 0;
  if (fabs(w[W_STUCKA]) > INT_FIELD_MAX || fabs(w[W_STUCKB]) > INT_FIELD_MAX) return 0;
  return 1;
}

static int lattice_ok(const int32_t *lat) {
  const int code = lat[0], D = lat[1];
  if (!((code == 0 && D == 6) || (code == 1 && D == 4) || (code == 2 && D == 8))) return 0;
  const int32_t *oa = lat + 2, *ob = oa + D, *bk = ob + D, *pv = bk + D, *nx = pv + D;
  for (int d = 0; d < D; d++) {
    if (bk[d] < 0 || bk[d] >= D || pv[d] < 0 || pv[d] >= D || nx[d] < 0 || nx[d] >= D) return 0;
    if (oa[bk[d]] != -oa[d] || ob[bk[d]] != -ob[d] || (oa[d] == 0 && ob[d] == 0)) return 0;
  }
  return 1;
}

// --------------------------------------------------------------------------------------------- one life
static void ctx_free(Ctx *c) {
  for (int64_t i = 0; i < c->cap_cell_pool; i++) free(c->cells[i].inbox);
  free(c->cells); free(c->sites); free(c->map); free(c->ev); free(c->blobs); free(c->blob_next);
  free(c->heap.a); free(c->local.a); free(c->wbuf); free(c->bbuf); free(c->rec); free(c->gsnap); free(c->ridx);
  free(c->fl_q);
  for (int g = 0; g < 6; g++) free(c->grp[g]);
}

static int run_one(const int32_t *lat, const double *unit, const double *gt, const double *pg, const double *w,
                   const uint64_t *seeds, const int32_t *init, int32_t n_init, double *L, uint64_t *H,
                   int64_t raster_cap, double *raster_t, uint64_t *raster_uid, int64_t *raster_n, int64_t fate_cap,
                   int64_t *fate_i, double *fate_f, int64_t *fate_n) {
  Ctx *c = calloc(1, sizeof(Ctx));
  if (!c) return -3;
  c->w = w; c->gt = gt; c->pg = pg; c->unit = unit;
  c->code = lat[0]; c->D = lat[1];
  for (int d = 0; d < c->D; d++) {
    c->off_a[d] = lat[2 + d]; c->off_b[d] = lat[2 + c->D + d]; c->back[d] = lat[2 + 2 * c->D + d];
    c->prv[d] = lat[2 + 3 * c->D + d]; c->nxt[d] = lat[2 + 4 * c->D + d];
  }
  c->seed = seeds[0]; c->tie_seed = seeds[1]; c->order_seed = seeds[2]; c->salt = seeds[3];
  c->flags = (int64_t)w[W_FLAGS]; c->fork_flags = (int64_t)w[W_FORKFLAGS];
  c->prog = (c->flags & F_PROGRAM) != 0;
  c->T = w[W_T]; c->t0 = w[W_T0]; c->t1 = c->t0 + c->T; c->t_open_abs = c->t0 + w[W_TOPEN];
  c->t_fork_abs = c->t0 + w[W_TFORK];
  c->d_min = w[W_DMIN]; c->d0 = w[W_D0]; c->delay_sd = w[W_DELAYSD]; c->jit = w[W_JIT]; c->tau_mis = w[W_TAUMIS];
  c->P0 = w[W_P0]; c->clock_sd = w[W_CLOCKSD]; c->tick_jit = w[W_TICKJIT]; c->tau_z = w[W_TAUZ]; c->th = w[W_TH];
  c->th_lo = w[W_THLO]; c->tau_R = w[W_TAUR]; c->tau_e = w[W_TAUE]; c->h_inc = w[W_HINC];
  c->c_live = w[W_CLIVE]; c->c_spike = w[W_CSPIKE]; c->c_tw = w[W_CTW]; c->c_msg = w[W_CMSG]; c->c_div = w[W_CDIV];
  c->c_sec = w[W_CSEC]; c->n_max = w[W_NMAX]; c->e_max = w[W_EMAX]; c->fabric_R = (int32_t)w[W_FABRICR];
  c->oracle_cap = w[W_ORACLE]; c->window_h = w[W_WINDOWH]; c->window = c->window_h > 0.0;
  c->drop_p = w[W_DROPP]; c->noise_rate = w[W_NOISE]; c->kill_t = w[W_KILLT]; c->kill_frac = w[W_KILLFRAC];
  c->stuck_t = w[W_STUCKT]; c->stuck_a = (int32_t)w[W_STUCKA]; c->stuck_b = (int32_t)w[W_STUCKB];
  c->cap_cells = 4 * (int64_t)(c->n_max > 0 ? c->n_max : 0) + 4 * MAX_INIT + 64;
  c->cell_free = -1; c->ev_free = -1; c->blob_free = -1;
  c->R = 1.0; c->tw = c->t0; c->last_birth = c->t0; c->t_ext = -1.0; c->t_end = c->t1; c->cap_t = -INFINITY;
  for (int i = 0; i < HASH_SIZE; i++) c->H[i] = HASH_INIT;
  c->raster_cap = (raster_t && raster_uid) ? raster_cap : 0; c->raster_t = raster_t; c->raster_uid = raster_uid;
  c->fate_cap = (fate_i && fate_f) ? fate_cap : 0; c->fate_i = fate_i; c->fate_f = fate_f;
  c->want_g = c->fate_cap > 0 && !c->prog;
  if (map_rehash(c, 1024)) { ctx_free(c); free(c); return -3; }
  start_life(c, init, n_init);
  if (!c->fail) {
    if (c->window) run_window(c);
    else run_heap(c);
  }
  flush(c);
  close_life(c, L);
  for (int i = 0; i < HASH_SIZE; i++) H[i] = c->H[i];
  if (raster_n) *raster_n = c->raster_n;
  if (fate_n) *fate_n = c->fate_n;
  int rc = (c->fail & FAIL_ALLOC) ? -3 : 0;
  ctx_free(c);
  free(c);
  return rc;
}

// ---------------------------------------------------------------------------------------------- exports
int32_t life_abi_version(void) { return ABI_VERSION; }

void life_sizes(int32_t out[10]) {
  const int32_t s[10] = {ABI_VERSION, GENOME_SIZE, PROGRAM_SIZE, WORLD_SIZE, LEDGER_SIZE, HASH_SIZE, NK, MAX_INIT,
                         FATE_I, FATE_F};
  memcpy(out, s, sizeof s);
}

uint64_t life_hash64(uint64_t seed, uint64_t stream, int32_t n, const uint64_t *keys) {
  uint64_t h = hash_start(seed, stream);
  for (int32_t i = 0; i < n; i++) h = splitmix64(h ^ keys[i]);
  return h;
}

double life_normal(uint64_t seed, uint64_t stream, int32_t n, const uint64_t *keys) {
  return normal_n(seed, stream, n, keys);
}

void life_decode(const double y[21], double theta[21]) { decode(y, theta); }

void life_readout(const double gt[809], const double g[16], double y[21]) { readout(gt, g, y); }

static int row_finite(const double *row, int n) {
  for (int i = 0; i < n; i++) if (!isfinite(row[i])) return 0;
  return 1;
}

int32_t life_run(int32_t n_lives, int32_t threads, const int32_t *lat, const double *unit, int32_t n_genomes,
                 const double *genomes, int32_t n_programs, const double *programs, const int32_t *genome_of,
                 const int32_t *init_cells, const int32_t *n_init, const double *world, const uint64_t *seeds,
                 double *ledger, uint64_t *hashes, int64_t raster_cap, double *raster_t, uint64_t *raster_uid,
                 int64_t *raster_n, int64_t fate_cap, int64_t *fate_i, double *fate_f, int64_t *fate_n) {
  if (n_lives < 0 || !lat || !unit || !genome_of || !world || !seeds || !ledger || !hashes) return -1;
  if (!lattice_ok(lat)) return -4;
  for (int32_t i = 0; i < n_lives; i++) {
    const double *w = world + (int64_t)i * WORLD_SIZE;
    if (!world_ok(w)) return -2;
    const int prog = ((int64_t)w[W_FLAGS] & F_PROGRAM) != 0;
    const int32_t gi = genome_of[i], rows = prog ? n_programs : n_genomes;  // each table has its own row count
    const double *table = prog ? programs : genomes;
    if (!table || gi < 0 || gi >= rows) return -1;
    const int size = prog ? PROGRAM_SIZE : GENOME_SIZE;
    if (!row_finite(table + (int64_t)gi * size, size)) return -1;  // 4.4: a packed row holds no NaN or infinity
    const int32_t ni = n_init ? n_init[i] : 0;
    if (ni < 0 || ni > MAX_INIT) return -4;
    if (ni > 0 && !init_cells) return -1;
    const int32_t *ic = init_cells ? init_cells + (int64_t)i * MAX_INIT * 3 : NULL;
    const int32_t R = (int32_t)w[W_FABRICR];
    for (int32_t j = 0; j < ni; j++) {
      if (prog && (ic[3 * j + 2] < -1 || ic[3 * j + 2] >= N_ROWS)) return -4;
      if (R > 0 && !in_disk(lat[0], ic[3 * j], ic[3 * j + 1], R)) return -4;
      for (int32_t q = 0; q < j; q++)
        if (ic[3 * q] == ic[3 * j] && ic[3 * q + 1] == ic[3 * j + 1]) return -4;
    }
  }
  if (threads < 1) threads = 1;
  if (raster_cap < 0) raster_cap = 0;
  if (fate_cap < 0) fate_cap = 0;
  int32_t rc = 0;
#pragma omp parallel for schedule(dynamic, 1) num_threads(threads)
  for (int32_t i = 0; i < n_lives; i++) {
    const double *w = world + (int64_t)i * WORLD_SIZE;
    const int prog = ((int64_t)w[W_FLAGS] & F_PROGRAM) != 0;
    const double *gt = prog ? NULL : genomes + (int64_t)genome_of[i] * GENOME_SIZE;
    const double *pg = prog ? programs + (int64_t)genome_of[i] * PROGRAM_SIZE : NULL;
    const int32_t ni = n_init ? n_init[i] : 0;
    const int32_t *ic = ni > 0 ? init_cells + (int64_t)i * MAX_INIT * 3 : NULL;
    const int rl = raster_cap > 0 && raster_t && raster_uid;
    const int fl = fate_cap > 0 && fate_i && fate_f;
    int r = run_one(lat, unit, gt, pg, w, seeds + (int64_t)i * 4, ic, ni, ledger + (int64_t)i * LEDGER_SIZE,
                    hashes + (int64_t)i * HASH_SIZE, rl ? raster_cap : 0, rl ? raster_t + (int64_t)i * raster_cap : NULL,
                    rl ? raster_uid + (int64_t)i * raster_cap : NULL, raster_n ? raster_n + i : NULL,
                    fl ? fate_cap : 0, fl ? fate_i + (int64_t)i * fate_cap * FATE_I : NULL,
                    fl ? fate_f + (int64_t)i * fate_cap * FATE_F : NULL, fate_n ? fate_n + i : NULL);
    if (r) {
#pragma omp critical
      rc = r;
    }
  }
  return rc;
}
