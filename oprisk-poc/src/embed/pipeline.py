"""Compute and store 3-facet embeddings (summary, root_cause, impact) using bge-large-en-v1.5."""
import os
from pathlib import Path

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

from src.db import get_engine, get_session_factory
from src.models import Incident

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _embed(texts: list[str]) -> np.ndarray:
    model = get_model()
    return model.encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def run_embeddings(session: Session) -> dict:
    """Embed all incidents that have a summary but no vec_summary yet."""
    stmt = select(Incident).where(
        Incident.one_sentence_summary.isnot(None),
        Incident.vec_summary.is_(None),
    )
    incidents = session.scalars(stmt).all()
    logger.info(f"Found {len(incidents)} incidents to embed")

    tracker = {"embedded": 0, "skipped": 0}

    for i in tqdm(range(0, len(incidents), BATCH_SIZE), desc="Embedding"):
        batch = incidents[i : i + BATCH_SIZE]

        summaries = [inc.one_sentence_summary or "" for inc in batch]
        root_causes = [inc.root_cause_summary or "" for inc in batch]
        impacts = [inc.customer_impact_summary or "" for inc in batch]

        vec_summaries = _embed(summaries)
        vec_root_causes = _embed(root_causes)
        vec_impacts = _embed(impacts)

        for j, incident in enumerate(batch):
            incident.vec_summary = vec_summaries[j].tolist()
            incident.vec_root_cause = vec_root_causes[j].tolist()
            incident.vec_impact = vec_impacts[j].tolist()
            tracker["embedded"] += 1

        session.commit()
        logger.debug(f"Committed embedding batch {i // BATCH_SIZE + 1}")

    logger.success(
        f"Embeddings complete: {tracker['embedded']} embedded, {tracker['skipped']} skipped"
    )
    return tracker


if __name__ == "__main__":
    engine = get_engine()
    SessionFactory = get_session_factory(engine)
    with SessionFactory() as session:
        run_embeddings(session)
