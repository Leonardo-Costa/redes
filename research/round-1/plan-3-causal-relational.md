---
plan: 3
title: "Causal and Relational Analysis: Beyond Semantic Search"
date: 2026-05-05
status: complete
decisions_addressed: [D6, D7]
adr_changes: ["ADR 6: KEEP no full-KG in v1, but ADD a lightweight relation table (cause/effect/co-occurrence triples extracted by LLM) inside Postgres alongside pgvector"]
---

# Plan 3 — Causal and Relational Analysis: Beyond Semantic Search

## Executive Summary
- **Pure semantic search cannot answer Section 1.4's relational questions**. "When symptom A appears, what is the most likely root cause historically?" is a conditional-probability/co-occurrence question, not a similarity question. Vector similarity returns "narratives that look like the query", not "what tends to follow A". Confirmed by Microsoft's own GraphRAG research: vector RAG fails on global/relational queries even at 1M-token context windows ([LazyGraphRAG blog](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)).
- **A full Microsoft GraphRAG deployment is overkill and economically irrational at 5k narratives**. Reported indexing costs of $5–20 per 1MB and $47k for 100k internal docs make it disproportionate for a POC. LazyGraphRAG (0.1% of GraphRAG indexing cost, comparable quality) and LightRAG (cheaper than GraphRAG) are stronger candidates *if* a graph approach is taken.
- **Graphiti is the wrong tool for this problem**. It is purpose-built for *agent memory* with bi-temporal validity (when a fact became true / was invalidated), which is conceptually elegant but solves a different problem than "find recurring causal chains in a static incident corpus". It also adds Neo4j/FalkorDB/Kuzu as a hard dependency, conflicting with D7 (pgvector / Postgres-only stack).
- **The best approach for D6 is a hybrid: keep pgvector as the primary store, but add an LLM-extracted relation table (cause→effect, symptom↔product, observed-with) inside Postgres**. This delivers the relational queries Section 1.4 needs without paying the cost of a full graph database. NPMI on the resulting triple counts gives statistically interpretable co-occurrence answers. Apache AGE or simple SQL self-joins are sufficient for any path queries the POC actually requires.
- **Process mining (PM4Py) is not applicable in v1**. It requires structured event logs (XES, case_id + timestamped activity sequence), which a corpus of free-text narratives does not have. It is a candidate for v2 *only if* the LLM extracts structured event sequences per incident.

## Findings by Sub-Question

### SQ1: Causal discovery in incident text — robust methods and benchmarks?
**Answer**: Two distinct paradigms exist, and the POC must not confuse them. (a) *Causal discovery from observational data* (PC algorithm, NOTEARS, etc.) requires numeric variables and statistical assumptions — not applicable to free-text incident narratives. (b) *Cause-effect relation extraction from text* is an information-extraction task: given a narrative, label spans as cause/effect. This is well-benchmarked (FinCausal 2020/2022/2023/2025 at FNP, IncidentAI [arxiv:2310.12074], CASIE for cybersecurity events, nuclear LER causality [arxiv:2404.05656]). Modern LLMs handle (b) competently with structured-output prompting + Pydantic schemas. Note: LLM-extracted causal relations capture *what authors wrote about causality*, not validated causal mechanisms — this is a critical interpretive caveat for the analyst-facing UX.

