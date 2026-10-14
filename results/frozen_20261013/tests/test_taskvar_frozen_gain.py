"""Paired interaction arithmetic and fork-window contract for the frozen-tissue measurement."""
import numpy as np
import pytest

from scripts.taskvar_frozen_gain import CONDITIONS, contrasts, validate_frozen_pair, worlds
from src.life import spec


def test_frozen_interaction_retains_covariance_across_all_four_arms():
    background = np.array([100.0, -200.0, 300.0, -400.0])
    fitness = {key: np.stack([background, background]) for key in CONDITIONS}
    fitness["freeze"][1] += [3, 4, 5, 6]
    fitness["freeze+lateral_off"][1] += [1, 2, 3, 4]
    result = contrasts(fitness)
    assert result["frozen_lateral_interaction"] == {"mean": 2.0, "se": 0.0, "n": 4}
    assert result["interaction_change_under_freeze"] == {"mean": -2.0, "se": 0.0, "n": 4}
    expected_se = np.std([3, 4, 5, 6], ddof=1) / 2
    assert result["frozen_gain"]["se"] == pytest.approx(expected_se)


@pytest.mark.parametrize("bad", [np.zeros((2, 1)), np.zeros((3, 4)), np.full((2, 4), np.nan)])
def test_invalid_paired_rows_rejected(bad):
    fitness = {key: np.zeros((2, 4)) for key in CONDITIONS}
    fitness["normal"] = bad
    with pytest.raises(ValueError):
        contrasts(fitness)


def test_worlds_share_a_post_transition_window_and_existing_flags():
    base = spec.world("catch_speck_l4", d0=0.5, d_min=0.25, sigma=0.4, lam_s=4)
    settings = worlds(base)
    assert [settings[name].fork_flags for name in CONDITIONS] == [0, 16, 2048, 2064]
    for world in settings.values():
        assert (world.T, world.t_fork, world.t_open) == (1536, 768, 800)
        assert world.t_open > world.t_fork + world.d_min
        assert (world.d0, world.d_min, world.sigma, world.lam_s) == (0.5, 0.25, 0.4, 4)
        assert world.c_live == base.c_live


def test_fixed_tissue_assertion_catches_post_open_growth_and_lost_pairing():
    def row():
        return {"births": np.zeros(2), "deaths": np.zeros(2), "last_birth": np.array([768.2, 400]),
                "n_end": np.array([100, 120]), "live_time": np.array([73600, 88320]), "status": np.zeros(2)}

    rows = {key: {i: row() for i in range(2)} for key in ("freeze", "freeze+lateral_off")}
    assert validate_frozen_pair(rows)["paired_complete_lives_by_genotype"] == [2, 2]
    rows["freeze"][0]["births"][0] = 1
    with pytest.raises(ValueError, match="changed population"):
        validate_frozen_pair(rows)
    rows["freeze"][0]["births"][0] = 0
    rows["freeze"][0]["n_end"][0] = 101
    with pytest.raises(ValueError, match="different tissue"):
        validate_frozen_pair(rows)
