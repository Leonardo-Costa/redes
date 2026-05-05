"""Six typed tool implementations for the Anthropic agent."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from src.models import Incident, Cluster, ClusterSignal, NoveltyQueue


# ── tool result types ──────────────────────────────────────────────────────────

@dataclass
class IncidentSummary:
    id: int
    cfpb_id: str | None
    date_received: str | None
    one_sentence_summary: str | None
    product_domain: str | None
    basel_category: str | None
    financial_impact: str | None
    root_cause_type: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cfpb_id": self.cfpb_id,
            "date_received": self.date_received,
            "summary": self.one_sentence_summary,
            "product_domain": self.product_domain,
            "basel_category": self.basel_category,
            "financial_impact": self.financial_impact,
            "root_cause_type": self.root_cause_type,
        }


@dataclass
class IncidentDetail:
    id: int
    cfpb_id: str | None
    narrative: str
    date_received: str | None
    one_sentence_summary: str | None
    root_cause_summary: str | None
    customer_impact_summary: str | None
    product_domain: str | None
    basel_category: str | None
    root_cause_type: str | None
    financial_impact: str | None
    detection_stage: str | None
    third_party_involved: bool | None
    automated_system_involved: bool | None
    regulatory_implication: bool | None
    suggests_recurring_pattern: bool | None
    affected_systems: list[str]
    keywords: list[str]

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class SignalReport:
    cluster_id: int
    facet: str
    signal: str | None
    month: str | None
    count: int
    poisson_pvalue: float | None
    bocpd_changepoint: bool | None
    popularity_score: float | None

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class ClusterReport:
    cluster_id: int
    facet: str
    label: str | None
    size: int | None
    signal: str | None
    sample_incidents: list[dict]

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "facet": self.facet,
            "label": self.label,
            "size": self.size,
            "signal": self.signal,
            "sample_incidents": self.sample_incidents,
        }


@dataclass
class CooccurrenceRow:
    entity_a: str
    entity_b: str
    npmi: float
    co_count: int

    def to_dict(self) -> dict:
        return self.__dict__


# ── embedding helper ───────────────────────────────────────────────────────────

_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        import os
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
        _embed_model = SentenceTransformer(model_name)
    return _embed_model


def _embed_query(text: str) -> list[float]:
    model = _get_embed_model()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()


# ── tool implementations ───────────────────────────────────────────────────────

def semantic_search(
    session: Session,
    query: str,
    facet: str = "summary",
    k: int = 10,
) -> list[dict]:
    """Vector similarity search across incidents."""
    facet_col = {
        "summary": Incident.vec_summary,
        "root_cause": Incident.vec_root_cause,
        "impact": Incident.vec_impact,
    }.get(facet, Incident.vec_summary)

    vec = _embed_query(query)

    stmt = (
        select(Incident)
        .where(facet_col.isnot(None))
        .order_by(facet_col.cosine_distance(vec))
        .limit(k)
    )
    incidents = session.scalars(stmt).all()
    return [_incident_to_summary(inc).to_dict() for inc in incidents]


def filter_incidents(
    session: Session,
    date_from: str | None = None,
    date_to: str | None = None,
    product: str | None = None,
    financial_impact: str | None = None,
    cluster_id: int | None = None,
    facet: str = "summary",
    limit: int = 50,
) -> list[dict]:
    """Filter incidents by structured criteria."""
    filters = []
    if date_from:
        filters.append(Incident.date_received >= date_from)
    if date_to:
        filters.append(Incident.date_received <= date_to)
    if product:
        filters.append(Incident.product_domain == product)
    if financial_impact:
        filters.append(Incident.financial_impact == financial_impact)
    if cluster_id is not None:
        col = {
            "summary": Incident.cluster_id_summary,
            "root_cause": Incident.cluster_id_root_cause,
            "impact": Incident.cluster_id_impact,
        }.get(facet, Incident.cluster_id_summary)
        filters.append(col == cluster_id)

    stmt = select(Incident).where(Incident.one_sentence_summary.isnot(None))
    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.limit(limit)

    incidents = session.scalars(stmt).all()
    return [_incident_to_summary(inc).to_dict() for inc in incidents]


def temporal_signal(
    session: Session,
    cluster_id: int,
    facet: str = "summary",
) -> dict:
    """Return temporal signal info for a cluster."""
    stmt = select(ClusterSignal).where(
        ClusterSignal.cluster_id == cluster_id,
        ClusterSignal.facet == facet,
    ).order_by(ClusterSignal.month.desc()).limit(1)
    sig = session.scalars(stmt).first()
    if not sig:
        return {"error": f"No signal data for cluster {cluster_id} / {facet}"}
    return SignalReport(
        cluster_id=sig.cluster_id,
        facet=sig.facet,
        signal=sig.signal,
        month=str(sig.month) if sig.month else None,
        count=sig.count,
        poisson_pvalue=sig.poisson_pvalue,
        bocpd_changepoint=sig.bocpd_changepoint,
        popularity_score=sig.popularity_score,
    ).to_dict()


def cluster_summary(
    session: Session,
    cluster_id: int,
    facet: str = "summary",
) -> dict:
    """Return cluster metadata plus sample incidents."""
    cluster = session.get(Cluster, cluster_id)
    label = cluster.label if cluster else None
    size = cluster.size if cluster else None

    sig_stmt = select(ClusterSignal).where(
        ClusterSignal.cluster_id == cluster_id,
        ClusterSignal.facet == facet,
    ).order_by(ClusterSignal.month.desc()).limit(1)
    sig = session.scalars(sig_stmt).first()

    col = {
        "summary": Incident.cluster_id_summary,
        "root_cause": Incident.cluster_id_root_cause,
        "impact": Incident.cluster_id_impact,
    }.get(facet, Incident.cluster_id_summary)

    samples_stmt = select(Incident).where(col == cluster_id).limit(5)
    samples = session.scalars(samples_stmt).all()

    return ClusterReport(
        cluster_id=cluster_id,
        facet=facet,
        label=label,
        size=size,
        signal=sig.signal if sig else None,
        sample_incidents=[_incident_to_summary(inc).to_dict() for inc in samples],
    ).to_dict()


def causal_lookup(
    session: Session,
    entity: str,
    relation_type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Look up causal/co-occurrence relations for an entity name."""
    from src.models import Relation as RelModel, EntityMention
    from sqlalchemy import or_

    filters = [or_(
        RelModel.source_entity_raw.ilike(f"%{entity}%"),
        RelModel.target_entity_raw.ilike(f"%{entity}%"),
    )]
    if relation_type:
        filters.append(RelModel.relation_type == relation_type)

    stmt = select(RelModel).where(and_(*filters)).limit(limit)
    rels = session.scalars(stmt).all()
    return [
        {
            "source": r.source_entity_raw,
            "relation": r.relation_type,
            "target": r.target_entity_raw,
            "confidence": r.confidence,
            "incident_id": r.incident_id,
        }
        for r in rels
    ]


