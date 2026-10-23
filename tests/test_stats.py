from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as sps

from seas.experiments.stats import holm, non_inferiority, rank_biserial, wilcoxon_p


def test_holm_known_answer() -> None:
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03)
    assert adj["c"] == pytest.approx(0.06)
    assert adj["b"] == pytest.approx(0.06)  # monotone step-down


def test_non_inferiority_detects_and_rejects() -> None:
    rng = np.random.default_rng(0)
    good = rng.normal(0.0, 0.01, 30)  # true diff 0 < margin 0.02
    bad = rng.normal(0.03, 0.01, 30)  # true diff 0.03 > margin
    assert non_inferiority(good)["p_ni_t"] < 0.05
    assert non_inferiority(good)["upper95_t"] < 0.02
    assert non_inferiority(bad)["p_ni_t"] > 0.5
    r = non_inferiority(good)
    t = sps.ttest_1samp(good - 0.02, 0.0, alternative="less")
    assert r["p_ni_t"] == pytest.approx(t.pvalue)


def test_non_inferiority_zero_variance() -> None:
    assert non_inferiority(np.zeros(30))["p_ni_t"] == 0.0
    assert non_inferiority(np.full(30, 0.05))["p_ni_t"] == 1.0


def test_wilcoxon_all_zero_and_direction() -> None:
    assert wilcoxon_p(np.zeros(10), "less") == 1.0
    assert wilcoxon_p(-np.arange(1, 21, dtype=float), "less") < 0.001


def test_rank_biserial_bounds() -> None:
    assert rank_biserial(-np.arange(1, 6, dtype=float)) == -1.0
    assert rank_biserial(np.arange(1, 6, dtype=float)) == 1.0
    assert rank_biserial(np.zeros(4)) == 0.0
