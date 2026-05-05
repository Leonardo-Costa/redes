"""SQLAlchemy ORM models."""
from __future__ import annotations
from datetime import date
from sqlalchemy import (
    BigInteger, Boolean, Date, Float, ForeignKey, Integer,
    String, Text, ARRAY, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from src.db import Base


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cfpb_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    date_received: Mapped[date | None] = mapped_column(Date)

    # Extracted summaries (embedded)
    one_sentence_summary: Mapped[str | None] = mapped_column(Text)
    root_cause_summary: Mapped[str | None] = mapped_column(Text)
    customer_impact_summary: Mapped[str | None] = mapped_column(Text)

    # Structured classifications
    basel_category: Mapped[str | None] = mapped_column(String(64))
    product_domain: Mapped[str | None] = mapped_column(String(64))
    root_cause_type: Mapped[str | None] = mapped_column(String(64))
    financial_impact: Mapped[str | None] = mapped_column(String(32))
    detection_stage: Mapped[str | None] = mapped_column(String(32))

    # Booleans
    third_party_involved: Mapped[bool | None] = mapped_column(Boolean)
    automated_system_involved: Mapped[bool | None] = mapped_column(Boolean)
    customer_facing: Mapped[bool | None] = mapped_column(Boolean)
    regulatory_implication: Mapped[bool | None] = mapped_column(Boolean)
    suggests_recurring_pattern: Mapped[bool | None] = mapped_column(Boolean)

    # Lists stored as arrays
    affected_systems: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    # CFPB ground truth (for validation)
    cfpb_product: Mapped[str | None] = mapped_column(String(128))
    cfpb_issue: Mapped[str | None] = mapped_column(String(256))

    # Embeddings (3 facets, 1024-dim for bge-large-en-v1.5)
    vec_summary: Mapped[list[float] | None] = mapped_column(Vector(1024))
    vec_root_cause: Mapped[list[float] | None] = mapped_column(Vector(1024))
    vec_impact: Mapped[list[float] | None] = mapped_column(Vector(1024))

    # Cluster assignments
    cluster_id_novelty: Mapped[int | None] = mapped_column(Integer)
    cluster_id_summary: Mapped[int | None] = mapped_column(Integer)
    cluster_id_root_cause: Mapped[int | None] = mapped_column(Integer)
    cluster_id_impact: Mapped[int | None] = mapped_column(Integer)

    entity_mentions: Mapped[list[EntityMention]] = relationship(back_populates="incident")
    relations: Mapped[list[Relation]] = relationship(back_populates="incident")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32))  # product/channel/process/error_code/actor
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    __table_args__ = (UniqueConstraint("entity_type", "canonical_name"),)

    mentions: Mapped[list[EntityMention]] = relationship(back_populates="entity")


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("incidents.id"), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("entities.id"))
    entity_type: Mapped[str] = mapped_column(String(32))
    raw_name: Mapped[str] = mapped_column(Text)
    facet: Mapped[str | None] = mapped_column(String(32))  # summary/root_cause/impact
    evidence_span: Mapped[str | None] = mapped_column(Text)

    incident: Mapped[Incident] = relationship(back_populates="entity_mentions")
    entity: Mapped[Entity | None] = relationship(back_populates="mentions")


class Relation(Base):
    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("incidents.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32))  # cause_of/observed_with/impacts/precedes
    source_entity_raw: Mapped[str] = mapped_column(Text)
    target_entity_raw: Mapped[str] = mapped_column(Text)
    evidence_span: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    incident: Mapped[Incident] = relationship(back_populates="relations")


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facet: Mapped[str] = mapped_column(String(32))  # summary/root_cause/impact/novelty
    label: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clusters.id"))
    size: Mapped[int | None] = mapped_column(Integer)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class NoveltyQueue(Base):
    __tablename__ = "novelty_queue"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("incidents.id"), unique=True)
    noise_score: Mapped[float | None] = mapped_column(Float)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class ClusterSignal(Base):
    __tablename__ = "cluster_signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(Integer, ForeignKey("clusters.id"))
    facet: Mapped[str] = mapped_column(String(32))
    month: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer)
    signal: Mapped[str | None] = mapped_column(String(32))  # growing/shrinking/emerging/stable/noise
    poisson_pvalue: Mapped[float | None] = mapped_column(Float)
    bocpd_changepoint: Mapped[bool | None] = mapped_column(Boolean)
    popularity_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("cluster_id", "facet", "month"),)


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64))
    user_message: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[str | None] = mapped_column(Text)  # JSON
    assistant_response: Mapped[str | None] = mapped_column(Text)
    incident_ids_cited: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    created_at: Mapped[str | None] = mapped_column(String(32))
