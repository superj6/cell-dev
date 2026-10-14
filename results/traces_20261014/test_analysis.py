"""Descriptive estimand/cardinality checks; no life simulation."""
import analyze as A
import numpy as np
import pytest


def test_paired_covariance_is_retained():
    a, b = [2., 14., 8., 22.], [1., 11., 5., 21.]
    values = np.asarray(a) - np.asarray(b)
    result = A.stats(A.subtract(a, b))
    assert result['mean'] == values.mean()
    assert result['se'] == values.std(ddof=1) / 2


def test_undefined_life_is_retained():
    result = A.stats([1., 2., None, 4.])
    assert result['n'] == 4 and result['mean'] is None and result['se'] is None
    assert A.subtract([1., None, 3., 4.], [0., 2., None, 1.]) == [1., None, None, 3.]


def test_missing_life_is_rejected_even_if_undefined():
    with pytest.raises(ValueError, match='four'):
        A.stats([None, 1., 2.])
    with pytest.raises(ValueError, match='length'):
        A.subtract([1., 2.], [1.])


def test_nonfinite_is_not_reported_as_a_result():
    with pytest.raises(ValueError, match='finite'):
        A.stats([1., np.inf, 2., 3.])