A separate strand — LLMs for *root-cause analysis* of cloud/software incidents (RCACopilot EuroSys'24, OpenRCA, ReAct-based RCA agents) — works on telemetry+logs+narrative jointly and is not directly transferable, but confirms that LLM-driven cause attribution is an active and reasonably mature field.

**Evidence**:
- FinCausal shared task series, 2020–2025 — https://aclanthology.org/2020.fnp-1.3/, https://aclanthology.org/2022.fnp-1.16/, https://aclanthology.org/2025.finnlp-1.21/
- IncidentAI dataset (high-pressure gas incidents; NER + cause-effect + IR tasks) — https://arxiv.org/abs/2310.12074
- CASIE (cybersecurity events, AAAI 2020) — https://github.com/Ebiquity/CASIE
- "Causality Extraction from Nuclear Licensee Event Reports Using a Hybrid Framework" — https://arxiv.org/abs/2404.05656
- "Causal Inference with Large Language Model: A Survey" — https://arxiv.org/html/2409.09822v2
- "LLM Cannot Discover Causality, and Should Be Restricted to Non-Decisional Support" — https://arxiv.org/html/2506.00844v1 (cautionary)
- RCACopilot — https://arxiv.org/pdf/2305.15778

**Implication for the POC**: Add to the LLM pre-extraction schema (Plan 1) an explicit `causal_relations: list[CauseEffect]` field where each `CauseEffect` has `cause`, `effect`, `evidence_span`, `confidence`. Store these as rows in a `relations` table keyed to incident_id. Frame all UI answers as "*according to the narratives*, X tends to be reported alongside Y" — never as causal claims. This sidesteps the LLM-causality limitation flagged by the 2026 critique.

### SQ2: Is process mining (PM4Py) relevant for ITSM/ServiceNow incident logs?
**Answer**: No, not for this POC. Process mining requires a structured event log (case_id, activity, timestamp), which is what ServiceNow exposes via its audit trail (ITSM Process Mining Content Pack, IBM Process Mining ServiceNow connector) — but that is *workflow telemetry* (created → assigned → resolved), not the *narrative content* this POC analyzes. PM4Py expects XES files and discovers Petri nets / DFGs from sequences. The corpus described in the brief is ~5k free-text incident narratives; converting them to event logs would require LLM pre-extraction of event sequences, which is itself a research question. **PM4Py is a v2 candidate, not a v1 component.**

**Evidence**:
- PM4Py repo and library — https://github.com/process-intelligence-solutions/pm4py (requires XES event logs)
- ServiceNow ITSM Process Mining Content Pack — https://store.servicenow.com/store/app/021f2b6e1b646a50a85b16db234bcb4c (workflow events, not narratives)
- IBM Process Mining ServiceNow integration — https://www.ibm.com/products/process-mining/integrations/it-service-management-servicenow
- "Process Mining for Problem Management: Incident Patterns That Signal a Hidden Problem" (ServiceNow) — https://www.servicenow.com/community/process-mining-blog/process-mining-for-problem-management-incident-patterns-that/ba-p/3534292

**Implication for the POC**: Drop process mining from the v1 scope. Re-evaluate in v2 if the system migrates to a real ServiceNow data feed where workflow event logs are available alongside narratives — at that point the *combination* (narrative semantics × workflow process mining) is genuinely interesting and is not covered by either pgvector or GraphRAG.

### SQ3: Microsoft GraphRAG — what does it genuinely add over classic RAG?
**Answer**: GraphRAG's distinctive value is on *global / corpus-wide* queries — exactly the type Section 1.4 calls "thematic exploration" ("what are the main themes in the dataset?"). Microsoft's own paper ("From Local to Global", arxiv:2404.16130) shows vector RAG fails these because they are query-focused summarization, not retrieval. The mechanism: build entity graph → cluster into communities (Leiden) → pre-summarize each community → aggregate at query time. For *local* / "who-what-when-where" queries vector RAG remains stronger and cheaper. The graph structure becomes decisive when answer quality depends on multi-hop relationships that span chunk boundaries (e.g., "which root causes co-occur with product Z?" requires aggregating *across* incidents, not finding *one* incident).

The catch is cost. Indexing requires an LLM call per chunk for entity extraction plus community summarization. Reported costs: $5–20 per 1MB, $8.20 per 1.2M tokens, $0.40 per query. A FinServ case study reports $47k indexing cost for 100k docs. For 5k narratives the indexing cost is plausibly $200–800 — non-trivial relative to the $15–40 Sonnet pre-extraction the brief already plans.

**Evidence**:
- "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" — https://arxiv.org/abs/2404.16130
- LazyGraphRAG announcement (vector RAG fails to improve even at 1M-token context window) — https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- "RAG vs. GraphRAG: A Systematic Evaluation" — https://arxiv.org/html/2502.11371v1 (vector wins on local, graph wins on global)
- "When to use Graphs in RAG" (ICLR'26) — https://arxiv.org/html/2506.05690v3
- microsoft/graphrag repo — https://github.com/microsoft/graphrag (warns "indexing can be expensive")
- "GraphRAG Costs Explained" — https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/graphrag-costs-explained-what-you-need-to-know/4207978

**Implication for the POC**: Vanilla Microsoft GraphRAG is overkill and costly for 5k narratives. **However, the *output* of its indexing pipeline — entities + relations + community summaries — is exactly what answers the relational questions Section 1.4 demands.** The right move is to *replicate the useful artifacts* (entity/relation extraction, optional community summaries via cluster labeling from Plan 1) in our own pipeline, without adopting the full GraphRAG indexing/query stack.

### SQ4: Graphiti — temporal graph memory vs static GraphRAG. Relevant here?
**Answer**: No, not for v1. Graphiti (Zep, arxiv:2501.13956) is purpose-built for *agent conversational memory* with bi-temporal modeling: every edge has both a `valid_from`/`valid_to` (when the fact held in the world) and an `ingested_at`/`invalidated_at` (when the system learned it). Sub-second incremental updates are the headline feature. This is the right tool for chatbot personalization / longitudinal user state — not for batch analysis of a static incident corpus where we already know the incident timestamps.

It also brings infrastructure cost: Neo4j 5.26 / FalkorDB / Kuzu / Neptune as a hard dependency and OpenAI/Gemini for structured-output calls. That conflicts with D7 (pgvector-only stack) and adds an additional service to operate.

The temporal-incident question Section 1.4 actually asks ("which themes are growing over the last 6 months?") is solved by Plan 4's temporal analysis (DTM, changepoint, z-score on cluster counts) over `incident.occurred_at`, not by Graphiti's bi-temporal edge validity.

**Evidence**:
- "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" — https://arxiv.org/abs/2501.13956
- Graphiti repo — https://github.com/getzep/graphiti
- Graphiti vs GraphRAG comparison (Neo4j blog) — https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/

**Implication for the POC**: Reject Graphiti for v1. Reconsider in v2 if/when the system moves from batch analysis to a streaming / agentic mode where incidents arrive continuously and the analyst expects the assistant to "remember" prior conversations.

### SQ5: Co-occurrence analysis — PMI vs embedding similarity vs LLM extraction?
**Answer**: For the question "which root causes co-occur with product Z?" the three approaches answer subtly different questions and have different interpretability profiles:

| Method | What it measures | Interpretability | Statistical rigor | Cost |
|---|---|---|---|---|
| Embedding cosine sim | Semantic proximity in vector space | Low ("why are these similar?") | None native | Cheap (already have embeddings) |
| LLM relation extraction | What the narrative *says* causes what | High (cite text span) | None native | Medium ($15–40 once for 5k) |
| NPMI on extracted entities | How often A and B co-occur vs chance | High (signed score in [-1,1]) | Yes (chi-square / Fisher exact) | Cheap (after extraction) |

The right architecture is to **stack them**: LLM extraction produces structured entity/relation rows → NPMI/chi-square is computed over those rows → embedding similarity is reserved for *retrieval* of supporting examples. NPMI specifically (vs raw PMI) has a fixed [-1,1] range and is the de-facto standard in topic-coherence and biomedical text-mining literature. It directly answers "co-occur more than chance".

**Evidence**:
- Bouma 2009, "Normalized PMI in Collocation Extraction" — https://svn.spraakdata.gu.se/repos/gerlof/pub/www/Docs/npmi-pfd.pdf
- Aletras & Stevenson, "Evaluating Topic Coherence Using Distributional Semantics" — https://aclanthology.org/W13-0102.pdf
- NPMI for biomedical literature gene-disease association — https://pmc.ncbi.nlm.nih.gov/articles/PMC7144681/
- Jurafsky SLP3 ch. on PMI — https://web.stanford.edu/~jurafsky/slp3/J.pdf

**Implication for the POC**: For the relational question class, LLM extraction + NPMI gives the analyst *interpretable, statistically grounded* answers ("Product Z co-occurs with root_cause=`manual_input_error` with NPMI=0.42, observed 87 times vs 31 expected, p<0.001") that pure semantic search cannot produce. This is the highest-ROI addition to the architecture and costs almost nothing on top of the LLM pre-extraction the brief already plans.

### SQ6: LightRAG vs GraphRAG — should we consider it for the POC?
**Answer**: LightRAG (HKUDS, EMNLP 2025) is genuinely cheaper and more incremental-friendly than vanilla GraphRAG (graph cost reportedly ~$0.15 vs ~$4 per document; dual-level retrieval combines entity- and relation-level lookups). Its results on UltraDomain (Agriculture, CS, Legal, Mix) show it ties or beats GraphRAG on comprehensiveness/diversity/empowerment except on the Mix domain (50.4% vs 49.6%). It is MIT-licensed, has a Web UI with KG visualization, REST API, and a 32B+ parameter LLM as the recommended driver. Importantly, it supports multiple storage backends including PostgreSQL — meaning it could in principle slot into the existing Postgres stack.

Caveats: (a) recommended LLM scale (32B+, 32–64K context) is substantially heavier than what 5k narratives require; (b) "outperforms GraphRAG" benchmarks are by the authors on a benchmark they curated — independent reviews are rarer; (c) the architectural value over a *bespoke* relation-extraction + NPMI + pgvector pipeline is unclear when the corpus is small.

**Evidence**:
- LightRAG paper — https://arxiv.org/abs/2410.05779 / https://arxiv.org/html/2410.05779v1
- HKUDS/LightRAG repo — https://github.com/HKUDS/LightRAG
- Independent review (LearnOpenCV) — https://learnopencv.com/lightrag/
- "Unbiased Evaluation Framework for GraphRAG" (cautions about reproducibility of self-reported gains) — https://arxiv.org/html/2506.06331v1

**Implication for the POC**: LightRAG is the *least bad* off-the-shelf graph-RAG choice if we ever decide to adopt one, but adopting it for a 5k-narrative POC introduces a heavy dependency for limited benefit. Recommendation: do not adopt in v1; revisit if v2 grows to 50k+ narratives or if free-text question answering becomes the dominant interface.

## Approach Comparison

| Approach | Pros (max 3) | Cons (max 3) | Maturity (1-5) | Cost | Recommendation |
|---|---|---|---|---|---|
| Pure semantic search (pgvector) | Cheap; already in stack; great for "find similar incident" | Cannot answer relational/causal/global questions; no co-occurrence; no aggregation | 5 | Low | ⚠️ Necessary but insufficient |
| LLM relation extraction + structured table in Postgres | Interpretable; cheap; reuses planned LLM pre-extraction; native SQL aggregation | Schema design effort; brittle to ontology drift; LLM extraction noise | 4 | Low ($0.05–0.10 per doc) | ✅ Adopt for v1 |
| Microsoft GraphRAG | Best-in-class on global thematic queries; entity+community summaries; well-funded | Indexing cost ($5–20/MB); over-engineered for 5k; couples to Azure ecosystem; community detection brittle | 4 | Medium-High ($200–800 for 5k indexing) | ❌ Avoid for v1 |
| LazyGraphRAG | 0.1% of GraphRAG indexing cost; matches/beats it on global queries | Open-source release Q1-Q2 2026 — production-readiness uncertain at POC time; query-time cost; still requires graph infra | 3 | Low at index, medium at query | ⚠️ Watch for v2 |
| LightRAG | Cheaper than GraphRAG; supports Postgres backend; incremental-friendly | 32B+ LLM recommended; benchmarks self-reported; redundant with bespoke pipeline at 5k scale | 3 | Medium | ⚠️ Consider for v2 if scale grows |
| Graphiti (temporal graph) | Bi-temporal model elegant for agentic memory; provenance; sub-second updates | Solves wrong problem (agent memory ≠ corpus analysis); requires Neo4j/FalkorDB/Kuzu; conflicts with D7 | 4 | Medium | ❌ Avoid (wrong tool) |
| Process mining (PM4Py) | Mature; rich algorithm zoo (Petri nets, DFGs); good for ServiceNow workflow | Requires XES event logs, not narratives; needs case_id + activity sequence; out of scope for free-text | 5 | Low | ❌ Avoid for v1 (not applicable) |
| PMI / NPMI co-occurrence matrix | Statistically grounded; interpretable [-1,1]; cheap on extracted entities; chi-square testable | Needs entity extraction first; ignores semantics of edge type; sparse counts noisy | 5 | Trivial | ✅ Adopt for v1 (on top of relation table) |
| Apache AGE (graph in Postgres) | Cypher in Postgres; same DB as pgvector; ACID; no extra service | Less mature than Neo4j; query optimizer for graph workloads weaker; Cypher learning curve | 3 | Low | ⚠️ Optional; only if path queries become important |

## Recommended Architecture

**The big idea**: keep the brief's pgvector core, but enrich the LLM pre-extraction (Plan 1) so it produces *both* facet summaries (for embedding) *and* a small, structured relation table that lives in Postgres next to the vectors. This delivers Section 1.4's relational/causal capability at a fraction of GraphRAG's cost.

```
Incident narrative
   │
   ▼
LLM pre-extraction (Sonnet, structured output, Pydantic)
   ├─ facet summaries (symptom / root_cause / impact)  → embeddings → pgvector
   ├─ entities (products, channels, processes, error_codes)  → entities table
   └─ relations: causal_relations [cause→effect, evidence_span, confidence]
                  observed_with [entity_a, entity_b]
                                                              → relations table
                                                              → entity_mentions table

Query layer (decision map by question class, Section 1.4):
   1. Thematic exploration       → cluster on facet embeddings (Plan 2) + LLM cluster naming
   2a. "Symptom A → root cause?" → SELECT root_cause, COUNT, NPMI
                                   FROM relations WHERE cause LIKE 'symptom_A'
                                   GROUP BY root_cause ORDER BY NPMI DESC
   2b. "RCs co-occurring with Z" → NPMI(root_cause, product=Z) over entity_mentions
   2c. "Recurring chain A→B→C"   → SQL self-join over relations
                                   (for v1; promote to Apache AGE Cypher if depth>3)
   3. Temporal trends            → Plan 4 (DTM / changepoint over cluster counts)
   4. Self-service classification → Plan 5
   5. Pattern detection           → NPMI + cluster co-occurrence
   6. Signal vs noise             → Plan 4 (multiple-testing-corrected significance)
```

Concrete schema additions (Postgres):
```sql
CREATE TABLE entities (
  id BIGSERIAL PRIMARY KEY,
  type TEXT,            -- product / channel / process / error_code / actor
  canonical_name TEXT,
  alias_set TEXT[]
);
CREATE TABLE entity_mentions (
  incident_id BIGINT REFERENCES incidents(id),
  entity_id BIGINT REFERENCES entities(id),
  facet TEXT,           -- which facet the entity was extracted from
  evidence_span TEXT
);
CREATE TABLE relations (
  incident_id BIGINT REFERENCES incidents(id),
  relation_type TEXT,   -- cause_of / observed_with / impacts
  source_entity_id BIGINT REFERENCES entities(id),
  target_entity_id BIGINT REFERENCES entities(id),
  evidence_span TEXT,
  confidence REAL
);
-- Materialized view for NPMI
CREATE MATERIALIZED VIEW entity_cooccurrence AS
SELECT a.entity_id AS e1, b.entity_id AS e2,
       COUNT(*) AS observed,
       /* NPMI computed in app layer or as PG function */ ...
FROM entity_mentions a JOIN entity_mentions b USING (incident_id)
WHERE a.entity_id < b.entity_id
GROUP BY a.entity_id, b.entity_id;
```

This is *de facto* a small knowledge graph — but materialized as relational tables in the same Postgres instance pgvector lives in. No Neo4j, no GraphRAG indexer, no extra service.

**Integration with other plans:**
- **Feeds into Plan 5 (conversational interface)** because the chat agent can now translate questions like "what root causes co-occur with product Z?" into SQL over `relations` + `entity_mentions`, returning both an aggregated answer (NPMI ranking) and citation-grade evidence (the `evidence_span` per row). Pure RAG cannot do this.
- **Feeds into Plan 4 (temporal/trend)** because `relations.created_at` (= incident.occurred_at) gives a per-relation time series the trend module can run DTM/changepoint on, not just per-cluster counts.
- **Depends on Plan 1 (LLM pre-extraction)** for the relation/entity schema. Plan 1's Pydantic schema must add `entities`, `causal_relations` fields. Cost delta over current Plan 1 estimate is small (~10–20% extra tokens per call).
- **Validates Plan 2 (clustering)** by enabling cross-checks: a cluster that has high internal NPMI between its top entities is more coherent than one that does not.

## Architectural Decisions

### Hypotheses from the brief

- **D6 — No KG in v1**: **REVISE** (do not REPLACE).
  - Rationale: The brief's instinct is correct that a *full* knowledge graph (Neo4j + GraphRAG-style community detection + Cypher) is not justified at 5k narratives. But "no KG" was over-applied: it eliminated *the relational structure itself*, leaving the system unable to answer Section 1.4's causal/relational questions. The right calibration is "no graph database in v1, but **yes** to a relation/entity table inside Postgres". This preserves D6's cost discipline while restoring the relational capability.
  - Specific alternative: add `entities`, `entity_mentions`, `relations` tables to Postgres (schema above). Compute NPMI in SQL or app layer. Use Apache AGE only if/when depth-3+ path queries become a real user need (unlikely in v1). Microsoft GraphRAG, LightRAG, Graphiti are all rejected for v1.

- **D7 — pgvector for vector store**: **CONFIRM**.
  - Rationale: The relational-store decision above strengthens D7 — keeping everything in Postgres means vectors, entities, relations, and SQL aggregations live in one ACID engine. No cross-system joins. This is operationally simpler than any (pgvector + Neo4j) or (pgvector + LightRAG-store) split.

### ADRs affected
- **ADR 6 — No Knowledge Graph in v1**: **CHANGE** (relax, don't reverse).
  - Specific change: rephrase ADR 6 from "no knowledge graph" to "no dedicated graph database; entity/relation extraction and storage happen in Postgres tables alongside pgvector". Add explicit non-goals: no community detection at indexing time, no Cypher-required queries in v1, no Neo4j/Graphiti/GraphRAG. Add explicit goals: LLM-extracted relations, NPMI co-occurrence, evidence spans for citation. Document the upgrade path to Apache AGE / LazyGraphRAG / LightRAG for v2 if scale or query complexity demand it.

## Open Questions
1. **Ontology stability across runs**: how often will the LLM emit "manual input error" vs "manual_input_error" vs "user input mistake" for the same canonical entity? Need to prototype canonicalization (alias-set + embedding-based merging) before NPMI is meaningful. This is the largest unresolved risk for the relation table.
2. **Confidence calibration**: should we threshold `relations.confidence` before counting toward NPMI? Sonnet's structured-output confidence is not always well-calibrated. A pilot on 100 hand-labeled incidents would resolve this.
3. **Multi-hop chains (A→B→C)**: SQL self-joins are fine at depth 2. Depth 3+ over a 50k+ relation table may need Apache AGE / Cypher for query ergonomics. Defer until needed.
4. **Multiple-testing correction for "is this co-occurrence significant?"**: with thousands of entity pairs the per-pair p-value is meaningless; need Benjamini-Hochberg or similar. This bleeds into Plan 4's "signal vs noise" question.
5. **Should clusters themselves participate in the relation graph?** ("cluster_X co-occurs with product Z"). Probably yes, but design needs to wait until Plan 2's cluster identities are stable.

## References

### Papers
- [2024] Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" — https://arxiv.org/abs/2404.16130
- [2024] Guo et al., "LightRAG: Simple and Fast Retrieval-Augmented Generation" (EMNLP 2025) — https://arxiv.org/abs/2410.05779
- [2025] Rasmussen et al., "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" — https://arxiv.org/abs/2501.13956
- [2023] Hatakeyama-Sato et al., "Towards Safer Operations: An Expert-involved Dataset of High-Pressure Gas Incidents (IncidentAI)" — https://arxiv.org/abs/2310.12074
- [2020] Mariko et al., "The Financial Document Causality Detection Shared Task (FinCausal 2020)" — https://aclanthology.org/2020.fnp-1.3/
- [2022] FinCausal 2022 — https://aclanthology.org/2022.fnp-1.16/
- [2025] FinCausal 2025 — https://aclanthology.org/2025.finnlp-1.21/
- [2020] Satyapanich, Ferraro & Finin, "CASIE: Extracting Cybersecurity Event Information from Text" (AAAI 2020) — https://ojs.aaai.org/index.php/AAAI/article/view/6401
- [2024] "Causality Extraction from Nuclear Licensee Event Reports Using a Hybrid Framework" — https://arxiv.org/abs/2404.05656
- [2024] "Causal Inference with Large Language Model: A Survey" — https://arxiv.org/html/2409.09822v2
- [2025] "RAG vs. GraphRAG: A Systematic Evaluation and Key Insights" — https://arxiv.org/html/2502.11371v1
- [2025] "When to use Graphs in RAG: A Comprehensive Analysis" (ICLR'26) — https://arxiv.org/html/2506.05690v3
- [2025] "How Significant Are the Real Performance Gains? An Unbiased Evaluation Framework for GraphRAG" — https://arxiv.org/html/2506.06331v1
- [2025] "LLM Cannot Discover Causality, and Should Be Restricted to Non-Decisional Support in Causal Discovery" — https://arxiv.org/html/2506.00844v1
- [2024] RCACopilot, "Automatic Root Cause Analysis via Large Language Models for Cloud Incidents" (EuroSys'24) — https://arxiv.org/pdf/2305.15778
- [2024] Roy et al., "Exploring LLM-based Agents for Root Cause Analysis" (FSE'24 Industry) — https://arxiv.org/abs/2403.04123
- [2009] Bouma, "Normalized (Pointwise) Mutual Information in Collocation Extraction" — https://svn.spraakdata.gu.se/repos/gerlof/pub/www/Docs/npmi-pfd.pdf
- [2013] Aletras & Stevenson, "Evaluating Topic Coherence Using Distributional Semantics" — https://aclanthology.org/W13-0102.pdf
- Jurafsky SLP3, "Pointwise Mutual Information" — https://web.stanford.edu/~jurafsky/slp3/J.pdf

### Repositories
- microsoft/graphrag — Microsoft's graph-based RAG pipeline — https://github.com/microsoft/graphrag
- HKUDS/LightRAG — Lightweight graph-RAG with Postgres backend — https://github.com/HKUDS/LightRAG
- getzep/graphiti — Temporal knowledge graph for agent memory — https://github.com/getzep/graphiti
- process-intelligence-solutions/pm4py — Process mining in Python — https://github.com/process-intelligence-solutions/pm4py
- Ebiquity/CASIE — Cybersecurity event extraction — https://github.com/Ebiquity/CASIE
- apache/age — Postgres graph extension (Cypher) — https://github.com/apache/age
- GraphRAG-Bench/GraphRAG-Benchmark — GraphRAG eval suite — https://github.com/GraphRAG-Bench/GraphRAG-Benchmark

### Blog Posts / Engineering Case Studies
- "LazyGraphRAG sets a new standard for GraphRAG quality and cost" — Microsoft Research — https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- "BenchmarkQED: Automated benchmarking of RAG systems" — Microsoft Research — https://www.microsoft.com/en-us/research/blog/benchmarkqed-automated-benchmarking-of-rag-systems/
- "GraphRAG Costs Explained" — Microsoft Tech Community — https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/graphrag-costs-explained-what-you-need-to-know/4207978
- "GraphRAG and PostgreSQL integration in docker" — Microsoft Tech Community — https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/graphrag-and-postgresql-integration-in-docker-with-cypher-query-and-ai-agents/4420623
- "Graphiti: Knowledge Graph Memory for an Agentic World" — Neo4j developer blog — https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/
- "LightRAG: Simple and Fast Alternative to GraphRAG" — LearnOpenCV — https://learnopencv.com/lightrag/
- "Combining pgvector and Apache AGE" — Microsoft Tech Community — https://techcommunity.microsoft.com/blog/adforpostgresql/combining-pgvector-and-apache-age---knowledge-graph--semantic-intelligence-in-a-/4508781
- "Optimizing ServiceNow Incident Management with Process Mining" — psbpm.com — https://psbpm.com/en/optimizing-servicenow-incident-management-with-process-mining/
- ORX "Cause and Impact Operational Risk Reference Taxonomy" — https://orx.org/resource/cause-and-impact-operational-risk-reference-taxonomy

### Products / Vendors
- Neo4j AuraDB — managed graph DB — https://neo4j.com/cloud/aura/
- FalkorDB — Redis-based graph DB (Graphiti backend) — https://www.falkordb.com/
- Kuzu — embedded graph DB — https://kuzudb.com/
- Apache AGE — Postgres graph extension — https://age.apache.org/
- Zep / Graphiti (managed) — https://www.getzep.com/
- ServiceNow ITSM Process Mining Content Pack — https://store.servicenow.com/store/app/021f2b6e1b646a50a85b16db234bcb4c
- IBM Process Mining (ServiceNow integration) — https://www.ibm.com/products/process-mining/integrations/it-service-management-servicenow
