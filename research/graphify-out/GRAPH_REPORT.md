# Graph Report - research  (2026-05-05)

## Corpus Check
- Corpus is ~4,460 words - fits in a single context window. You may not need a graph.

## Summary
- 55 nodes · 77 edges · 10 communities (8 shown, 2 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.82)
- Token cost: 4,200 input · 3,100 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Datasets & Academic References|Datasets & Academic References]]
- [[_COMMUNITY_Knowledge Graph & Causal Analysis|Knowledge Graph & Causal Analysis]]
- [[_COMMUNITY_Conversational Interface & Market Practices|Conversational Interface & Market Practices]]
- [[_COMMUNITY_Topic Modeling Methods|Topic Modeling Methods]]
- [[_COMMUNITY_Temporal Analysis & Drift Detection|Temporal Analysis & Drift Detection]]
- [[_COMMUNITY_Core Architecture (Embedding + Clustering)|Core Architecture (Embedding + Clustering)]]
- [[_COMMUNITY_Self-Service Classification Loop|Self-Service Classification Loop]]
- [[_COMMUNITY_OpRisk Classification Research|OpRisk Classification Research]]
- [[_COMMUNITY_Regulatory Framework (Basel4557)|Regulatory Framework (Basel/4557)]]
- [[_COMMUNITY_Test Datasets (Postmortems)|Test Datasets (Postmortems)]]

