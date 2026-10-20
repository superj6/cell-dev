// One-life event kernel, ABI v8. The contract is docs/LIFE_ABI.md; section numbers below refer to it.
//
// One continuous, clockless life per genome (GRN mode) or phenotype program (program mode) on a sparse, unbounded
// lattice fabric (or a dense disk): 2D lattices, or prisms of stacked planes z = 0 .. L_max - 1 (4.3). Sites process
// their own events in time-ordered batches (6.2); every cross-site effect is a message delayed by at least d_min
// (6.3). Handlers emit records that one sequential accountant consumes in canonical (t, sitekey, seq) order (9.1), so
// floating-point sums are identical under every scheduler. The accountant also runs the world: the BELL-1 lumen
// (world kind 0, 9.2) or CATCH (world kind 1, 9.7: the dot, its blobs, strokes, clicks and receptor thinning; the
// RECEPTOR events it sends arrive d_min after their cause). The heap scheduler (production) and the window scheduler
// (tests) share every handler (11). Lives run in parallel with OpenMP and are independent of thread count and batch
// composition.
//
// Build: gcc -O3 -fopenmp -ffp-contract=off -fPIC -shared -std=c11 (no -ffast-math, no -march): see build.py.
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define ABI_VERSION 8
#define NG 16          // gene slots
#define S_MAX 10       // ABI 8: receptor modality slots (0 = the ABI-3 receptor; 1..9 world-bound, gene-gated)
#define NIN 34         // regulatory inputs: g[16], m/(1+m)[2], f/tau_tr, r/tau_tr[2], n_view/D, rho/tau_tr, is_S, is_M,
                       // then ABI 8's rho_m/tau_tr for m = 1..9
#define NK 32          // phenotype knobs: ABI 3's 23, then ABI 8's gains g_r1..g_r9
#define DMAX 10        // largest lattice degree (square8prism)
#define GENOME_SIZE (NG * NIN + 5 * NG + NK * NG + NK + 4)  // 1172
#define PROGRAM_SIZE (5 * NK + 14)                          // 174
#define N_MODK 5       // world keys per modality slot m >= 1: kind, arg, lam_bg, lam_s, K
#define N_SRC 8        // ABI 8 eco world: food/toxin sources
#define N_AG 8         // agents (predators, prey, pests)
#define N_WALL 8       // axis-aligned walls
#define N_DISK 4       // shelters, fertile disks
#define N_PLANT 16     // plant slots
#define N_ITEM 8       // carried items
#define N_SPEC 4       // odour species
#define SRC_K 13       // world keys per source
#define AG_K 20        // world keys per agent
#define ECO_HEAD 51    // eco keys before the per-entity blocks
#define ECO_SIZE (ECO_HEAD + N_SRC * SRC_K + N_AG * AG_K + N_WALL * 4 + 2 * N_DISK * 3)
#define WORLD_V7 83
#define WORLD_SIZE (WORLD_V7 + (S_MAX - 1) * N_MODK + ECO_SIZE)
#define LEDGER_V7 143
#define N_ECOL 33      // eco ledger columns
#define LEDGER_SIZE (LEDGER_V7 + 4 * (S_MAX - 1) + N_ECOL)
#define HASH_SIZE 5
#define MAX_INIT 1024
#define FATE_I 7
#define FATE_F 18
#define LMAX_MAX 8             // stack heights 1..8 (4.7)
#define COORD_MAX 4194304      // 2^22: |a|, |b| of an initial cell, so every reachable |a| < 2^24 (3, 4.6)
#define RATE_MAX 1024.0        // lambda_max bound
#define SPEED_MAX 1024.0       // g_n and v_t bound
#define LENGTH_MAX 1048576.0   // 2^20: sigma, b2_sigma and R_max bound
// world ranges (4.7): time stays resolvable at 2^-21 or finer, and no period or delay is shorter than STEP_MIN
#define TIME_MAX 1073741824.0  // 2^30: bound on T and |t0|
#define STEP_MIN 0.0009765625  // 2^-10: smallest d_min and smallest possible tick period
#define SD_MAX 1.0             // frozen log-normal spreads (delay_sd, clock_sd)
#define NOISE_MAX 1024.0       // membrane-noise kicks per cell per unit
#define NMAX_MAX 1048576.0     // 2^20 live cells
#define INT_FIELD_MAX 1073741824.0  // 2^30: fabric_R, oracle_cap, |stuck_a|, |stuck_b|

// knobs (section 8)
enum { K_W0, K_W1, K_B, K_TAUM, K_TREF, K_EMIT0, K_EMIT1, K_DELTA, K_KAPPA, K_PDIV, K_ASYM, K_PDIE, K_PHI, K_SEC0,
       K_SEC1, K_POL0, K_POL1, K_TAUTR, K_A0, K_A1, K_CHI, K_ZETA, K_GR };
#define K_GRM(m) (K_GR + (m))  // ABI 8: gain of modality m (m = 0 is g_r)
// packed genome offsets (4.4)
enum { GO_W = 0, GO_B = NG * NIN, GO_LAM = GO_B + NG, GO_G0 = GO_LAM + NG, GO_Q = GO_G0 + NG, GO_ACT = GO_Q + NG,
       GO_A = GO_ACT + NG, GO_A0 = GO_A + NK * NG, GO_DM = GO_A0 + NK, GO_KM = GO_DM + 2 };
// program table (4.5)
enum { PR_JUV = 5 * NK, PR_NVRIM, PR_ZYGROW, PR_FLANKGATE, PR_PDIVLO, PR_KGROW, PR_TIMERSTEP, PR_PRUNE, PR_KKEEP,
       PR_KDIE, PR_DM0, PR_DM1, PR_KM0, PR_KM1 };
enum { ROW_ALONE, ROW_CONTACT, ROW_JUVENILE, ROW_RIM, ROW_ZYGOTE, N_ROWS };
// world vector (4.7)
enum { W_T, W_T0, W_TOPEN, W_TFORK, W_FLAGS, W_FORKFLAGS, W_DMIN, W_D0, W_DELAYSD, W_JIT, W_TAUMIS, W_P0, W_CLOCKSD,
       W_TICKJIT, W_TAUZ, W_TH, W_THLO, W_TAUR, W_TAUE, W_HINC, W_CLIVE, W_CSPIKE, W_CTW, W_CMSG, W_CDIV, W_CSEC,
       W_NMAX, W_EMAX, W_FABRICR, W_ORACLE, W_WINDOWH, W_DROPP, W_NOISE, W_KILLT, W_KILLFRAC, W_STUCKT, W_STUCKA,
       W_STUCKB, W_KILLRATE, W_WOUNDRATE, W_DRIFTTAU,
       W_WORLDKIND, W_LMAX, W_STUCKZ, W_SIGMA, W_LAMS, W_LAMBG, W_GN, W_DRAGEXP, W_THCLICK, W_THREL, W_RHOC, W_VT,
       W_TAUTURN, W_RMIN, W_RMAX, W_TRESP, W_RCAP, W_CMISS, W_CREC, W_B2AMP, W_B2SIGMA, W_B2VALUE, W_B2RHO, W_B2P,
       W_B2MODE, W_VISMODE, W_VISON, W_VISOFF, W_VISLOW,
       W_TASKMODE, W_SAMPLEMIN, W_SAMPLEMAX, W_BLANKMIN, W_BLANKMAX, W_CHOICET, W_RESETT,
       W_PATCHCOUNT, W_PATCHCAP, W_PATCHFAST, W_PATCHSLOW, W_PATCHLAND, W_PATCHCONTACT,
       W_MOD = WORLD_V7, W_ECO = WORLD_V7 + (S_MAX - 1) * N_MODK };
// ABI 8 modality slot keys (relative to W_MOD + N_MODK * (m - 1)) and kinds
enum { MK_KIND, MK_ARG, MK_BG, MK_S, MK_K };
enum { MOD_NONE, MOD_ODOUR, MOD_FLOW, MOD_TOUCH, MOD_VIB, MOD_SUN, MOD_KINDS };
// ABI 8 eco block (relative to W_ECO): the head, then sources, agents, walls, shelters, fertile disks
enum { E_MODE, E_NSRC, E_NAG, E_NWALL, E_NSHELTER, E_NFERTILE,
       E_CURSPEED, E_CURHEAD, E_CURTURN, E_CURTURNMAX,
       E_PUFFSIG0, E_PUFFD, E_PUFFLIFE, E_PUFFCUT, E_PUFFCAP, E_LANDMARK,
       E_SUNHEAD, E_VIBVREF, E_RBODY, E_ARENA, E_KILLHITS, E_OCCLUDE,
       E_HOMEX, E_HOMEY, E_HOMER, E_HOMESIG, E_HOMEB, E_CARRYCAP = E_HOMEB + 4, E_CARRYMULT, E_CARRYDIGEST, E_CARRYDRAG,
       E_PLANTCAP, E_PLANTCOST, E_RIPENMIN, E_RIPENMAX, E_RIPEWIN, E_PLANTVALUE, E_PLANTSIG, E_PLANTLIGHT,
       E_PLANTB, E_SOILSIG = E_PLANTB + 4, E_SOILB, E_HEAD_END = E_SOILB + 4 };
enum { SK_X, SK_Y, SK_VALUE, SK_CAP, SK_PERIOD, SK_PHASE, SK_LIGHT, SK_SIGMA, SK_PUFF, SK_B };
enum { AK_TYPE, AK_X, AK_Y, AK_V1, AK_V2, AK_RSENSE, AK_P, AK_RCONTACT, AK_VALUE, AK_LOOK, AK_TSTATE, AK_TREST,
       AK_SIGMA, AK_LIGHT, AK_B, AK_RX = AK_B + 4, AK_RY };
#define E_SRC (ECO_HEAD)
#define E_AG (E_SRC + N_SRC * SRC_K)
#define E_WALL (E_AG + N_AG * AG_K)
#define E_SHELTER (E_WALL + N_WALL * 4)
#define E_FERTILE (E_SHELTER + N_DISK * 3)
enum { AG_NONE, AG_PURSUIT, AG_AMBUSH, AG_DARTER, AG_FREEZER, AG_BURROWER, AG_PEST, AG_TYPES };
enum { AS_WANDER, AS_ACTIVE, AS_REST, AS_HIDDEN };  // active: chase (predators), flee or freeze (prey), seek (pests)
// ledger columns (4.9)
enum { L_INCOME, L_LIVE, L_SECINT, L_SPIKES, L_KAPPA, L_CONTACT, L_CLAIMS, L_BIRTHS, L_REJECTS, L_REJWALL, L_DEATHS,
       L_KILLS, L_COST, L_GUARD, L_NET, L_F, L_NEND, L_NPEAK, L_TEND, L_STATUS, L_EVENTS, L_BEATS, L_PINT,
       L_ARRIVALS, L_ARRDROP, L_PACKETS, L_MSEC, L_MDEC, L_MLOST, L_MCONTENT, L_MINFLIGHT, L_CLAMPS, L_LASTBIRTH,
       L_TICKS, L_TEXT,
       L_CAPTURES, L_MISSES, L_CLICKS, L_B2CLICKS, L_RESPAWNS, L_NUDGES, L_RECCAND, L_RECACCEPT, L_RECEVENTS,
       L_RECGAIN, L_SAMPLES, L_DISTSUM, L_ZONE, L_PATH, L_XEND, L_YEND, L_NSEND, L_NMEND, L_NHEND, L_LIVES, L_LIVEM,
       L_LIVEH, L_LOWCAPTURES,
       L_CHOICEOPEN_N, L_CHOICEOPEN_B, L_CARRY_N, L_CARRY_B, L_CORRECT_N, L_CORRECT_B,
       L_WRONG_N, L_WRONG_B, L_TIMEOUT_N, L_TIMEOUT_B, L_UNFINISHED_N, L_UNFINISHED_B,
       L_PATCHOPEN = 70, L_PATCHSOURCE = 74, L_PATCHSUPPLY = 78, L_PATCHSPILL = 82, L_PATCHHARVEST = 86,
       L_PATCHEMPTY = 90, L_PATCHEND = 94, L_PATCHGEOM = 98, L_PATCHINITIAL = 99, L_PATCHREFILL = 103,
       L_CONTACTSTARTS = 107, L_CONTACTMATURITIES = 111, L_CONTACTSUPPLY = 115, L_CONTACTSPILL = 119,
       L_CONTACTHARVEST = 123, L_CONTACTPENDINGOPEN = 127, L_CONTACTPENDINGEND = 131,
       L_CONTACTSTOCKOPEN = 135, L_CONTACTSTOCKEND = 139,
       L_MODCAND = LEDGER_V7, L_MODACCEPT = L_MODCAND + 9, L_MODEVENTS = L_MODACCEPT + 9, L_MODGAIN = L_MODEVENTS + 9,
       L_ECO = L_MODGAIN + 9 };
// ABI 8 eco ledger columns (relative to L_ECO)
enum { EL_FOOD, EL_FOODINC, EL_TOXIN, EL_TOXINCOST, EL_PREY, EL_PREYINC, EL_PLANTED, EL_PLANTCOST, EL_RIPENED,
       EL_HARVESTED, EL_HARVESTINC, EL_SPOILED, EL_PESTEATEN, EL_PICKED, EL_DELIVERED, EL_DELIVERINC, EL_DIGESTED,
       EL_DIGESTINC, EL_HITS, EL_DAMAGECOST, EL_KILLED, EL_WALLCONTACTS, EL_PUFFS, EL_ALARMS, EL_DETECTIONS,
       EL_SHELTER, EL_THREAT, EL_STILL, EL_HOME, EL_LOADED, EL_UPFLOW, EL_CROSSFLOW, EL_NEARFOOD, EL_COUNT };
// flags (12)
enum { F_CONTACTS_OFF = 1 << 0, F_CHEM_OFF = 1 << 1, F_APOPTOSIS_OFF = 1 << 2, F_DIVISION_OFF = 1 << 3,
       F_FREEZE = 1 << 4, F_GENES_BLIND = 1 << 5, F_IDENTITY_CLAMP = 1 << 6, F_PHENO_FIXED = 1 << 7,
       F_LOCKSTEP = 1 << 8, F_PROGRAM = 1 << 9, F_INTEGER_TWIN = 1 << 10, F_LATERAL_OFF = 1 << 11,
       F_HIDDEN_OFF = 1 << 12, F_RECEPTOR_OFF = 1 << 13, F_MOTOR_OFF = 1 << 14 };
#define F_ALL ((1 << 15) - 1)
#define F_BASE_ONLY (F_LOCKSTEP | F_PROGRAM | F_INTEGER_TWIN)
// status bits (4.12)
enum { ST_EXTINCT = 1, ST_GUARD_CELLS = 2, ST_GUARD_EVENTS = 4, ST_RASTER_OVF = 8, ST_FATE_OVF = 16,
       ST_CHEM_CLAMP = 32, ST_MISMATCH = 64, ST_CAPACITY = 128, ST_WALL = 256, ST_KILLED = 512 };
// draw streams (3)
enum { S_ZYG = 1, S_UID, S_TAU, S_CLK, S_PHASE, S_DC, S_JIT, S_DROP, S_TICK, S_DIE, S_DIV, S_PLACE, S_NOISE, S_NSIGN,
       S_KILL, S_TIE, S_ORDER, S_RCAND, S_RACC, S_TURN, S_HEAD, S_RTIME, S_PANG, S_PDIST, S_PPRES, S_VISIBILITY,
       S_TASK_CLASS, S_TASK_DURATION, S_TASK_GEOMETRY, S_TASK_SIDE, S_PATCH_LAYOUT, S_PATCH_RATE, S_PATCH_PHASE,
       S_RCAND_M, S_RACC_M, S_ECO_PUFF, S_ECO_CUR, S_ECO_AG, S_ECO_PLANT };
// event groups and kinds (6.1)
enum { G_CLAIM, G_NOTICE, G_PACKET, G_MEMB, G_TICK, G_EXO };
enum { N_BORN, N_PRESENT, N_ACK, N_REJECT, N_DIED };
enum { M_ARRIVAL, M_THRESHOLD, M_NOISE, M_RCAND, M_RECEPT, M_RCANDM, M_RECEPTM };  // ABI 8: u2 = m << 56 | j
#define MJ_SHIFT 56
#define MJ_MASK ((1ULL << MJ_SHIFT) - 1ULL)
enum { X_KILL, X_STUCK };
// records (9.1)
enum { R_BIRTH, R_SPIKE, R_TICK, R_CHEM, R_PACKET, R_LOST, R_CLAIM, R_RESOLVE, R_DEATH, R_RCAND, R_RECEPT,
       R_RCANDM, R_RECEPTM };
// hash families (9.6)
enum { H_ALL, H_SPIKES, H_FATE, H_CHEM, H_WORLD };
// world kinds (4.7) and the CATCH world's world events (9.7.3) and click outcomes (9.7.4)
enum { WK_BELL, WK_CATCH };
enum { PL_START, PL_CLICK, PL_TIMER, PL_WITH };
enum { TASK_SAMPLE, TASK_BLANK, TASK_CHOICE, TASK_GAP };
enum { TC_OPEN, TC_CARRY, TC_CORRECT, TC_WRONG, TC_TIMEOUT, TC_UNFINISHED, TC_COUNT };
enum { PC_OPEN, PC_SOURCE, PC_SUPPLY, PC_SPILL, PC_HARVEST, PC_EMPTY, PC_END, PC_INITIAL, PC_REFILL, PC_COUNT };
enum { CC_STARTS, CC_MATURITIES, CC_SUPPLY, CC_SPILL, CC_HARVEST, CC_PENDING_OPEN, CC_PENDING_END,
       CC_STOCK_OPEN, CC_STOCK_END, CC_COUNT };
// internal failures (the life is invalid: capacity bit)
enum { FAIL_ALLOC = 1, FAIL_LIMIT = 2, FAIL_CAUSAL = 4 };

static const uint64_t HASH_INIT = 0x243F6A8885A308D3ULL;
static const double TWO_M53 = 1.0 / 9007199254740992.0;
static const double TAU_M_T[5] = {1.0, 2.0, 4.0, 8.0, 16.0};
static const double DELTA_T[4] = {0.0, 0.5, 1.0, 2.0};
static const double KAPPA_T[4] = {0.0, 0.25, 0.5, 1.0};
static const double PHI_T[4] = {0.0, 0.5, 1.0, 2.0};
static const double TAU_TR_T[4] = {2.0, 4.0, 8.0, 16.0};
static const double TWO_PI = 6.283185307179586;  // the double nearest 2 pi (2)
static const double S32 = 0.8660254037844386;    // the double nearest sqrt(3) / 2 (2)

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
// (uint32(a) << 32 | uint32(b)) XOR (z << 56): z = 0 is ABI 2's key; injective for |a| < 2^24 and 0 <= z < 16 (3)
static inline uint64_t sitekey(int32_t a, int32_t b, int32_t z) {
  return (((uint64_t)(uint32_t)a << 32) | (uint64_t)(uint32_t)b) ^ ((uint64_t)(uint32_t)z << 56);
}
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
  th[K_ZETA] = q8(y[21]); th[K_GR] = q8(y[22]);
  for (int m = 1; m < S_MAX; m++) th[K_GRM(m)] = q8(y[K_GRM(m)]);  // ABI 8 gains
}

#ifdef LIFE_FAST
static inline int nzbits(double x) { uint64_t u; memcpy(&u, &x, 8); return u != 0; }
#endif

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
  double t_birth, va, ta, tr, f, r[2], rho, ttr, z, tz, t_prev, taumis, Pn, tau, timer, timer_birth;
  uint64_t view[DMAX];
  double dc[DMAX], inc[DMAX][2], sd[DMAX], weff[DMAX][2];
  double g[NG], m[2], th[NK];
  double rhom[S_MAX];    // ABI 8: receptor traces of modalities 1..9 (index 0 unused: rho is modality 0's)
  int64_t nrecm[S_MAX];  // ABI 8: next candidate index of modality m
  int8_t pendm[S_MAX];   // ABI 8: a candidate of modality m is in flight
  Pkt *inbox;
} Cell;

typedef struct {
  uint64_t sk, tie;
  int64_t births;
  int32_t a, b, z, cell, exists;
  int32_t acc_occ;       // accountant (CATCH): in the act-plane occupancy O at the left limit of its time group (9.7.1)
  int32_t acc_live;      // accountant (CATCH): holds a live cell, as of the records consumed so far (9.7.2)
  int32_t acc_occ0;      // accountant (ABI 8): in the sense-plane occupancy O0 at the left limit (exposed faces)
  double fx, fy, tf;     // accountant (CATCH): the occupant's own pull, decaying from tf (9.7.2)
  int32_t nbr[DMAX];
} Site;

typedef struct {
  double t;
  uint64_t sk;
  int32_t seq, kind, site, pad;
  uint64_t u1, u2, u3;
  int64_t i1, g;         // integer payload; offset of a g[16] snapshot (-1 none)
  double x[4];
} Rec;

typedef struct {         // a CATCH blob (9.7.1); blob 0 is the target
  int exists, present;
  double t, x, y, vx, vy;            // anchor and velocity
  uint64_t h, q, k, m;               // next heading, placement, turn and timer indices
  double tau, r;                     // next turn and next timer re-placement (+inf = none)
} Blob;

typedef struct {
  double x, y, period, first, next;
  uint64_t arrival_index;
  int64_t stock, initial_remaining;
  // ABI 7: one pending physical job and observer-only FIFO provenance for post-initial packets.
  double contact_due;
  uint64_t contact_starts;
  int contact_pending;
  int64_t contact_stock, origin_head, origin_n;
  uint8_t *origins;
} Patch;

// ABI 8 eco world (9.8): sources, puffs, agents, walls, disks, plants and carried items; all world state, never cell input
typedef struct {
  double x, y, value, light, sigma, puff_rate, b[N_SPEC], period, first, next, next_puff;
  int64_t cap, stock;
  uint64_t arrival_index, puff_k;
} Src;
typedef struct { double t, ox, oy, a[N_SPEC]; } Puff;  // release time; centre = (ox, oy) + A(t); amounts per species
typedef struct {
  int type, state, vis, pad;
  double t, x, y, vx, vy, speed, t_stop, until, next_look;  // anchor (t, x, y), velocity until t_stop
  uint64_t q;                                              // look counter
  double v1, v2, r_sense, p, r_contact, value, look, t_state, t_rest, sigma, light, b[N_SPEC], rx, ry;
} Agent;
typedef struct { double x0, x1, y0, y1; } Wall;
typedef struct { double x, y, r; } Disk;
typedef struct { int state, vis; double x, y, t_ripe, t_spoil; uint64_t id; } Plant;  // 0 empty, 1 growing, 2 ripe
typedef struct { double value, due; uint64_t id; } Item;

