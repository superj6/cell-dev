"""AG-specific source/ABI4 checks; no input copying, engine imports or fixture trees."""

import __future__

import ast
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
S = importlib.util.spec_from_file_location("AG_reader_tests", HERE / "analyze.py")
M = importlib.util.module_from_spec(S)
S.loader.exec_module(M)
ROOT = next((p for p in HERE.parents if (p / "src/life/spec.py").is_file()), None)
SOURCE = (
    HERE.parent
    if (HERE.parent / "measure.py").is_file()
    else ROOT / "outputs/autonomous_visibility_dark_tail_gradient_20261014"
)


def world():
    return dict(
        t0=0,
        T=1024,
        t_open=0,
        world_kind=1,
        b2_amp=0,
        b2_value=0,
        c_live=0.001,
        c_spike=0.02,
        c_tw=0.03,
        c_msg=0.04,
        c_div=0.05,
        c_sec=0.06,
        c_miss=0.07,
        c_rec=0.08,
        R_cap=500,
        n_max=128,
    )


def row(captures, low):
    w = world()
    r = {k: np.zeros(512, dtype=np.float64) for k in M.A.COLS}
    for k, v in dict(
        captures=captures,
        low_light_captures=low,
        clicks=captures,
        n_end=1,
        n_peak=1,
        n_S_end=1,
        live_time=1024,
        live_S=1024,
        t_end=1024,
        t_ext=-1,
        window=1024,
        spikes=2,
    ).items():
        r[k][:] = v
    r["income"] = 500 * r["captures"]
    r["cost"], _ = M.A.physical_costs(r, w)
    r["net"] = r["income"] - r["cost"] - r["guard_charge"]
    r["F_kernel"] = r["net"] / 1024
    r["F"] = r["F_kernel"] - r["extinct_charge"]
    r["ledger"] = np.stack([r["F_kernel" if k == "F" else k] for k in M.A.LEDGER], axis=1)
    r.update(seeds=np.arange(512, dtype=np.uint64), cpu_seconds=np.asarray(0.01), wall_seconds=np.asarray(0.02))
    return r


def function_tree(path, names):
    tree = ast.parse(path.read_text())
    f = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {x.name for x in f} == set(names)

    class NoImports(ast.NodeTransformer):
        def visit_Import(self, node):
            return None

        def visit_ImportFrom(self, node):
            return None

    return ast.fix_missing_locations(NoImports().visit(ast.Module(body=f, type_ignores=[])))


def producer_report(rows, w):
    env = {"np": np}
    src = M.external(SOURCE, "scripts/taskvar_gates.py")
    exec(compile(function_tree(src, {"paired"}), str(src), "exec", flags=__future__.annotations.compiler_flag), env)
    env.update(
        ABI=SimpleNamespace(
            LEDGER=M.A.LEDGER,
            column_cost=lambda led, w: M.A.physical_costs({k: led[:, i] for i, k in enumerate(M.A.LEDGER)}, vars(w))[0],
        ),
        COLS=M.A.COLS,
        ROLES=list(M.LABELS),
        PARENTS=M.PARENTS,
    )
    src = SOURCE / "measure.py"
    exec(
        compile(function_tree(src, {"contrast_reports"}), str(src), "exec", flags=__future__.annotations.compiler_flag),
        env,
    )
    return env["contrast_reports"](rows, {"flash5_dark": SimpleNamespace(**w)})


def test_four_roles132_vectors_actual_producer():
    rows = {
        "flash5_dark": {
            0: row(4 + np.arange(512) % 2, 2),
            1: row(4, 1),
            2: row(5 + np.arange(512) % 2, 1),
            3: row(3, 2),
        }
    }
    summary, vectors = M.contrasts(rows, {"flash5_dark": world()})
    assert len(vectors) == 132 and all(x.shape == (512,) for x in vectors.values())
    report = {"contrasts": producer_report(rows, world())}
    M.compare_report(report, vectors, {"flash5_dark": world()})
    assert summary["H_D90_minus_P_D90"]["low_light_captures"]["mean"] == -1
    assert summary["H_D90_minus_P_D90"]["bright_captures"]["mean"] == 2
    assert summary["H_L92_minus_P_L92"]["F"]["mean"] < 0


def test_identical_roles_retained():
    rows = {"flash5_dark": {i: row(4, 2) for i in range(4)}}
    _, vectors = M.contrasts(rows, {"flash5_dark": world()})
    assert len(vectors) == 132 and all(np.all(x == 0) for x in vectors.values())


@pytest.mark.parametrize(
    "kind", ["57cols", "missing_low", "excess_low", "birth_census", "F_penalty", "seed_order", "missing_role"]
)
def test_abi4_and_role_corruptions(kind):
    rows = {"flash5_dark": {i: row(4, 2) for i in range(4)}}
    r = rows["flash5_dark"][2]
    if kind == "57cols":
        r["ledger"] = r["ledger"][:, :57]
    elif kind == "missing_low":
        del r["low_light_captures"]
    elif kind == "excess_low":
        r["low_light_captures"][:] = 5
        r["ledger"][:, 57] = 5
    elif kind == "birth_census":
        r["births"][:] = 1
        r["ledger"][:, M.A.L["births"]] = 1
    elif kind == "F_penalty":
        r["F"][0] += 1
    elif kind == "seed_order":
        r["seeds"] = r["seeds"][::-1]
    elif kind == "missing_role":
        del rows["flash5_dark"][2]
    with pytest.raises((ValueError, KeyError)):
        M.contrasts(rows, {"flash5_dark": world()})


