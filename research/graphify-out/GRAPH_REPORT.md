# Graph Report - research  (2026-05-05)

## Corpus Check
- 8 files · ~22,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 177 nodes · 269 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 42 edges (avg confidence: 0.86)
- Token cost: 4,200 input · 3,100 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Core Architecture & Brief Spec|Core Architecture & Brief Spec]]
- [[_COMMUNITY_Topic Modeling Methods (Plan 1)|Topic Modeling Methods (Plan 1)]]
- [[_COMMUNITY_Temporal Analysis & Novelty Detection (Plan 4)|Temporal Analysis & Novelty Detection (Plan 4)]]
- [[_COMMUNITY_Conversational Interface & Market Practices (Plan 5)|Conversational Interface & Market Practices (Plan 5)]]
- [[_COMMUNITY_Architectural Decision Validation (D1-D8)|Architectural Decision Validation (D1-D8)]]
- [[_COMMUNITY_Causal & Relational Analysis (Plan 3)|Causal & Relational Analysis (Plan 3)]]
- [[_COMMUNITY_Topic Modeling Baselines & Failures|Topic Modeling Baselines & Failures]]
- [[_COMMUNITY_Knowledge Graph & GraphRAG Research|Knowledge Graph & GraphRAG Research]]
- [[_COMMUNITY_Temporal Baselines & Drift Detection|Temporal Baselines & Drift Detection]]
- [[_COMMUNITY_Postmortem Datasets|Postmortem Datasets]]
- [[_COMMUNITY_Neural Topic Models|Neural Topic Models]]

## God Nodes (most connected - your core abstractions)
1. `Plan 1 — Modern Topic Modeling: Which Approach Wins on Incident Corpora?` - 32 edges
2. `Plan 5 — Conversational Interface and Market Practices` - 28 edges
3. `Plan 4 — Temporal Analysis and Novelty Detection` - 27 edges
4. `Plan 2 — Self-Service Classification: Runtime Taxonomy Definition and Refinement` - 21 edges
5. `Plan 3 — Causal and Relational Analysis: Beyond Semantic Search` - 20 edges
6. `Operational Risk Incident Intelligence POC` - 19 edges
7. `Research Decision Validation Table (D1-D8)` - 11 edges
8. `Research Plan 1 — Modern Topic Modeling` - 9 edges
9. `Research Plan 2 — Self-Service Classification` - 7 edges
10. `Research Plan 3 — Causal and Relational Analysis` - 7 edges

## Surprising Connections (you probably didn't know these)
- `Clio-style pipeline: LLM facet extraction → embed summary → cluster → recursive label` --semantically_similar_to--> `Teacher-student loop (LLM teacher → SetFit student)`  [INFERRED] [semantically similar]
  research/round-1/plan-1-topic-modeling.md → research/round-1/plan-2-selfservice-classification.md
- `Plan 5 — Conversational Interface and Market Practices` --conceptually_related_to--> `Research Plan Template Schema`  [INFERRED]
  research/round-1/plan-5-conversational-market.md → research/round-1/TEMPLATE.md
- `BERTrend — Neural Topic Modeling for Emerging Trends Detection` --semantically_similar_to--> `Capgemini Invent OpRisk Tools — Taxonomy Rationalization + Weak Signals Analysis`  [INFERRED] [semantically similar]
  research/round-1/plan-4-temporal-novelty.md → research/round-1/plan-5-conversational-market.md
- `3-Test Gate for emergence — persistence + coherence + Poisson significance` --semantically_similar_to--> `Audit Trail Requirement — every agent answer must cite incident IDs and show tool calls (CFPB/OCC)`  [INFERRED] [semantically similar]
  research/round-1/plan-4-temporal-novelty.md → research/round-1/plan-5-conversational-market.md
- `Microsoft GraphRAG` --semantically_similar_to--> `LightRAG`  [INFERRED] [semantically similar]
  research/raw/00-initial-brief.md → research/round-1/plans.md