typedef struct { double t_send, t_arr; uint64_t tsk, sender; double amt[2]; } Flight;
typedef struct { int32_t a, b; } Col;  // a column (a, b) of the projected footprint (9.7.2)
typedef struct { int64_t *lo, *hi; int64_t *par; int64_t cap; } FillBuf;  // free runs and their union-find parents
typedef struct { uint64_t key, sk; double t; int32_t ev, pad; } WEnt;  // window visit key, site, time, event

typedef struct {
  // configuration
  const double *w, *gt, *pg, *unit;
  int D, code, base, nplane, prog, window, kind, L_max;  // base: base lattice code; nplane: in-plane slots
  int32_t off_a[DMAX], off_b[DMAX], off_z[DMAX], back[DMAX], prv[DMAX], nxt[DMAX];
  uint32_t smask[LMAX_MAX];  // per height z: the slots that stay inside the stack (4.3)
  uint64_t seed, tie_seed, order_seed, salt;
  int64_t flags, fork_flags, fl;
  double T, t0, t1, t_open_abs, t_fork_abs, d_min, d0, delay_sd, jit, tau_mis, P0, clock_sd, tick_jit, tau_z, th,
      th_lo, tau_R, tau_e, h_inc, c_live, c_spike, c_tw, c_msg, c_div, c_sec, n_max, e_max, oracle_cap, window_h,
      drop_p, noise_rate, kill_t, kill_frac, stuck_t;
  int32_t fabric_R, stuck_a, stuck_b, stuck_z;
  // CATCH world keys (4.7) and lambda_max (9.7.1)
  double sigma, lam_s, lam_bg, g_n, drag_exp, th_click, th_rel, rho_c, v_t, tau_turn, R_min, R_max, t_resp, R_cap,
      c_miss, c_rec, b2_amp, b2_sigma, b2_value, b2_rho, b2_p, lam_max, c_b2;
  int b2_mode;
  // ABI 4 visibility belongs to the world; cells receive only the existing local receptor events.
  int visibility_mode, bright;
  double visibility_on, visibility_off, visibility_low, visibility_next;
  uint64_t visibility_k;
  int64_t low_light_captures;
  // ABI 5 delayed matching is world state, never a new cell input or shared cell update.
  int task_mode, task_phase, task_class, task_consumed, task_defer_gap;
  uint64_t task_trial;
  double sample_min, sample_max, blank_min, blank_max, choice_T, reset_T, task_next, task_choice_start;
  int64_t task_counts[TC_COUNT][2];
  // ABI 6: stationary food stocks and exogenous source schedules, never cell inputs.
  int patch_count, patch_capacity, patch_opened;
  double patch_fast, patch_slow, patch_landmark;
  Patch patch[4];
  int64_t patch_left[4], patch_initial_open[4], patch_counts[PC_COUNT][4], patch_geometric_misses;
  double patch_contact_delay;
  int64_t contact_counts[CC_COUNT][4];
  int64_t cap_cells;
  // ABI 8 modality slots m = 1..9 (lam_m[m] = 0: unbound) and their ledger counts
  int mod_kind[S_MAX], mod_arg[S_MAX];
  double mod_bg[S_MAX], mod_s[S_MAX], mod_K[S_MAX], lam_m[S_MAX];
  int64_t mod_cand[S_MAX], mod_accept[S_MAX], mod_events[S_MAX];
  double mod_gain[S_MAX];
  // ABI 8 eco world (9.8)
  int eco, n_src, n_ag, n_wall, n_shelter, n_fertile, kill_hits, occlude, plant_cap, carry_cap, eco_dead;
  Src src[N_SRC]; int64_t src_left[N_SRC];
  Agent ag[N_AG];
  Wall wall[N_WALL];
  Disk shelter[N_DISK], fertile[N_DISK];
  Plant plant[N_PLANT];
  Item item[N_ITEM]; int n_item;
  double cur_speed, cur_head, cur_turn, cur_turn_max, cur_ts, cur_Ax, cur_Ay, cur_ux, cur_uy, cur_next;
  uint64_t cur_k;
  Puff *puff; int64_t puff_cap, puff_head, puff_n;
  double puff_sig0, puff_D, puff_life, puff_cut, landmark, sun_x, sun_y, vib_vref, r_body, arena;
  double home_x, home_y, home_r, home_sig, home_b[N_SPEC], carry_mult, carry_digest, carry_drag, gam0;
  double plant_cost, ripen_min, ripen_max, ripe_win, plant_value, plant_sig, plant_light, plant_b[N_SPEC];
  double soil_sig, soil_b[N_SPEC];
  uint64_t plant_ids, item_ids;
  int blk_x, blk_y, blk_wx, blk_wy;  // a wall face blocks motion along +x (1) / -x (-1) (and y); the blocking walls
  double kink_t;
  int kink_kind, kink_wall, kink_face;
  int64_t hits_all;
  double samp_x, samp_y;             // the dot at the previous sample (flow-relative path)
  int64_t eco_n[EL_COUNT];           // integer eco ledger counts (EL_FOOD, ...)
  double eco_x[EL_COUNT];            // eco ledger sums (EL_FOODINC, ...)
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
#ifdef LIFE_FAST
  int n_ract; int8_t ract[NG]; int n_wj[NG]; int8_t wj[NG][NIN];  // nonzero readout columns, GRN inputs
#endif
  // simulator counts (site-level, order-free) and oracle-cap counts; cap_count is n_alive + n_inflight at cap_t-
  int64_t n_alive_sim, n_inflight_sim, events, c_arrivals, c_arrdrop, c_ticks, cap_count;
  double cap_t;
  // accountant (5.3, 9)
  double A, R, tw; int above;
  int64_t n, inflight, n_peak, n_plane[3];  // live cells per plane: S (z = 0), M (z = 1), H (z >= 2)
  double income, live_time, sec_int, kappa_sum, cost, P_int, m_sec, m_dec, m_lost, m_content, m_inflight;
  int64_t spikes, contact, claims, births, rejects, rejwall, deaths, kills, beats, packets, clamps;
  double last_birth, t_ext, t_end, live_plane[3];
  int extinct, guard;
  int64_t status;
  uint64_t H[HASH_SIZE];
  Flight *fl_q; int64_t fl_head, fl_n, fl_cap;
  // CATCH world (9.7): the dot, the blobs, the key, deferred writes of the current time group, and its ledger columns
  double t_x, X, Y, Fx, Fy, gam, path, next_sample;
  int64_t n_foot, n_fill;  // live sense-plane cells (traction); tiles of the filled footprint (drag, 9.7.2)
  Col *col; int64_t n_col, cap_col;  // occupied columns (a, b), the projected footprint, sorted by (b, a)
  FillBuf fill;                      // scratch of filled_count
  int armed;
  Blob blob[2];
  int32_t *dO; int64_t n_dO, cap_dO;  // deferred changes of O, as pairs: site index, 1 = add / 0 = remove
  int32_t dP[8]; int n_dP;            // deferred placements: blob, cause pairs
  int64_t captures, misses, clicks, b2_clicks, respawns, nudges, rec_cand, rec_accept, rec_events, samples, zone;
  double rec_gain, dist_sum;
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

// the site record of (a, b, z) if one was ever created, else -1 (never creates one: used by the accountant)
static int32_t site_find(const Ctx *c, int32_t a, int32_t b, int32_t z) {
  uint64_t sk = sitekey(a, b, z), m = (uint64_t)c->map_cap - 1, i = map_hash(c, sk) & m;
  while (c->map[i] >= 0) {
    if (c->sites[c->map[i]].sk == sk) return c->map[i];
    i = (i + 1) & m;
  }
  return -1;
}

static int32_t site_get(Ctx *c, int32_t a, int32_t b, int32_t z) {  // only ever called for in-stack sites (4.3)
  uint64_t sk = sitekey(a, b, z), m = (uint64_t)c->map_cap - 1, i = map_hash(c, sk) & m;
  while (c->map[i] >= 0) {
    if (c->sites[c->map[i]].sk == sk) return c->map[i];
    i = (i + 1) & m;
  }
  if (z < 0 || z >= c->L_max) { c->fail |= FAIL_CAUSAL; return -1; }  // an out-of-stack site does not exist
  if (c->n_sites >= INT32_MAX - 1) { c->fail |= FAIL_LIMIT; return -1; }
  if (grow((void **)&c->sites, &c->cap_sites, c->n_sites + 1, sizeof(Site), 256)) { c->fail |= FAIL_ALLOC; return -1; }
  int32_t si = (int32_t)c->n_sites++;
  Site *s = &c->sites[si];
  s->sk = sk; s->tie = hash1(c->tie_seed, S_TIE, sk); s->births = 0; s->a = a; s->b = b; s->z = z; s->cell = -1;
  s->exists = c->fabric_R == 0 || in_disk(c->base, a, b, c->fabric_R);
  s->acc_occ = 0; s->acc_live = 0; s->acc_occ0 = 0; s->fx = s->fy = 0.0; s->tf = 0.0;
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
  const Site *s = &c->sites[si];
  j = site_get(c, s->a + c->off_a[d], s->b + c->off_b[d], s->z + c->off_z[d]);
  if (j >= 0) c->sites[si].nbr[d] = j;
  return j;
}
static inline int in_stack(const Ctx *c, int32_t si, int d) { return (c->smask[c->sites[si].z] >> d) & 1u; }

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
  X->f = X->f * e; X->r[0] = X->r[0] * e; X->r[1] = X->r[1] * e; X->rho = X->rho * e;
  for (int m = 1; m < S_MAX; m++) X->rhom[m] = X->rhom[m] * e;
  X->ttr = t;
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

#ifdef LIFE_FAST
// Fast build (build.py fast=True): the readout skips gene columns whose weights are all exactly zero. A skipped term
// adds +-0, which changes a sum only when the whole sum is zero (the sign of zero), so such knobs are redone in full;
// the result is bitwise the full readout's.
static void readout_fast(const Ctx *c, const double *g, double *y) {
  const double *A = c->gt + GO_A, *a0 = c->gt + GO_A0;
  const int n = c->n_ract;
  int p = 0;
  for (; p + 4 <= NK; p += 4) {
    double v0 = a0[p], v1 = a0[p + 1], v2 = a0[p + 2], v3 = a0[p + 3];
    for (int i = 0; i < n; i++) {
      const int k = c->ract[i]; const double gk = g[k];
      v0 = v0 + A[p * NG + k] * gk; v1 = v1 + A[(p + 1) * NG + k] * gk;
      v2 = v2 + A[(p + 2) * NG + k] * gk; v3 = v3 + A[(p + 3) * NG + k] * gk;
    }
    y[p] = v0; y[p + 1] = v1; y[p + 2] = v2; y[p + 3] = v3;
  }
  for (; p < NK; p++) {
    double v = a0[p];
    for (int i = 0; i < n; i++) { const int k = c->ract[i]; v = v + A[p * NG + k] * g[k]; }
    y[p] = v;
  }
  if (n < NG)
    for (p = 0; p < NK; p++)
      if (y[p] == 0.0) {  // sign of zero: redo this knob in full
        double v = a0[p];
        for (int k = 0; k < NG; k++) v = v + A[p * NG + k] * g[k];
        y[p] = v;
      }
}
#endif

static void set_theta(const Ctx *c, Cell *X, int nv) {
  if (c->prog) {
    memcpy(X->th, c->pg + NK * prog_row(c, X, nv), NK * sizeof(double));
  } else {
    double y[NK];
#ifdef LIFE_FAST
    readout_fast(c, X->g, y);
#else
    readout(c->gt, X->g, y);
#endif
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
  const int lateral_off = (c->fl & F_LATERAL_OFF) != 0;
  if (n_ch > 0 && !(c->fl & F_CONTACTS_OFF) && !((c->fl & F_HIDDEN_OFF) && c->sites[si].z >= 2)) {
    uint8_t mask = (uint8_t)(e0 | (e1 << 1));
    double jit = (c->flags & F_LOCKSTEP) ? 0.0 : c->jit;
    for (int d = 0; d < c->D; d++) {
      if (X->view[d] == 0) continue;
      if (lateral_off && c->off_z[d] == 0) continue;  // ABI 3 fork: in-plane spikes undelivered (12)
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
  double dz = 0.0, zt = 0.0, zn = 0.0, kap = th[K_KAPPA];
  if (kap > 0.0) {
    zt = X->z * exp(-(t - X->tz) / c->tau_z); zn = zt + kap;
    if (zn > 1.0) zn = 1.0;
    dz = zn - zt; X->z = zn; X->tz = t;
  }
  Rec *r = emit(c, R_SPIKE);
  if (r) { r->u1 = X->uid; r->x[0] = kap; r->i1 = n_out; r->x[1] = dz; r->x[2] = zt; r->x[3] = zn; }
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
  for (int d = 0; d < c->D; d++)
    if (in_stack(c, si, d)) notice(c, si, d, t + c->d_min, N_DIED, 0, uid, 0);
}

// time of receptor candidate j of cell uid (7.10): t_prev - log(u_j) / lambda_max, moved to nextup(t_prev) if it does
// not advance (t_prev is the birth time for j = 0, else candidate j - 1)
static inline double receptor_next(uint64_t seed, uint64_t uid, uint64_t j, double t_prev, double lam) {
  const double t = t_prev - log(draw2(seed, S_RCAND, uid, j)) / lam;
  return t > t_prev ? t : nextafter(t_prev, INFINITY);
}
// ABI 8: candidate j of modality m >= 1 (streams S_RCAND_M / S_RACC_M keyed (uid, m, j))
static inline double receptor_next_m(uint64_t seed, uint64_t uid, int m, uint64_t j, double t_prev, double lam) {
  const double t = t_prev - log(draw3(seed, S_RCAND_M, uid, (uint64_t)m, j)) / lam;
  return t > t_prev ? t : nextafter(t_prev, INFINITY);
}
// ABI 8 (7.10): a sense cell's stream of modality m runs while the world binds m and the cell's own gain is nonzero; a
// candidate that finds the gain 0 is dropped and stops the stream, which the next tick with a nonzero gain restarts.
static void mod_activate(Ctx *c, int32_t si, Cell *X, double t) {
  if (c->sites[si].z != 0) return;
  for (int m = 1; m < S_MAX; m++)
    if (c->lam_m[m] > 0.0 && !X->pendm[m] && X->th[K_GRM(m)] != 0.0) {
      X->pendm[m] = 1;
      self_ev(c, si, receptor_next_m(c->seed, X->uid, m, (uint64_t)X->nrecm[m], t, c->lam_m[m]), G_MEMB, M_RCANDM,
              X->uid, ((uint64_t)m << MJ_SHIFT) | (uint64_t)X->nrecm[m]);
    }
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
  const Site *S0 = &c->sites[si];
  if (c->stuck_t >= 0.0 && t < c->t0 + c->stuck_t && S0->a == c->stuck_a && S0->b == c->stuck_b &&
      S0->z == c->stuck_z)
    self_ev(c, si, c->t0 + c->stuck_t, G_EXO, X_STUCK, uid, 0);
  if (c->kind == WK_CATCH && S0->z == 0 && c->lam_max > 0.0)  // the receptor's candidate stream (7.10)
    self_ev(c, si, receptor_next(c->seed, uid, 0, t, c->lam_max), G_MEMB, M_RCAND, uid, 0);
  if (c->kind == WK_CATCH) mod_activate(c, si, X, t);  // ABI 8 gene-gated modality streams
  for (int d = 0; d < c->D; d++)
    if (in_stack(c, si, d)) notice(c, si, d, t + c->d_min, N_BORN, 0, uid, (uint64_t)k);
  if (mother != 0) notice(c, si, bslot, t + c->d_min, N_ACK, mother, uid, (uint64_t)k);
}

static double contact_delay(const Ctx *c, int32_t si, const Cell *X, int d, uint64_t knb) {  // 7.7 DC
  if (c->flags & F_LOCKSTEP) return c->d0;
  const Site *s = &c->sites[si];
  uint64_t keys[3] = {s->sk, sitekey(s->a + c->off_a[d], s->b + c->off_b[d], s->z + c->off_z[d]),
                      ((uint64_t)X->k << 32) | knb};
  return c->d0 * exp(c->delay_sd * normal_n(c->seed, S_DC, 3, keys));
}

#ifdef LIFE_FAST
// Fast build: a packet goes straight into the accountant's flight queue instead of through an R_PACKET record (its
// only uses are the packets count, the in-flight content at close, which is sorted before it is summed, and the hashes,
// which the fast build does not keep).
static void flight_push(Ctx *c, double t, uint64_t tsk, uint64_t sender, const double *amt) {
  while (c->fl_n > 0 && c->fl_q[c->fl_head].t_arr < t) { c->fl_head = (c->fl_head + 1) % c->fl_cap; c->fl_n--; }
  if (c->fl_n == c->fl_cap) {
    int64_t nc = c->fl_cap ? 2 * c->fl_cap : 1024;
    Flight *q = malloc((size_t)nc * sizeof(Flight));
    if (!q) { c->fail |= FAIL_ALLOC; return; }
    for (int64_t i = 0; i < c->fl_n; i++) q[i] = c->fl_q[(c->fl_head + i) % c->fl_cap];
    free(c->fl_q);
    c->fl_q = q; c->fl_cap = nc; c->fl_head = 0;
  }
  Flight *f = &c->fl_q[(c->fl_head + c->fl_n) % c->fl_cap];
  f->t_send = t; f->t_arr = t + c->d_min; f->tsk = tsk; f->sender = sender; f->amt[0] = amt[0]; f->amt[1] = amt[1];
  c->fl_n++;
}
#endif

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
  // 3. view and inputs (flank[e] serves placement in step 8; fbest only the program-mode gate of 7.5). A slot is open
  // iff it is in the stack and empty (4.3): a slot that points out of the stack is never claimed or counted.
  traces_to(X, t);
  const uint32_t sm = c->smask[c->sites[si].z];
  int nv = 0, any_open = 0, fbest = 0, flank[DMAX];
  for (int d = 0; d < D; d++) nv += X->view[d] != 0;
  for (int e = 0; e < D; e++) {
    flank[e] = (X->view[c->prv[e]] != 0) + (X->view[c->nxt[e]] != 0);
    if (X->view[e] == 0 && ((sm >> e) & 1u)) {
      any_open = 1;
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
      x[21] = (double)nv / (double)D;  // flank_best is not a gene input (ABI 2, LIFE_ABI.md 15.32)
      x[22] = X->rho / ttr;            // receptor trace (0 forever outside CATCH)
      const int zc = c->sites[si].z;   // plane cues: 0 outside CATCH (15.38)
      x[23] = (c->kind == WK_CATCH && zc == 0) ? 1.0 : 0.0;
      x[24] = (c->kind == WK_CATCH && zc == 1) ? 1.0 : 0.0;
      for (int m = 1; m < S_MAX; m++) x[24 + m] = X->rhom[m] / ttr;  // ABI 8 receptor traces (0 when unused)
      if (fl & F_GENES_BLIND) {
        x[18] = x[19] = x[20] = x[21] = x[22] = 0.0;
        for (int m = 1; m < S_MAX; m++) x[24 + m] = 0.0;
      }
      const double *W = c->gt + GO_W, *bb = c->gt + GO_B, *lam = c->gt + GO_LAM;
      for (int k = 0; k < NG; k++) {
        if (lam[k] == 0.0) { s[k] = 0.0; continue; }  // g + 0 * (s - g) == g exactly: skip the row
        double p = bb[k];
#ifdef LIFE_FAST
        const int nj = c->n_wj[k]; const int8_t *jj = c->wj[k];  // nonzero weights only; a zero sum is redone in full
        for (int i = 0; i < nj; i++) p = p + W[k * NIN + jj[i]] * x[jj[i]];
        if (p == 0.0 && nj < NIN) { p = bb[k]; for (int j = 0; j < NIN; j++) p = p + W[k * NIN + j] * x[j]; }
#else
        for (int j = 0; j < NIN; j++) p = p + W[k * NIN + j] * x[j];
#endif
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
  if (c->kind == WK_CATCH) mod_activate(c, si, X, t);
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
#ifdef LIFE_FAST
      if (t >= c->t_open_abs) c->packets++;
      flight_push(c, t, c->sites[c->sites[si].nbr[d]].sk, X->uid, amt);
#else
      Rec *rp = emit(c, R_PACKET);
      if (rp) {
        rp->u1 = X->uid; rp->u2 = X->view[d]; rp->u3 = c->sites[c->sites[si].nbr[d]].sk;
        rp->x[0] = amt[0]; rp->x[1] = amt[1];
      }
#endif
    }
    for (int i = 0; i < 2; i++) X->m[i] = X->m[i] - nvd * amt[i];
  }
  Rec *rc = emit(c, R_CHEM);
  if (rc) { rc->x[0] = sec; rc->x[1] = dec; rc->i1 = clamp; }
  // 8. division
  if (!(fl & (F_DIVISION_OFF | F_FREEZE)) && X->claim_pending == 0 && any_open) {
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
      // the morphogen polarity vector in 3D (15.37); the chiral term turns it within the plane only
      const double *u = c->unit;
      double px = 0.0, py = 0.0, pz = 0.0;
      for (int d = 0; d < D; d++) {
        px = px + X->sd[d] * u[3 * d]; py = py + X->sd[d] * u[3 * d + 1]; pz = pz + X->sd[d] * u[3 * d + 2];
      }
      const double chi = X->th[K_CHI], vx = px - chi * py, vy = py + chi * px, vz = pz;
      int best = -1;
      double bs = 0.0;
      for (int e = 0; e < D; e++) {
        if (X->view[e] != 0 || !((sm >> e) & 1u)) continue;
        double sc;
        if (c->off_z[e] == 0)  // in-plane slot: ABI 2's score
          sc = u[3 * e] * vx + u[3 * e + 1] * vy + X->th[K_PHI] * (double)flank[e] +
               1e-3 * draw3(c->seed, S_PLACE, X->uid, (uint64_t)X->n_div, (uint64_t)e);
        else  // up or down: the vertical polarity plus the genetic bias zeta (rule N8)
          sc = u[3 * e + 2] * vz + X->th[K_ZETA] * u[3 * e + 2] +
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
  // 3. membrane step (7.2), preceded by the current receptor candidate (7.10): records R_RCAND, R_RECEPT, R_SPIKE
  if (c->ngrp[G_MEMB]) {
    int64_t n_arr = 0, n_del = 0, cnt0 = 0, cnt1 = 0, n_rec = 0;
    int thr = 0, n_kick = 0;
    double S = 0.0;
    if (X) {
      for (int64_t i = 0; i < c->ngrp[G_MEMB]; i++) {
        const Ev *e = &c->ev[c->grp[G_MEMB][i]];
        if (e->sub != M_RCAND || e->uid != X->uid) continue;
        const uint64_t j = e->u2;  // candidate j at c_j = t: the world thins it from its record (9.7.5)
        Rec *rr = emit(c, R_RCAND);
        if (rr) { rr->u1 = X->uid; rr->u2 = j; }
        self_ev(c, si, receptor_next(c->seed, X->uid, j + 1, t, c->lam_max), G_MEMB, M_RCAND, X->uid, j + 1);
      }
      for (int64_t i = 0; i < c->ngrp[G_MEMB]; i++) {  // ABI 8: modality candidates, in (m, j) order
        const Ev *e = &c->ev[c->grp[G_MEMB][i]];
        if (e->sub != M_RCANDM || e->uid != X->uid) continue;
        const int m = (int)(e->u2 >> MJ_SHIFT);
        const uint64_t j = e->u2 & MJ_MASK;
        if (m < 1 || m >= S_MAX || j != (uint64_t)X->nrecm[m]) continue;
        X->nrecm[m] = (int64_t)j + 1;
        if (X->th[K_GRM(m)] != 0.0 && c->lam_m[m] > 0.0) {
          Rec *rr = emit(c, R_RCANDM);
          if (rr) { rr->u1 = X->uid; rr->u2 = j; rr->i1 = m; }
          self_ev(c, si, receptor_next_m(c->seed, X->uid, m, j + 1, t, c->lam_m[m]), G_MEMB, M_RCANDM, X->uid,
                  ((uint64_t)m << MJ_SHIFT) | (j + 1));
        } else {
          X->pendm[m] = 0;
        }
      }
    }
    const int rec_on = X && !(c->fl & F_RECEPTOR_OFF) && X->th[K_GR] != 0.0;  // g_r = 0: no receptor (15.40)
    int64_t n_rm[S_MAX] = {0};
    int any_rm = 0;
    for (int64_t i = 0; i < c->ngrp[G_MEMB]; i++) {
      const Ev *e = &c->ev[c->grp[G_MEMB][i]];
      if (e->sub == M_ARRIVAL) {
        n_arr++;
        if (X && e->uid == X->uid) {
          n_del++;
          if (e->mask & 1) { cnt0++; S += X->weff[e->slot][0]; }
          if (e->mask & 2) { cnt1++; S += X->weff[e->slot][1]; }
        }
      } else if (e->sub == M_RECEPT) {
        if (rec_on && e->uid == X->uid) n_rec++;  // a RECEPTOR that is not delivered vanishes
      } else if (e->sub == M_RECEPTM) {
        const int m = (int)(e->u2 >> MJ_SHIFT);
        if (X && e->uid == X->uid && m >= 1 && m < S_MAX && !(c->fl & F_RECEPTOR_OFF) && X->th[K_GRM(m)] != 0.0) {
          n_rm[m]++; any_rm = 1;
        }
      } else if (e->sub == M_RCAND || e->sub == M_RCANDM) {
        continue;  // handled above
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
    if (n_rec > 0) {  // before the step, so before any R_SPIKE; charged refractory or not
      Rec *rr = emit(c, R_RECEPT);
      if (rr) { rr->u1 = X->uid; rr->i1 = n_rec; rr->x[0] = X->th[K_GR]; }
    }
    if (any_rm)
      for (int m = 1; m < S_MAX; m++)
        if (n_rm[m] > 0) {  // ABI 8: one record per delivered modality, in m order
          Rec *rr = emit(c, R_RECEPTM);
          if (rr) { rr->u1 = X->uid; rr->u2 = (uint64_t)m; rr->i1 = n_rm[m]; rr->x[0] = X->th[K_GRM(m)]; }
        }
    if (X && (n_del > 0 || n_kick > 0 || thr || n_rec > 0 || any_rm)) {
      int go = 1;
      if (n_del > 0 || n_rec > 0 || any_rm) {
        traces_to(X, t);
        X->r[0] = X->r[0] + (double)cnt0; X->r[1] = X->r[1] + (double)cnt1;
        X->rho = X->rho + (double)n_rec;
        for (int m = 1; m < S_MAX; m++) X->rhom[m] = X->rhom[m] + (double)n_rm[m];
      }
      if (t < X->tr) go = 0;  // refractory: input lost, traces already counted
      if (go) {
        if (n_rec > 0) S = S + X->th[K_GR] * (double)n_rec;  // one rounding, after the exact sum
        if (any_rm)
          for (int m = 1; m < S_MAX; m++) if (n_rm[m] > 0) S = S + X->th[K_GRM(m)] * (double)n_rm[m];
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
#ifdef LIFE_FAST
  (void)c; (void)fam; (void)w; (void)n;  // the fast build keeps no hashes: every family stays HASH_INIT
#else
  uint64_t h = c->H[fam];
  for (int i = 0; i < n; i++) h = splitmix64(h ^ w[i]);
  c->H[fam] = h;
#endif
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

static inline int plane_of(int32_t z) { return z == 0 ? 0 : (z == 1 ? 1 : 2); }  // S, M, H (9.1)

static void tick_charge(Ctx *c, double t, double tprev, double sp, int plane) {
  const double to = c->t_open_abs;
  if (t > to) {
    const double dl = t - (tprev < to ? to : tprev);
    c->live_time = c->live_time + dl;
    c->sec_int = c->sec_int + sp * dl;
    c->cost = c->cost + c->c_live * dl;
    c->cost = c->cost + c->c_sec * (sp * dl);
    c->live_plane[plane] = c->live_plane[plane] + dl;
  }
}

static void fate_log(Ctx *c, int kind, const Rec *r, uint64_t uid, uint64_t mother, int64_t aux, double age) {
  if (c->fate_cap > 0 && c->fate_n < c->fate_cap) {
    int64_t *fi = c->fate_i + c->fate_n * FATE_I;
    double *ff = c->fate_f + c->fate_n * FATE_F;
    fi[0] = kind; fi[1] = (int64_t)uid; fi[2] = (int64_t)mother;
    fi[3] = c->sites[r->site].a; fi[4] = c->sites[r->site].b; fi[5] = aux; fi[6] = c->sites[r->site].z;
    ff[0] = r->t; ff[1] = age;
    for (int k = 0; k < NG; k++) ff[2 + k] = r->g >= 0 ? c->gsnap[r->g + k] : 0.0;
  }
  c->fate_n++;
}

// --------------------------------------------------------------------------------- the CATCH world (9.7)
// The accountant owns all of it: the dot (X, Y) and its force, the blobs, the hotspot key, the act-plane occupancy O
// (Site.acc_occ) and each act-plane occupant's own pull (Site.fx, fy, tf). It reads cells only through records, and
// the only thing it sends back is a RECEPTOR event, d_min after the R_RCAND record that caused it.
static inline int64_t flags_at(const Ctx *c, double t) { return c->flags | (t >= c->t_fork_abs ? c->fork_flags : 0); }

static inline void planar(const Ctx *c, int32_t a, int32_t b, double *ox, double *oy) {  // 4.3
  if (c->base == 0) { *ox = (double)a + 0.5 * (double)b; *oy = (double)b * S32; }
  else { *ox = (double)a; *oy = (double)b; }
}
static inline double halo(double dx, double dy, double sigma) {
  return exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma));
}
static inline double poisson_next(uint64_t seed, uint64_t stream, uint64_t b, uint64_t k, double t_prev, double mean) {
  return t_prev - mean * log(draw2(seed, stream, b, k));
}
static inline void dot_gain(double dt, double tau_z, double gam, double *k, double *e) {
  *e = exp(-dt / tau_z);
  *k = tau_z * (1.0 - *e) / gam;
}
static void blob_heading(uint64_t seed, uint64_t b, uint64_t h, double v_t, double *vx, double *vy) {
  const double phi = TWO_PI * draw2(seed, S_HEAD, b, h);
  *vx = v_t * cos(phi); *vy = v_t * sin(phi);
}
static void blob_place(uint64_t seed, uint64_t b, uint64_t q, double x, double y, double r_min, double r_max,
                       double *bx, double *by) {
  const double th = TWO_PI * draw2(seed, S_PANG, b, q);
  const double r = r_min + draw2(seed, S_PDIST, b, q) * (r_max - r_min);
  *bx = x + r * cos(th); *by = y + r * sin(th);
}

// ABI 8 (9.8.3): a wall face blocks the force component that points into it; the force itself keeps every pull
static inline double eff_fx(const Ctx *c) {
  return ((c->blk_x > 0 && c->Fx > 0.0) || (c->blk_x < 0 && c->Fx < 0.0)) ? 0.0 : c->Fx;
}
static inline double eff_fy(const Ctx *c) {
  return ((c->blk_y > 0 && c->Fy > 0.0) || (c->blk_y < 0 && c->Fy < 0.0)) ? 0.0 : c->Fy;
}
static inline void dot_at(const Ctx *c, double t, double *x, double *y) {  // evaluated; the anchor does not move
  if (c->n_foot == 0 || t == c->t_x) { *x = c->X; *y = c->Y; return; }  // no footprint, no traction (15.44)
  double k, e;
  dot_gain(t - c->t_x, c->tau_z, c->gam, &k, &e);
  if (c->eco) { *x = c->X + eff_fx(c) * k; *y = c->Y + eff_fy(c) * k; return; }
  *x = c->X + c->Fx * k; *y = c->Y + c->Fy * k;
}
static void dot_adv(Ctx *c, double t) {  // moves the anchor to t
  if (t <= c->t_x) return;
  const double e = exp(-(t - c->t_x) / c->tau_z);
  if (c->n_foot > 0) {
    const double fx = c->eco ? eff_fx(c) : c->Fx, fy = c->eco ? eff_fy(c) : c->Fy;
    const double k = c->tau_z * (1.0 - e) / c->gam, dx = fx * k, dy = fy * k;
    c->X = c->X + dx; c->Y = c->Y + dy;
    c->path = c->path + sqrt(dx * dx + dy * dy);
  }
  c->Fx = c->Fx * e; c->Fy = c->Fy * e; c->t_x = t;
}
static inline void blob_at(const Blob *B, double t, double *x, double *y) {
  const double dt = t - B->t;
  *x = B->x + B->vx * dt; *y = B->y + B->vy * dt;
}

static void place(Ctx *c, int b, int cause, double t) {  // PLACE (9.7.3): around the dot, keeping the heading
  Blob *B = &c->blob[b];
  double X, Y;
  dot_at(c, t, &X, &Y);
  blob_place(c->seed, (uint64_t)b, B->q, X, Y, c->R_min, c->R_max, &B->x, &B->y);
  B->t = t;
  if (b == 1) B->present = draw2(c->seed, S_PPRES, 1, B->q) < c->b2_p;
  if (b == 0 && c->visibility_mode == 1) {
    c->bright = 1;
    c->visibility_next = t + c->visibility_on;
  }
  B->q += 1;
  const uint64_t w[7] = {12, dbits(t), (uint64_t)b, (uint64_t)cause, dbits(B->x), dbits(B->y), (uint64_t)B->present};
  fold(c, H_WORLD, w, 7); fold(c, H_ALL, w, 7);
}
static void world_timer(Ctx *c, int b) {  // a timer re-placement of blob b, a world event at r_b
  Blob *B = &c->blob[b];
  const double t = B->r;
  place(c, b, PL_TIMER, t);
  if (b == 0 && t >= c->t_open_abs) c->respawns++;
  if (b == 0 && c->blob[1].exists && c->b2_mode == 0) place(c, 1, PL_WITH, t);
  B->r = poisson_next(c->seed, S_RTIME, (uint64_t)b, B->m, t, c->t_resp);
  B->m += 1;
}
static void world_turn(Ctx *c, int b) {  // a tumble of blob b, a world event at tau_b
  Blob *B = &c->blob[b];
  const double t = B->tau;
  double x, y;
  blob_at(B, t, &x, &y);
  B->x = x; B->y = y; B->t = t;
  blob_heading(c->seed, (uint64_t)b, B->h, c->v_t, &B->vx, &B->vy);
  B->h += 1;
  const uint64_t w[5] = {13, dbits(t), (uint64_t)b, dbits(B->vx), dbits(B->vy)};
  fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
  B->tau = poisson_next(c->seed, S_TURN, (uint64_t)b, B->k, t, c->tau_turn);
  B->k += 1;
}
static void world_visibility(Ctx *c) {
  const double t = c->visibility_next;
  if (c->visibility_mode == 1) {
    c->bright = 0;
    c->visibility_next = INFINITY;
  } else {
    c->bright = !c->bright;
    c->visibility_next = poisson_next(c->seed, S_VISIBILITY, 0, c->visibility_k++, t,
                                     c->bright ? c->visibility_on : c->visibility_off);
  }
  const uint64_t w[4] = {14, dbits(t), 0, (uint64_t)c->bright};
  fold(c, H_WORLD, w, 4); fold(c, H_ALL, w, 4);
}

static void task_enter(Ctx *c, double t, int phase) {
  c->task_phase = phase; c->task_consumed = 0; c->task_defer_gap = 0;
  for (int b = 0; b < 2; b++) {
    Blob *B = &c->blob[b];
    B->exists = 1; B->present = 0;
    B->t = t; B->x = B->y = B->vx = B->vy = 0.0;
    B->r = B->tau = INFINITY;
  }
  if (phase == TASK_SAMPLE) {
    c->task_class = draw2(c->seed, S_TASK_CLASS, c->task_trial, 0) < 0.5 ? 0 : 1;
    Blob *B = &c->blob[c->task_class];
    dot_at(c, t, &B->x, &B->y); B->present = 1;
    const double duration = c->sample_min + (c->sample_max - c->sample_min) *
                            draw2(c->seed, S_TASK_DURATION, c->task_trial, 0);
    c->task_next = t + duration;
  } else if (phase == TASK_BLANK) {
    const double duration = c->blank_min + (c->blank_max - c->blank_min) *
                            draw2(c->seed, S_TASK_DURATION, c->task_trial, 1);
    c->task_next = t + duration;
  } else if (phase == TASK_CHOICE) {
    double X, Y;
    dot_at(c, t, &X, &Y);
    const double theta = TWO_PI * draw2(c->seed, S_TASK_GEOMETRY, c->task_trial, 0);
    const double radius = c->R_min + (c->R_max - c->R_min) *
                          draw2(c->seed, S_TASK_GEOMETRY, c->task_trial, 1);
    const double dx = radius * cos(theta), dy = radius * sin(theta);
    const int positive = draw2(c->seed, S_TASK_SIDE, c->task_trial, 0) < 0.5;
    Blob *P = &c->blob[positive ? 0 : 1], *N = &c->blob[positive ? 1 : 0];
    P->x = X + dx; P->y = Y + dy; N->x = X - dx; N->y = Y - dy;
    P->present = N->present = 1;
    c->task_choice_start = t;
    if (t >= c->t_open_abs) c->task_counts[TC_OPEN][c->task_class]++;
    c->task_next = t + c->choice_T;
  } else {
    c->task_next = t + c->reset_T;
  }
  const uint64_t w[9] = {15, dbits(t), c->task_trial, (uint64_t)phase, (uint64_t)c->task_class,
                         dbits(c->blob[0].x), dbits(c->blob[0].y), dbits(c->blob[1].x), dbits(c->blob[1].y)};
  fold(c, H_WORLD, w, 9); fold(c, H_ALL, w, 9);
}

static void task_resolve(Ctx *c, double t, int outcome, int slot) {
  // outcome: 0 timeout, 1 correct, 2 wrong. Slot 2 denotes timeout.
  // Carry-in is counted lazily, once, when an eligible pre-window choice resolves or closes unfinished.
  if (t >= c->t_open_abs) {
    const int cls = c->task_class;
    if (c->task_choice_start < c->t_open_abs) c->task_counts[TC_CARRY][cls]++;
    if (outcome == 0) c->task_counts[TC_TIMEOUT][cls]++;
    else if (outcome == 1) {
      c->task_counts[TC_CORRECT][cls]++;
      c->income = c->income + c->R_cap;
    } else {
      c->task_counts[TC_WRONG][cls]++;
      c->cost = c->cost + c->c_b2;
    }
  }
  c->task_consumed = 1;
  c->task_next = INFINITY;  // cancel a timeout even when the click shares its exact deadline
  const uint64_t w[6] = {16, dbits(t), c->task_trial, (uint64_t)c->task_class,
                         (uint64_t)outcome, (uint64_t)slot};
  fold(c, H_WORLD, w, 6); fold(c, H_ALL, w, 6);
}

static void task_transition(Ctx *c) {
  const double t = c->task_next;
  if (c->task_phase == TASK_SAMPLE) task_enter(c, t, TASK_BLANK);
  else if (c->task_phase == TASK_BLANK) task_enter(c, t, TASK_CHOICE);
  else if (c->task_phase == TASK_CHOICE) {
    task_resolve(c, t, 0, 2);
    task_enter(c, t, TASK_GAP);
  } else {
    c->task_trial++;
    task_enter(c, t, TASK_SAMPLE);
  }
}

static void task_close(Ctx *c, double t) {
  if (t > c->t_open_abs && c->task_phase == TASK_CHOICE && !c->task_consumed) {
    const int cls = c->task_class;
    if (c->task_choice_start < c->t_open_abs) c->task_counts[TC_CARRY][cls]++;
    c->task_counts[TC_UNFINISHED][cls]++;
  }
  for (int cls = 0; cls < 2; cls++) {
    const int64_t opened = c->task_counts[TC_OPEN][cls] + c->task_counts[TC_CARRY][cls];
    const int64_t resolved = c->task_counts[TC_CORRECT][cls] + c->task_counts[TC_WRONG][cls] +
                             c->task_counts[TC_TIMEOUT][cls] + c->task_counts[TC_UNFINISHED][cls];
    if (opened != resolved) c->status |= ST_MISMATCH;
  }
  const uint64_t w[5] = {17, dbits(t), c->task_trial, (uint64_t)c->task_phase, (uint64_t)c->task_class};
  fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
}

// ABI 6/7 resource stock: mutation is physical; observations and packet provenance are passive.
static void patch_origin_push(Ctx *c, int i, uint8_t origin) {
  Patch *p = &c->patch[i];
  if (!p->origins || p->origin_head < 0 || p->origin_head >= c->patch_capacity ||
      p->origin_n < 0 || p->origin_n >= c->patch_capacity || (origin != 2 && origin != 3)) {
    c->status |= ST_MISMATCH; return;
  }
  p->origins[(p->origin_head + p->origin_n) % c->patch_capacity] = origin;
  p->origin_n++;
  if (origin == 3) p->contact_stock++;
}

static int patch_origin_pop(Ctx *c, int i) {
  Patch *p = &c->patch[i];
  if (!p->origins || p->origin_head < 0 || p->origin_head >= c->patch_capacity ||
      p->origin_n <= 0 || p->origin_n > c->patch_capacity) {
    c->status |= ST_MISMATCH; return 0;
  }
  const int origin = p->origins[p->origin_head];
  if (origin != 2 && origin != 3) c->status |= ST_MISMATCH;
  p->origin_head = (p->origin_head + 1) % c->patch_capacity;
  p->origin_n--;
  if (origin == 3) p->contact_stock--;
  return origin;
}

static void patch_window_before(Ctx *c, double t) {
  if (c->patch_opened || t < c->t_open_abs) return;
  c->patch_opened = 1;
  for (int i = 0; i < c->patch_count; i++) {
    c->patch_counts[PC_OPEN][i] = c->patch[i].stock;
    c->patch_initial_open[i] = c->patch[i].initial_remaining;
    if (c->patch_contact_delay > 0.0) {
      c->contact_counts[CC_PENDING_OPEN][i] = c->patch[i].contact_pending;
      c->contact_counts[CC_STOCK_OPEN][i] = c->patch[i].contact_stock;
    }
  }
}

static void patch_start(Ctx *c) {
  const double theta0 = TWO_PI * draw2(c->seed, S_PATCH_LAYOUT, 0, 0);
  for (int i = 0; i < c->patch_count; i++) {
    Patch *p = &c->patch[i];
    const double theta = theta0 + (TWO_PI * (double)i) / (double)c->patch_count;
    const double r = c->R_min + (c->R_max - c->R_min) * draw2(c->seed, S_PATCH_LAYOUT, (uint64_t)i, 1);
    p->x = r * cos(theta); p->y = r * sin(theta);
    p->period = draw2(c->seed, S_PATCH_RATE, (uint64_t)i, 0) < 0.5 ? c->patch_fast : c->patch_slow;
    const double phase = p->period * draw2(c->seed, S_PATCH_PHASE, (uint64_t)i, 0);
    p->first = c->t0 + phase;
    if (p->first <= c->t0) p->first = nextafter(c->t0, INFINITY);
    p->next = p->first; p->arrival_index = 0;
    p->stock = p->initial_remaining = c->patch_capacity;
    if (c->patch_contact_delay > 0.0) {
      p->contact_due = INFINITY;
      p->origins = malloc((size_t)c->patch_capacity * sizeof(uint8_t));
      if (!p->origins) { c->fail |= FAIL_ALLOC; return; }
    }
    c->patch_left[i] = p->stock;
    const uint64_t w[8] = {18, dbits(c->t0), (uint64_t)i, dbits(p->x), dbits(p->y),
                           dbits(p->period), dbits(p->first), (uint64_t)c->patch_capacity};
    fold(c, H_WORLD, w, 8); fold(c, H_ALL, w, 8);
  }
}

static void patch_source(Ctx *c, int i) {
  Patch *p = &c->patch[i];
  const double t = p->next;
  patch_window_before(c, t);
  const int64_t before = p->stock;
  const int admitted = before < c->patch_capacity;
  if (admitted) {
    p->stock++;
    if (c->patch_contact_delay > 0.0) patch_origin_push(c, i, 2);
  }
  if (t >= c->t_open_abs) {
    c->patch_counts[PC_SOURCE][i]++;
    c->patch_counts[admitted ? PC_SUPPLY : PC_SPILL][i]++;
  }
  const uint64_t w[7] = {19, dbits(t), (uint64_t)i, p->arrival_index,
                         (uint64_t)before, (uint64_t)p->stock, (uint64_t)admitted};
  fold(c, H_WORLD, w, 7); fold(c, H_ALL, w, 7);
  p->arrival_index++;
  p->next = p->first + (double)p->arrival_index * p->period;
}

static void patch_contact_start(Ctx *c, int i, double t) {
  Patch *p = &c->patch[i];
  patch_window_before(c, t);
  p->contact_pending = 1;
  p->contact_due = t + c->patch_contact_delay;
  if (t >= c->t_open_abs) c->contact_counts[CC_STARTS][i]++;
  const uint64_t w[5] = {22, dbits(t), (uint64_t)i, p->contact_starts, dbits(p->contact_due)};
  fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
  p->contact_starts++;
}

static void patch_contact_mature(Ctx *c, int i) {
  Patch *p = &c->patch[i];
  const double t = p->contact_due;
  patch_window_before(c, t);
  const int64_t before = p->stock;
  const int admitted = before < c->patch_capacity;
  if (admitted) { p->stock++; patch_origin_push(c, i, 3); }
  if (t >= c->t_open_abs) {
    c->patch_counts[PC_SOURCE][i]++;
    c->patch_counts[admitted ? PC_SUPPLY : PC_SPILL][i]++;
    c->contact_counts[CC_MATURITIES][i]++;
    c->contact_counts[admitted ? CC_SUPPLY : CC_SPILL][i]++;
  }
  const uint64_t w[7] = {23, dbits(t), (uint64_t)i, p->contact_starts - 1,
                         (uint64_t)before, (uint64_t)p->stock, (uint64_t)admitted};
  fold(c, H_WORLD, w, 7); fold(c, H_ALL, w, 7);
  p->contact_pending = 0; p->contact_due = INFINITY;
}

static void patch_nearest(const Ctx *c, double t, double *x, double *y) {
  double X, Y, best = INFINITY;
  dot_at(c, t, &X, &Y);
  for (int i = 0; i < c->patch_count; i++) {
    const double dx = X - c->patch[i].x, dy = Y - c->patch[i].y, q = dx * dx + dy * dy;
    if (q < best) { best = q; *x = c->patch[i].x; *y = c->patch[i].y; }
  }
}

static double patch_rate(const Ctx *c, double px, double py) {
  double rate = c->lam_bg;
  for (int i = 0; i < c->patch_count; i++) {
    const double fraction = (double)c->patch_left[i] / (double)c->patch_capacity;
    const double amplitude = c->patch_landmark + (1.0 - c->patch_landmark) * fraction;
    const double component = c->lam_s * (amplitude * halo(px - c->patch[i].x, py - c->patch[i].y, c->sigma));
    rate = rate + component;
  }
  return rate;
}

static void patch_click(Ctx *c, double t) {
  patch_window_before(c, t);
  double X, Y;
  dot_at(c, t, &X, &Y);
  const int cnt = t >= c->t_open_abs;
  int slot = 4, outcome = 0, origin = 0;
  int64_t before = 0, after = 0;
  if (cnt) c->clicks++;
  for (int i = 0; i < c->patch_count; i++) {
    Patch *p = &c->patch[i];
    const double dx = X - p->x, dy = Y - p->y;
    if (dx * dx + dy * dy <= c->rho_c * c->rho_c) { slot = i; break; }
  }
  if (slot < 4) {
    Patch *p = &c->patch[slot];
    before = p->stock;
    if (before > 0) {
      outcome = 1; p->stock--;
      origin = p->initial_remaining > 0 ? 1 : 2;
      if (origin == 1) p->initial_remaining--;
      else if (c->patch_contact_delay > 0.0) origin = patch_origin_pop(c, slot);
      if (cnt) {
        c->captures++; c->income = c->income + c->R_cap;
        c->patch_counts[PC_HARVEST][slot]++;
        c->patch_counts[origin == 1 ? PC_INITIAL : PC_REFILL][slot]++;
        if (origin == 3) c->contact_counts[CC_HARVEST][slot]++;
      }
    } else {
      outcome = 2;
      if (cnt) c->patch_counts[PC_EMPTY][slot]++;
      if (c->patch_contact_delay > 0.0 && !p->contact_pending) patch_contact_start(c, slot, t);
    }
    after = p->stock;
  } else if (cnt) c->patch_geometric_misses++;
  if (outcome != 1 && cnt) { c->misses++; c->cost = c->cost + c->c_miss; }
  const uint64_t w[7] = {20, dbits(t), (uint64_t)outcome, (uint64_t)slot,
                         (uint64_t)before, (uint64_t)after, (uint64_t)origin};
  fold(c, H_WORLD, w, 7); fold(c, H_ALL, w, 7);
  const uint64_t click[5] = {11, dbits(t), outcome == 1 ? 1 : 0, dbits(X), dbits(Y)};
  fold(c, H_WORLD, click, 5); fold(c, H_ALL, click, 5);
}

static void patch_close(Ctx *c, double t) {
  if (t <= c->t_open_abs) {
    memset(c->patch_counts, 0, sizeof(c->patch_counts)); c->patch_geometric_misses = 0;
    memset(c->contact_counts, 0, sizeof(c->contact_counts));
  } else {
    patch_window_before(c, t);
    int64_t harvested = 0, empty = 0;
    for (int i = 0; i < c->patch_count; i++) {
      c->patch_counts[PC_END][i] = c->patch[i].stock;
      const int64_t op = c->patch_counts[PC_OPEN][i], end = c->patch_counts[PC_END][i];
      const int64_t source = c->patch_counts[PC_SOURCE][i], supply = c->patch_counts[PC_SUPPLY][i];
      const int64_t spill = c->patch_counts[PC_SPILL][i], h = c->patch_counts[PC_HARVEST][i];
      const int64_t ih = c->patch_counts[PC_INITIAL][i], rh = c->patch_counts[PC_REFILL][i];
      if (source != supply + spill || op + supply != h + end || op + source != h + spill + end ||
          h != ih + rh || c->patch_initial_open[i] != ih + c->patch[i].initial_remaining ||
          op < 0 || op > c->patch_capacity || end < 0 || end > c->patch_capacity ||
          c->patch[i].initial_remaining < 0 || c->patch[i].initial_remaining > end) c->status |= ST_MISMATCH;
      for (int k = 0; k < PC_COUNT; k++) if (c->patch_counts[k][i] < 0) c->status |= ST_MISMATCH;
      if (c->patch_contact_delay > 0.0) {
        Patch *p = &c->patch[i];
        c->contact_counts[CC_PENDING_END][i] = p->contact_pending;
        c->contact_counts[CC_STOCK_END][i] = p->contact_stock;
        const int64_t starts = c->contact_counts[CC_STARTS][i], mat = c->contact_counts[CC_MATURITIES][i];
        const int64_t cs = c->contact_counts[CC_SUPPLY][i], sp = c->contact_counts[CC_SPILL][i];
        const int64_t ch = c->contact_counts[CC_HARVEST][i], po = c->contact_counts[CC_PENDING_OPEN][i];
        const int64_t so = c->contact_counts[CC_STOCK_OPEN][i];
        if (po + starts != mat + p->contact_pending || mat != cs + sp || so + cs != ch + p->contact_stock ||
            po < 0 || po > 1 || p->contact_pending < 0 || p->contact_pending > 1 ||
            starts > c->patch_counts[PC_EMPTY][i] ||
            so > op - c->patch_initial_open[i] || p->contact_stock < 0 ||
            p->contact_stock > end - p->initial_remaining || cs > supply || sp > spill || mat > source || ch > rh ||
            c->patch_initial_open[i] < 0 || c->patch_initial_open[i] > op ||
            (starts >= 0 && po >= 0 && p->contact_starts < (uint64_t)(starts + po)) ||
            (p->contact_pending && (!isfinite(p->contact_due) || p->contact_due < t || !p->contact_starts)) ||
            (!p->contact_pending && p->contact_due != INFINITY)) c->status |= ST_MISMATCH;
        for (int k = 0; k < CC_COUNT; k++) if (c->contact_counts[k][i] < 0) c->status |= ST_MISMATCH;
        if (!p->origins || p->origin_head < 0 || p->origin_head >= c->patch_capacity || p->origin_n < 0 ||
            p->origin_n > c->patch_capacity || p->origin_n != end - p->initial_remaining) {
          c->status |= ST_MISMATCH;
        } else {
          int64_t contacts = 0;
          for (int64_t j = 0; j < p->origin_n; j++) {
            const int origin = p->origins[(p->origin_head + j) % c->patch_capacity];
            if (origin == 3) contacts++;
            else if (origin != 2) c->status |= ST_MISMATCH;
          }
          if (contacts != p->contact_stock) c->status |= ST_MISMATCH;
        }
      }
      harvested += h; empty += c->patch_counts[PC_EMPTY][i];
    }
    if (c->patch_geometric_misses < 0 || c->captures != harvested ||
        c->misses != empty + c->patch_geometric_misses || c->clicks != c->captures + c->misses)
      c->status |= ST_MISMATCH;
  }
  for (int i = 0; i < c->patch_count; i++) {
    const uint64_t w[5] = {21, dbits(t), (uint64_t)i, (uint64_t)c->patch[i].stock,
                           (uint64_t)c->patch[i].initial_remaining};
    fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
  }
  if (c->patch_contact_delay > 0.0) for (int i = 0; i < c->patch_count; i++) {
    const Patch *p = &c->patch[i];
    const uint64_t w[7] = {24, dbits(t), (uint64_t)i, (uint64_t)p->contact_pending,
                           dbits(p->contact_pending ? p->contact_due : 0.0),
                           (uint64_t)p->contact_stock, p->contact_starts};
    fold(c, H_WORLD, w, 7); fold(c, H_ALL, w, 7);
  }
}

// ------------------------------------------------------------------------------------- the eco world (ABI 8, 9.8)
// Sources release odour puffs that drift with a meandering current and spread as they age; rule-based agents
// (predators, prey, pests) move in straight segments chosen at their own look events; walls block the dot (the swept
// body, inflated by r_body) and stop agents; the dot may carry food home, plant in fertile disks and harvest. Every
// quantity is world state. Cells receive only receptor events of their bound modalities at their own screen point.
static void send_receptor_m(Ctx *c, int32_t si, double t, uint64_t uid, int m, uint64_t j);

static inline int64_t eco_count(const Ctx *c, double t) { return t >= c->t_open_abs; }
static inline double eco_amp(const Ctx *c, int i, int64_t stock) {
  return c->landmark + (1.0 - c->landmark) * ((double)stock / (double)c->src[i].cap);
}
static inline void cur_A(const Ctx *c, double t, double *ax, double *ay) {
  *ax = c->cur_Ax + c->cur_ux * (t - c->cur_ts); *ay = c->cur_Ay + c->cur_uy * (t - c->cur_ts);
}
static inline void ag_pos(const Agent *g, double t, double *x, double *y) {
  const double tt = t < g->t_stop ? t : g->t_stop, dt = tt - g->t;
  *x = g->x + g->vx * dt; *y = g->y + g->vy * dt;
}
static inline int in_disk2(double x, double y, const Disk *d) {
  const double dx = x - d->x, dy = y - d->y;
  return dx * dx + dy * dy <= d->r * d->r;
}
static int eco_sheltered(const Ctx *c, double x, double y) {
  for (int i = 0; i < c->n_shelter; i++) if (in_disk2(x, y, &c->shelter[i])) return 1;
  return 0;
}
static void eco_fold(Ctx *c, const uint64_t *w, int n) { fold(c, H_WORLD, w, n); fold(c, H_ALL, w, n); }

// entry parameter s in [0, 1) of the segment P + s E into the open box (x0, x1) x (y0, y1), INFINITY if none; *face is
// 0 for an x face, 1 for a y face (the slab entered last; x on a tie). A start inside the open box enters at 0.
static double seg_enter(double X, double Y, double ex, double ey, double x0, double x1, double y0, double y1,
                        int *face) {
  double sx0, sx1, sy0, sy1;
  if (ex == 0.0) {
    if (!(x0 < X && X < x1)) return INFINITY;
    sx0 = -INFINITY; sx1 = INFINITY;
  } else {
    const double a = (x0 - X) / ex, b = (x1 - X) / ex;
    sx0 = a < b ? a : b; sx1 = a < b ? b : a;
  }
  if (ey == 0.0) {
    if (!(y0 < Y && Y < y1)) return INFINITY;
    sy0 = -INFINITY; sy1 = INFINITY;
  } else {
    const double a = (y0 - Y) / ey, b = (y1 - Y) / ey;
    sy0 = a < b ? a : b; sy1 = a < b ? b : a;
  }
  const double s_in = sx0 > sy0 ? sx0 : sy0, s_out = sx1 < sy1 ? sx1 : sy1;
  if (!(s_in < s_out) || !(s_out > 0.0) || !(s_in < 1.0)) return INFINITY;
  *face = sx0 >= sy0 ? 0 : 1;
  return s_in < 0.0 ? 0.0 : s_in;
}

static void eco_set_gam(Ctx *c) {  // drag: the footprint's, times the load factor
  c->gam = c->gam0 * (1.0 + c->carry_drag * (double)c->n_item);
}

// the dot's next contact change (9.8.3): a hit of the free path into an inflated wall, or a slide off the end of a
// blocking face; a change at the current anchor (s = 0) is applied at once
static void eco_contact(Ctx *c, int kind, int w, int face) {
  const Wall *W = &c->wall[w];
  if (kind == 0) {
    if (face == 0) {
      const double fx = eff_fx(c);
      c->X = fx > 0.0 ? W->x0 - c->r_body : W->x1 + c->r_body;
      c->blk_x = fx > 0.0 ? 1 : -1; c->blk_wx = w;
    } else {
      const double fy = eff_fy(c);
      c->Y = fy > 0.0 ? W->y0 - c->r_body : W->y1 + c->r_body;
      c->blk_y = fy > 0.0 ? 1 : -1; c->blk_wy = w;
    }
    if (eco_count(c, c->t_x)) c->eco_n[EL_WALLCONTACTS]++;
  } else if (face == 0) {
    c->blk_x = 0;
  } else {
    c->blk_y = 0;
  }
  const uint64_t wd[7] = {44, dbits(c->t_x), (uint64_t)kind, (uint64_t)w, (uint64_t)face, dbits(c->X), dbits(c->Y)};
  eco_fold(c, wd, 7);
}
static void eco_kink(Ctx *c) {
  c->kink_t = INFINITY;
  if (!c->eco || c->n_wall == 0 || c->n_foot == 0) return;
  for (int it = 0; it < 8; it++) {
    if (c->blk_x && c->Fx != 0.0 && !((c->blk_x > 0) == (c->Fx > 0.0))) c->blk_x = 0;  // pulled away from the face
    if (c->blk_y && c->Fy != 0.0 && !((c->blk_y > 0) == (c->Fy > 0.0))) c->blk_y = 0;
    const double fx = eff_fx(c), fy = eff_fy(c);
    if (fx == 0.0 && fy == 0.0) return;
    const double kinf = c->tau_z / c->gam, ex = fx * kinf, ey = fy * kinf;
    double best = INFINITY;
    int bw = -1, bf = 0, bk = 0;
    for (int w = 0; w < c->n_wall; w++) {
      const Wall *W = &c->wall[w];
      int face = 0;
      const double sv = seg_enter(c->X, c->Y, ex, ey, W->x0 - c->r_body, W->x1 + c->r_body, W->y0 - c->r_body,
                                  W->y1 + c->r_body, &face);
      if (sv < best) { best = sv; bw = w; bf = face; bk = 0; }
    }
    if (c->blk_x && ey != 0.0) {
      const Wall *W = &c->wall[c->blk_wx];
      const double lim = ey > 0.0 ? W->y1 + c->r_body : W->y0 - c->r_body, sv = (lim - c->Y) / ey;
      if (sv >= 0.0 && sv < 1.0 && sv < best) { best = sv; bw = c->blk_wx; bf = 0; bk = 1; }
    }
    if (c->blk_y && ex != 0.0) {
      const Wall *W = &c->wall[c->blk_wy];
      const double lim = ex > 0.0 ? W->x1 + c->r_body : W->x0 - c->r_body, sv = (lim - c->X) / ex;
      if (sv >= 0.0 && sv < 1.0 && sv < best) { best = sv; bw = c->blk_wy; bf = 1; bk = 1; }
    }
    if (bw < 0) return;
    if (best > 0.0) {
      double tk = c->t_x - c->tau_z * log(1.0 - best);
      if (!(tk > c->t_x)) tk = nextafter(c->t_x, INFINITY);
      c->kink_t = tk; c->kink_kind = bk; c->kink_wall = bw; c->kink_face = bf;
      return;
    }
    eco_contact(c, bk, bw, bf);
  }
}
static void eco_kink_event(Ctx *c) {
  const double t = c->kink_t;
  dot_adv(c, t);
  eco_contact(c, c->kink_kind, c->kink_wall, c->kink_face);
  eco_kink(c);
}

// --- odour: puffs of every source in release order, then agents, home, soil and ripe plants (9.8.2)
static double eco_conc(const Ctx *c, int k, double t, double px, double py) {
  double ax, ay, C = 0.0;
  cur_A(c, t, &ax, &ay);
  const double s02 = c->puff_sig0 * c->puff_sig0;
  for (int64_t q = 0; q < c->puff_n; q++) {
    const Puff *p = &c->puff[(c->puff_head + q) % c->puff_cap];
    const double age = t - p->t;
    if (age > c->puff_life || p->a[k] == 0.0) continue;
    const double s2 = s02 + 2.0 * c->puff_D * age, dx = px - (p->ox + ax), dy = py - (p->oy + ay);
    const double d2 = dx * dx + dy * dy;
    if (d2 > c->puff_cut * s2) continue;
    C = C + p->a[k] * (s02 / s2) * exp(-d2 / (2.0 * s2));
  }
  for (int i = 0; i < c->n_ag; i++) {
    const Agent *g = &c->ag[i];
    if (!g->vis || g->b[k] == 0.0) continue;
    double x, y;
    ag_pos(g, t, &x, &y);
    C = C + g->b[k] * halo(px - x, py - y, g->sigma);
  }
  if (c->home_r > 0.0 && c->home_b[k] != 0.0) C = C + c->home_b[k] * halo(px - c->home_x, py - c->home_y, c->home_sig);
  if (c->soil_b[k] != 0.0)
    for (int i = 0; i < c->n_fertile; i++)
      C = C + c->soil_b[k] * halo(px - c->fertile[i].x, py - c->fertile[i].y, c->soil_sig);
  if (c->plant_b[k] != 0.0)
    for (int i = 0; i < N_PLANT; i++)
      if (c->plant[i].vis) C = C + c->plant_b[k] * halo(px - c->plant[i].x, py - c->plant[i].y, c->plant_sig);
  return C;
}
static int eco_occluded(const Ctx *c, double sx, double sy, double px, double py) {
  if (!c->occlude) return 0;
  for (int w = 0; w < c->n_wall; w++) {
    const Wall *W = &c->wall[w];
    int face;
    if (seg_enter(sx, sy, px - sx, py - sy, W->x0, W->x1, W->y0, W->y1, &face) < 1.0) return 1;
  }
  return 0;
}
static double eco_light(const Ctx *c, double t, double px, double py) {  // modality 0 in an eco life
  double rate = c->lam_bg;
  for (int i = 0; i < c->n_src; i++) {
    const Src *S = &c->src[i];
    if (S->light == 0.0 || eco_occluded(c, S->x, S->y, px, py)) continue;
    rate = rate + c->lam_s * ((S->light * eco_amp(c, i, c->src_left[i])) * halo(px - S->x, py - S->y, S->sigma));
  }
  if (c->plant_light != 0.0)
    for (int i = 0; i < N_PLANT; i++)
      if (c->plant[i].vis && !eco_occluded(c, c->plant[i].x, c->plant[i].y, px, py))
        rate = rate + c->lam_s * (c->plant_light * halo(px - c->plant[i].x, py - c->plant[i].y, c->plant_sig));
  for (int i = 0; i < c->n_ag; i++) {
    const Agent *g = &c->ag[i];
    if (!g->vis || g->light == 0.0) continue;
    double x, y;
    ag_pos(g, t, &x, &y);
    if (!eco_occluded(c, x, y, px, py)) rate = rate + c->lam_s * (g->light * halo(px - x, py - y, g->sigma));
  }
  return rate;
}
// the exposed face of a sense-plane cell (the in-plane neighbour sites outside O0), normalized; 0 inside the body
static void sense_face(Ctx *c, Site *s, double *nx, double *ny) {
  double fx = 0.0, fy = 0.0;
  for (int d = 0; d < c->nplane; d++) {
    int32_t j = s->nbr[d];
    if (j < 0) {
      j = site_find(c, s->a + c->off_a[d], s->b + c->off_b[d], s->z);
      if (j >= 0) s->nbr[d] = j;
    }
    if (j < 0 || !c->sites[j].acc_occ0) { fx = fx + c->unit[3 * d]; fy = fy + c->unit[3 * d + 1]; }
  }
  const double n = sqrt(fx * fx + fy * fy);
  if (n > 0.0) { *nx = fx / n; *ny = fy / n; } else { *nx = 0.0; *ny = 0.0; }
}
static double mod_rate(Ctx *c, int m, Site *s, double t, double px, double py) {
  const double bg = c->mod_bg[m], sc = c->mod_s[m], K = c->mod_K[m];
  switch (c->mod_kind[m]) {
    case MOD_ODOUR: {
      const double C = eco_conc(c, c->mod_arg[m], t, px, py);
      return bg + sc * (C / (C + K));
    }
    case MOD_FLOW: {
      double nx, ny;
      sense_face(c, s, &nx, &ny);
      double vx = 0.0, vy = 0.0;
      if (c->n_foot > 0) {
        const double e = exp(-(t - c->t_x) / c->tau_z);
        vx = eff_fx(c) * e / c->gam; vy = eff_fy(c) * e / c->gam;
      }
      const double ux = c->cur_ux - vx, uy = c->cur_uy - vy, p = -(ux * nx + uy * ny) / K;
      return bg + sc * clipd(p, 0.0, 1.0);
    }
    case MOD_TOUCH: {
      const double r2 = K * K;
      for (int w = 0; w < c->n_wall; w++) {
        const Wall *W = &c->wall[w];
        const double dx = px < W->x0 ? W->x0 - px : (px > W->x1 ? px - W->x1 : 0.0);
        const double dy = py < W->y0 ? W->y0 - py : (py > W->y1 ? py - W->y1 : 0.0);
        if (dx * dx + dy * dy <= r2) return bg + sc;
      }
      for (int i = 0; i < c->n_ag; i++) {
        const Agent *g = &c->ag[i];
        if (!g->vis) continue;
        double x, y;
        ag_pos(g, t, &x, &y);
        const double dx = px - x, dy = py - y;
        if (dx * dx + dy * dy <= r2) return bg + sc;
      }
      return bg;
    }
    case MOD_VIB: {
      double V = 0.0;
      for (int i = 0; i < c->n_ag; i++) {
        const Agent *g = &c->ag[i];
        if (!g->vis || g->speed == 0.0 || !(t < g->t_stop)) continue;
        double x, y;
        ag_pos(g, t, &x, &y);
        V = V + (g->speed / c->vib_vref) * halo(px - x, py - y, K);
      }
      return bg + sc * (V / (V + 1.0));
    }
    case MOD_SUN: {
      double nx, ny;
      sense_face(c, s, &nx, &ny);
      const double p = nx * c->sun_x + ny * c->sun_y;
      return bg + sc * (p > 0.0 ? p : 0.0);
    }
    default: return bg;
  }
}

// --- world events
static void eco_refill(Ctx *c, int i) {
  Src *S = &c->src[i];
  const double t = S->next;
  const int64_t before = S->stock;
  if (S->stock < S->cap) S->stock++;
  const uint64_t w[5] = {40, dbits(t), (uint64_t)i, (uint64_t)before, (uint64_t)S->stock};
  eco_fold(c, w, 5);
  S->arrival_index++;
  S->next = S->first + (double)S->arrival_index * S->period;
}
static void eco_puff(Ctx *c, int i) {
  Src *S = &c->src[i];
  const double t = S->next_puff;
  while (c->puff_n > 0 && t - c->puff[c->puff_head].t > c->puff_life) {  // expired, oldest first
    c->puff_head = (c->puff_head + 1) % c->puff_cap; c->puff_n--;
  }
  if (c->puff_n == c->puff_cap) { c->puff_head = (c->puff_head + 1) % c->puff_cap; c->puff_n--; }
  Puff *p = &c->puff[(c->puff_head + c->puff_n) % c->puff_cap];
  double ax, ay;
  cur_A(c, t, &ax, &ay);
  const double amp = eco_amp(c, i, S->stock);
  p->t = t; p->ox = S->x - ax; p->oy = S->y - ay;
  for (int k = 0; k < N_SPEC; k++) p->a[k] = S->b[k] * amp;
  c->puff_n++;
  if (eco_count(c, t)) c->eco_n[EL_PUFFS]++;
  const uint64_t w[7] = {41, dbits(t), (uint64_t)i, S->puff_k, dbits(p->ox), dbits(p->oy), dbits(amp)};
  eco_fold(c, w, 7);
  S->next_puff = poisson_next(c->seed, S_ECO_PUFF, (uint64_t)i, S->puff_k, t, 1.0 / S->puff_rate);
  S->puff_k++;
}
static void eco_turn(Ctx *c) {
  const double t = c->cur_next;
  double ax, ay;
  cur_A(c, t, &ax, &ay);
  c->cur_Ax = ax; c->cur_Ay = ay; c->cur_ts = t;
  c->cur_head = c->cur_head + c->cur_turn_max * (2.0 * draw2(c->seed, S_ECO_CUR, 1, c->cur_k) - 1.0);
  c->cur_ux = c->cur_speed * cos(c->cur_head); c->cur_uy = c->cur_speed * sin(c->cur_head);
  const uint64_t w[5] = {42, dbits(t), c->cur_k, dbits(c->cur_ux), dbits(c->cur_uy)};
  eco_fold(c, w, 5);
  c->cur_next = poisson_next(c->seed, S_ECO_CUR, 0, c->cur_k, t, c->cur_turn);
  c->cur_k++;
}
static void ag_stop(const Ctx *c, Agent *g) {  // the agent stops where its segment over one look meets a wall
  g->t_stop = INFINITY;
  if (g->vx == 0.0 && g->vy == 0.0) return;
  double best = INFINITY;
  for (int w = 0; w < c->n_wall; w++) {
    const Wall *W = &c->wall[w];
    int face;
    const double sv = seg_enter(g->x, g->y, g->vx * g->look, g->vy * g->look, W->x0, W->x1, W->y0, W->y1, &face);
    if (sv < best) best = sv;
  }
  if (best < INFINITY) g->t_stop = g->t + best * g->look;
}
static void ag_head(Agent *g, double dx, double dy, double v) {  // velocity v along (dx, dy), 0 for a zero vector
  const double n = sqrt(dx * dx + dy * dy);
  if (n > 0.0) { g->vx = v * (dx / n); g->vy = v * (dy / n); g->speed = v; }
  else { g->vx = g->vy = 0.0; g->speed = 0.0; }
}
static void ag_look(Ctx *c, int i) {
  Agent *g = &c->ag[i];
  const double t = g->next_look;
  const int cnt = eco_count(c, t);
  double x, y, X, Y;
  ag_pos(g, t, &x, &y);
  const int stopped = !(t < g->t_stop) && g->speed > 0.0;
  g->x = x; g->y = y; g->t = t;
  dot_at(c, t, &X, &Y);
  const double dx = X - x, dy = Y - y, d2 = dx * dx + dy * dy, rs2 = g->r_sense * g->r_sense;
  const double rc2 = g->r_contact * g->r_contact;
  const int shel = eco_sheltered(c, X, Y), st0 = g->state;
  const double u0 = draw3(c->seed, S_ECO_AG, (uint64_t)i, g->q, 0), u1 = draw3(c->seed, S_ECO_AG, (uint64_t)i, g->q, 1);
  const double u2 = draw3(c->seed, S_ECO_AG, (uint64_t)i, g->q, 2);
  int hit = 0, plant_hit = -1;
  double tx = 0.0, ty = 0.0;  // a target direction for active motion
  switch (g->type) {
    case AG_PURSUIT:
      if (g->state == AS_REST && t >= g->until) g->state = AS_WANDER;
      if (g->state == AS_WANDER && !shel && d2 <= rs2 && u0 < g->p) {
        g->state = AS_ACTIVE; g->until = t + g->t_state;
        if (cnt) c->eco_n[EL_DETECTIONS]++;
      } else if (g->state == AS_ACTIVE && (shel || t >= g->until || d2 > 4.0 * rs2)) {
        g->state = AS_WANDER;
      }
      if (g->state == AS_ACTIVE && d2 <= rc2 && !c->eco_dead) { hit = 1; g->state = AS_REST; g->until = t + g->t_rest; }
      tx = dx; ty = dy;
      break;
    case AG_AMBUSH:
      if (g->state == AS_REST && t >= g->until) g->state = AS_WANDER;
      if (g->state == AS_WANDER && !shel && d2 <= rc2 && u0 < g->p && !c->eco_dead) {
        hit = 1; g->state = AS_REST; g->until = t + g->t_rest;
        if (cnt) c->eco_n[EL_DETECTIONS]++;
      }
      break;
    case AG_DARTER: case AG_FREEZER: case AG_BURROWER:
      if (g->state == AS_HIDDEN) {
        if (t >= g->until) { g->state = AS_WANDER; g->x = g->rx; g->y = g->ry; }
      } else if (g->state == AS_ACTIVE) {
        if (g->type == AG_BURROWER) {
          const double qx = g->rx - x, qy = g->ry - y;
          if (qx * qx + qy * qy <= 0.0625) { g->state = AS_HIDDEN; g->until = t + g->t_rest; }
          else if (t >= g->until) g->state = AS_WANDER;
        } else if (t >= g->until) {
          g->state = AS_WANDER;
        }
      } else if (d2 <= rs2 && u0 < g->p) {
        g->state = AS_ACTIVE; g->until = t + g->t_state;
        if (cnt) c->eco_n[EL_ALARMS]++;
      }
      if (g->type == AG_DARTER) { tx = -dx; ty = -dy; }
      else if (g->type == AG_BURROWER) { tx = g->rx - g->x; ty = g->ry - g->y; }
      break;
    case AG_PEST: {
      double best = INFINITY;
      int bi = -1;
      for (int k = 0; k < N_PLANT; k++) {
        if (c->plant[k].state != 2) continue;
        const double qx = c->plant[k].x - x, qy = c->plant[k].y - y, q = qx * qx + qy * qy;
        if (q <= rs2 && q < best) { best = q; bi = k; }
      }
      if (bi >= 0 && best <= rc2) {
        plant_hit = bi; g->state = AS_WANDER;
      } else if (bi >= 0) {
        g->state = AS_ACTIVE; tx = c->plant[bi].x - x; ty = c->plant[bi].y - y;
      } else {
        g->state = AS_WANDER;
      }
      break;
    }
    default: break;
  }
  // velocity
  const double r2 = g->x * g->x + g->y * g->y;
  if (g->state == AS_WANDER && g->type != AG_AMBUSH) {
    if (r2 > c->arena * c->arena) ag_head(g, -g->x, -g->y, g->v1);
    else if (u1 < 0.3 || st0 != AS_WANDER || stopped || g->speed == 0.0) {
      const double h = TWO_PI * u2;
      ag_head(g, cos(h), sin(h), g->v1);
    } else {
      ag_head(g, g->vx, g->vy, g->v1);
    }
  } else if (g->state == AS_ACTIVE && g->type != AG_FREEZER && g->type != AG_AMBUSH) {
    ag_head(g, tx, ty, g->v2);
  } else {
    ag_head(g, 0.0, 0.0, 0.0);
  }
  g->vis = g->state != AS_HIDDEN && !(g->type == AG_FREEZER && g->state == AS_ACTIVE);
  ag_stop(c, g);
  if (hit) {
    if (cnt) {
      c->eco_n[EL_HITS]++;
      c->eco_x[EL_DAMAGECOST] = c->eco_x[EL_DAMAGECOST] + g->value; c->cost = c->cost + g->value;
    }
    c->hits_all++;  // every hit counts toward death, counted or not
    if (c->kill_hits > 0 && c->hits_all >= c->kill_hits) c->eco_dead = 1;
  }
  if (plant_hit >= 0) {
    c->plant[plant_hit].state = 0; c->plant[plant_hit].vis = 0;
    if (cnt) c->eco_n[EL_PESTEATEN]++;
  }
  const uint64_t w[9] = {45, dbits(t), (uint64_t)i, (uint64_t)g->state, dbits(g->vx), dbits(g->vy),
                         (uint64_t)(hit | (plant_hit >= 0 ? 2 : 0)), dbits(g->x), dbits(g->y)};
  eco_fold(c, w, 9);
  g->q++;
  g->next_look = t + g->look;
}
static void eco_digest(Ctx *c) {
  const Item it = c->item[0];
  const double t = it.due;
  dot_adv(c, t);
  for (int k = 1; k < c->n_item; k++) c->item[k - 1] = c->item[k];
  c->n_item--;
  if (eco_count(c, t)) {
    c->eco_n[EL_DIGESTED]++; c->eco_x[EL_DIGESTINC] = c->eco_x[EL_DIGESTINC] + it.value;
    c->income = c->income + it.value; c->captures++;
  }
  eco_set_gam(c);
  const uint64_t w[4] = {46, dbits(t), it.id, dbits(it.value)};
  eco_fold(c, w, 4);
  eco_kink(c);
}
static void eco_plant_event(Ctx *c, int i, int spoil) {
  Plant *P = &c->plant[i];
  const double t = spoil ? P->t_spoil : P->t_ripe;
  if (spoil) { P->state = 0; P->vis = 0; if (eco_count(c, t)) c->eco_n[EL_SPOILED]++; }
  else { P->state = 2; P->vis = 1; if (eco_count(c, t)) c->eco_n[EL_RIPENED]++; }
  const uint64_t w[5] = {47, dbits(t), (uint64_t)i, P->id, (uint64_t)P->state};
  eco_fold(c, w, 5);
}
static void eco_world_to(Ctx *c, double t) {  // strictly below t, in (time, kind, index) order
  for (;;) {
    double best = INFINITY;
    int kind = -1, idx = -1;
#define ECO_CAND(tt, k, ix) do { const double tt_ = (tt); if (tt_ < best) { best = tt_; kind = (k); idx = (ix); } } while (0)
    for (int i = 0; i < c->n_src; i++) if (c->src[i].period > 0.0) ECO_CAND(c->src[i].next, 0, i);
    for (int i = 0; i < c->n_src; i++) if (c->src[i].puff_rate > 0.0) ECO_CAND(c->src[i].next_puff, 1, i);
    ECO_CAND(c->cur_next, 2, 0);
    for (int i = 0; i < c->n_ag; i++) ECO_CAND(c->ag[i].next_look, 3, i);
    ECO_CAND(c->kink_t, 4, 0);
    if (c->n_item > 0) ECO_CAND(c->item[0].due, 5, 0);
    for (int i = 0; i < N_PLANT; i++) {
      if (c->plant[i].state == 1) ECO_CAND(c->plant[i].t_ripe, 6, i);
      else if (c->plant[i].state == 2) ECO_CAND(c->plant[i].t_spoil, 7, i);
    }
#undef ECO_CAND
    if (!(best < t)) return;
    switch (kind) {
      case 0: eco_refill(c, idx); break;
      case 1: eco_puff(c, idx); break;
      case 2: eco_turn(c); break;
      case 3: ag_look(c, idx); break;
      case 4: eco_kink_event(c); break;
      case 5: eco_digest(c); break;
      case 6: eco_plant_event(c, idx, 0); break;
      default: eco_plant_event(c, idx, 1); break;
    }
  }
}

// --- clicks, samples, start and close
static void eco_click(Ctx *c, double t) {  // 9.8.4: prey, ripe plant, source, home, planting, else a miss
  double X, Y;
  dot_at(c, t, &X, &Y);
  const int cnt = eco_count(c, t);
  const double r2 = c->rho_c * c->rho_c;
  int outcome = 0, idx = -1;
  double val = 0.0;
  if (cnt) c->clicks++;
  for (int i = 0; i < c->n_ag && outcome == 0; i++) {  // 1. prey
    Agent *g = &c->ag[i];
    if (g->type < AG_DARTER || g->type > AG_BURROWER || g->state == AS_HIDDEN) continue;
    double x, y;
    ag_pos(g, t, &x, &y);
    const double dx = X - x, dy = Y - y;
    if (dx * dx + dy * dy <= r2) {
      outcome = 5; idx = i; val = g->value;
      g->x = x; g->y = y; g->t = t; g->vx = g->vy = 0.0; g->speed = 0.0; g->t_stop = INFINITY;
      g->state = AS_HIDDEN; g->until = t + g->t_rest;  // its visibility changes at the group's end
      if (cnt) {
        c->eco_n[EL_PREY]++; c->eco_x[EL_PREYINC] = c->eco_x[EL_PREYINC] + val;
        c->income = c->income + val; c->captures++;
      }
    }
  }
  for (int i = 0; i < N_PLANT && outcome == 0; i++) {  // 2. a ripe plant
    Plant *P = &c->plant[i];
    if (P->state != 2) continue;
    const double dx = X - P->x, dy = Y - P->y;
    if (dx * dx + dy * dy <= r2) {
      outcome = 6; idx = i; val = c->plant_value;
      P->state = 0;  // its visibility changes at the group's end
      if (cnt) {
        c->eco_n[EL_HARVESTED]++; c->eco_x[EL_HARVESTINC] = c->eco_x[EL_HARVESTINC] + val;
        c->income = c->income + val; c->captures++;
      }
    }
  }
  for (int i = 0; i < c->n_src && outcome == 0; i++) {  // 3. a stocked source
    Src *S = &c->src[i];
    const double dx = X - S->x, dy = Y - S->y;
    if (S->stock <= 0 || dx * dx + dy * dy > r2) continue;
    S->stock--; idx = i; val = S->value;
    if (val < 0.0) {
      outcome = 2;
      if (cnt) { c->eco_n[EL_TOXIN]++; c->eco_x[EL_TOXINCOST] = c->eco_x[EL_TOXINCOST] + (-val); c->cost = c->cost + (-val); }
    } else if (c->carry_cap > 0 && c->n_item < c->carry_cap) {
      outcome = 3;
      Item *it = &c->item[c->n_item++];
      it->value = val; it->due = t + c->carry_digest; it->id = c->item_ids++;
      if (cnt) c->eco_n[EL_PICKED]++;
      eco_set_gam(c);
    } else {
      outcome = 1;
      if (cnt) {
        c->eco_n[EL_FOOD]++; c->eco_x[EL_FOODINC] = c->eco_x[EL_FOODINC] + val;
        c->income = c->income + val; c->captures++;
      }
    }
  }
  if (outcome == 0 && c->carry_cap > 0 && c->n_item > 0) {  // 4. home
    const double dx = X - c->home_x, dy = Y - c->home_y;
    if (dx * dx + dy * dy <= c->home_r * c->home_r) {
      outcome = 4; idx = c->n_item;
      for (int k = 0; k < c->n_item; k++) {
        const double v = c->item[k].value * c->carry_mult;
        val = val + v;
        if (cnt) {
          c->eco_n[EL_DELIVERED]++; c->eco_x[EL_DELIVERINC] = c->eco_x[EL_DELIVERINC] + v;
          c->income = c->income + v; c->captures++;
        }
      }
      c->n_item = 0;
      eco_set_gam(c);
    }
  }
  if (outcome == 0 && c->plant_cap > 0) {  // 5. planting in a fertile disk, away from every plant
    int fertile = 0, free_slot = -1, near = 0;
    for (int i = 0; i < c->n_fertile; i++) fertile |= in_disk2(X, Y, &c->fertile[i]);
    for (int i = 0; i < c->plant_cap; i++) {
      const Plant *P = &c->plant[i];
      if (P->state == 0) { if (free_slot < 0) free_slot = i; continue; }
      const double dx = X - P->x, dy = Y - P->y;
      if (dx * dx + dy * dy <= r2) near = 1;
    }
    if (fertile && !near && free_slot >= 0) {
      outcome = 7; idx = free_slot;
      Plant *P = &c->plant[free_slot];
      P->state = 1; P->vis = 0; P->x = X; P->y = Y; P->id = c->plant_ids++;
      P->t_ripe = t + (c->ripen_min + (c->ripen_max - c->ripen_min) * draw2(c->seed, S_ECO_PLANT, P->id, 0));
      P->t_spoil = P->t_ripe + c->ripe_win;
      if (cnt) {
        c->eco_n[EL_PLANTED]++; c->eco_x[EL_PLANTCOST] = c->eco_x[EL_PLANTCOST] + c->plant_cost;
        c->cost = c->cost + c->plant_cost;
      }
    }
  }
  if (outcome == 0 && cnt) { c->misses++; c->cost = c->cost + c->c_miss; }
  const uint64_t w[7] = {43, dbits(t), (uint64_t)outcome, (uint64_t)(int64_t)idx, dbits(val), dbits(X), dbits(Y)};
  eco_fold(c, w, 7);
  const uint64_t click[5] = {11, dbits(t), outcome == 0 ? 0 : 1, dbits(X), dbits(Y)};
  eco_fold(c, click, 5);
  if (outcome == 3 || outcome == 4) eco_kink(c);
}
static void eco_sample(Ctx *c, double cs) {  // 9.8.5: measurement only, at the left limit of integer time cs
  double X, Y;
  dot_at(c, cs, &X, &Y);
  if (cs >= c->t_open_abs) {
    c->samples++;
    double best = INFINITY;
    for (int i = 0; i < c->n_src; i++) {
      if (c->src[i].stock <= 0 || c->src[i].value <= 0.0) continue;
      const double dx = X - c->src[i].x, dy = Y - c->src[i].y, q = dx * dx + dy * dy;
      if (q < best) best = q;
    }
    if (best < INFINITY) {
      const double d = sqrt(best);
      c->dist_sum = c->dist_sum + d;
      if (best <= c->rho_c * c->rho_c) c->zone++;
      if (d <= c->rho_c + 1.0) c->eco_n[EL_NEARFOOD]++;
    }
    if (eco_sheltered(c, X, Y)) c->eco_n[EL_SHELTER]++;
    int threat = 0;
    for (int i = 0; i < c->n_ag && !threat; i++) {
      const Agent *g = &c->ag[i];
      if (g->type != AG_PURSUIT && g->type != AG_AMBUSH) continue;
      double x, y;
      ag_pos(g, cs, &x, &y);
      const double dx = X - x, dy = Y - y, q = dx * dx + dy * dy;
      if ((g->type == AG_PURSUIT && g->state == AS_ACTIVE && q <= 36.0) ||
          (g->type == AG_AMBUSH && g->state != AS_REST && q <= 9.0)) threat = 1;
    }
    if (threat) {
      c->eco_n[EL_THREAT]++;
      double v = 0.0;
      if (c->n_foot > 0) {
        const double e = exp(-(cs - c->t_x) / c->tau_z), fx = eff_fx(c) * e / c->gam, fy = eff_fy(c) * e / c->gam;
        v = sqrt(fx * fx + fy * fy);
      }
      if (v < 0.02) c->eco_n[EL_STILL]++;
    }
    if (c->home_r > 0.0) {
      const double dx = X - c->home_x, dy = Y - c->home_y;
      if (dx * dx + dy * dy <= c->home_r * c->home_r) c->eco_n[EL_HOME]++;
    }
    if (c->n_item > 0) c->eco_n[EL_LOADED]++;
    if (c->cur_speed > 0.0) {
      const double ux = c->cur_ux / c->cur_speed, uy = c->cur_uy / c->cur_speed;
      const double mx = X - c->samp_x, my = Y - c->samp_y, cr = mx * uy - my * ux;
      c->eco_x[EL_UPFLOW] = c->eco_x[EL_UPFLOW] + (-(mx * ux + my * uy));
      c->eco_x[EL_CROSSFLOW] = c->eco_x[EL_CROSSFLOW] + (cr < 0.0 ? -cr : cr);
    }
  }
  c->samp_x = X; c->samp_y = Y;
}
static void eco_start(Ctx *c) {  // 9.8.1, before the first time group
  const double *e = c->w + W_ECO;
  c->n_src = (int)e[E_NSRC]; c->n_ag = (int)e[E_NAG]; c->n_wall = (int)e[E_NWALL];
  c->n_shelter = (int)e[E_NSHELTER]; c->n_fertile = (int)e[E_NFERTILE];
  c->cur_speed = e[E_CURSPEED]; c->cur_head = e[E_CURHEAD]; c->cur_turn = e[E_CURTURN];
  c->cur_turn_max = e[E_CURTURNMAX];
  c->puff_sig0 = e[E_PUFFSIG0]; c->puff_D = e[E_PUFFD]; c->puff_life = e[E_PUFFLIFE]; c->puff_cut = e[E_PUFFCUT];
  c->puff_cap = (int64_t)e[E_PUFFCAP]; c->landmark = e[E_LANDMARK];
  c->sun_x = cos(e[E_SUNHEAD]); c->sun_y = sin(e[E_SUNHEAD]); c->vib_vref = e[E_VIBVREF]; c->r_body = e[E_RBODY];
  c->arena = e[E_ARENA]; c->kill_hits = (int)e[E_KILLHITS]; c->occlude = e[E_OCCLUDE] != 0.0;
  c->home_x = e[E_HOMEX]; c->home_y = e[E_HOMEY]; c->home_r = e[E_HOMER]; c->home_sig = e[E_HOMESIG];
  for (int k = 0; k < N_SPEC; k++) c->home_b[k] = e[E_HOMEB + k];
  c->carry_cap = (int)e[E_CARRYCAP]; c->carry_mult = e[E_CARRYMULT]; c->carry_digest = e[E_CARRYDIGEST];
  c->carry_drag = e[E_CARRYDRAG];
  c->plant_cap = (int)e[E_PLANTCAP]; c->plant_cost = e[E_PLANTCOST]; c->ripen_min = e[E_RIPENMIN];
  c->ripen_max = e[E_RIPENMAX]; c->ripe_win = e[E_RIPEWIN]; c->plant_value = e[E_PLANTVALUE];
  c->plant_sig = e[E_PLANTSIG]; c->plant_light = e[E_PLANTLIGHT];
  for (int k = 0; k < N_SPEC; k++) { c->plant_b[k] = e[E_PLANTB + k]; c->soil_b[k] = e[E_SOILB + k]; }
  c->soil_sig = e[E_SOILSIG];
  c->puff = malloc((size_t)(c->puff_cap > 0 ? c->puff_cap : 1) * sizeof(Puff));
  if (!c->puff) { c->fail |= FAIL_ALLOC; return; }
  c->puff_head = c->puff_n = 0;
  c->cur_ts = c->t0; c->cur_Ax = c->cur_Ay = 0.0;
  c->cur_ux = c->cur_speed * cos(c->cur_head); c->cur_uy = c->cur_speed * sin(c->cur_head);
  c->cur_next = c->cur_turn > 0.0 ? poisson_next(c->seed, S_ECO_CUR, 0, 0, c->t0, c->cur_turn) : INFINITY;
  c->cur_k = 1;
  for (int i = 0; i < c->n_src; i++) {
    const double *q = e + E_SRC + SRC_K * i;
    Src *S = &c->src[i];
    S->x = q[SK_X]; S->y = q[SK_Y]; S->value = q[SK_VALUE]; S->cap = (int64_t)q[SK_CAP]; S->stock = S->cap;
    S->period = q[SK_PERIOD]; S->light = q[SK_LIGHT]; S->sigma = q[SK_SIGMA]; S->puff_rate = q[SK_PUFF];
    for (int k = 0; k < N_SPEC; k++) S->b[k] = q[SK_B + k];
    S->first = c->t0 + q[SK_PHASE];
    if (!(S->first > c->t0)) S->first = nextafter(c->t0, INFINITY);
    S->next = S->period > 0.0 ? S->first : INFINITY; S->arrival_index = 0;
    S->next_puff = S->puff_rate > 0.0 ? poisson_next(c->seed, S_ECO_PUFF, (uint64_t)i, 0, c->t0, 1.0 / S->puff_rate)
                                      : INFINITY;
    S->puff_k = 1;
    c->src_left[i] = S->stock;
  }
  for (int i = 0; i < c->n_ag; i++) {
    const double *q = e + E_AG + AG_K * i;
    Agent *g = &c->ag[i];
    g->type = (int)q[AK_TYPE]; g->state = AS_WANDER; g->vis = 1;
    g->t = c->t0; g->x = q[AK_X]; g->y = q[AK_Y]; g->vx = g->vy = 0.0; g->speed = 0.0; g->t_stop = INFINITY;
    g->until = c->t0;
    g->v1 = q[AK_V1]; g->v2 = q[AK_V2]; g->r_sense = q[AK_RSENSE]; g->p = q[AK_P]; g->r_contact = q[AK_RCONTACT];
    g->value = q[AK_VALUE]; g->look = q[AK_LOOK]; g->t_state = q[AK_TSTATE]; g->t_rest = q[AK_TREST];
    g->sigma = q[AK_SIGMA]; g->light = q[AK_LIGHT];
    for (int k = 0; k < N_SPEC; k++) g->b[k] = q[AK_B + k];
    g->rx = q[AK_RX]; g->ry = q[AK_RY];
    g->q = 0;
    g->next_look = c->t0 + g->look * draw2(c->seed, S_ECO_AG, (uint64_t)i, ~0ULL);
  }
  for (int i = 0; i < c->n_wall; i++) {
    const double *q = e + E_WALL + 4 * i;
    c->wall[i].x0 = q[0]; c->wall[i].x1 = q[1]; c->wall[i].y0 = q[2]; c->wall[i].y1 = q[3];
  }
  for (int i = 0; i < c->n_shelter; i++) {
    const double *q = e + E_SHELTER + 3 * i;
    c->shelter[i].x = q[0]; c->shelter[i].y = q[1]; c->shelter[i].r = q[2];
  }
  for (int i = 0; i < c->n_fertile; i++) {
    const double *q = e + E_FERTILE + 3 * i;
    c->fertile[i].x = q[0]; c->fertile[i].y = q[1]; c->fertile[i].r = q[2];
  }
  for (int i = 0; i < N_PLANT; i++) { c->plant[i].state = 0; c->plant[i].vis = 0; }
  c->n_item = 0; c->plant_ids = c->item_ids = 0;
  c->blk_x = c->blk_y = 0; c->kink_t = INFINITY; c->samp_x = c->samp_y = 0.0; c->gam0 = 1.0;
  c->hits_all = 0; c->eco_dead = 0;
  const uint64_t w[7] = {48, dbits(c->t0), (uint64_t)c->n_src, (uint64_t)c->n_ag, (uint64_t)c->n_wall,
                         dbits(c->cur_ux), dbits(c->cur_uy)};
  eco_fold(c, w, 7);
}
static void eco_close(Ctx *c, double te) {  // 9.8.6: conservation checks and the end-of-life words
  for (int i = 0; i < c->n_src; i++) {
    const Src *S = &c->src[i];
    if (S->stock < 0 || S->stock > S->cap) c->status |= ST_MISMATCH;
    const uint64_t w[4] = {49, dbits(te), (uint64_t)i, (uint64_t)S->stock};
    eco_fold(c, w, 4);
  }
  if (c->n_item < 0 || c->n_item > c->carry_cap || c->n_item > N_ITEM) c->status |= ST_MISMATCH;
  int planted = 0;
  for (int i = 0; i < N_PLANT; i++) planted += c->plant[i].state != 0;
  const uint64_t w[6] = {50, dbits(te), (uint64_t)c->n_item, (uint64_t)planted, (uint64_t)c->hits_all,
                         (uint64_t)c->eco_dead};
  eco_fold(c, w, 6);
}
static void catch_candidate_m(Ctx *c, const Rec *r, int cnt) {  // 9.8.2: modality m >= 1, thinning at the left limit
  const double t = r->t;
  Site *s = &c->sites[r->site];
  const int m = (int)r->i1;
  if (cnt) c->mod_cand[m]++;
  double X, Y, ox, oy;
  dot_at(c, t, &X, &Y);
  planar(c, s->a, s->b, &ox, &oy);
  const double rate = mod_rate(c, m, s, t, X + ox, Y + oy);
  const int acc = draw3(c->seed, S_RACC_M, r->u1, (uint64_t)m, r->u2) * c->lam_m[m] < rate;
  const uint64_t w[6] = {30, dbits(t), r->u1, (uint64_t)m, r->u2, (uint64_t)acc};
  eco_fold(c, w, 6);
  if (acc) {
    if (cnt) c->mod_accept[m]++;
    send_receptor_m(c, r->site, t + c->d_min, r->u1, m, r->u2);
  }
}

static void world_to(Ctx *c, double t) {  // strictly below t: timer, turn, then visibility; blob breaks earlier ties
  if (c->eco) { eco_world_to(c, t); return; }
  if (c->patch_count) {
    for (;;) {
      double best = INFINITY;
      int slot = -1, contact = 0;
      for (int i = 0; i < c->patch_count; i++) {
        if (c->patch[i].next < best) { best = c->patch[i].next; slot = i; contact = 0; }
        // Strict '<' plus slot order preserves (time, slot, passive-before-contact) ties.
        if (c->patch_contact_delay > 0.0 && c->patch[i].contact_pending && c->patch[i].contact_due < best) {
          best = c->patch[i].contact_due; slot = i; contact = 1;
        }
      }
      if (!(best < t)) break;
      if (contact) patch_contact_mature(c, slot);
      else patch_source(c, slot);
    }
    patch_window_before(c, t);
    return;
  }
  if (c->task_mode) {
    while (c->task_next < t) task_transition(c);
    return;
  }
  for (;;) {
    double best = INFINITY;
    int kind = -1, bb = -1;
    for (int k = 0; k < 2; k++)
      for (int b = 0; b < 2; b++) {
        if (!c->blob[b].exists) continue;
        const double tt = k == 0 ? c->blob[b].r : c->blob[b].tau;
        if (tt < best) { best = tt; kind = k; bb = b; }
      }
    if (c->visibility_next < best) { best = c->visibility_next; kind = 2; }
    if (!(best < t)) return;
    if (kind == 0) world_timer(c, bb);
    else if (kind == 1) world_turn(c, bb);
    else world_visibility(c);
  }
}
static void catch_sample(Ctx *c, double cs) {  // 9.7.6: an integer time, at the left limit; measurement only
  world_to(c, cs);
  if (c->eco) { eco_sample(c, cs); c->next_sample = cs + 1.0; return; }
  if (c->task_mode && c->task_phase != TASK_CHOICE) { c->next_sample = cs + 1.0; return; }
  double X, Y, x0, y0;
  dot_at(c, cs, &X, &Y);
  if (c->patch_count) patch_nearest(c, cs, &x0, &y0);
  else blob_at(&c->blob[0], cs, &x0, &y0);
  const double ex = X - x0, ey = Y - y0;
  double q = ex * ex + ey * ey;
  if (c->task_mode) {
    double x1, y1;
    blob_at(&c->blob[1], cs, &x1, &y1);
    const double fx = X - x1, fy = Y - y1, q1 = fx * fx + fy * fy;
    if (q1 < q) q = q1;
  }
  if (cs >= c->t_open_abs) {
    c->samples++;
    c->dist_sum = c->dist_sum + sqrt(q);
    if (q <= c->rho_c * c->rho_c) c->zone++;
  }
  c->next_sample = cs + 1.0;
}
static void catch_start(Ctx *c) {  // 9.7.1, before the first time group
  c->X = c->Y = c->Fx = c->Fy = 0.0; c->t_x = c->t0; c->n_foot = 0; c->n_fill = 0; c->n_col = 0; c->armed = 1; c->gam = 1.0;
  c->bright = 1; c->visibility_k = 0; c->visibility_next = INFINITY;
  if (c->eco) { eco_start(c); c->next_sample = c->t0 + 1.0; return; }
  if (c->patch_count) { patch_start(c); c->next_sample = c->t0 + 1.0; return; }
  if (c->task_mode) {
    c->task_trial = 0;
    task_enter(c, c->t0, TASK_SAMPLE);
    c->next_sample = c->t0 + 1.0;
    return;
  }
  c->blob[0].exists = 1; c->blob[0].present = 1;
  c->blob[1].exists = c->b2_amp > 0.0; c->blob[1].present = 0;
  for (int b = 0; b < 2; b++) {
    Blob *B = &c->blob[b];
    if (!B->exists) continue;
    blob_heading(c->seed, (uint64_t)b, 0, c->v_t, &B->vx, &B->vy);
    B->h = 1;
    B->tau = c->tau_turn > 0.0 ? poisson_next(c->seed, S_TURN, (uint64_t)b, 0, c->t0, c->tau_turn) : INFINITY;
    B->k = 1;
    B->r = (c->t_resp > 0.0 && (b == 0 || c->b2_mode == 1)) ? poisson_next(c->seed, S_RTIME, (uint64_t)b, 0, c->t0,
                                                                            c->t_resp) : INFINITY;
    B->m = 1;
    B->q = 0;
  }
  for (int b = 0; b < 2; b++)
    if (c->blob[b].exists) place(c, b, PL_START, c->t0);
  if (c->visibility_mode == 2)
    c->visibility_next = poisson_next(c->seed, S_VISIBILITY, 0, c->visibility_k++, c->t0, c->visibility_on);
  c->next_sample = c->t0 + 1.0;
}
static void defer_place(Ctx *c, int b, int cause) {
  if (c->n_dP >= 4) { c->fail |= FAIL_LIMIT; return; }
  c->dP[2 * c->n_dP] = b; c->dP[2 * c->n_dP + 1] = cause; c->n_dP++;
}
static void defer_occ(Ctx *c, int32_t si, int32_t add) {
  if (grow((void **)&c->dO, &c->cap_dO, c->n_dO + 2, sizeof(int32_t), 256)) { c->fail |= FAIL_ALLOC; return; }
  c->dO[c->n_dO++] = si; c->dO[c->n_dO++] = add;
}
static void catch_click(Ctx *c, double t) {  // 9.7.4: the screen registers a press at the hotspot, the dot itself
  if (c->eco) { eco_click(c, t); return; }
  if (c->patch_count) { patch_click(c, t); return; }
  double X, Y, x0, y0;
  dot_at(c, t, &X, &Y);
  blob_at(&c->blob[0], t, &x0, &y0);
  const double ex = X - x0, ey = Y - y0, d0 = ex * ex + ey * ey;
  const int cnt = t >= c->t_open_abs;
  uint64_t outcome = 0;
  if (cnt) c->clicks++;
  if (c->task_mode) {
    int slot = -1;
    if (c->task_phase == TASK_CHOICE && !c->task_consumed) {
      if (d0 <= c->rho_c * c->rho_c) slot = 0;
      else {
        double x1, y1;
        blob_at(&c->blob[1], t, &x1, &y1);
        const double fx = X - x1, fy = Y - y1;
        if (fx * fx + fy * fy <= c->b2_rho * c->b2_rho) slot = 1;
      }
    }
    if (slot >= 0) {
      outcome = (uint64_t)slot + 1;
      if (cnt) {
        if (slot == 0) c->captures++;
        else c->b2_clicks++;
      }
      task_resolve(c, t, slot == c->task_class ? 1 : 2, slot);
      c->task_defer_gap = 1;
    } else if (cnt) {
      c->misses++; c->cost = c->cost + c->c_miss;
    }
    const uint64_t w[5] = {11, dbits(t), outcome, dbits(X), dbits(Y)};
    fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
    return;
  }
  if (d0 <= c->rho_c * c->rho_c) {  // capture: the target is re-placed after every record of the group
    outcome = 1;
    if (cnt) {
      c->captures++; c->income = c->income + c->R_cap;
      if (!c->bright) c->low_light_captures++;
    }
    defer_place(c, 0, PL_CLICK);
    if (c->blob[1].exists && c->b2_mode == 0) defer_place(c, 1, PL_WITH);
  } else {
    int hit = 0;
    if (c->blob[1].exists && c->blob[1].present) {
      double x1, y1;
      blob_at(&c->blob[1], t, &x1, &y1);
      const double fx = X - x1, fy = Y - y1, d1 = fx * fx + fy * fy;
      hit = d1 <= c->b2_rho * c->b2_rho;
    }
    if (hit) {  // a click on the second blob
      outcome = 2;
      if (cnt) {
        c->b2_clicks++;
        if (c->b2_value > 0.0) c->income = c->income + c->b2_value;
        else if (c->b2_value < 0.0) c->cost = c->cost + (-c->b2_value);
      }
      if (c->b2_mode == 1) defer_place(c, 1, PL_CLICK);
    } else {  // a miss
      if (cnt) { c->misses++; c->cost = c->cost + c->c_miss; }
    }
  }
  const uint64_t w[5] = {11, dbits(t), outcome, dbits(X), dbits(Y)};
  fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
}
static void catch_stroke(Ctx *c, const Rec *r) {  // 9.7.2: R_SPIKE of an act-plane cell with kappa > 0
  const double t = r->t;
  dot_adv(c, t);
  Site *s = &c->sites[r->site];
  double nx = 0.0, ny = 0.0;  // the exposed face: in-plane neighbour sites outside O (walls count as empty)
  for (int d = 0; d < c->nplane; d++) {
    int32_t j = s->nbr[d];
    if (j < 0) {
      j = site_find(c, s->a + c->off_a[d], s->b + c->off_b[d], s->z);
      if (j >= 0) s->nbr[d] = j;
    }
    if (j < 0 || !c->sites[j].acc_occ) { nx = nx + c->unit[3 * d]; ny = ny + c->unit[3 * d + 1]; }
  }
  const double dz = r->x[1];
  if (dz > 0.0 && (nx != 0.0 || ny != 0.0)) {
    const double gdz = c->g_n * dz, ei = exp(-(t - s->tf) / c->tau_z);
    s->fx = s->fx * ei + gdz * nx; s->fy = s->fy * ei + gdz * ny; s->tf = t;
    c->Fx = c->Fx + gdz * nx; c->Fy = c->Fy + gdz * ny;
    if (t >= c->t_open_abs) c->nudges++;
    if (c->eco) eco_kink(c);
  }
  if (s->a == 0 && s->b == 0) {  // the hotspot (0, 0, 1): the key step with the record's zt and zn
    if (c->armed == 0 && r->x[2] < c->th_rel) c->armed = 1;
    if (c->armed == 1 && r->x[3] >= c->th_click) { c->armed = 0; catch_click(c, t); }
  }
}
static int column_live(const Ctx *c, const Site *s) {  // another live cell in the column (a, b) of s (9.7.2)
  for (int32_t z = 0; z < c->L_max; z++) {
    if (z == s->z) continue;
    const int32_t j = site_find(c, s->a, s->b, z);
    if (j >= 0 && c->sites[j].acc_live) return 1;
  }
  return 0;
}

// The filled footprint (9.7.2, 15.61): the n tiles of the occupied columns col[] (sorted by (b, a), distinct) plus
// every free tile they enclose (no path of edge-sharing free tiles to infinity). Row runs: each occupied row splits
// into free runs; its two unbounded runs and every run of a row next to an empty row are outside (node 0); runs of
// adjacent rows that share an edge are joined. O(n) time and memory. Returns -1 if the scratch cannot grow.
#define RUN_INF ((int64_t)1 << 40)
static int64_t fill_find(int64_t *par, int64_t x) {
  while (par[x] != x) { par[x] = par[par[x]]; x = par[x]; }
  return x;
}
static int64_t filled_count(const Col *col, int64_t n, int hex, FillBuf *fb) {
  if (n == 0) return 0;
  const int64_t need = 3 * n + 1;
  if (need > fb->cap) {
    int64_t c1 = fb->cap, c2 = fb->cap, c3 = fb->cap;  // the three arrays grow alike
    const size_t e8 = sizeof(int64_t);
    if (grow((void **)&fb->lo, &c1, need, e8, 256) || grow((void **)&fb->hi, &c2, need, e8, 256)
        || grow((void **)&fb->par, &c3, need, e8, 256))
      return -1;
    fb->cap = c1;
  }
  int64_t *lo = fb->lo, *hi = fb->hi, *par = fb->par;
  const int64_t dlo = hex ? -1 : 0, dhi = 0;  // a-offsets of the edge-sharing tiles in the row above (b + 1)
  lo[0] = -RUN_INF; hi[0] = RUN_INF; par[0] = 0;
  int64_t R = 1, ps = 0, pe = 0, i = 0;
  int32_t pb = 0;
  while (i < n) {
    const int32_t b = col[i].b;
    int64_t j = i;
    while (j + 1 < n && col[j + 1].b == b) j++;
    const int below = pe > ps && pb == b - 1, above = j + 1 < n && col[j + 1].b == b + 1;
    const int64_t s = R;
    lo[R] = -RUN_INF; hi[R] = (int64_t)col[i].a - 1; par[R] = 0; R++;
    for (int64_t k = i; k < j; k++)
      if (col[k + 1].a > col[k].a + 1) {
        lo[R] = (int64_t)col[k].a + 1; hi[R] = (int64_t)col[k + 1].a - 1; par[R] = (below && above) ? R : 0; R++;
      }
    lo[R] = (int64_t)col[j].a + 1; hi[R] = RUN_INF; par[R] = 0; R++;
    if (below) {  // join each run of row b - 1 to the runs of row b it shares an edge with
      int64_t p = ps, q = s;
      while (p < pe && q < R) {
        const int64_t l1 = lo[p] + dlo, h1 = hi[p] + dhi;
        if ((l1 > lo[q] ? l1 : lo[q]) <= (h1 < hi[q] ? h1 : hi[q])) {
          const int64_t x = fill_find(par, p), y = fill_find(par, q);
          if (x < y) par[y] = x; else par[x] = y;
        }
        if (h1 < hi[q]) p++;
        else if (hi[q] < h1) q++;
        else { p++; q++; }
      }
    }
    ps = s; pe = R; pb = b; i = j + 1;
  }
  int64_t filled = n;
  for (int64_t r = 1; r < R; r++)
    if (lo[r] != -RUN_INF && hi[r] != RUN_INF && fill_find(par, r) != 0) filled += hi[r] - lo[r] + 1;
  return filled;
}
static inline int col_less(Col x, Col y) { return x.b != y.b ? x.b < y.b : x.a < y.a; }
static int64_t col_pos(const Ctx *c, Col x) {  // the first index whose column is not below x
  int64_t lo = 0, hi = c->n_col;
  while (lo < hi) {
    const int64_t m = lo + (hi - lo) / 2;
    if (col_less(c->col[m], x)) lo = m + 1; else hi = m;
  }
  return lo;
}
// The column (a, b) of s gains its first or loses its last live cell: P changes, and n_fill and gam follow (15.61).
static void footprint_change(Ctx *c, const Site *s, int add) {
  const Col x = {s->a, s->b};
  const int64_t k = col_pos(c, x);
  if (add) {
    if (grow((void **)&c->col, &c->cap_col, c->n_col + 1, sizeof(Col), 64)) { c->fail |= FAIL_ALLOC; return; }
    memmove(&c->col[k + 1], &c->col[k], (size_t)(c->n_col - k) * sizeof(Col));
    c->col[k] = x; c->n_col++;
  } else {
    memmove(&c->col[k], &c->col[k + 1], (size_t)(c->n_col - k - 1) * sizeof(Col));
    c->n_col--;
  }
  const int64_t nf = filled_count(c->col, c->n_col, c->base == 0, &c->fill);
  if (nf < 0) { c->fail |= FAIL_ALLOC; return; }
  c->n_fill = nf;
  if (nf > 0) {
    if (c->eco) { c->gam0 = pow((double)nf, c->drag_exp); eco_set_gam(c); }
    else c->gam = pow((double)nf, c->drag_exp);
  }
}
static void catch_birth(Ctx *c, const Rec *r) {  // 9.7.2
  const double t = r->t;
  Site *s = &c->sites[r->site];
  dot_adv(c, t);
  if (!column_live(c, s)) footprint_change(c, s, 1);  // drag: the filled footprint (15.59, 15.61)
  s->acc_live = 1;
  if (s->z == 0) { c->n_foot += 1; if (c->eco) defer_occ(c, r->site, 3); }
  if (s->z == 1) { s->fx = 0.0; s->fy = 0.0; s->tf = t; defer_occ(c, r->site, 1); }
  if (c->eco) eco_kink(c);
}
static void catch_death(Ctx *c, const Rec *r) {  // 9.7.2: a dead cell stops pulling (15.43)
  const double t = r->t;
  Site *s = &c->sites[r->site];
  dot_adv(c, t);
  s->acc_live = 0;
  if (!column_live(c, s)) footprint_change(c, s, 0);
  if (s->z == 0) { c->n_foot -= 1; if (c->eco) defer_occ(c, r->site, 2); }
  if (s->z == 1) {
    const double ei = exp(-(t - s->tf) / c->tau_z);
    c->Fx = c->Fx - s->fx * ei; c->Fy = c->Fy - s->fy * ei;
    defer_occ(c, r->site, 0);
  }
  if (c->eco) eco_kink(c);
}
static void send_receptor(Ctx *c, int32_t si, double t, uint64_t uid, uint64_t j) {  // 9.7.5: the world's message
  if (c->window && t < c->wend) c->fail |= FAIL_CAUSAL;  // it must land in a later window (11.2)
  int32_t ei;
  Ev *e = ev_make(c, &ei, t, si, G_MEMB, M_RECEPT);
  if (!e) return;
  e->uid = uid; e->u2 = j;
  push_ev(c, ei);
}
static void send_receptor_m(Ctx *c, int32_t si, double t, uint64_t uid, int m, uint64_t j) {  // ABI 8 (9.8.2)
  if (c->window && t < c->wend) c->fail |= FAIL_CAUSAL;
  int32_t ei;
  Ev *e = ev_make(c, &ei, t, si, G_MEMB, M_RECEPTM);
  if (!e) return;
  e->uid = uid; e->u2 = ((uint64_t)m << MJ_SHIFT) | j;
  push_ev(c, ei);
}
static void catch_candidate(Ctx *c, const Rec *r, int cnt) {  // 9.7.5: thinning at the left limit
  const double t = r->t;
  const Site *s = &c->sites[r->site];
  if (cnt) c->rec_cand++;
  double X, Y, ox, oy, x0, y0;
  dot_at(c, t, &X, &Y);
  planar(c, s->a, s->b, &ox, &oy);
  const double px = X + ox, py = Y + oy;
  double rate;
  if (c->eco) rate = eco_light(c, t, px, py);
  else if (c->patch_count) rate = patch_rate(c, px, py);
  else {
    blob_at(&c->blob[0], t, &x0, &y0);
    rate = c->task_mode && !c->blob[0].present ? c->lam_bg :
                  c->lam_bg + c->lam_s * halo(px - x0, py - y0, c->sigma);
    if (c->visibility_mode != 0 && !c->bright)
      rate = c->lam_bg + c->visibility_low * (c->lam_s * halo(px - x0, py - y0, c->sigma));
    if (c->blob[1].exists && c->blob[1].present) {
      double x1, y1;
      blob_at(&c->blob[1], t, &x1, &y1);
      rate = rate + c->lam_s * (c->b2_amp * halo(px - x1, py - y1, c->b2_sigma));
    }
  }
  const int acc = draw2(c->seed, S_RACC, r->u1, r->u2) * c->lam_max < rate;
  const uint64_t w[5] = {9, dbits(t), r->u1, r->u2, (uint64_t)acc};
  fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
  if (acc) {
    if (cnt) c->rec_accept++;
    send_receptor(c, r->site, t + c->d_min, r->u1, r->u2);
  }
}

static void acc_record(Ctx *c, const Rec *r) {  // 9.1
  const double t = r->t;
  const int cnt = t >= c->t_open_abs;
  while (c->fl_n > 0 && c->fl_q[c->fl_head].t_arr < t) {  // packets whose arrival the accountant has passed
    c->fl_head = (c->fl_head + 1) % c->fl_cap;
    c->fl_n--;
  }
  uint64_t w[6];
  const int catch_ = c->kind == WK_CATCH;
  switch (r->kind) {
    case R_BIRTH:
      if (catch_) catch_birth(c, r);
      else world_adv(c, t);
      c->n += 1;
      c->n_plane[plane_of(c->sites[r->site].z)] += 1;
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
        if (catch_) {  // only act-plane strokes reach the CATCH world (rule N1), unless motor_off (12)
          if (c->sites[r->site].z == 1 && !(flags_at(c, t) & F_MOTOR_OFF)) catch_stroke(c, r);
        } else {
          world_adv(c, t);
          c->A = c->A + r->x[1];
          if (c->above == 0 && c->A / (double)c->n > c->th) {
            c->above = 1;
            if (cnt) c->beats++;
          }
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
      tick_charge(c, t, r->x[0], r->x[1], plane_of(c->sites[r->site].z));
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
      if (catch_) {
        c->n -= 1;
        catch_death(c, r);
      } else {
        world_adv(c, t);
        c->A = c->A - r->x[0];
        if (c->A < 0) c->A = 0.0;
        c->n -= 1;
        if (c->n == 0) c->A = 0.0;
      }
      c->n_plane[plane_of(c->sites[r->site].z)] -= 1;
      if (cnt) {
        if (r->i1 == 3) c->kills++;
        else c->deaths++;
      }
      c->m_lost = c->m_lost + r->x[1];
      fate_log(c, 2, r, r->u1, r->u2, r->i1, r->x[2]);
      w[0] = 3; w[1] = dbits(t); w[2] = r->u1; w[3] = (uint64_t)r->i1;
      fold(c, H_FATE, w, 4); fold(c, H_ALL, w, 4);
      break;
    case R_RCAND:  // only CATCH lives have receptor candidates
      if (catch_) catch_candidate(c, r, cnt);
      break;
    case R_RCANDM:  // ABI 8 modality candidates (bound modalities only)
      if (catch_) catch_candidate_m(c, r, cnt);
      break;
    case R_RECEPTM: {
      const int m = (int)r->u2;
      const double gr = r->x[0], ga = fabs(gr) * (double)r->i1;
      if (cnt) {
        c->mod_events[m] += r->i1;
        c->mod_gain[m] = c->mod_gain[m] + ga;
        c->cost = c->cost + c->c_rec * ga;
      }
      w[0] = 31; w[1] = dbits(t); w[2] = r->u1; w[3] = (uint64_t)m; w[4] = (uint64_t)r->i1; w[5] = dbits(gr);
      fold(c, H_WORLD, w, 6); fold(c, H_ALL, w, 6);
      break;
    }
    case R_RECEPT: {
      const double gr = r->x[0], ga = fabs(gr) * (double)r->i1;
      if (cnt) {
        c->rec_events += r->i1;
        c->rec_gain = c->rec_gain + ga;
        c->cost = c->cost + c->c_rec * ga;
      }
      w[0] = 10; w[1] = dbits(t); w[2] = r->u1; w[3] = (uint64_t)r->i1; w[4] = dbits(gr);
      fold(c, H_WORLD, w, 5); fold(c, H_ALL, w, 5);
      break;
    }
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

static void group_begin(Ctx *c, double t) {  // CATCH: every world event below t first (9.7.1)
  if (c->kind == WK_CATCH) {
    world_to(c, t);
    if (c->patch_count)
      for (int i = 0; i < c->patch_count; i++) c->patch_left[i] = c->patch[i].stock;
    if (c->eco)
      for (int i = 0; i < c->n_src; i++) c->src_left[i] = c->src[i].stock;
  }
}

static void group_end(Ctx *c, double t) {
  if (c->kind == WK_CATCH) {  // the group's deferred writes: the changes of O, then its click's placements (15.46)
    for (int64_t i = 0; i < c->n_dO; i += 2) {
      if (c->dO[i + 1] >= 2) c->sites[c->dO[i]].acc_occ0 = c->dO[i + 1] - 2;  // ABI 8: O0
      else c->sites[c->dO[i]].acc_occ = c->dO[i + 1];
    }
    c->n_dO = 0;
    if (c->eco) {  // clicks change what prey and plants emit only from the group's end (left-limit fields)
      for (int i = 0; i < c->n_ag; i++) {
        Agent *g = &c->ag[i];
        g->vis = g->state != AS_HIDDEN && !(g->type == AG_FREEZER && g->state == AS_ACTIVE);
      }
      for (int i = 0; i < N_PLANT; i++) c->plant[i].vis = c->plant[i].state == 2;
    }
    for (int i = 0; i < c->n_dP; i++) place(c, c->dP[2 * i], c->dP[2 * i + 1], t);
    c->n_dP = 0;
    if (c->task_mode && c->task_defer_gap) task_enter(c, t, TASK_GAP);
  }
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
  group_begin(c, tg);
  for (int64_t i = 0; i < c->n_rec; i++) {
    const Rec *r = &c->rec[idx[i]];
    if (r->t != tg) { group_end(c, tg); tg = r->t; group_begin(c, tg); }
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
  if (trip) { c->guard = 1; c->t_end = cg; return 1; }
  if (c->eco_dead) { c->status |= ST_KILLED; c->t_end = cg; return 1; }  // ABI 8: the body was killed before cg
  return 0;
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
  if (c->kind == WK_CATCH) {  // the rest of the timeline: samples at integer c < t_end, world events below t_end
    while (c->next_sample < te) catch_sample(c, c->next_sample);
    world_to(c, te);
    dot_adv(c, te);
    if (c->task_mode) task_close(c, te);
    if (c->patch_count) patch_close(c, te);
    if (c->eco) eco_close(c, te);
  } else {
    world_adv(c, te);
  }
  int64_t nl = 0;
  uint64_t *live = malloc((size_t)(c->n_sites > 0 ? c->n_sites : 1) * 2 * sizeof(uint64_t));
  if (!live) { c->fail |= FAIL_ALLOC; }
  else {
    for (int64_t s = 0; s < c->n_sites; s++)
      if (c->sites[s].cell >= 0) { live[2 * nl] = c->sites[s].sk; live[2 * nl + 1] = (uint64_t)s; nl++; }
    if (nl > 1) qsort(live, (size_t)nl, 2 * sizeof(uint64_t), site_sk_cmp);
    for (int64_t i = 0; i < nl; i++) {
      const Site *s = &c->sites[live[2 * i + 1]];
      Cell *X = &c->cells[s->cell];
      tick_charge(c, te, X->t_prev, X->th[K_SEC0] + X->th[K_SEC1], plane_of(s->z));
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
  col = col + c->c_miss * (double)c->misses;  // the CATCH charges: +0.0 each in a BELL life
  col = col + c->c_rec * c->rec_gain;
  if (c->task_mode)
    col = col + c->c_b2 * (double)(c->task_counts[TC_WRONG][0] + c->task_counts[TC_WRONG][1]);
  else col = col + c->c_b2 * (double)c->b2_clicks;
  for (int m = 1; m < S_MAX; m++) col = col + c->c_rec * c->mod_gain[m];  // ABI 8 modality receptor costs
  col = col + c->eco_x[EL_TOXINCOST];
  col = col + c->eco_x[EL_DAMAGECOST];
  col = col + c->eco_x[EL_PLANTCOST];
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
  L[L_CAPTURES] = (double)c->captures; L[L_MISSES] = (double)c->misses; L[L_CLICKS] = (double)c->clicks;
  L[L_B2CLICKS] = (double)c->b2_clicks; L[L_RESPAWNS] = (double)c->respawns; L[L_NUDGES] = (double)c->nudges;
  L[L_RECCAND] = (double)c->rec_cand; L[L_RECACCEPT] = (double)c->rec_accept;
  L[L_RECEVENTS] = (double)c->rec_events; L[L_RECGAIN] = c->rec_gain; L[L_SAMPLES] = (double)c->samples;
  L[L_DISTSUM] = c->dist_sum; L[L_ZONE] = (double)c->zone; L[L_PATH] = c->path; L[L_XEND] = c->X;
  L[L_YEND] = c->Y; L[L_NSEND] = (double)c->n_plane[0]; L[L_NMEND] = (double)c->n_plane[1];
  L[L_NHEND] = (double)c->n_plane[2]; L[L_LIVES] = c->live_plane[0]; L[L_LIVEM] = c->live_plane[1];
  L[L_LIVEH] = c->live_plane[2];
  L[L_LOWCAPTURES] = (double)c->low_light_captures;
  for (int k = 0; k < TC_COUNT; k++)
    for (int cls = 0; cls < 2; cls++) L[L_CHOICEOPEN_N + 2 * k + cls] = (double)c->task_counts[k][cls];
  for (int i = 0; i < 4; i++) {
    for (int k = 0; k < 7; k++) L[L_PATCHOPEN + 4 * k + i] = (double)c->patch_counts[k][i];
    L[L_PATCHINITIAL + i] = (double)c->patch_counts[PC_INITIAL][i];
    L[L_PATCHREFILL + i] = (double)c->patch_counts[PC_REFILL][i];
    for (int k = 0; k < CC_COUNT; k++) L[L_CONTACTSTARTS + 4 * k + i] = (double)c->contact_counts[k][i];
  }
  L[L_PATCHGEOM] = (double)c->patch_geometric_misses;
  for (int m = 1; m < S_MAX; m++) {
    L[L_MODCAND + m - 1] = (double)c->mod_cand[m]; L[L_MODACCEPT + m - 1] = (double)c->mod_accept[m];
    L[L_MODEVENTS + m - 1] = (double)c->mod_events[m]; L[L_MODGAIN + m - 1] = c->mod_gain[m];
  }
  c->eco_n[EL_KILLED] = c->eco_dead;
  {
    static const int sums[] = {EL_FOODINC, EL_TOXINCOST, EL_PREYINC, EL_PLANTCOST, EL_HARVESTINC, EL_DELIVERINC,
                               EL_DIGESTINC, EL_DAMAGECOST, EL_UPFLOW, EL_CROSSFLOW};
    int is_sum[EL_COUNT] = {0};
    for (size_t k = 0; k < sizeof sums / sizeof sums[0]; k++) is_sum[sums[k]] = 1;
    for (int k = 0; k < EL_COUNT; k++) L[L_ECO + k] = is_sum[k] ? c->eco_x[k] : (double)c->eco_n[k];
  }
  for (int i = 0; i < LEDGER_SIZE; i++) { uint64_t wv = dbits(L[i]); fold(c, H_ALL, &wv, 1); }
}

// ------------------------------------------------------------------------------------------- schedulers
static void start_life(Ctx *c, const int32_t *init, int32_t n_init) {  // all initial cells are born at t0 (7.6)
  int32_t zero[4] = {0, 0, 0, -1};
  if (n_init <= 0) { init = zero; n_init = 1; }
  for (int32_t j = 0; j < n_init && !c->fail; j++) {
    const int32_t *ic = init + 4 * j;  // (a, b, z, row)
    int32_t si = site_get(c, ic[0], ic[1], ic[2]);
    if (si < 0) return;
    c->cur_site = si; c->cur_t = c->t0; c->seq = 0;
    c->fl = c->flags | (c->t0 >= c->t_fork_abs ? c->fork_flags : 0);
    const uint64_t uid = hash1(c->seed, S_ZYG, (uint64_t)j) | 1ULL;
    birth(c, si, c->t0, uid, 0, 0, c->prog ? NULL : c->gt + GO_G0, 0.0, j, c->prog ? ic[3] : -1);
  }
  flush(c);
}

// a guard time c (section 10): the guards, then (CATCH, unless a guard tripped) the sample of 9.7.6; 1 = tripped
static int guard_time(Ctx *c, double cg) {
  if (guard_check(c, cg)) return 1;
  if (c->kind == WK_CATCH) catch_sample(c, cg);
  return 0;
}

static void run_heap(Ctx *c) {  // 11.1; a flush can create events (RECEPTORs), so the loop runs until none is left
  double next_guard = c->t0 + 1.0;
  int stop = 0;
  while (!stop && !c->fail && c->heap.n > 0) {
    const double t = c->heap.a[0].t;
    if (t >= c->t1) break;
    while (next_guard < c->t1 && next_guard <= t) {
      if (guard_time(c, next_guard)) { stop = 1; break; }
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
      if (guard_time(c, next_guard)) break;
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
    flush(c);  // RECEPTORs sent here land at t + d_min >= wend, in a later window
    if ((k + 1) % per_unit == 0 && wend < c->t1 && guard_time(c, wend)) return;
  }
}

// ---------------------------------------------------------------------------------------------- validation
static int is_int(double x) { return isfinite(x) && x == floor(x); }

static int abi8_ok(const double *w);
static double eco_light_bound(const double *w);
static int world_ok(const double *w) {  // the rules of spec.validate_world (4.7)
  for (int i = 0; i < WORLD_SIZE; i++) if (!isfinite(w[i])) return 0;
  if (w[W_KILLRATE] != 0.0 || w[W_WOUNDRATE] != 0.0 || w[W_DRIFTTAU] != 0.0) return 0;
  if (!(w[W_T] > 0.0) || !is_int(w[W_T]) || !is_int(w[W_T0])) return 0;
  if (w[W_T] > TIME_MAX || fabs(w[W_T0]) > TIME_MAX) return 0;
  const int ints[14] = {W_NMAX, W_EMAX, W_FABRICR, W_ORACLE, W_STUCKA, W_STUCKB, W_WORLDKIND, W_LMAX, W_STUCKZ,
                        W_B2MODE, W_VISMODE, W_TASKMODE, W_PATCHCOUNT, W_PATCHCAP};
  for (int i = 0; i < 14; i++) if (!is_int(w[ints[i]])) return 0;
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
  // ABI 3 keys (41-65): they hold for every world kind, so validity never depends on the kind
  if (!(w[W_WORLDKIND] == 0.0 || w[W_WORLDKIND] == 1.0)) return 0;
  if (!(w[W_LMAX] >= 1.0 && w[W_LMAX] <= (double)LMAX_MAX && w[W_STUCKZ] >= 0.0 && w[W_STUCKZ] < w[W_LMAX])) return 0;
  if (!(w[W_SIGMA] > 0.0 && w[W_SIGMA] <= LENGTH_MAX && w[W_B2SIGMA] > 0.0 && w[W_B2SIGMA] <= LENGTH_MAX)) return 0;
  if (!(w[W_LAMS] >= 0.0 && w[W_LAMBG] >= 0.0 && w[W_B2AMP] >= 0.0)) return 0;
  if (!(w[W_LAMBG] + w[W_LAMS] * (1.0 + w[W_B2AMP]) <= RATE_MAX)) return 0;
  if (!(w[W_GN] >= 0.0 && w[W_GN] <= SPEED_MAX && w[W_VT] >= 0.0 && w[W_VT] <= SPEED_MAX)) return 0;
  if (!(w[W_DRAGEXP] >= 0.0 && w[W_DRAGEXP] <= 2.0)) return 0;
  if (!(w[W_THREL] >= 0.0 && w[W_THREL] < w[W_THCLICK] && w[W_THCLICK] <= 1.0)) return 0;
  if (!(w[W_RHOC] >= 0.0 && w[W_B2RHO] >= 0.0 && w[W_RMIN] >= 0.0 && w[W_RMIN] <= w[W_RMAX] &&
        w[W_RMAX] <= LENGTH_MAX)) return 0;
  if (!(w[W_TAUTURN] >= 0.0 && w[W_TAUTURN] <= TIME_MAX && w[W_TRESP] >= 0.0 && w[W_TRESP] <= TIME_MAX)) return 0;
  if ((w[W_TAUTURN] > 0.0 && w[W_TAUTURN] < STEP_MIN) || (w[W_TRESP] > 0.0 && w[W_TRESP] < STEP_MIN)) return 0;
  if (!(w[W_RCAP] >= 0.0 && w[W_CMISS] >= 0.0 && w[W_CREC] >= 0.0)) return 0;
  if (!(w[W_B2P] >= 0.0 && w[W_B2P] <= 1.0 && (w[W_B2MODE] == 0.0 || w[W_B2MODE] == 1.0))) return 0;
  // ABI 4: one neutral representation; enabled visibility applies only to a single CATCH target.
  if (!(w[W_VISMODE] >= 0.0 && w[W_VISMODE] <= 2.0 && w[W_VISLOW] >= 0.0 && w[W_VISLOW] <= 1.0)) return 0;
  if (w[W_VISMODE] == 0.0) {
    if (w[W_VISON] != 0.0 || w[W_VISOFF] != 0.0 || w[W_VISLOW] != 1.0) return 0;
  } else {
    if (w[W_WORLDKIND] != WK_CATCH || w[W_B2AMP] != 0.0) return 0;
    if (!(w[W_VISON] >= STEP_MIN && w[W_VISON] <= TIME_MAX)) return 0;
    if (w[W_VISMODE] == 1.0) {
      if (w[W_VISOFF] != 0.0) return 0;
    } else if (!(w[W_VISOFF] >= STEP_MIN && w[W_VISOFF] <= TIME_MAX)) return 0;
  }
  // ABI 5: the first delayed-match mode has a small, explicit stationary-world contract.
  if (w[W_TASKMODE] == 0.0) {
    for (int i = W_SAMPLEMIN; i <= W_RESETT; i++) if (w[i] != 0.0) return 0;
  } else if (w[W_TASKMODE] == 1.0) {
    for (int i = W_SAMPLEMIN; i <= W_RESETT; i++)
      if (!(w[i] >= STEP_MIN && w[i] <= TIME_MAX)) return 0;
    if (!(w[W_SAMPLEMIN] <= w[W_SAMPLEMAX] && w[W_BLANKMIN] <= w[W_BLANKMAX] &&
          w[W_BLANKMIN] > w[W_DMIN])) return 0;
    if (w[W_WORLDKIND] != WK_CATCH || w[W_VISMODE] != 0.0 ||
        w[W_VT] != 0.0 || w[W_TAUTURN] != 0.0 || w[W_TRESP] != 0.0) return 0;
    if (w[W_B2AMP] != 1.0 || w[W_B2P] != 1.0 || w[W_B2MODE] != 0.0) return 0;
    if (!(w[W_SIGMA] < w[W_B2SIGMA] && w[W_RHOC] == w[W_B2RHO] &&
          2.0 * w[W_RMIN] > w[W_RHOC] + w[W_B2RHO] && w[W_B2VALUE] < 0.0)) return 0;
  } else return 0;
  if (w[W_PATCHCOUNT] == 0.0) {
    for (int i = W_PATCHCAP; i <= W_PATCHCONTACT; i++) if (w[i] != 0.0) return 0;
  } else {
    if (!(w[W_PATCHCOUNT] >= 1.0 && w[W_PATCHCOUNT] <= 4.0 &&
          w[W_PATCHCAP] >= 1.0 && w[W_PATCHCAP] <= 1048576.0)) return 0;
    if (w[W_WORLDKIND] != WK_CATCH || w[W_TASKMODE] != 0.0 || w[W_VISMODE] != 0.0 ||
        w[W_VT] != 0.0 || w[W_TAUTURN] != 0.0 || w[W_TRESP] != 0.0 || w[W_B2AMP] != 0.0 ||
        w[W_B2VALUE] != 0.0 || w[W_B2MODE] != 0.0 || w[W_B2P] != 1.0) return 0;
    if (!(w[W_PATCHFAST] >= STEP_MIN && w[W_PATCHFAST] <= w[W_PATCHSLOW] &&
          w[W_PATCHSLOW] <= TIME_MAX && w[W_PATCHLAND] >= 0.0 && w[W_PATCHLAND] < 1.0)) return 0;
    if (!(w[W_RHOC] > 0.0 && w[W_RMIN] >= 2.0 * w[W_RHOC])) return 0;
    if (!(w[W_LAMBG] + w[W_LAMS] * w[W_PATCHCOUNT] <= RATE_MAX)) return 0;
    if (!(w[W_PATCHCOUNT] * (ceil(w[W_T] / w[W_PATCHFAST]) + 1.0) <= 1048576.0)) return 0;
    if (w[W_PATCHCONTACT] != 0.0) {
      if (!(w[W_PATCHCONTACT] >= STEP_MIN && w[W_PATCHCONTACT] <= TIME_MAX)) return 0;
      if (!(w[W_PATCHCOUNT] * (ceil(w[W_T] / w[W_PATCHFAST]) + ceil(w[W_T] / w[W_PATCHCONTACT]) + 2.0)
            <= 1048576.0)) return 0;
    }
  }
  return abi8_ok(w);
}

// ABI 8: the largest light rate of an eco life (sources, plants, agents), the bound of modality 0's thinning
static double eco_light_bound(const double *w) {
  const double *e = w + W_ECO;
  double L = 0.0;
  for (int i = 0; i < (int)e[E_NSRC]; i++) L = L + e[E_SRC + SRC_K * i + SK_LIGHT];
  L = L + e[E_PLANTCAP] * e[E_PLANTLIGHT];
  for (int i = 0; i < (int)e[E_NAG]; i++) L = L + e[E_AG + AG_K * i + AK_LIGHT];
  return L;
}
static int all_zero(const double *x, int n) {
  for (int i = 0; i < n; i++) if (x[i] != 0.0) return 0;
  return 1;
}
static int abi8_ok(const double *w) {  // the ABI 8 rules of spec.validate_world (modality slots, the eco block)
  const double *e = w + W_ECO;
  if (!(e[E_MODE] == 0.0 || e[E_MODE] == 1.0)) return 0;
  for (int m = 1; m < S_MAX; m++) {
    const double *q = w + W_MOD + N_MODK * (m - 1);
    const double k = q[MK_KIND];
    if (!is_int(k) || k < 0.0 || k >= (double)MOD_KINDS || !is_int(q[MK_ARG])) return 0;
    if (k == 0.0) { if (!all_zero(q, N_MODK)) return 0; continue; }
    if (e[E_MODE] != 1.0) return 0;
    if (!(q[MK_BG] >= 0.0 && q[MK_S] >= 0.0 && q[MK_BG] + q[MK_S] > 0.0 && q[MK_BG] + q[MK_S] <= RATE_MAX &&
          q[MK_K] > 0.0 && q[MK_K] <= LENGTH_MAX)) return 0;
    if (k == (double)MOD_ODOUR) { if (!(q[MK_ARG] >= 0.0 && q[MK_ARG] < (double)N_SPEC)) return 0; }
    else if (q[MK_ARG] != 0.0) return 0;
  }
  if (e[E_MODE] == 0.0) return all_zero(e + 1, ECO_SIZE - 1);
  if (w[W_WORLDKIND] != WK_CATCH || w[W_TASKMODE] != 0.0 || w[W_VISMODE] != 0.0 || w[W_PATCHCOUNT] != 0.0 ||
      w[W_B2AMP] != 0.0 || w[W_VT] != 0.0 || w[W_TAUTURN] != 0.0 || w[W_TRESP] != 0.0) return 0;
  const int counts[5] = {E_NSRC, E_NAG, E_NWALL, E_NSHELTER, E_NFERTILE}, caps[5] = {N_SRC, N_AG, N_WALL, N_DISK, N_DISK};
  for (int i = 0; i < 5; i++) if (!is_int(e[counts[i]]) || e[counts[i]] < 0.0 || e[counts[i]] > caps[i]) return 0;
  if (!(e[E_CURSPEED] >= 0.0 && e[E_CURSPEED] <= SPEED_MAX && e[E_CURTURN] >= 0.0 && e[E_CURTURN] <= TIME_MAX &&
        (e[E_CURTURN] == 0.0 || e[E_CURTURN] >= STEP_MIN) && e[E_CURTURNMAX] >= 0.0 && e[E_CURTURNMAX] <= 4.0 &&
        fabs(e[E_CURHEAD]) <= 64.0 && fabs(e[E_SUNHEAD]) <= 64.0)) return 0;
  if (!(e[E_PUFFSIG0] > 0.0 && e[E_PUFFSIG0] <= LENGTH_MAX && e[E_PUFFD] >= 0.0 && e[E_PUFFD] <= LENGTH_MAX &&
        e[E_PUFFLIFE] > 0.0 && e[E_PUFFLIFE] <= TIME_MAX && e[E_PUFFCUT] > 0.0 && e[E_PUFFCUT] <= 1024.0 &&
        is_int(e[E_PUFFCAP]) && e[E_PUFFCAP] >= 1.0 && e[E_PUFFCAP] <= 4096.0)) return 0;
  if (!(e[E_LANDMARK] >= 0.0 && e[E_LANDMARK] < 1.0 && e[E_VIBVREF] > 0.0 && e[E_RBODY] >= 0.0 &&
        e[E_RBODY] <= LENGTH_MAX && e[E_ARENA] > 0.0 && e[E_ARENA] <= LENGTH_MAX && is_int(e[E_KILLHITS]) &&
        e[E_KILLHITS] >= 0.0 && e[E_KILLHITS] <= 1048576.0 && (e[E_OCCLUDE] == 0.0 || e[E_OCCLUDE] == 1.0))) return 0;
  if (!(e[E_HOMER] >= 0.0 && e[E_HOMESIG] > 0.0 && e[E_PLANTSIG] > 0.0 && e[E_SOILSIG] > 0.0)) return 0;
  for (int k = 0; k < N_SPEC; k++)
    if (!(e[E_HOMEB + k] >= 0.0 && e[E_PLANTB + k] >= 0.0 && e[E_SOILB + k] >= 0.0)) return 0;
  if (!(is_int(e[E_CARRYCAP]) && e[E_CARRYCAP] >= 0.0 && e[E_CARRYCAP] <= N_ITEM && e[E_CARRYMULT] >= 0.0 &&
        e[E_CARRYDRAG] >= 0.0 && (e[E_CARRYCAP] == 0.0 || (e[E_CARRYDIGEST] >= STEP_MIN && e[E_CARRYDIGEST] <= TIME_MAX))))
    return 0;
  if (!(is_int(e[E_PLANTCAP]) && e[E_PLANTCAP] >= 0.0 && e[E_PLANTCAP] <= N_PLANT && e[E_PLANTCOST] >= 0.0 &&
        e[E_PLANTVALUE] >= 0.0 && e[E_PLANTLIGHT] >= 0.0)) return 0;
  if (e[E_PLANTCAP] > 0.0 && !(e[E_RIPENMIN] >= STEP_MIN && e[E_RIPENMAX] >= e[E_RIPENMIN] &&
                               e[E_RIPENMAX] <= TIME_MAX && e[E_RIPEWIN] >= STEP_MIN && e[E_RIPEWIN] <= TIME_MAX))
    return 0;
  const int ns = (int)e[E_NSRC], na = (int)e[E_NAG], nw = (int)e[E_NWALL];
  for (int i = 0; i < N_SRC; i++) {
    const double *q = e + E_SRC + SRC_K * i;
    if (i >= ns) { if (!all_zero(q, SRC_K)) return 0; continue; }
    if (!(is_int(q[SK_CAP]) && q[SK_CAP] >= 1.0 && q[SK_CAP] <= 1048576.0 && q[SK_PERIOD] >= 0.0 &&
          q[SK_PERIOD] <= TIME_MAX && (q[SK_PERIOD] == 0.0 || q[SK_PERIOD] >= STEP_MIN) && q[SK_PHASE] >= 0.0 &&
          q[SK_PHASE] <= TIME_MAX && q[SK_LIGHT] >= 0.0 && q[SK_SIGMA] > 0.0 && q[SK_SIGMA] <= LENGTH_MAX &&
          q[SK_PUFF] >= 0.0 && q[SK_PUFF] <= 16.0 && fabs(q[SK_X]) <= LENGTH_MAX && fabs(q[SK_Y]) <= LENGTH_MAX))
      return 0;
    for (int k = 0; k < N_SPEC; k++) if (!(q[SK_B + k] >= 0.0)) return 0;
  }
  for (int i = 0; i < N_AG; i++) {
    const double *q = e + E_AG + AG_K * i;
    if (i >= na) { if (!all_zero(q, AG_K)) return 0; continue; }
    if (!(is_int(q[AK_TYPE]) && q[AK_TYPE] >= 1.0 && q[AK_TYPE] < (double)AG_TYPES && q[AK_LOOK] >= 0.1 &&
          q[AK_LOOK] <= TIME_MAX && q[AK_V1] >= 0.0 && q[AK_V1] <= SPEED_MAX && q[AK_V2] >= 0.0 &&
          q[AK_V2] <= SPEED_MAX && q[AK_RSENSE] >= 0.0 && q[AK_RCONTACT] >= 0.0 && q[AK_P] >= 0.0 && q[AK_P] <= 1.0 &&
          q[AK_TSTATE] >= 0.0 && q[AK_TREST] >= 0.0 && q[AK_SIGMA] > 0.0 && q[AK_LIGHT] >= 0.0 &&
          fabs(q[AK_X]) <= LENGTH_MAX && fabs(q[AK_Y]) <= LENGTH_MAX && fabs(q[AK_RX]) <= LENGTH_MAX &&
          fabs(q[AK_RY]) <= LENGTH_MAX)) return 0;
    if (q[AK_TYPE] <= (double)AG_AMBUSH && !(q[AK_VALUE] >= 0.0)) return 0;  // damage is a charge
    for (int k = 0; k < N_SPEC; k++) if (!(q[AK_B + k] >= 0.0)) return 0;
  }
  for (int i = 0; i < N_WALL; i++) {
    const double *q = e + E_WALL + 4 * i;
    if (i >= nw) { if (!all_zero(q, 4)) return 0; continue; }
    if (!(q[0] < q[1] && q[2] < q[3] && fabs(q[0]) <= LENGTH_MAX && fabs(q[1]) <= LENGTH_MAX &&
          fabs(q[2]) <= LENGTH_MAX && fabs(q[3]) <= LENGTH_MAX)) return 0;
  }
  for (int g = 0; g < 2; g++) {
    const int base = g ? E_FERTILE : E_SHELTER, n = (int)e[g ? E_NFERTILE : E_NSHELTER];
    for (int i = 0; i < N_DISK; i++) {
      const double *q = e + base + 3 * i;
      if (i >= n) { if (!all_zero(q, 3)) return 0; continue; }
      if (!(q[2] > 0.0 && q[2] <= LENGTH_MAX && fabs(q[0]) <= LENGTH_MAX && fabs(q[1]) <= LENGTH_MAX)) return 0;
    }
  }
  if (!(w[W_LAMBG] + w[W_LAMS] * eco_light_bound(w) <= RATE_MAX)) return 0;
  if (!(w[W_RHOC] > 0.0)) return 0;
  return 1;
}

// 4.3: codes 0 hex (6), 1 square4 (4), 2 square8 (8), 3 hexprism (8), 4 square4prism (6), 5 square8prism (10);
// [code, D, off_a, off_b, off_z, back, prev, next, rot]; a prism's in-plane slots come first, then up and down
static int lattice_ok(const int32_t *lat) {
  static const int DEG[6] = {6, 4, 8, 8, 6, 10};
  const int code = lat[0], D = lat[1];
  if (code < 0 || code > 5 || D != DEG[code]) return 0;
  const int nplane = code >= 3 ? D - 2 : D;
  const int32_t *oa = lat + 2, *ob = oa + D, *oz = ob + D, *bk = oz + D, *pv = bk + D, *nx = pv + D, *rt = nx + D;
  for (int d = 0; d < D; d++) {
    if (bk[d] < 0 || bk[d] >= D || pv[d] < 0 || pv[d] >= D || nx[d] < 0 || nx[d] >= D || rt[d] < 0 || rt[d] >= D)
      return 0;
    if (oa[bk[d]] != -oa[d] || ob[bk[d]] != -ob[d] || oz[bk[d]] != -oz[d]) return 0;
    if (oa[d] == 0 && ob[d] == 0 && oz[d] == 0) return 0;
    if (oz[d] != (d < nplane ? 0 : (d == nplane ? 1 : -1))) return 0;
  }
  return 1;
}

// --------------------------------------------------------------------------------------------- one life
static void ctx_free(Ctx *c) {
  for (int64_t i = 0; i < c->cap_cell_pool; i++) free(c->cells[i].inbox);
  free(c->cells); free(c->sites); free(c->map); free(c->ev); free(c->blobs); free(c->blob_next);
  free(c->heap.a); free(c->local.a); free(c->wbuf); free(c->bbuf); free(c->rec); free(c->gsnap); free(c->ridx);
  free(c->fl_q); free(c->dO); free(c->col); free(c->fill.lo); free(c->fill.hi); free(c->fill.par);
  for (int i = 0; i < 4; i++) free(c->patch[i].origins);
  free(c->puff);
  for (int g = 0; g < 6; g++) free(c->grp[g]);
}

static int run_one(const int32_t *lat, const double *unit, const double *gt, const double *pg, const double *w,
                   const uint64_t *seeds, const int32_t *init, int32_t n_init, double *L, uint64_t *H,
                   int64_t raster_cap, double *raster_t, uint64_t *raster_uid, int64_t *raster_n, int64_t fate_cap,
                   int64_t *fate_i, double *fate_f, int64_t *fate_n) {
  Ctx *c = calloc(1, sizeof(Ctx));
  if (!c) return -3;
  c->w = w; c->gt = gt; c->pg = pg; c->unit = unit;
  c->code = lat[0]; c->D = lat[1]; c->base = c->code % 3; c->nplane = c->code >= 3 ? c->D - 2 : c->D;
  for (int d = 0; d < c->D; d++) {
    c->off_a[d] = lat[2 + d]; c->off_b[d] = lat[2 + c->D + d]; c->off_z[d] = lat[2 + 2 * c->D + d];
    c->back[d] = lat[2 + 3 * c->D + d]; c->prv[d] = lat[2 + 4 * c->D + d]; c->nxt[d] = lat[2 + 5 * c->D + d];
  }
  c->kind = (int)w[W_WORLDKIND]; c->L_max = (int)w[W_LMAX]; c->stuck_z = (int32_t)w[W_STUCKZ];
  for (int z = 0; z < c->L_max; z++) {  // the slots that stay inside the stack 0 <= z < L_max (4.3)
    uint32_t m = 0;
    for (int d = 0; d < c->D; d++) {
      const int zz = z + c->off_z[d];
      if (zz >= 0 && zz < c->L_max) m |= 1u << d;
    }
    c->smask[z] = m;
  }
  c->sigma = w[W_SIGMA]; c->lam_s = w[W_LAMS]; c->lam_bg = w[W_LAMBG]; c->g_n = w[W_GN]; c->drag_exp = w[W_DRAGEXP];
  c->th_click = w[W_THCLICK]; c->th_rel = w[W_THREL]; c->rho_c = w[W_RHOC]; c->v_t = w[W_VT];
  c->tau_turn = w[W_TAUTURN]; c->R_min = w[W_RMIN]; c->R_max = w[W_RMAX]; c->t_resp = w[W_TRESP];
  c->R_cap = w[W_RCAP]; c->c_miss = w[W_CMISS]; c->c_rec = w[W_CREC]; c->b2_amp = w[W_B2AMP];
  c->b2_sigma = w[W_B2SIGMA]; c->b2_value = w[W_B2VALUE]; c->b2_rho = w[W_B2RHO]; c->b2_p = w[W_B2P];
  c->b2_mode = (int)w[W_B2MODE];
  c->visibility_mode = (int)w[W_VISMODE]; c->visibility_on = w[W_VISON];
  c->visibility_off = w[W_VISOFF]; c->visibility_low = w[W_VISLOW];
  c->task_mode = (int)w[W_TASKMODE]; c->sample_min = w[W_SAMPLEMIN]; c->sample_max = w[W_SAMPLEMAX];
  c->blank_min = w[W_BLANKMIN]; c->blank_max = w[W_BLANKMAX];
  c->choice_T = w[W_CHOICET]; c->reset_T = w[W_RESETT]; c->task_next = INFINITY;
  c->patch_count = (int)w[W_PATCHCOUNT]; c->patch_capacity = (int)w[W_PATCHCAP];
  c->patch_fast = w[W_PATCHFAST]; c->patch_slow = w[W_PATCHSLOW]; c->patch_landmark = w[W_PATCHLAND];
  c->patch_contact_delay = w[W_PATCHCONTACT];
  c->lam_max = c->patch_count ? c->lam_bg + c->lam_s * (double)c->patch_count :
                              c->lam_bg + c->lam_s * (1.0 + c->b2_amp);
  c->eco = (int)w[W_ECO + E_MODE];
  if (c->eco) c->lam_max = c->lam_bg + c->lam_s * eco_light_bound(w);
  for (int m = 1; m < S_MAX; m++) {  // ABI 8 modality slots
    const double *q = w + W_MOD + N_MODK * (m - 1);
    c->mod_kind[m] = (int)q[MK_KIND]; c->mod_arg[m] = (int)q[MK_ARG];
    c->mod_bg[m] = q[MK_BG]; c->mod_s[m] = q[MK_S]; c->mod_K[m] = q[MK_K];
    c->lam_m[m] = c->mod_kind[m] != MOD_NONE ? c->mod_bg[m] + c->mod_s[m] : 0.0;
  }
  c->c_b2 = c->b2_value < 0.0 ? -c->b2_value : 0.0;
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
  c->wend = -INFINITY;
  for (int i = 0; i < HASH_SIZE; i++) c->H[i] = HASH_INIT;
  c->raster_cap = (raster_t && raster_uid) ? raster_cap : 0; c->raster_t = raster_t; c->raster_uid = raster_uid;
  c->fate_cap = (fate_i && fate_f) ? fate_cap : 0; c->fate_i = fate_i; c->fate_f = fate_f;
  c->want_g = c->fate_cap > 0 && !c->prog;
#ifdef LIFE_FAST
  if (!c->prog && c->gt) {  // the genome's nonzero readout columns and GRN weights (any bit set, so -0.0 counts)
    const double *A = c->gt + GO_A, *W = c->gt + GO_W;
    c->n_ract = 0;
    for (int k = 0; k < NG; k++) {
      int any = 0;
      for (int q = 0; q < NK; q++) any |= nzbits(A[q * NG + k]);
      if (any) c->ract[c->n_ract++] = (int8_t)k;
    }
    for (int k = 0; k < NG; k++) {
      c->n_wj[k] = 0;
      for (int j = 0; j < NIN; j++) if (nzbits(W[k * NIN + j])) c->wj[k][c->n_wj[k]++] = (int8_t)j;
    }
  }
#endif
  if (map_rehash(c, 1024)) { ctx_free(c); free(c); return -3; }
  if (c->kind == WK_CATCH) catch_start(c);  // the world exists before the first time group (9.7.1)
  if (c->fail & FAIL_ALLOC) { ctx_free(c); free(c); return -3; }
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

void life_decode(const double y[NK], double theta[NK]) { decode(y, theta); }

void life_readout(const double gt[GENOME_SIZE], const double g[16], double y[NK]) { readout(gt, g, y); }

// CATCH closed forms (9.7), each the spec.py function of the same name
double life_halo(double dx, double dy, double sigma) { return halo(dx, dy, sigma); }

void life_dot_gain(double dt, double tau_z, double gam, double out[2]) { dot_gain(dt, tau_z, gam, &out[0], &out[1]); }

void life_blob_heading(uint64_t seed, int32_t blob, uint64_t h, double v_t, double out[2]) {
  blob_heading(seed, (uint64_t)(int64_t)blob, h, v_t, &out[0], &out[1]);
}

void life_blob_place(uint64_t seed, int32_t blob, uint64_t q, double x, double y, double r_min, double r_max,
                     double out[2]) {
  blob_place(seed, (uint64_t)(int64_t)blob, q, x, y, r_min, r_max, &out[0], &out[1]);
}

double life_receptor_next(uint64_t seed, uint64_t uid, uint64_t j, double t_prev, double lam_max) {
  return receptor_next(seed, uid, j, t_prev, lam_max);
}

static int col_cmp(const void *x, const void *y) {
  const Col p = *(const Col *)x, q = *(const Col *)y;
  return col_less(p, q) ? -1 : (col_less(q, p) ? 1 : 0);
}

// spec.filled_footprint: the filled footprint of the columns (a[i], b[i]) (repeats allowed) on base lattice `base`
// (the code % 3 of 4.3: 0 hex, 1 square4, 2 square8); -1 on allocation failure
int64_t life_filled_footprint(int32_t base, int64_t n, const int32_t *a, const int32_t *b) {
  if (n <= 0) return 0;
  Col *col = malloc((size_t)n * sizeof(Col));
  if (!col) return -1;
  for (int64_t i = 0; i < n; i++) { col[i].a = a[i]; col[i].b = b[i]; }
  qsort(col, (size_t)n, sizeof(Col), col_cmp);
  int64_t m = 0;
  for (int64_t i = 0; i < n; i++)
    if (m == 0 || col_less(col[m - 1], col[i])) col[m++] = col[i];
  FillBuf fb = {0};
  const int64_t r = filled_count(col, m, base == 0, &fb);
  free(col); free(fb.lo); free(fb.hi); free(fb.par);
  return r;
}

static int key_cmp(const void *a, const void *b) {
  const uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return (x > y) - (x < y);
}

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
    const int32_t *ic = init_cells ? init_cells + (int64_t)i * MAX_INIT * 4 : NULL;
    const int32_t R = (int32_t)w[W_FABRICR], L_max = (int32_t)w[W_LMAX];
    uint64_t keys[MAX_INIT];
    for (int32_t j = 0; j < ni; j++) {  // (a, b, z, row): in the stack, within the key bound, on its own site (4.6)
      const int32_t a = ic[4 * j], b = ic[4 * j + 1], z = ic[4 * j + 2], row = ic[4 * j + 3];
      if (prog && (row < -1 || row >= N_ROWS)) return -4;
      if (z < 0 || z >= L_max || a < -COORD_MAX || a > COORD_MAX || b < -COORD_MAX || b > COORD_MAX) return -4;
      if (R > 0 && !in_disk(lat[0] % 3, a, b, R)) return -4;
      keys[j] = sitekey(a, b, z);
    }
    if (ni > 1) {
      qsort(keys, (size_t)ni, sizeof(uint64_t), key_cmp);
      for (int32_t j = 1; j < ni; j++)
        if (keys[j] == keys[j - 1]) return -4;
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
    const int32_t *ic = ni > 0 ? init_cells + (int64_t)i * MAX_INIT * 4 : NULL;
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
