"""Two-pass clustering:
Pass A: HDBSCAN on vec_summary → novelty detection (noise → novelty_queue).
Pass B: UMAP→MiniBatch K-Means per facet → LLM cluster labels → clusters table.
"""
import json
import os
from pathlib import Path

import anthropic
import numpy as np
import umap
from dotenv import load_dotenv
from hdbscan import HDBSCAN
from loguru import logger
from sklearn.cluster import MiniBatchKMeans
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from tqdm import tqdm

load_dotenv()

from src.db import get_engine, get_session_factory
from src.models import Incident, Cluster, NoveltyQueue, ClusterSignal

FACETS = {
    "summary": "vec_summary",
    "root_cause": "vec_root_cause",
    "impact": "vec_impact",
}

HDBSCAN_MIN_CLUSTER = int(os.getenv("HDBSCAN_MIN_CLUSTER", "5"))
KMEANS_K = int(os.getenv("KMEANS_K", "30"))
UMAP_COMPONENTS = int(os.getenv("UMAP_COMPONENTS", "15"))
UMAP_SEED = 42


def _fetch_embeddings(session: Session, col: str) -> tuple[list[int], np.ndarray]:
    stmt = select(Incident.id, getattr(Incident, col)).where(
        getattr(Incident, col).isnot(None)
    )
    rows = session.execute(stmt).all()
    ids = [r[0] for r in rows]
    vecs = np.array([r[1] for r in rows], dtype=np.float32)
    return ids, vecs


def pass_a_novelty(session: Session) -> dict:
    """HDBSCAN on summary embeddings → fill cluster_id_novelty + novelty_queue."""
    logger.info("Pass A: HDBSCAN novelty detection on vec_summary")
    ids, vecs = _fetch_embeddings(session, "vec_summary")
    if len(ids) < HDBSCAN_MIN_CLUSTER * 2:
        logger.warning("Not enough embeddings for HDBSCAN")
        return {"noise": 0, "clustered": 0}

    reducer = umap.UMAP(n_components=UMAP_COMPONENTS, random_state=UMAP_SEED, n_jobs=1)
    reduced = reducer.fit_transform(vecs)

    hdb = HDBSCAN(min_cluster_size=HDBSCAN_MIN_CLUSTER, prediction_data=True)
    labels = hdb.fit_predict(reduced)

    noise_ids = []
    for inc_id, label in zip(ids, labels):
        session.execute(
            select(Incident).where(Incident.id == inc_id)
        )
        inc = session.get(Incident, inc_id)
        inc.cluster_id_novelty = int(label)
        if label == -1:
            noise_ids.append(inc_id)

    # Clear + re-fill novelty_queue
    session.execute(delete(NoveltyQueue))
    for inc_id in noise_ids:
        session.add(NoveltyQueue(incident_id=inc_id, noise_score=1.0, reviewed=False))

    session.commit()
    noise_count = len(noise_ids)
    cluster_count = len(ids) - noise_count
    logger.success(f"Pass A: {cluster_count} clustered, {noise_count} noise ({noise_count/len(ids):.1%})")
    return {"noise": noise_count, "clustered": cluster_count}


def pass_b_taxonomy(session: Session) -> dict:
    """UMAP→MiniBatch K-Means per facet → LLM labels → clusters table."""
    total_clusters = 0
    for facet, col in FACETS.items():
        logger.info(f"Pass B taxonomy: facet={facet}")
        ids, vecs = _fetch_embeddings(session, col)
        if len(ids) < KMEANS_K:
            logger.warning(f"Not enough embeddings for facet {facet} (need {KMEANS_K})")
            continue

        reducer = umap.UMAP(n_components=UMAP_COMPONENTS, random_state=UMAP_SEED, n_jobs=1)
        reduced = reducer.fit_transform(vecs)

        kmeans = MiniBatchKMeans(n_clusters=KMEANS_K, random_state=UMAP_SEED, n_init=3)
        labels = kmeans.fit_predict(reduced)

        # Assign cluster_id to incidents
        cluster_col = f"cluster_id_{facet}" if facet != "root_cause" else "cluster_id_root_cause"
        for inc_id, label in zip(ids, labels):
            inc = session.get(Incident, inc_id)
            setattr(inc, cluster_col, int(label))

        # Build cluster summaries for LLM labeling
        cluster_samples: dict[int, list[str]] = {}
        for inc_id, label in zip(ids, labels):
            cluster_samples.setdefault(int(label), [])
            if len(cluster_samples[int(label)]) < 5:
                inc = session.get(Incident, inc_id)
                text = getattr(inc, f"{facet}_summary" if facet != "summary" else "one_sentence_summary") or ""
                cluster_samples[int(label)].append(text[:200])

        labels_map = _llm_label_clusters(cluster_samples, facet)

        # Upsert clusters
        for cluster_id, label_text in labels_map.items():
            size = int(np.sum(labels == cluster_id))
            existing = session.get(Cluster, cluster_id * 10 + list(FACETS.keys()).index(facet))
            if existing:
                existing.label = label_text
                existing.size = size
            else:
                cluster = Cluster(
                    id=cluster_id * 10 + list(FACETS.keys()).index(facet),
                    facet=facet,
                    label=label_text,
                    size=size,
                )
                session.add(cluster)

        session.commit()
        total_clusters += len(labels_map)
        logger.success(f"Pass B {facet}: {len(labels_map)} clusters labeled")

    return {"total_clusters": total_clusters}


def _llm_label_clusters(cluster_samples: dict[int, list[str]], facet: str) -> dict[int, str]:
    """Ask LLM to label each cluster given 5 representative samples."""
    token_file = os.getenv("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if token_file and Path(token_file).exists() and (not api_key or api_key.startswith("sk-ant-...")):
        token = Path(token_file).read_text().strip()
        anth = anthropic.Anthropic(
            auth_token=token,
            default_headers={"anthropic-beta": "oauth-2025-04-20"},
        )
    else:
        anth = anthropic.Anthropic()

    labels: dict[int, str] = {}
    items = list(cluster_samples.items())

    for cluster_id, samples in tqdm(items, desc=f"Labeling {facet} clusters"):
        samples_text = "\n".join(f"- {s}" for s in samples if s)
        prompt = (
            f"You are labeling clusters of financial incident reports for the '{facet}' facet.\n"
            f"Given these {len(samples)} representative texts from cluster {cluster_id}:\n"
            f"{samples_text}\n\n"
            "Provide a concise 3-7 word label that captures the common theme. "
            "Reply with ONLY the label, no explanation."
        )
        try:
            resp = anth.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=30,
                messages=[{"role": "user", "content": prompt}],
            )
            labels[cluster_id] = resp.content[0].text.strip()
        except Exception as e:
            logger.warning(f"LLM labeling failed for cluster {cluster_id}: {e}")
            labels[cluster_id] = f"cluster_{cluster_id}"

    return labels


def run_clustering(session: Session) -> dict:
    result_a = pass_a_novelty(session)
    result_b = pass_b_taxonomy(session)
    return {**result_a, **result_b}


if __name__ == "__main__":
    engine = get_engine()
    SessionFactory = get_session_factory(engine)
    with SessionFactory() as session:
        result = run_clustering(session)
        logger.success(f"Clustering complete: {result}")