## Hyperedges (group relationships)
- **Topic Modeling Pipeline: LLM Extraction + Embedding + HDBSCAN** — 00_initial_brief_llm_pre_extraction, 00_initial_brief_embedding_strategy, 00_initial_brief_hdbscan_umap, 00_initial_brief_clio_approach [EXTRACTED 0.95]
- **5 Research Plans collectively validate 8 architectural decisions in D1-D8 table** — plans_plan1_topic_modeling, plans_plan2_selfservice_classification, plans_plan3_causal_relational, plans_plan4_temporal_novelty, plans_plan5_conversational_market, notes_decision_table [EXTRACTED 0.95]
- **Knowledge Graph technologies collectively address causal/relational analysis gap (ADR 6 reconsideration)** — 00_initial_brief_graphrag, 00_initial_brief_graphiti, plans_lightrag, plans_adr6_reconsideration, plans_plan3_causal_relational [INFERRED 0.85]
- **Topic Modeling Pipeline: LLM Extraction + Embedding + HDBSCAN** — 00_initial_brief_llm_pre_extraction, 00_initial_brief_embedding_strategy, 00_initial_brief_hdbscan_umap, 00_initial_brief_clio_approach [EXTRACTED 0.95]
- **5 Research Plans collectively validate 8 architectural decisions in D1-D8 table** — plans_plan1_topic_modeling, plans_plan2_selfservice_classification, plans_plan3_causal_relational, plans_plan4_temporal_novelty, plans_plan5_conversational_market, notes_decision_table [EXTRACTED 0.95]
- **Knowledge Graph technologies collectively address causal/relational analysis gap (ADR 6 reconsideration)** — 00_initial_brief_graphrag, 00_initial_brief_graphiti, plans_lightrag, plans_adr6_reconsideration, plans_plan3_causal_relational [INFERRED 0.85]
- **Clio-style pipeline open-source reproduction ecosystem** — plan_1_topic_modeling_clio, plan_1_topic_modeling_kura, plan_1_topic_modeling_openclio, plan_1_topic_modeling_hercules [EXTRACTED 0.95]
- **Postgres-native relational + vector store core architecture** — plan_3_causal_relational_pgvector, plan_3_causal_relational_llm_relation_table, plan_3_causal_relational_apache_age [INFERRED 0.85]
- **D1/D2/D3 jointly confirmed across Plans 1 and 2 — LLM extraction, per-facet clustering, summary embeddings** — plan_1_topic_modeling_d1_confirm, plan_1_topic_modeling_d2_confirm, plan_1_topic_modeling_d3_confirm [EXTRACTED 0.95]
- **Plan 4 temporal layers feed directly into Plan 5 conversational tools (temporal_signal, cluster_summary, causal_lookup)** — plan_4_layered_temporal_stack, plan_4_bocpd, plan_4_bertrend, plan_5_hybrid_rag_architecture, plan_5_anthropic_tool_calling [EXTRACTED 0.95]
- **Prophet/z-score and free text-to-SQL are both rejected for analogous trust/accuracy reasons in their respective domains** — plan_4_prophet, plan_4_d5_replace, plan_5_text_to_sql_rejected, plan_5_adr_text_to_sql [INFERRED 0.75]
- **BERTrend popularity metric + 3-test gate + BH-FDR form the full emergence detection and alert filtering system** — plan_4_popularity_metric, plan_4_three_test_gate, plan_4_bh_fdr, plan_4_bertrend [EXTRACTED 0.95]

## Communities (11 total, 2 thin omitted)

### Community 0 - "Core Architecture & Brief Spec"
Cohesion: 0.09
Nodes (28): Basel II/III Operational Risk Framework, Capgemini Invent OpRisk Tools, CFPB Consumer Complaint Database, Multi-field Embedding Strategy (summary fields), UMAP + HDBSCAN Clustering Pipeline, Post-POC Migration to Client (PT-BR), NL Q&A Agent (text-to-SQL + semantic search), arXiv:2212.01285 — Text Analysis for OpRisk Loss Descriptions (+20 more)

### Community 1 - "Topic Modeling Methods (Plan 1)"
Cohesion: 0.11
Nodes (27): BERTopic, BERTrend, BERTrend paper arXiv 2411.05930, CFPB BERTopic paper arXiv 2205.07259, Clio (Anthropic), Clio paper arXiv 2412.13678, Clio-style pipeline: LLM facet extraction → embed summary → cluster → recursive label, CobwebTM (+19 more)

### Community 2 - "Temporal Analysis & Novelty Detection (Plan 4)"
Cohesion: 0.11
Nodes (27): ADR-005 — Replace Prophet/z-score with layered temporal stack, ADR-006 — Adopt BH-FDR correction for multi-cluster alerting, ADR-007 — BERTopic topics_over_time for viz only; BERTrend pattern for emergence, BERTopic topics_over_time — visualization only, not emergence detection, BERTrend — Neural Topic Modeling for Emerging Trends Detection, Benjamini-Hochberg FDR correction for multi-cluster monitoring, BOCPD — Bayesian Online Changepoint Detection, ACM TIST 2024 — Concept Drift Adaptation in Text Stream Mining Systematic Review (+19 more)

