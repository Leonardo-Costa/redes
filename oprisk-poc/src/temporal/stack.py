"""Temporal signal detection: Poisson GLM + BH-FDR + BOCPD + popularity metric.

Produces cluster_signals rows: {cluster_id, facet, month, signal, pvalue, changepoint, popularity}.
"""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import ruptures as rpt
import statsmodels.api as sm
from loguru import logger
from scipy.stats import poisson
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from src.db import get_engine, get_session_factory
from src.models import Incident, Cluster, ClusterSignal

FACETS = {
    "summary": ("cluster_id_summary", "vec_summary"),
    "root_cause": ("cluster_id_root_cause", "vec_root_cause"),
    "impact": ("cluster_id_impact", "vec_impact"),
}

BH_FDR_Q = 0.10
POPULARITY_DECAY = 0.8  # recency weight per month


def _monthly_counts(session: Session, facet: str, cluster_col: str) -> pd.DataFrame:
    """Build monthly incident counts per cluster for a given facet."""
    stmt = select(
        Incident.date_received,
        getattr(Incident, cluster_col),
    ).where(
        getattr(Incident, cluster_col).isnot(None),
        Incident.date_received.isnot(None),
    )
    rows = session.execute(stmt).all()
    if not rows:
        return pd.DataFrame(columns=["month", "cluster_id", "count"])

    df = pd.DataFrame(rows, columns=["date_received", "cluster_id"])
    df["date_received"] = pd.to_datetime(df["date_received"])
    df["month"] = df["date_received"].dt.to_period("M").dt.to_timestamp()
    counts = df.groupby(["month", "cluster_id"]).size().reset_index(name="count")
    return counts


def _poisson_glm_pvalues(counts_df: pd.DataFrame) -> dict[int, float]:
    """Fit Poisson GLM per cluster, return growth p-value."""
    pvalues: dict[int, float] = {}
    months = sorted(counts_df["month"].unique())
    if len(months) < 3:
        return pvalues

    month_idx = {m: i for i, m in enumerate(months)}

    # Corpus-level total per month (offset)
    corpus = counts_df.groupby("month")["count"].sum().reindex(months, fill_value=0)

    for cluster_id in counts_df["cluster_id"].unique():
        sub = counts_df[counts_df["cluster_id"] == cluster_id].set_index("month")["count"]
        y = sub.reindex(months, fill_value=0).values
        x = np.array([month_idx[m] for m in months], dtype=float)
        offset = np.log(corpus.values.clip(1))

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                glm = sm.GLM(
                    y,
                    sm.add_constant(x),
                    family=sm.families.Poisson(),
                    offset=offset,
                ).fit(disp=False)
            pvalues[int(cluster_id)] = float(glm.pvalues[1])  # slope p-value
        except Exception:
            pvalues[int(cluster_id)] = 1.0

    return pvalues


def _bh_fdr(pvalues: dict[int, float], q: float = BH_FDR_Q) -> set[int]:
    """Benjamini-Hochberg FDR correction; returns cluster IDs that are significant."""
    if not pvalues:
        return set()
    ids = list(pvalues.keys())
    ps = np.array([pvalues[i] for i in ids])
    m = len(ps)
    order = np.argsort(ps)
    threshold = np.arange(1, m + 1) / m * q
    sig_mask = ps[order] <= threshold
    # All tests up to last significant pass
    if not sig_mask.any():
        return set()
    last = np.where(sig_mask)[0][-1]
    sig_ids = {ids[order[i]] for i in range(last + 1)}
    return sig_ids


def _bocpd_changepoint(series: np.ndarray) -> bool:
    """Detect changepoint in count series via PELT (ruptures). Returns True if changepoint."""
    if len(series) < 4:
        return False
    try:
        algo = rpt.Pelt(model="rbf").fit(series.reshape(-1, 1).astype(float))
        result = algo.predict(pen=3)
        # PELT always includes len(series) as last breakpoint; real changepoint if any extra
        return len(result) > 1
    except Exception:
        return False


