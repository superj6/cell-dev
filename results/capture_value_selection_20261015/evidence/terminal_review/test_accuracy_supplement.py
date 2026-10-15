"""Only aggregate ratio semantics and count corruption; no scientific inputs."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('AM_accuracy',Path(__file__).with_name('accuracy_supplement.py'))
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def test_zero_clicks_and_aggregate_not_mean_life_fraction():
    blank=M.describe_counts(np.zeros(3),np.zeros(3),np.zeros(3))
    assert blank['aggregate_capture_fraction'] is None and blank['clickless_lives']==3
    result=M.describe_counts(np.array([0.,1.,1.]),np.array([0.,0.,8.]),np.array([0.,1.,9.]))
    assert result['aggregate_capture_fraction']==.2
    assert result['clickless_lives']==1 and result['clickless_fraction']==1/3
    assert result['total_clicks']==10 and result['mean_clicks_per_life']==10/3
    assert 'se' not in result


def test_invalid_counts_are_rejected():
    for captures,misses,clicks in (([1],[0],[0]),([1.5],[.5],[2]),([-1],[2],[1]),([np.nan],[0],[1])):
        with pytest.raises(ValueError):
            M.describe_counts(np.array(captures),np.array(misses),np.array(clicks))
