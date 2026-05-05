"""Load a stratified sample from the CFPB Consumer Complaint Database."""
import os
import random
from collections import defaultdict

import pandas as pd
from datasets import load_dataset
from loguru import logger
from sqlalchemy.orm import Session

from src.db import get_engine, get_session_factory
from src.models import Incident


SAMPLE_SIZE = int(os.getenv("CFPB_SAMPLE_SIZE", "1200"))
SEED = int(os.getenv("CFPB_SEED", "42"))
MIN_NARRATIVE_CHARS = 100
TOP_N_PRODUCTS = 8


def load_cfpb_sample() -> pd.DataFrame:
    logger.info("Loading CFPB dataset from HuggingFace (streaming)...")
    ds = load_dataset(
        "CFPB/consumer-finance-complaints",
        split="train",
        streaming=True,
        trust_remote_code=True,
    )

    # Collect enough records to stratify — scan up to 200k
    records = []
    for row in ds:
        narrative = (row.get("consumer_complaint_narrative") or "").strip()
        if len(narrative) >= MIN_NARRATIVE_CHARS:
            records.append({
                "cfpb_id": str(row.get("complaint_id", "")),
                "narrative": narrative,
                "date_received": row.get("date_received"),
                "cfpb_product": row.get("product", ""),
                "cfpb_issue": row.get("issue", ""),
            })
        if len(records) >= 200_000:
            break

    df = pd.DataFrame(records)
    logger.info(f"Collected {len(df):,} narratives before stratification")
    return stratify_sample(df, SAMPLE_SIZE, SEED)


def stratify_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Proportional stratified sample across top-N product categories."""
    random.seed(seed)

    top_products = (
        df["cfpb_product"].value_counts().head(TOP_N_PRODUCTS).index.tolist()
    )
    df_top = df[df["cfpb_product"].isin(top_products)].copy()

    counts = df_top["cfpb_product"].value_counts()
    total = counts.sum()
    quota = {p: max(1, round(n * c / total)) for p, c in counts.items()}
    # Adjust for rounding
    diff = n - sum(quota.values())
    if diff != 0:
        largest = counts.index[0]
        quota[largest] += diff

    samples: list[pd.DataFrame] = []
    for product, q in quota.items():
        pool = df_top[df_top["cfpb_product"] == product]
        samples.append(pool.sample(min(q, len(pool)), random_state=seed))

    result = pd.concat(samples).sample(frac=1, random_state=seed).reset_index(drop=True)
    logger.info(f"Stratified sample: {len(result)} records across {len(quota)} products")
    for p, c in result["cfpb_product"].value_counts().items():
        logger.info(f"  {p}: {c}")
    return result


def ingest_to_db(df: pd.DataFrame, session: Session) -> int:
    """Insert CFPB records into incidents table. Skip already-present cfpb_ids."""
    existing = {r[0] for r in session.query(Incident.cfpb_id).all()}
    new_rows = df[~df["cfpb_id"].isin(existing)]

    incidents = [
        Incident(
            cfpb_id=row["cfpb_id"],
            narrative=row["narrative"],
            date_received=_parse_date(row.get("date_received")),
            cfpb_product=row.get("cfpb_product"),
            cfpb_issue=row.get("cfpb_issue"),
        )
        for _, row in new_rows.iterrows()
    ]
    session.bulk_save_objects(incidents)
    session.commit()
    logger.info(f"Inserted {len(incidents)} incidents ({len(existing)} already existed)")
    return len(incidents)


def _parse_date(value):
    if not value:
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def load_sample(synthetic: bool = False) -> pd.DataFrame:
    """Load CFPB sample (real or synthetic fallback)."""
    if synthetic:
        from src.ingest.synthetic import generate_synthetic_dataset
        logger.info("Using synthetic dataset (offline mode)")
        return generate_synthetic_dataset(SAMPLE_SIZE, SEED)
    return load_cfpb_sample()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true", help="Use offline synthetic data")
    args = parser.parse_args()

    engine = get_engine()
    Session = get_session_factory(engine)
    with Session() as session:
        df = load_sample(synthetic=args.synthetic)
        n = ingest_to_db(df, session)
        logger.success(f"Ingestion complete — {n} new incidents in DB")