def _popularity_score(series: np.ndarray) -> float:
    """Recency-weighted count sum as popularity proxy."""
    if len(series) == 0:
        return 0.0
    weights = POPULARITY_DECAY ** np.arange(len(series) - 1, -1, -1)
    return float(np.dot(series, weights))


def _classify_signal(
    pvalue: float | None,
    is_significant: bool,
    changepoint: bool,
    slope: float,
    popularity: float,
    all_popularity: list[float],
) -> str:
    median_pop = float(np.median(all_popularity)) if all_popularity else 0
    if is_significant and slope > 0:
        return "growing"
    if is_significant and slope < 0:
        return "shrinking"
    if changepoint and popularity > median_pop * 1.5:
        return "emerging"
    if popularity > np.percentile(all_popularity, 80) if all_popularity else False:
        return "stable"
    return "stable"


def run_temporal(session: Session) -> dict:
    logger.info("Running temporal signal detection")
    session.execute(delete(ClusterSignal))

    rows_written = 0
    for facet, (cluster_col, _) in FACETS.items():
        counts_df = _monthly_counts(session, facet, cluster_col)
        if counts_df.empty:
            logger.warning(f"No monthly data for facet {facet}")
            continue

        pvalues = _poisson_glm_pvalues(counts_df)
        significant_ids = _bh_fdr(pvalues)

        months = sorted(counts_df["month"].unique())

        # Compute slopes
        slopes: dict[int, float] = {}
        for cluster_id in counts_df["cluster_id"].unique():
            sub = counts_df[counts_df["cluster_id"] == cluster_id].set_index("month")["count"]
            series = sub.reindex(months, fill_value=0).values
            if len(series) >= 2:
                slopes[int(cluster_id)] = float(np.polyfit(range(len(series)), series, 1)[0])
            else:
                slopes[int(cluster_id)] = 0.0

        # Popularity per cluster (last value in series)
        popularities: dict[int, float] = {}
        for cluster_id in counts_df["cluster_id"].unique():
            sub = counts_df[counts_df["cluster_id"] == cluster_id].set_index("month")["count"]
            series = sub.reindex(months, fill_value=0).values
            popularities[int(cluster_id)] = _popularity_score(series)

        all_pops = list(popularities.values())

        for cluster_id in counts_df["cluster_id"].unique():
            sub = counts_df[counts_df["cluster_id"] == cluster_id].set_index("month")["count"]
            series = sub.reindex(months, fill_value=0).values
            cid = int(cluster_id)

            is_sig = cid in significant_ids
            cp = _bocpd_changepoint(series)
            pval = pvalues.get(cid)
            slope = slopes.get(cid, 0.0)
            pop = popularities.get(cid, 0.0)
            signal = _classify_signal(pval, is_sig, cp, slope, pop, all_pops)

            # Latest month as the signal date
            last_month = months[-1].date() if hasattr(months[-1], "date") else months[-1]

            session.add(ClusterSignal(
                cluster_id=cid,
                facet=facet,
                month=last_month,
                count=int(series[-1]),
                signal=signal,
                poisson_pvalue=pval,
                bocpd_changepoint=cp,
                popularity_score=pop,
            ))
            rows_written += 1

        session.commit()
        n_growing = sum(1 for c in counts_df["cluster_id"].unique() if c in significant_ids and slopes.get(int(c), 0) > 0)
        logger.success(f"Temporal {facet}: {len(significant_ids)} significant, {n_growing} growing")

    logger.success(f"Temporal stack complete: {rows_written} signal rows written")
    return {"signals": rows_written}


if __name__ == "__main__":
    engine = get_engine()
    SessionFactory = get_session_factory(engine)
    with SessionFactory() as session:
        result = run_temporal(session)
        logger.success(f"Done: {result}")