def approved_world_case(monkeypatch):
    if ROOT:
        source = ROOT / "results/visibility_dark_tail_information_20261014/protocol.json"
        summary = ROOT / "results/visibility_dark_tail_information_20261014/analysis_result/summary.json"
        spec = ROOT / "src/life/spec.py"
    else:
        source = SOURCE / "inputs/AD/protocol.json"
        summary = SOURCE / "inputs/AD/analysis_result/summary.json"
        spec = M.external(SOURCE, "src/life/spec.py")
    assert M.sha(source) == M.AD_PROTOCOL
    old = M.read(source)
    w = copy.deepcopy(old["worlds"]["flash5_dark"]["production"]["world"])
    tree = ast.parse(spec.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "World")
    meta = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_META" for t in n.targets)
    )
    keys = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and n.target.id not in meta]
    arr = np.asarray([w[k] for k in keys], dtype=np.float64)
    p = {
        "AD_protocol_sha256": M.AD_PROTOCOL,
        "world": w,
        "world_packing": {"abi": 4, "keys": keys, "values": arr.tolist(), "raw_sha256": M.raw_sha(arr)},
        "configuration_changes": {
            "life.world": "catch_speck_flash5_dim25_l4",
            "life.abi": 4,
            "world": {"visibility_low": 0.0},
        },
    }
    actual_read, actual_sha = M.read, M.sha
    monkeypatch.setattr(
        M,
        "read",
        lambda x: actual_read(
            source
            if str(x).endswith("inputs/AD/protocol.json")
            else summary
            if str(x).endswith("inputs/AD/analysis_result/summary.json")
            else x
        ),
    )
    monkeypatch.setattr(M, "sha", lambda x: actual_sha(source if str(x).endswith("inputs/AD/protocol.json") else x))
    return p, tree


def test_exact_AD70_packing_without_engine(monkeypatch):
    p, tree = approved_world_case(monkeypatch)
    M.check_worlds(Path("synthetic-not-written"), p, tree)
    assert len(p["world_packing"]["keys"]) == 70 and p["world"]["visibility_low"] == 0


@pytest.mark.parametrize("kind", ["amplitude", "mode", "packing_order", "abi3", "config_price"])
def test_world_or_packing_change_rejected(monkeypatch, kind):
    p, tree = approved_world_case(monkeypatch)
    if kind == "amplitude":
        p["world"]["visibility_low"] = 0.25
    elif kind == "mode":
        p["world"]["visibility_mode"] = 2
    elif kind == "packing_order":
        p["world_packing"]["keys"] = p["world_packing"]["keys"][::-1]
    elif kind == "abi3":
        p["world_packing"]["abi"] = 3
    elif kind == "config_price":
        p["configuration_changes"]["world"]["R_cap"] = 1000
    with pytest.raises(ValueError):
        M.check_worlds(Path("synthetic-not-written"), p, tree)


def test_exact_reused_accountant_and_helper():
    assert M.sha(HERE / "offline_accounting.py") == "7d61ecfbc8c3ae96f3808655901a04c3542c6418fea5d6cc5f696afe22836421"
    assert M.sha(HERE / "helpers/genetics.py") == "8fd717bdecb5f0e073e04838bbf286a4a968924bc9848b55c5a8d2b2055f4139"
    assert len(M.A.LEDGER) == 58 and len(M.A.COLS) == 61


def test_unregistered_emits_no_outcomes(monkeypatch):
    monkeypatch.setattr(M, "PROTOCOL_SHA", None)
    result, vectors = M.analyze(Path("synthetic-not-written"))
    assert result["status"] == "incomplete" and not result["scientific_outcomes_emitted"] and not vectors


@pytest.mark.parametrize("corrupt", [False, True])
def test_all130_existing_AC_timing_rows_without_copying(monkeypatch, corrupt):
    historical = ROOT / "results/visibility_flash_gradient_20261014" if ROOT else SOURCE / "inputs/AC"
    review = (
        M.read(ROOT / "outputs/audit_visibility_dark_tail_gradient_20261014/historical_AC_timing_review.json")
        if ROOT
        else M.read(SOURCE / "inputs/historical_flash_costs.json")
    )
    cp = M.read(historical / "protocol.json")
    rates = review["cpu_per_life"]
    p = {
        "AC_protocol_sha256": M.AC_PROTOCOL,
        "panel_genotype_sha256": cp["panel_genotype_sha256"],
        "historical_flash_cpu_per_life": rates,
    }
    fake = Path("synthetic-not-written")

    def map_path(path):
        path = Path(path)
        try:
            rel = path.relative_to(fake / "inputs/AC")
        except ValueError:
            return path
        return historical / ("operations/budget.json" if str(rel) == "budget.json" and ROOT else rel)

    old_read, old_sha, old_npz = M.read, M.sha, M.npz

    def read(path):
        if Path(path) == fake / "inputs/historical_flash_costs.json":
            return {
                "source_protocol_sha256": M.AC_PROTOCOL,
                "source_pins": {k: v for k, v in review["source_pins"].items() if k.endswith(".npz")},
                "cpu_per_life": rates,
                "lives_per_row": 32,
            }
        return old_read(map_path(path))

    def npz(path):
        row = old_npz(map_path(path))
        if corrupt and str(path).endswith("D90/screen/row_0000.npz"):
            row["cpu_seconds"] = np.asarray(float(row["cpu_seconds"]) + 1)
        return row

    monkeypatch.setattr(M, "read", read)
    monkeypatch.setattr(M, "sha", lambda p: old_sha(map_path(p)))
    monkeypatch.setattr(M, "npz", npz)
    if corrupt:
        with pytest.raises(ValueError, match="historical CPU"):
            M.historical_costs(fake, p, cp)
    else:
        assert M.historical_costs(fake, p, cp) == rates