def get_incident(session: Session, incident_id: int) -> dict:
    """Return full detail for a single incident."""
    inc = session.get(Incident, incident_id)
    if not inc:
        return {"error": f"Incident {incident_id} not found"}
    return IncidentDetail(
        id=inc.id,
        cfpb_id=inc.cfpb_id,
        narrative=inc.narrative[:1000],
        date_received=str(inc.date_received) if inc.date_received else None,
        one_sentence_summary=inc.one_sentence_summary,
        root_cause_summary=inc.root_cause_summary,
        customer_impact_summary=inc.customer_impact_summary,
        product_domain=inc.product_domain,
        basel_category=inc.basel_category,
        root_cause_type=inc.root_cause_type,
        financial_impact=inc.financial_impact,
        detection_stage=inc.detection_stage,
        third_party_involved=inc.third_party_involved,
        automated_system_involved=inc.automated_system_involved,
        regulatory_implication=inc.regulatory_implication,
        suggests_recurring_pattern=inc.suggests_recurring_pattern,
        affected_systems=inc.affected_systems or [],
        keywords=inc.keywords or [],
    ).to_dict()


# ── helper ─────────────────────────────────────────────────────────────────────

def _incident_to_summary(inc: Incident) -> IncidentSummary:
    return IncidentSummary(
        id=inc.id,
        cfpb_id=inc.cfpb_id,
        date_received=str(inc.date_received) if inc.date_received else None,
        one_sentence_summary=inc.one_sentence_summary,
        product_domain=inc.product_domain,
        basel_category=inc.basel_category,
        financial_impact=inc.financial_impact,
        root_cause_type=inc.root_cause_type,
    )
