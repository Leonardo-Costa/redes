"""Tests for UI tool functions using a SQLite in-memory DB."""
import pytest
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models import Incident, Cluster, ClusterSignal, NoveltyQueue


@pytest.fixture(scope="module")
def session():
    """In-memory SQLite session with sample data (no pgvector/ARRAY)."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    # Create simplified tables manually — SQLite doesn't support ARRAY or Vector
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE incidents (
                id INTEGER PRIMARY KEY,
                cfpb_id TEXT,
                narrative TEXT NOT NULL,
                date_received TEXT,
                one_sentence_summary TEXT,
                root_cause_summary TEXT,
                customer_impact_summary TEXT,
                basel_category TEXT,
                product_domain TEXT,
                root_cause_type TEXT,
                financial_impact TEXT,
                detection_stage TEXT,
                third_party_involved INTEGER,
                automated_system_involved INTEGER,
                customer_facing INTEGER,
                regulatory_implication INTEGER,
                suggests_recurring_pattern INTEGER,
                affected_systems TEXT,
                keywords TEXT,
                cfpb_product TEXT,
                cfpb_issue TEXT,
                vec_summary TEXT,
                vec_root_cause TEXT,
                vec_impact TEXT,
                cluster_id_novelty INTEGER,
                cluster_id_summary INTEGER,
                cluster_id_root_cause INTEGER,
                cluster_id_impact INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE clusters (
                id INTEGER PRIMARY KEY,
                facet TEXT NOT NULL,
                label TEXT,
                parent_id INTEGER,
                size INTEGER,
                keywords TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE cluster_signals (
                id INTEGER PRIMARY KEY,
                cluster_id INTEGER NOT NULL,
                facet TEXT NOT NULL,
                month TEXT NOT NULL,
                count INTEGER NOT NULL,
                signal TEXT,
                poisson_pvalue REAL,
                bocpd_changepoint INTEGER,
                popularity_score REAL
            )
        """))
        conn.execute(text("""
            CREATE TABLE novelty_queue (
                id INTEGER PRIMARY KEY,
                incident_id INTEGER,
                noise_score REAL,
                reviewed INTEGER DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY,
                entity_type TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                aliases TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE entity_mentions (
                id INTEGER PRIMARY KEY,
                incident_id INTEGER,
                entity_id INTEGER,
                entity_type TEXT,
                raw_name TEXT,
                facet TEXT,
                evidence_span TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE relations (
                id INTEGER PRIMARY KEY,
                incident_id INTEGER,
                relation_type TEXT,
                source_entity_raw TEXT,
                target_entity_raw TEXT,
                evidence_span TEXT,
                confidence REAL
            )
        """))
        conn.execute(text("""
            CREATE TABLE agent_sessions (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                user_message TEXT,
                tool_calls TEXT,
                assistant_response TEXT,
                incident_ids_cited TEXT,
                created_at TEXT
            )
        """))
        conn.commit()

    Session = sessionmaker(bind=engine)
    s = Session()

    # Insert sample incidents
    for i in range(20):
        inc = Incident(
            cfpb_id=f"TEST-{i:04d}",
            narrative=f"Customer complained about issue {i} with their account.",
            date_received=date(2022 + (i % 3), (i % 12) + 1, 1),
            one_sentence_summary=f"Incident {i} summary.",
            root_cause_summary=f"Root cause {i}.",
            customer_impact_summary=f"Impact {i}.",
            product_domain="credit_card" if i % 2 == 0 else "mortgage",
            basel_category="execution_delivery_process",
            root_cause_type="process_failure",
            financial_impact="medium" if i % 3 == 0 else "low",
            detection_stage="customer_reported",
            third_party_involved=False,
            automated_system_involved=True,
            customer_facing=True,
            regulatory_implication=False,
            suggests_recurring_pattern=i % 5 == 0,
            cluster_id_summary=i % 5,
            cluster_id_root_cause=i % 3,
            cluster_id_impact=i % 4,
        )
        s.add(inc)

    for cluster_id in range(5):
        s.add(Cluster(id=cluster_id, facet="summary", label=f"Cluster {cluster_id}", size=4))
        s.add(ClusterSignal(
            cluster_id=cluster_id,
            facet="summary",
            month=date(2024, 1, 1),
            count=10 + cluster_id,
            signal="stable" if cluster_id < 3 else "growing",
            poisson_pvalue=0.05,
            bocpd_changepoint=False,
            popularity_score=float(cluster_id * 10),
        ))

    s.commit()
    yield s
    s.close()


def test_filter_incidents_no_filters(session):
    from src.ui.tools import filter_incidents
    results = filter_incidents(session, limit=5)
    assert len(results) == 5
    assert "id" in results[0]
    assert "summary" in results[0]


def test_filter_incidents_by_product(session):
    from src.ui.tools import filter_incidents
    results = filter_incidents(session, product="credit_card", limit=50)
    assert all(r["product_domain"] == "credit_card" for r in results)


def test_filter_incidents_by_impact(session):
    from src.ui.tools import filter_incidents
    results = filter_incidents(session, financial_impact="medium", limit=50)
    assert all(r["financial_impact"] == "medium" for r in results)


def test_filter_incidents_by_date(session):
    from src.ui.tools import filter_incidents
    results = filter_incidents(session, date_from="2022-01-01", date_to="2022-12-31", limit=50)
    for r in results:
        if r["date_received"]:
            year = int(r["date_received"][:4])
            assert year == 2022


def test_filter_incidents_by_cluster(session):
    from src.ui.tools import filter_incidents
    results = filter_incidents(session, cluster_id=0, facet="summary", limit=50)
    assert len(results) > 0


def test_get_incident_found(session):
    from src.ui.tools import get_incident
    result = get_incident(session, 1)
    assert "narrative" in result
    assert result["id"] == 1


def test_get_incident_not_found(session):
    from src.ui.tools import get_incident
    result = get_incident(session, 99999)
    assert "error" in result


def test_temporal_signal_found(session):
    from src.ui.tools import temporal_signal
    result = temporal_signal(session, cluster_id=0, facet="summary")
    assert "signal" in result
    assert result["cluster_id"] == 0


def test_temporal_signal_not_found(session):
    from src.ui.tools import temporal_signal
    result = temporal_signal(session, cluster_id=999, facet="summary")
    assert "error" in result


def test_cluster_summary(session):
    from src.ui.tools import cluster_summary
    result = cluster_summary(session, cluster_id=0, facet="summary")
    assert result["cluster_id"] == 0
    assert "label" in result
    assert isinstance(result["sample_incidents"], list)


def test_causal_lookup_no_results(session):
    from src.ui.tools import causal_lookup
    results = causal_lookup(session, entity="nonexistent_entity_xyz")
    assert isinstance(results, list)
    assert len(results) == 0
