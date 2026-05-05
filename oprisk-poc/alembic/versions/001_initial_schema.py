"""Initial schema — all tables.

Revision ID: 001
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "incidents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cfpb_id", sa.String(64), unique=True, nullable=True),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("date_received", sa.Date(), nullable=True),
        sa.Column("one_sentence_summary", sa.Text(), nullable=True),
        sa.Column("root_cause_summary", sa.Text(), nullable=True),
        sa.Column("customer_impact_summary", sa.Text(), nullable=True),
        sa.Column("basel_category", sa.String(64), nullable=True),
        sa.Column("product_domain", sa.String(64), nullable=True),
        sa.Column("root_cause_type", sa.String(64), nullable=True),
        sa.Column("financial_impact", sa.String(32), nullable=True),
        sa.Column("detection_stage", sa.String(32), nullable=True),
        sa.Column("third_party_involved", sa.Boolean(), nullable=True),
        sa.Column("automated_system_involved", sa.Boolean(), nullable=True),
        sa.Column("customer_facing", sa.Boolean(), nullable=True),
        sa.Column("regulatory_implication", sa.Boolean(), nullable=True),
        sa.Column("suggests_recurring_pattern", sa.Boolean(), nullable=True),
        sa.Column("affected_systems", ARRAY(sa.Text()), nullable=True),
        sa.Column("keywords", ARRAY(sa.Text()), nullable=True),
        sa.Column("cfpb_product", sa.String(128), nullable=True),
        sa.Column("cfpb_issue", sa.String(256), nullable=True),
        sa.Column("vec_summary", Vector(1024), nullable=True),
        sa.Column("vec_root_cause", Vector(1024), nullable=True),
        sa.Column("vec_impact", Vector(1024), nullable=True),
        sa.Column("cluster_id_novelty", sa.Integer(), nullable=True),
        sa.Column("cluster_id_summary", sa.Integer(), nullable=True),
        sa.Column("cluster_id_root_cause", sa.Integer(), nullable=True),
        sa.Column("cluster_id_impact", sa.Integer(), nullable=True),
    )

    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("aliases", ARRAY(sa.Text()), nullable=True),
        sa.UniqueConstraint("entity_type", "canonical_name", name="uq_entity_type_name"),
    )

    op.create_table(
        "entity_mentions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), sa.ForeignKey("entities.id"), nullable=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("raw_name", sa.Text(), nullable=False),
        sa.Column("facet", sa.String(32), nullable=True),
        sa.Column("evidence_span", sa.Text(), nullable=True),
    )

    op.create_table(
        "relations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("source_entity_raw", sa.Text(), nullable=False),
        sa.Column("target_entity_raw", sa.Text(), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
    )

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facet", sa.String(32), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("clusters.id"), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("keywords", ARRAY(sa.Text()), nullable=True),
    )

    op.create_table(
        "novelty_queue",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("incident_id", sa.BigInteger(), sa.ForeignKey("incidents.id"), unique=True),
        sa.Column("noise_score", sa.Float(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), default=False),
    )

    op.create_table(
        "cluster_signals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("facet", sa.String(32), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("signal", sa.String(32), nullable=True),
        sa.Column("poisson_pvalue", sa.Float(), nullable=True),
        sa.Column("bocpd_changepoint", sa.Boolean(), nullable=True),
        sa.Column("popularity_score", sa.Float(), nullable=True),
        sa.UniqueConstraint("cluster_id", "facet", "month", name="uq_cluster_signal"),
    )

    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.Text(), nullable=True),
        sa.Column("assistant_response", sa.Text(), nullable=True),
        sa.Column("incident_ids_cited", ARRAY(sa.BigInteger()), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=True),
    )

    # HNSW indexes (created after table, pgvector syntax)
    op.execute("""
        CREATE INDEX incidents_vec_summary_hnsw
        ON incidents USING hnsw (vec_summary vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX incidents_vec_root_cause_hnsw
        ON incidents USING hnsw (vec_root_cause vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX incidents_vec_impact_hnsw
        ON incidents USING hnsw (vec_impact vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.drop_table("agent_sessions")
    op.drop_table("cluster_signals")
    op.drop_table("novelty_queue")
    op.drop_table("clusters")
    op.drop_table("relations")
    op.drop_table("entity_mentions")
    op.drop_table("entities")
    op.drop_table("incidents")
    op.execute("DROP EXTENSION IF EXISTS vector")