## God Nodes (most connected - your core abstractions)
1. `Operational Risk Incident Intelligence POC` - 19 edges
2. `Research Decision Validation Table (D1-D8)` - 11 edges
3. `Research Plan 1 — Modern Topic Modeling` - 8 edges
4. `Research Plan 2 — Self-Service Classification` - 6 edges
5. `Research Plan 3 — Causal and Relational Analysis` - 6 edges
6. `Research Plan 4 — Temporal Analysis and Novelty Detection` - 6 edges
7. `Research Plan 5 — Conversational Interface and Market Practices` - 6 edges
8. `Self-Service Classification Capability` - 4 edges
9. `Microsoft GraphRAG` - 4 edges
10. `ADR 6: No Knowledge Graph in v1` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Microsoft GraphRAG` --semantically_similar_to--> `LightRAG`  [INFERRED] [semantically similar]
  research/raw/00-initial-brief.md → research/round-1/plans.md
- `Hybrid RAG (Semantic Search + SQL in same agent)` --semantically_similar_to--> `NL Q&A Agent (text-to-SQL + semantic search)`  [INFERRED] [semantically similar]
  research/round-1/plans.md → research/raw/00-initial-brief.md
- `Intelligence Platform Reframe (vs pure BI classification)` --rationale_for--> `Operational Risk Incident Intelligence POC`  [EXTRACTED]
  research/decisions/00-brief-reading-notes.md → research/raw/00-initial-brief.md
- `Graphify Tool Setup` --references--> `Operational Risk Incident Intelligence POC`  [EXTRACTED]
  research/decisions/00-brief-reading-notes.md → research/raw/00-initial-brief.md
- `Research Decision Validation Table (D1-D8)` --references--> `LLM Pre-Extraction before Clustering`  [EXTRACTED]
  research/decisions/00-brief-reading-notes.md → research/raw/00-initial-brief.md

## Hyperedges (group relationships)
- **Topic Modeling Pipeline: LLM Extraction + Embedding + HDBSCAN** — 00_initial_brief_llm_pre_extraction, 00_initial_brief_embedding_strategy, 00_initial_brief_hdbscan_umap, 00_initial_brief_clio_approach [EXTRACTED 0.95]
- **5 Research Plans collectively validate 8 architectural decisions in D1-D8 table** — plans_plan1_topic_modeling, plans_plan2_selfservice_classification, plans_plan3_causal_relational, plans_plan4_temporal_novelty, plans_plan5_conversational_market, notes_decision_table [EXTRACTED 0.95]
- **Knowledge Graph technologies collectively address causal/relational analysis gap (ADR 6 reconsideration)** — 00_initial_brief_graphrag, 00_initial_brief_graphiti, plans_lightrag, plans_adr6_reconsideration, plans_plan3_causal_relational [INFERRED 0.85]

## Communities (10 total, 2 thin omitted)

### Community 0 - "Datasets & Academic References"
Cohesion: 0.2
Nodes (10): CFPB Consumer Complaint Database, Post-POC Migration to Client (PT-BR), arXiv:2212.01285 — Text Analysis for OpRisk Loss Descriptions, arXiv:2301.05663 — NLP of Aviation Occurrence Reports, Pakhchanyan et al. (2022) — ML for OpRisk Basel Classification, Operational Risk Incident Intelligence POC, Self-Service Investigation Capability, Weak Signal Discovery Capability (+2 more)

### Community 1 - "Knowledge Graph & Causal Analysis"
Cohesion: 0.33
Nodes (9): ADR 6: No Knowledge Graph in v1, Graphiti (getzep), Microsoft GraphRAG, arXiv:2310.12074 — IncidentAI (Cinnamon/ACL), UCI Incident Management Process Event Log, ADR 6 Reconsideration (KG in v1), LightRAG, Research Plan 3 — Causal and Relational Analysis (+1 more)

### Community 2 - "Conversational Interface & Market Practices"
Cohesion: 0.29
Nodes (8): Capgemini Invent OpRisk Tools, NL Q&A Agent (text-to-SQL + semantic search), Streamlit UI, Conversational Self-Service as Key Differentiator vs BI Dashboard, DSPy (Stanford NLP), Hybrid RAG (Semantic Search + SQL in same agent), Research Plan 5 — Conversational Interface and Market Practices, Text-to-SQL for Incident Analysis

### Community 3 - "Topic Modeling Methods"
Cohesion: 0.38
Nodes (7): BERTopic Naive Clustering Failure, Clio-style Faceted Summarization, LLM Pre-Extraction before Clustering, BERTopic, Neural Topic Models (ProdLDA/ETM), Research Plan 1 — Modern Topic Modeling, Top2Vec

### Community 4 - "Temporal Analysis & Drift Detection"
Cohesion: 0.53
Nodes (6): Prophet/Z-score Temporal Signal Detection, Temporal Analysis Gap (Prophet/z-score rudimentary), Changepoint Detection (PELT, BOCPD), Concept Drift Detection, Dynamic Topic Models (DTM, Blei & Lafferty 2006), Research Plan 4 — Temporal Analysis and Novelty Detection

### Community 5 - "Core Architecture (Embedding + Clustering)"
Cohesion: 0.5
Nodes (5): Multi-field Embedding Strategy (summary fields), UMAP + HDBSCAN Clustering Pipeline, pgvector Vector Store, Pydantic Schema with Orthogonal Facets, Research Decision Validation Table (D1-D8)

### Community 6 - "Self-Service Classification Loop"
Cohesion: 0.67
Nodes (4): Active Learning (uncertainty sampling, query-by-committee), Annotation Tools (Argilla, Label Studio, Prodigy), Research Plan 2 — Self-Service Classification, Snorkel / Weak Supervision

### Community 7 - "OpRisk Classification Research"
Cohesion: 0.67
Nodes (3): SemiORC (ACL 2020) — Semi-supervised OpRisk Classification, Self-Service Classification Capability, Dynamic Topic Hierarchy Gap (online sub-cluster decomposition)

## Knowledge Gaps
- **18 isolated node(s):** `CFPB Consumer Complaint Database`, `Weak Signal Discovery Capability`, `Self-Service Investigation Capability`, `Resolução 4557 BCB`, `Pakhchanyan et al. (2022) — ML for OpRisk Basel Classification` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Operational Risk Incident Intelligence POC` connect `Datasets & Academic References` to `Knowledge Graph & Causal Analysis`, `Conversational Interface & Market Practices`, `Core Architecture (Embedding + Clustering)`, `OpRisk Classification Research`, `Regulatory Framework (Basel/4557)`?**
  _High betweenness centrality (0.519) - this node is a cross-community bridge._
- **Why does `Research Decision Validation Table (D1-D8)` connect `Core Architecture (Embedding + Clustering)` to `Knowledge Graph & Causal Analysis`, `Conversational Interface & Market Practices`, `Topic Modeling Methods`, `Temporal Analysis & Drift Detection`, `Self-Service Classification Loop`?**
  _High betweenness centrality (0.419) - this node is a cross-community bridge._
- **Why does `Research Plan 1 — Modern Topic Modeling` connect `Topic Modeling Methods` to `Temporal Analysis & Drift Detection`, `Core Architecture (Embedding + Clustering)`, `Self-Service Classification Loop`?**
  _High betweenness centrality (0.158) - this node is a cross-community bridge._
- **What connects `CFPB Consumer Complaint Database`, `Weak Signal Discovery Capability`, `Self-Service Investigation Capability` to the rest of the system?**
  _18 weakly-connected nodes found - possible documentation gaps or missing edges._