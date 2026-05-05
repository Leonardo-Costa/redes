"""Streamlit 4-tab OpRisk POC dashboard."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import select, func, text

load_dotenv()

from src.db import get_engine, get_session_factory
from src.models import Incident, Cluster, ClusterSignal, NoveltyQueue
from src.ui.agent import run_agent

st.set_page_config(
    page_title="OpRisk Intelligence POC",
    page_icon="⚠️",
    layout="wide",
)

# ── session state ──────────────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── db connection ──────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    engine = get_engine()
    return get_session_factory(engine)


SessionFactory = get_db()


def get_session():
    return SessionFactory()


# ── sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("⚠️ OpRisk Intelligence")
st.sidebar.markdown("POC — CFPB Synthetic Dataset")

with get_session() as s:
    total = s.scalar(select(func.count(Incident.id))) or 0
    extracted = s.scalar(
        select(func.count(Incident.id)).where(Incident.one_sentence_summary.isnot(None))
    ) or 0
    novelty_pending = s.scalar(
        select(func.count(NoveltyQueue.id)).where(NoveltyQueue.reviewed == False)
    ) or 0

st.sidebar.metric("Total incidents", total)
st.sidebar.metric("Extracted", f"{extracted}/{total}")
st.sidebar.metric("Novelty queue", novelty_pending)

# ── tabs ───────────────────────────────────────────────────────────────────────

tab_explore, tab_ask, tab_curate, tab_trends = st.tabs(
    ["🔍 Explore", "💬 Ask", "🏷️ Curate", "📈 Trends"]
)

# ────────────────────────────────────────────────────────────────────────────────
# TAB 1: EXPLORE
# ────────────────────────────────────────────────────────────────────────────────

with tab_explore:
    st.header("Incident Explorer")

    col1, col2, col3 = st.columns(3)
    with col1:
        product_filter = st.selectbox(
            "Product domain",
            ["All", "credit_card", "mortgage", "checking_savings", "student_loan",
             "auto_loan", "debt_collection", "credit_reporting", "money_transfers"],
        )
    with col2:
        impact_filter = st.selectbox(
            "Financial impact",
            ["All", "high", "medium", "low", "none", "unclear"],
        )
    with col3:
        basel_filter = st.selectbox(
            "Basel category",
            ["All", "execution_delivery_process", "clients_products_practices",
             "external_fraud", "internal_fraud", "business_disruption_systems",
             "employment_practices", "damage_physical_assets", "unclear"],
        )

    with get_session() as s:
        q = select(Incident).where(Incident.one_sentence_summary.isnot(None))
        if product_filter != "All":
            q = q.where(Incident.product_domain == product_filter)
        if impact_filter != "All":
            q = q.where(Incident.financial_impact == impact_filter)
        if basel_filter != "All":
            q = q.where(Incident.basel_category == basel_filter)
        q = q.limit(500)
        incidents = s.scalars(q).all()

        if incidents:
            df = pd.DataFrame([{
                "ID": i.id,
                "Date": i.date_received,
                "Product": i.product_domain,
                "Basel": i.basel_category,
                "Root cause": i.root_cause_type,
                "Impact": i.financial_impact,
                "Summary": (i.one_sentence_summary or "")[:120],
            } for i in incidents])

            # Distribution chart
            col_a, col_b = st.columns(2)
            with col_a:
                fig = px.histogram(df, x="Product", title="By Product Domain",
                                   color_discrete_sequence=["#3b82f6"])
                fig.update_layout(showlegend=False, height=300)
                st.plotly_chart(fig, use_container_width=True)
            with col_b:
                fig = px.histogram(df, x="Basel", title="By Basel Category",
                                   color_discrete_sequence=["#f59e0b"])
                fig.update_layout(showlegend=False, height=300)
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No incidents match the selected filters (or extraction not yet complete).")

    # UMAP scatter (only if embeddings exist)
    with get_session() as s:
        n_embedded = s.scalar(
            select(func.count(Incident.id)).where(Incident.vec_summary.isnot(None))
        ) or 0

    if n_embedded > 50:
        st.subheader("Cluster Map (UMAP 2D)")
        with get_session() as s:
            rows = s.execute(
                select(Incident.id, Incident.vec_summary, Incident.cluster_id_summary,
                       Incident.product_domain)
                .where(Incident.vec_summary.isnot(None))
                .limit(1000)
            ).all()
        if rows:
            import numpy as np
            import umap as umap_lib
            ids = [r[0] for r in rows]
            vecs = np.array([r[1] for r in rows], dtype=np.float32)
            clusters = [str(r[2]) if r[2] is not None else "?" for r in rows]
            products = [r[3] or "?" for r in rows]
            reducer = umap_lib.UMAP(n_components=2, random_state=42, n_jobs=1)
            xy = reducer.fit_transform(vecs)
            scatter_df = pd.DataFrame({
                "x": xy[:, 0], "y": xy[:, 1],
                "cluster": clusters, "product": products,
                "id": ids,
            })
            fig = px.scatter(scatter_df, x="x", y="y", color="product",
                             hover_data=["id", "cluster"],
                             title="Incidents colored by product domain")
            fig.update_traces(marker=dict(size=4, opacity=0.7))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
    elif n_embedded == 0:
        st.info("Run `python -m src.embed.pipeline` to generate embeddings for the cluster map.")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 2: ASK
# ────────────────────────────────────────────────────────────────────────────────

with tab_ask:
    st.header("Ask the Analyst Agent")
    st.caption("Ask questions about incident patterns, root causes, and trends.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("cited_ids"):
                st.caption(f"Cited incidents: {msg['cited_ids']}")

    if prompt := st.chat_input("e.g. What are the top recurring root causes?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                with get_session() as s:
                    try:
                        response, cited_ids = run_agent(
                            prompt, s,
                            session_id=st.session_state.session_id,
                        )
                    except Exception as e:
                        response = f"Error: {e}"
                        cited_ids = []
            st.markdown(response)
            if cited_ids:
                st.caption(f"Cited incidents: {cited_ids[:20]}")

        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "cited_ids": cited_ids,
        })

# ────────────────────────────────────────────────────────────────────────────────
# TAB 3: CURATE
# ────────────────────────────────────────────────────────────────────────────────

with tab_curate:
    st.header("Taxonomy Curator")
    st.caption("Define custom risk categories and bootstrap labels with the LLM.")

    st.subheader("Cluster Labels (Summary Facet)")
    with get_session() as s:
        clusters = s.scalars(
            select(Cluster).where(Cluster.facet == "summary").order_by(Cluster.size.desc())
        ).all()

    if clusters:
        cluster_data = []
        for c in clusters:
            cluster_data.append({
                "ID": c.id,
                "Label": c.label or "(unlabeled)",
                "Size": c.size,
                "Facet": c.facet,
            })
        st.dataframe(pd.DataFrame(cluster_data), use_container_width=True)
    else:
        st.info("No clusters yet. Run `python -m src.cluster.passes` after embedding.")

    st.subheader("Novelty Queue")
    with get_session() as s:
        queue = s.scalars(
            select(NoveltyQueue).where(NoveltyQueue.reviewed == False).limit(20)
        ).all()

    if queue:
        for item in queue:
            with get_session() as s:
                inc = s.get(Incident, item.incident_id)
            if inc:
                with st.expander(f"Incident {inc.id} — {inc.cfpb_product or 'unknown'}"):
                    st.write(inc.narrative[:400])
                    if st.button(f"Mark reviewed #{inc.id}", key=f"rev_{inc.id}"):
                        with get_session() as s:
                            nq = s.get(NoveltyQueue, item.id)
                            if nq:
                                nq.reviewed = True
                                s.commit()
                        st.rerun()
    else:
        st.success("Novelty queue is empty or clustering not yet run.")

# ────────────────────────────────────────────────────────────────────────────────
# TAB 4: TRENDS
# ────────────────────────────────────────────────────────────────────────────────

with tab_trends:
    st.header("Temporal Trends")

    with get_session() as s:
        signals = s.scalars(
            select(ClusterSignal).order_by(ClusterSignal.popularity_score.desc()).limit(100)
        ).all()

    if signals:
        sig_df = pd.DataFrame([{
            "Cluster": s.cluster_id,
            "Facet": s.facet,
            "Month": s.month,
            "Count": s.count,
            "Signal": s.signal,
            "P-value": round(s.poisson_pvalue, 4) if s.poisson_pvalue else None,
            "Changepoint": s.bocpd_changepoint,
            "Popularity": round(s.popularity_score, 2) if s.popularity_score else None,
        } for s in signals])

        col1, col2, col3, col4 = st.columns(4)
        growing = sig_df[sig_df["Signal"] == "growing"]
        emerging = sig_df[sig_df["Signal"] == "emerging"]
        col1.metric("Growing clusters", len(growing))
        col2.metric("Emerging clusters", len(emerging))
        col3.metric("Shrinking", len(sig_df[sig_df["Signal"] == "shrinking"]))
        col4.metric("Stable", len(sig_df[sig_df["Signal"] == "stable"]))

        st.subheader("Signal Table")
        signal_filter = st.multiselect(
            "Filter by signal",
            ["growing", "emerging", "shrinking", "stable"],
            default=["growing", "emerging"],
        )
        filtered = sig_df[sig_df["Signal"].isin(signal_filter)] if signal_filter else sig_df
        st.dataframe(filtered, use_container_width=True)

        # Monthly counts chart per facet
        st.subheader("Monthly Counts by Signal")
        with get_session() as s:
            rows = s.execute(
                select(Incident.date_received, Incident.product_domain)
                .where(Incident.date_received.isnot(None))
                .where(Incident.one_sentence_summary.isnot(None))
            ).all()
        if rows:
            time_df = pd.DataFrame(rows, columns=["date_received", "product_domain"])
            time_df["date_received"] = pd.to_datetime(time_df["date_received"])
            time_df["month"] = time_df["date_received"].dt.to_period("M").dt.to_timestamp()
            monthly = time_df.groupby(["month", "product_domain"]).size().reset_index(name="count")
            fig = px.line(monthly, x="month", y="count", color="product_domain",
                          title="Monthly Incident Count by Product Domain")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No temporal signals yet. Run `python -m src.temporal.stack` after clustering.")