### Community 3 - "Conversational Interface & Market Practices (Plan 5)"
Cohesion: 0.11
Nodes (26): ADR (Agent Framework) — native Anthropic tool-calling for v1; LangGraph only at v1.5, ADR (text-to-SQL surface) — NOT exposed in v1; curated typed tools only, ADR (UI) — Streamlit for v1 exploration; conversational self-service deferred to v1.5, ADR (Vector Store) — pgvector confirmed, HNSW index, no separate vector DB, Anthropic Native Tool-Calling — recommended agent pattern for v1 (4-6 typed tools), Audit Trail Requirement — every agent answer must cite incident IDs and show tool calls (CFPB/OCC), Building Effective Agents — Anthropic canonical guidance (Dec 2024), Capgemini Invent OpRisk Tools — Taxonomy Rationalization + Weak Signals Analysis (+18 more)

### Community 4 - "Architectural Decision Validation (D1-D8)"
Cohesion: 0.13
Nodes (22): D1 — LLM pre-extraction before clustering: CONFIRM, D2 — Cluster per facet: CONFIRM, D3 — Summaries as embedding unit: CONFIRM, Active learning (uncertainty sampling), ACL 2025 survey: From Selection to Generation — LLM-based Active Learning, Argilla 2.x, D1 — LLM pre-extraction before clustering: CONFIRM (Plan 2), D2 — Cluster per facet: CONFIRM (Plan 2) (+14 more)

### Community 5 - "Causal & Relational Analysis (Plan 3)"
Cohesion: 0.17
Nodes (19): NPMI (Normalized Pointwise Mutual Information), Apache AGE, CASIE (Cybersecurity Event Extraction), Chi-square co-occurrence, D6 — No KG in v1: REVISE — keep Postgres + add relation table, D7 — pgvector for vector store: CONFIRM, Plan 3 — Causal and Relational Analysis: Beyond Semantic Search, FinCausal shared task series (+11 more)

### Community 6 - "Topic Modeling Baselines & Failures"
Cohesion: 0.24
Nodes (11): BERTopic Naive Clustering Failure, Clio-style Faceted Summarization, LLM Pre-Extraction before Clustering, Active Learning (uncertainty sampling, query-by-committee), Annotation Tools (Argilla, Label Studio, Prodigy), BERTopic, Neural Topic Models (ProdLDA/ETM), Research Plan 1 — Modern Topic Modeling (+3 more)

### Community 7 - "Knowledge Graph & GraphRAG Research"
Cohesion: 0.33
Nodes (9): ADR 6: No Knowledge Graph in v1, Graphiti (getzep), Microsoft GraphRAG, arXiv:2310.12074 — IncidentAI (Cinnamon/ACL), UCI Incident Management Process Event Log, ADR 6 Reconsideration (KG in v1), LightRAG, Research Plan 3 — Causal and Relational Analysis (+1 more)

### Community 8 - "Temporal Baselines & Drift Detection"
Cohesion: 0.53
Nodes (6): Prophet/Z-score Temporal Signal Detection, Temporal Analysis Gap (Prophet/z-score rudimentary), Changepoint Detection (PELT, BOCPD), Concept Drift Detection, Dynamic Topic Models (DTM, Blei & Lafferty 2006), Research Plan 4 — Temporal Analysis and Novelty Detection

## Knowledge Gaps
- **50 isolated node(s):** `CFPB Consumer Complaint Database`, `Weak Signal Discovery Capability`, `Self-Service Investigation Capability`, `Resolução 4557 BCB`, `Pakhchanyan et al. (2022) — ML for OpRisk Basel Classification` (+45 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Plan 1 — Modern Topic Modeling: Which Approach Wins on Incident Corpora?` connect `Topic Modeling Methods (Plan 1)` to `Architectural Decision Validation (D1-D8)`, `Causal & Relational Analysis (Plan 3)`, `Topic Modeling Baselines & Failures`?**
  _High betweenness centrality (0.215) - this node is a cross-community bridge._
- **Why does `Plan 3 — Causal and Relational Analysis: Beyond Semantic Search` connect `Causal & Relational Analysis (Plan 3)` to `Topic Modeling Methods (Plan 1)`, `Architectural Decision Validation (D1-D8)`, `Knowledge Graph & GraphRAG Research`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Why does `Plan 2 — Self-Service Classification: Runtime Taxonomy Definition and Refinement` connect `Architectural Decision Validation (D1-D8)` to `Topic Modeling Methods (Plan 1)`, `Causal & Relational Analysis (Plan 3)`, `Topic Modeling Baselines & Failures`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **What connects `CFPB Consumer Complaint Database`, `Weak Signal Discovery Capability`, `Self-Service Investigation Capability` to the rest of the system?**
  _50 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Architecture & Brief Spec` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._
- **Should `Topic Modeling Methods (Plan 1)` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Should `Temporal Analysis & Novelty Detection (Plan 4)` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._