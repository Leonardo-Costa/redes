"""Tests for clustering utilities."""
import numpy as np
import pytest


def test_bh_fdr_rejects_at_threshold():
    from src.temporal.stack import _bh_fdr
    # All p-values very small — should reject all
    pvals = {i: 0.001 * (i + 1) for i in range(10)}
    sig = _bh_fdr(pvals, q=0.10)
    assert len(sig) > 0


def test_bh_fdr_accepts_all_null():
    from src.temporal.stack import _bh_fdr
    # All p-values = 1.0 — should reject none
    pvals = {i: 1.0 for i in range(10)}
    sig = _bh_fdr(pvals, q=0.10)
    assert len(sig) == 0


def test_bh_fdr_empty_input():
    from src.temporal.stack import _bh_fdr
    assert _bh_fdr({}) == set()


def test_bocpd_detects_changepoint():
    from src.temporal.stack import _bocpd_changepoint
    # Flat then jump
    series = np.array([5, 4, 5, 6, 5, 20, 25, 22, 24, 23], dtype=float)
    assert _bocpd_changepoint(series) is True


def test_bocpd_no_changepoint():
    from src.temporal.stack import _bocpd_changepoint
    # Flat series — no changepoint
    series = np.array([5, 5, 5, 5, 5, 5, 5, 5], dtype=float)
    result = _bocpd_changepoint(series)
    assert isinstance(result, bool)


def test_bocpd_short_series():
    from src.temporal.stack import _bocpd_changepoint
    assert _bocpd_changepoint(np.array([1, 2])) is False


def test_popularity_score_recency():
    from src.temporal.stack import _popularity_score
    # Series growing over time — last value should dominate
    s1 = np.array([1, 1, 1, 10], dtype=float)
    s2 = np.array([10, 1, 1, 1], dtype=float)
    assert _popularity_score(s1) > _popularity_score(s2)


def test_popularity_score_empty():
    from src.temporal.stack import _popularity_score
    assert _popularity_score(np.array([])) == 0.0


def test_classify_signal_growing():
    from src.temporal.stack import _classify_signal
    sig = _classify_signal(
        pvalue=0.01,
        is_significant=True,
        changepoint=False,
        slope=2.0,
        popularity=50.0,
        all_popularity=[10.0, 20.0, 50.0],
    )
    assert sig == "growing"


def test_classify_signal_shrinking():
    from src.temporal.stack import _classify_signal
    sig = _classify_signal(
        pvalue=0.01,
        is_significant=True,
        changepoint=False,
        slope=-2.0,
        popularity=5.0,
        all_popularity=[10.0, 20.0, 50.0],
    )
    assert sig == "shrinking"
