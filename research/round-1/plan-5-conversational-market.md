---
plan: 5
title: "Conversational Interface and Market Practices: What Banks Actually Do"
date: 2026-05-05
status: complete
decisions_addressed: [D7, D8]
adr_changes: ["ADR (UI): Streamlit accepted only for analyst-facing exploration UI; conversational self-service moved to v1.5 / stretch with strict scope (semantic-search + curated tools, NOT free-form text-to-SQL)", "ADR (Vector store): pgvector confirmed for ~5K corpus; HNSW index, no separate vector DB"]
---

# Plan 5 — Conversational Interface and Market Practices: What Banks Actually Do

## Executive Summary

- **Conversational self-service is NOT viable as a v1 MVP for free-form text-to-SQL.** Even Claude Sonnet 4.5 / Opus 4.5 lead Spider 1.0 at ~94% but Spider 2.0 (the realistic enterprise benchmark with multi-dialect schemas >3,000 columns) collapses to 35-59% state-of-the-art. With 5,000 incident narratives and a non-trivial schema, we will hallucinate columns and return silently-wrong numbers. Trust loss is unrecoverable in a risk-management context.
- **The mature 2025 pattern is *agentic hybrid RAG* with a small number of curated tools, not free text-to-SQL.** LinkedIn's SQL Bot (LangGraph + RAG + KG + self-correction) reaches ~95% user satisfaction, but only with heavy investment in semantic layer, knowledge graph, and per-domain glossaries — multi-quarter effort. For a POC, the right move is *narrow tool set* (semantic-search, faceted filter, time-series, cluster lookup) exposed via Anthropic native tool-calling, not a generic NL-to-SQL surface.
- **Streamlit IS adequate for the v1 analyst UI** (faceted exploration, cluster maps, chat-with-corpus over a fixed tool set), but only because our user is *one risk analyst, internal, technical-but-not-dev*. It is the wrong choice the moment we need (a) multi-tenant/RBAC, (b) true streaming agent traces, or (c) production-grade UX. For a chat-first conversational analyst experience we should use **Chainlit** (purpose-built, native streaming/observability) — but Chainlit went community-maintained in May 2025, which is a real risk.
- **pgvector is confirmed for v1.** At ~5K vectors per facet (15K total max with 3 facets), pgvector with HNSW gives ~1.5 ms latency and removes an entire infrastructure dependency. Specialized vector DBs (Qdrant, Weaviate, Pinecone) are unjustified at this scale; pgvectorscale only matters >10M vectors.
- **Capgemini Invent's "Taxonomy Rationalization" and "Weak Signals Analysis" tools are exactly the playbook we are replicating.** They are NLP-based (no public LLM mention), classify incidents into a dynamic taxonomy, and surface emerging risks for KRIs. Public documentation is marketing-level only — the architecture is closed — but the *capability surface* validates our scope. Zalando's "Postmortem Goldmines" (Sept 2025) is the closest published peer.

## Findings by Sub-Question

### SQ1: Text-to-SQL accuracy in 2025 — real numbers and common failure modes?

**Answer**: The headline numbers are misleading. Spider 1.0 (the easy benchmark from 2018) is essentially saturated — Claude Sonnet 4.5 / Opus 4.5 reportedly hit ~94.2%, GPT-5 91.8%, Gemini 3 Pro 90.5%. But Spider 2.0 (released ICLR 2025 Oral, designed to mirror enterprise reality with BigQuery/Snowflake dialects and 3,000+ column schemas) is brutal: even o1-preview solves only **17.1%** end-to-end, and GPT-4o **10.1%**. The current state-of-the-art on Spider 2.0-Snow is **35.83% via ReFoRCE** (Snowflake-Labs, Feb 2025), with newer agents reaching ~59% on a subset. On BIRD (a more realistic noisy-data benchmark), GPT-4o sits at ~52% in refined evaluation, peaking ~78% for o1-preview — but BIRD is still 11+ points behind humans.

The critical failure modes documented in production:

1. **Hallucinated columns / tables**: model invents plausible-but-nonexistent names (`Charter`, `County='Fresno'`).
2. **Silent semantic errors**: SQL executes, returns a number, the number is wrong. Noted as the most dangerous failure for trust ("90% accuracy = 100% useless" — Towards Data Science).
3. **Join-path errors**: incorrect joins on multi-table queries → incomplete or duplicated rows.
4. **Aggregate misuse**: wrong `GROUP BY`, wrong `SUM` vs `COUNT DISTINCT`.
5. **Dialect drift**: GPT-4o drops from 58.6% (PostgreSQL) to 50.0% (MySQL) on PARROT cross-dialect benchmark.
6. **Schema-complexity cliff**: enterprise schemas average 812 columns; some exceed 3,000 — accuracy collapses.

Mitigation that actually moves the needle: a **semantic layer / business glossary** triples accuracy from 16.7% → 54.2% on raw schemas (VentureBeat 2025); AtScale + dbt semantic layer report 92.5% on TPC-DS. Each "context level" (schema doc → relationships → glossary → semantic layer → eval suite) adds 10-20 pp.

**Evidence**:
- BIRD-bench leaderboard — https://bird-bench.github.io/
- Spider 2.0 — https://spider2-sql.github.io/ ; ReFoRCE paper — https://arxiv.org/abs/2502.00675
- "Why 90% Accuracy in Text-to-SQL is 100% Useless" — Towards Data Science — https://towardsdatascience.com/why-90-accuracy-in-text-to-sql-is-100-useless/
- "The Six Failures of Text-to-SQL" — Karl Weinmeister, Google Cloud — https://medium.com/google-cloud/the-six-failures-of-text-to-sql-and-how-to-fix-them-with-agents-ef5fd2b74b68
- "Headless vs. native semantic layer: 90%+ text-to-SQL accuracy" — VentureBeat — https://venturebeat.com/ai/headless-vs-native-semantic-layer-the-architectural-key-to-unlocking-90-text
- "Enterprise Text-to-SQL Accuracy Benchmarks" — Promethium — https://promethium.ai/guides/enterprise-text-to-sql-accuracy-benchmarks-2/

**Implication for the POC**: **Do NOT expose a generic text-to-SQL surface to risk analysts in v1.** The corpus has structured fields (date, channel, severity, source) plus narratives; we are tempted to let the LLM write `SELECT * FROM incidents WHERE ...`. Don't. Expose a small set of *typed*, *validated* tools (`filter_incidents(date_range, severity, channel)`, `semantic_search(query, facet, k)`, `cluster_lookup(cluster_id)`, `temporal_signal(theme, window)`) and let Claude orchestrate them. This is the difference between "Genie-style" (NL → SQL) and "Anthropic-style" (NL → tools). For v1, the tool route is the only one with acceptable trust.

### SQ2: Hybrid RAG orchestration patterns — LangGraph vs DSPy vs native tool-calling?

**Answer**: Three credible patterns in 2025-26, in increasing order of complexity:

1. **Anthropic native tool-calling** (the official "Building Effective Agents" guidance, Dec 2024 — still the canonical reference). Claude API directly with a curated tool list, simple agent loop (gather context → act → verify → repeat), no framework. Anthropic's explicit guidance: "start with simple prompts… add multi-step agentic systems only when simpler solutions fall short." This pattern *is* what powers Claude for Financial Services internally and is what Goldman Sachs / Moody's deployed when integrating Claude.

2. **LangGraph** for stateful, multi-step orchestration where you need explicit DAG control, persistence, and observability. The reference production case is **LinkedIn SQL Bot** (DARWIN platform): multi-agent with RAG + knowledge graph + LLM-rerank + self-correction, ~95% user satisfaction, "Fix with AI" used in 80% of sessions. LangGraph is also the de-facto choice when you want streaming intermediate steps to a UI.

3. **DSPy** (Stanford) for *prompt compilation* — when you have an evaluation harness and want to optimize prompts mechanically. DSPy's 2025 GEPA optimizer (Agrawal et al., July 2025) can outperform hand-tuned prompts. But DSPy's value compounds when you have hundreds of training examples; for a 5K-corpus POC with no labeled eval set, DSPy is over-engineering.

The pragmatic 2025 hybrid pattern is **LangGraph (for orchestration) + DSPy (for the prompt-optimization step on hot paths) + native Anthropic tool-calling (for the LLM↔tool boundary)**. ReFoRCE (Snowflake-Labs, top of Spider 2.0) explicitly uses self-refinement, majority-vote consensus, and execution-feedback loops — all easy in LangGraph, fiddly without.

**Evidence**:
- "Building Effective Agents" — Anthropic — https://www.anthropic.com/research/building-effective-agents
- LinkedIn SQL Bot — ZenML LLMOps Database — https://www.zenml.io/llmops-database/building-a-production-text-to-sql-assistant-with-multi-agent-architecture
- LinkedIn SQL Bot announcement — https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics
- LangGraph — https://docs.langchain.com/oss/python/langchain/rag
- DSPy — https://dspy.ai/ ; DSPy paper — https://arxiv.org/pdf/2310.03714
- ReFoRCE paper — https://arxiv.org/abs/2502.00675
- "Best AI Agent Frameworks 2025" — LangWatch — https://langwatch.ai/blog/best-ai-agent-frameworks-in-2025-comparing-langgraph-dspy-crewai-agno-and-more

**Implication for the POC**: For v1, use **Anthropic native tool-calling** with 4-6 typed tools. Do NOT introduce LangGraph until we have at least one workflow that needs (a) explicit retries with execution feedback, or (b) parallel sub-agents. DSPy: defer. The cost of LangGraph is debugging-overhead and a dependency we have to maintain through breaking changes; the benefit only appears when the agent loop has ≥3 stateful steps.

### SQ3: Chat interfaces for non-dev risk analysts — published bank examples?

**Answer**: Public, named bank deployments of conversational risk-analyst tools are scarce. The best public references are:

- **Goldman Sachs × Anthropic** (Feb 2026): co-developing autonomous Claude agents for trade/transaction accounting and KYC/onboarding. Specifically described as "embedded Anthropic engineers" — meaning the architecture is bespoke, not productized.
- **Moody's × Anthropic / MCP**: Moody's enriches data via a semantic layer and serves it to Claude through Model Context Protocol (MCP) servers. This is the cleanest documented pattern for "give Claude structured access to financial data with audit trail."
- **Anthropic Claude for Financial Services** (launched July 2025, expanded 2026): explicit GA product targeting research, modeling, compliance with verified data sources and audit trails. Sonnet 4.5 scores 55.3% on the Finance Agent benchmark vs 46.9% for GPT-5 and 29.4% for Gemini 2.5 Pro.
- **Internal-use anecdotes**: Anthropic reports 75% of their own engineers save 8-10 hours/week using SQL-generating agents (codename "goose"), and "non-engineering teams across sales, risk, and finance now query their data warehouse using natural language" — but no architecture details are public.

What's *missing* from the public record: a named retail/commercial bank publishing the architecture of an OpRisk-specific conversational analyst. Capgemini Invent's tools (see SQ4) and IBM watsonx.governance ORM are the closest vendor offerings, but neither publishes a real reference implementation.

What's published *outside* banking is more useful as a template: LinkedIn SQL Bot (SQ2), Zalando Postmortem Goldmines (SQ5), and Snowflake Intelligence / Databricks Genie (SQ4).

**Evidence**:
- "Advancing Claude for Financial Services" — Anthropic — https://www.anthropic.com/news/advancing-claude-for-financial-services
- "Anthropic rolls out financial AI tools" — Banking Dive — https://www.bankingdive.com/news/anthropic-rolls-out-financial-ai-tools-target-large-clients-claude/753249/
- "Goldman Sachs taps Anthropic's Claude" — CNBC, Feb 2026 — https://www.cnbc.com/2026/02/06/anthropic-goldman-sachs-ai-model-accounting.html
- "How generative AI can help banks manage risk and compliance" — McKinsey — https://www.mckinsey.com/capabilities/risk-and-resilience/our-insights/how-generative-ai-can-help-banks-manage-risk-and-compliance
- "Managing the new wave of risks from AI agents in banking" — Deloitte — https://www.deloitte.com/us/en/insights/industry/financial-services/agentic-ai-risks-banking.html

**Implication for the POC**: The bar to clear is "audit trail + verified data source + human-in-the-loop". CFPB / OCC have already declared chatbots are regulated compliance systems. For v1: every agent answer must (a) cite the underlying incident IDs, (b) show the tool calls, (c) be reproducible from the logged tool invocations. This is non-negotiable for a financial institution. It also rules out Streamlit's "rerun the whole script" model for the conversation core, because we lose the trace — see SQ6.

### SQ4: Capgemini Invent OpRisk tools — technical architecture and case studies?

**Answer**: Capgemini Invent operates two named OpRisk products that map almost 1:1 onto our POC:

- **Taxonomy Rationalization & Classification Tool**: "automatically classifies operational risk incidents into an internal taxonomy of risks based on incident descriptions and provides advanced exploration and visualization capabilities to assist risk managers' analysis." Uses NLP techniques to "build a dynamic and robust taxonomy of risks" and link internal/external incidents.
- **Weak Signals Analysis Tool**: "spots a company's most recurring operational risks, materially-relevant topics and related causes based on incident descriptions… for improved detection of emerging risks and provides experts with valuable content to help define KRIs."

That is *exactly* our scope: thematic exploration, causal/relational, temporal trend, self-service classification, weak-signal detection. Capgemini's framing validates the "AI-assisted, human-curated" posture (no autonomous decisioning).

**What is NOT public**: the architecture. Capgemini's marketing pages mention "NLP techniques" generically; there is no published whitepaper, no benchmark, no reference customer architecture. No mention of LLMs, no mention of clustering algorithms, no mention of vector store. This is consultancy IP — they sell the implementation. No case study with named customers exists in public web indices as of May 2026.

The closest published *technical* peer is **Zalando's Postmortem Goldmines** (Sept 2025) — see SQ5 — which is more honest about the engineering trade-offs. IBM watsonx.governance ORM exists but is narrower (model risk + RCSA workflow, not free-form incident clustering).

**Evidence**:
- Capgemini Operational Risk service — https://www.capgemini.com/service/operational-risk/
- "How to leverage data for a granular view on operational risk" — Capgemini, 2022 — https://www.capgemini.com/2022/03/how-to-leverage-data-for-a-granular-view-on-operational-risk/
- "Top 10 operational risks for 2024" — Risk.net — https://www.risk.net/risk-management/7959161/top-10-operational-risks-for-2024
- IBM watsonx.governance ORM — https://www.ibm.com/docs/en/watsonx/saas?topic=components-operational-risk-management-solution
- "Automate RCSA and enhance risk management" — IBM — https://www.ibm.com/think/insights/automate-rcsa-enhance-risk-management-generative-ai

**Implication for the POC**: We should explicitly position the deliverable as a Capgemini-Invent-style "Taxonomy Rationalization + Weak Signals" capability. This is a strong sales/communication anchor with stakeholders (it's a *known* category, not a novel artifact). Their public scope omits conversational interface — meaning if we ship a competent chat-over-corpus, we are *ahead* of the visible state of the art for in-house OpRisk tooling, not behind it.

### SQ5: FAANG / fintech postmortem tooling — what's been published?

**Answer**: The single most relevant public artifact is **Zalando Engineering — "Dead Ends or Data Goldmines? Investment Insights from Two Years of AI-Powered Postmortem Analysis"** (Sept 2025). It describes:

- LLM-based SRE assistant analyzing thousands of postmortems.
- Pattern identification across infra (Postgres, DynamoDB, ElastiCache, S3, Elasticsearch).
- Techniques: just-in-time injection, tool masking, **staged compaction**, **context isolation through sub-agents**, **file system offloading**, specialized embeddings.
- Critical gotcha named explicitly: **"Surface Attribution Error"** — the LLM blames a technology because it's mentioned in the text, not because it caused the outage. We will hit this *exactly* on incident narratives.
- Verdict: AI accelerates analysis but **human curation remains crucial** — explicit endorsement of the human-in-the-loop posture.

Other relevant findings:

- **Stripe**: built internal tooling like the "Big Red Button" and instituted Incident Review meetings (executives + engineers). No published architecture for postmortem analytics. Famous for the postmortem culture but not for AI-powered mining of it.
- **Monzo**: open-sourced their incident response tool **monzo/response** (https://github.com/monzo/response). Detailed public postmortems (e.g., July 2019). No public AI-powered analysis tool.
- **Google SRE**: standard postmortem template + manual trend analysis on root-cause and trigger types. AI is being added but Google has been more conservative about publishing its internal incident-analysis tooling.
- **Meta**: stated focus on ML-driven incident response expansion, but specifics not public.
- **Vendor space**: incident.io, Rootly, FireHydrant, PagerDuty all ship LLM-driven postmortem drafting / summarization / root-cause suggestion in 2025. Rootly markets "Auto-Detects Incident Root Causes in Seconds"; incident.io has Scribe (timeline transcription) and AI synthesis. These are the de-facto baseline a risk analyst will compare us against.

**Evidence**:
- "Dead Ends or Data Goldmines?" — Zalando Engineering, Sept 2025 — https://engineering.zalando.com/posts/2025/09/dead-ends-or-data-goldmines-ai-powered-postmortem-analysis.html
- "How Meta and Google use AI to improve incident response" — Rootly Blog — https://rootly.com/blog/how-meta-and-google-use-ai-to-improve-incident-response
- Google SRE Postmortem Analysis — https://sre.google/workbook/postmortem-analysis/
- Monzo Response — https://github.com/monzo/response
- "Checklist to service: scaling Stripe's incident response" — Retool Blog — https://retool.com/blog/incident-response-tools-stripe
- "Automated post-mortems compared: incident.io vs FireHydrant vs PagerDuty 2025" — incident.io — https://incident.io/blog/incident-io-vs-firehydrant-vs-pagerduty-automated-postmortems-2025
- "The post-mortem problem" — incident.io — https://incident.io/blog/the-post-mortem-problem

**Implication for the POC**: Adopt the Zalando lessons directly: **(a)** instrument for "Surface Attribution Error" — never let a pure LLM call decide a root cause without grounding the output in a structured causal field extracted by Plan 2; **(b)** keep humans in the loop for taxonomy curation; **(c)** use sub-agent context isolation for long-tail clustering tasks. The POC should *visibly* call out these gotchas in the analyst-facing UI ("This attribution is heuristic; verify against incident narrative") to build trust.

### SQ6: Streamlit vs Evidence.dev vs Gradio vs Chainlit vs React — which for exploratory incident analysis?

**Answer**: It depends on whether the *primary* surface is a chat or a dashboard. The honest matrix:

| Tool | Primary fit | Conversational? | EDA / dashboards? | Streaming agent traces | Multi-user / RBAC |
|------|-------------|-----------------|-------------------|------------------------|--------------------|
| **Streamlit** | Python data apps, prototypes | OK (st.chat_message added 2023) | Strong | Weak (full-script rerun, callback handler hack) | Weak |
| **Gradio** | ML model demos | OK | Weak (not designed for analytics) | OK (built-in stream) | Weak |
| **Chainlit** | LLM chat / agent UI | **Strongest** (built for it) | Weak (no native dashboards) | **Strongest** (built-in agent step viz) | Native SSO (Okta/Azure AD/Google) |
| **Evidence.dev** | SQL-first BI reports | No (it's reports) | Strong (SQL-native, markdown) | No | Static / Git-based |
| **Reflex** | Full-stack Python web app | OK | Strong | OK (WebSockets) | OK (FastAPI under the hood) |
| **Dash** | Production-grade Python dashboards | Awkward | Strong | OK | OK (Dash Enterprise) |
| **Retool** | Internal CRUD tools | OK | OK | OK | **Strongest** (enterprise) |
| **Custom React + FastAPI** | Anything | Strong | Strong | Strong | Strong | very expensive |

Concrete production realities for our POC:

- **Streamlit's full-script rerun model** breaks down for streaming agent steps; the `StreamlitCallbackHandler` exists but is brittle. For a chat that streams "tool call → result → reasoning → answer", you fight Streamlit. For a *dashboard with a small chat panel* (our actual case), it works.
- **Chainlit ReAct outperforms Streamlit on conversational agents**: cited 2.5× lower latency, 30% higher task success on agent evals. But in May 2025 the original Chainlit team stepped back; project is community-maintained. For a 6-12 month POC this risk is acceptable; for a multi-year platform it is not.
- **Evidence.dev is SQL-first and report-oriented**, not interactive — wrong shape for ad-hoc questions. Eliminate.
- **Gradio** is Hugging-Face-flavored, weaker on analytics; fine for an embedding-cluster demo, not as the analyst's main surface. Eliminate.
- **Reflex / Dash** are stronger for production but slower to prototype, and for a single-analyst v1 the marginal cost isn't justified. Defer.
- **Retool** has the best enterprise story (RBAC, audit) but you're writing JS for the custom blocks and the Python AI logic still has to be elsewhere — split-brain architecture. Defer.

**Evidence**:
- "Streamlit vs Gradio vs Chainlit: Best UI Framework for LLMs 2025" — Markaicode — https://markaicode.com/vs/streamlit-vs-gradio-vs-chainlit/
- "Best Streamlit Alternatives for Production-Grade Data Apps 2025" — Plotly — https://plotly.com/blog/best-streamlit-alternatives-production-data-apps/
- "Reflex vs Streamlit" — Reflex — https://reflex.dev/blog/reflex-streamlit/
- Streamlit chat docs — https://docs.streamlit.io/develop/tutorials/chat-and-llm-apps/build-conversational-apps
- "Gradio vs Streamlit" — Evidence — https://evidence.dev/learn/gradio-vs-streamlit
- "Rapid Prototyping of Chatbots with Streamlit and Chainlit" — Towards Data Science — https://towardsdatascience.com/rapid-prototyping-of-chatbots-with-streamlit-and-chainlit/
- Chainlit — https://chainlit.io/

**Implication for the POC**: **Streamlit for v1**, with two explicit caveats:
1. The primary surface is the *exploration dashboard* (cluster maps, faceted filters, temporal charts) with chat as a *secondary* panel that calls a small set of typed tools. This plays to Streamlit's strengths and around its weaknesses.
2. If user testing in v1 shows the analyst lives 80% in chat, **migrate the chat surface to Chainlit** in v1.5 (keep Streamlit for the dashboard pages). This is cheap because the LLM logic is in the agent, not the UI — Streamlit and Chainlit can call the same `agent.run()` function.

## Approach Comparison

| Approach | Pros (max 3) | Cons (max 3) | Maturity (1-5) | Cost | Recommendation |
|----------|--------------|--------------|----------------|------|----------------|
| Pure text-to-SQL agent (NL → SQL → DB) | (a) Maximum flexibility (b) Familiar BI pattern (c) Vendor solutions exist (Genie, Snowflake) | (a) Hallucinated columns silently wrong (b) Spider 2.0 SOTA only ~36-59% (c) Requires semantic layer to reach 90%+ | 3 | High (semantic-layer build) | ❌ Avoid for v1 — too risky for risk analysts |
| Hybrid RAG (semantic search + curated SQL tools) with LangGraph | (a) Stateful retries, parallel sub-agents (b) LinkedIn SQL Bot proven at 95% sat (c) Strong observability | (a) Framework overhead, breaking changes (b) Steeper learning curve (c) Overkill for ≤3-step loops | 4 | Medium-High | ⚠️ Consider for v1.5 once we know the agent shape |
| Hybrid RAG with DSPy | (a) Mechanical prompt optimization (b) GEPA optimizer (2025) outperforms hand-tuned (c) Typed signatures aid testing | (a) Needs labeled eval set we don't have (b) Smaller community (c) Over-engineering at POC scale | 3 | Medium | ❌ Defer — wrong stage |
| Hybrid RAG with native Anthropic tool-calling | (a) Simplest architecture (b) Anthropic's own recommended pattern (c) Direct Claude 4.5+ tool-use, no abstraction | (a) Manual orchestration code (b) No built-in DAG/persistence (c) Limited parallelism | 5 | Low | ✅ **Adopt for v1** |
| Streamlit UI (dashboard + chat panel) | (a) Fast prototyping (b) Native st.chat (c) Single-file deploy | (a) Full-script rerun hurts streaming (b) Weak multi-user/RBAC (c) Limited custom styling | 5 | Low | ✅ **Adopt for v1** |
| Chainlit (chat-first) | (a) Built for agent UIs (b) Native streaming + step viz (c) SSO out of the box | (a) Community-maintained since May 2025 (b) Weak for non-chat dashboards (c) Smaller ecosystem | 3 | Low | ⚠️ Adopt in v1.5 if chat dominates |
| Evidence.dev | (a) SQL-native (b) Git-based versioning (c) Beautiful reports | (a) Not interactive (b) No chat (c) Wrong shape for ad-hoc Q&A | 4 | Low | ❌ Avoid — wrong shape |
| Gradio | (a) Fast ML demos (b) HF ecosystem (c) Built-in streaming | (a) Not designed for dashboards (b) Weak data-table UX (c) Less analytics flexibility | 4 | Low | ❌ Avoid — wrong shape |
| Reflex / Dash / Retool / React+FastAPI | (a) Production-grade (b) Multi-user, RBAC (c) Real interactivity | (a) Slower to build (b) More moving parts (c) Premature for v1 | 4 | Medium-High | ⚠️ Defer to v2 |

## Recommended Architecture

**The conversational stack for v1:**

```
┌─────────────────────────────────────────────────────────────┐
│ Streamlit App (single-page, multi-tab)                       │
│  ├─ Tab "Explore"   : faceted filters, cluster map, charts   │
│  ├─ Tab "Ask"       : st.chat_message panel (the agent)      │
│  ├─ Tab "Curate"    : analyst defines/relabels taxonomy      │
│  └─ Tab "Trends"    : temporal charts (Plan 3 outputs)       │
└──────────────────────────┬───────────────────────────────────┘
                           │ calls
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ agent.run(question) — Anthropic native tool-calling         │
│   model: claude-sonnet-4.5 (default), claude-opus-4.5 (hard)│
│   loop: gather context → call tool(s) → verify → answer     │
│   max_iters: 6, with hard timeout                            │
└──────────────────────────┬───────────────────────────────────┘
                           │ tools (typed, validated)
       ┌───────────────────┼─────────────────────┐
       ▼                   ▼                     ▼
┌──────────────┐  ┌────────────────┐  ┌─────────────────────┐
│ semantic_    │  │ filter_        │  │ temporal_signal()   │
│ search()     │  │ incidents()    │  │ (Plan 3 z-score/    │
│ — pgvector   │  │ — SQL on       │  │  Prophet output)    │
│   per facet  │  │   structured   │  │                     │
└──────────────┘  │   columns      │  └─────────────────────┘
                  └────────────────┘
       ┌───────────────────┬─────────────────────┐
       ▼                   ▼                     ▼
┌──────────────┐  ┌────────────────┐  ┌─────────────────────┐
│ cluster_     │  │ causal_lookup()│  │ get_incident(id)    │
│ summary()    │  │ (Plan 2 graph) │  │ — full text +       │
│ (Plan 1 out) │  │                │  │   structured fields │
└──────────────┘  └────────────────┘  └─────────────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │ Postgres + pgvector         │
              │  - incidents (structured)   │
              │  - facet embeddings (3)     │
              │  - HNSW indexes per facet   │
              │  - clusters, themes, edges  │
              └────────────────────────────┘
```

**Tool design rules (non-negotiable):**

1. Every tool has a typed JSON schema; Claude cannot pass arbitrary SQL.
2. Every tool response includes the *underlying incident IDs* used. The agent quotes them in the final answer.
3. The full tool-call trace is logged per session (audit trail).
4. The chat panel renders intermediate tool calls (collapsed by default) so the analyst can verify reasoning.

**Why NOT free text-to-SQL in v1:**

- Risk-analyst trust is fragile and asymmetric: one silently-wrong number erases ten correct ones.
- Spider 2.0 SOTA is 36-59%; we have no semantic layer; expected accuracy on our schema would be ≤50%.
- Mitigation (semantic layer, glossary, eval suite) is multi-quarter — moves the POC out of "feasibility" timeline.

**v1.5 / stretch upgrades (only if v1 succeeds):**

- Add LangGraph if any tool needs >3 stateful steps with retries.
- Add a guarded `execute_sql()` tool *only* against a curated read-only view, *only* with a semantic-layer prompt, *only* with execution-feedback loop (ReFoRCE-style).
- Move the chat surface to Chainlit if the analyst lives in chat 80%+ of the time.

**Integration with other plans:**

- **Plan 1 (LLM pre-extraction + faceted clustering)** → produces `cluster_summary()` and `semantic_search()` per facet.
- **Plan 2 (causal/relational extraction)** → produces `causal_lookup()`.
- **Plan 3 (temporal/trend, Prophet/z-score)** → produces `temporal_signal()`.
- **Plan 4 (self-service classification UI)** → drives the "Curate" tab; reclassification calls back into the embeddings pipeline.

## Architectural Decisions

### Hypotheses from the brief (validate or revise)

- **D7 — pgvector as vector store**: **CONFIRM**.
  - Rationale: At 5K incidents × 3 facets = 15K vectors max, pgvector is dramatically over-provisioned. HNSW yields ~1.5 ms p50 latency; sequential scan is still fine at this scale (~650 ms but acceptable for analytical queries). Specialized vector DBs (Qdrant/Weaviate/Pinecone) add infra complexity with zero performance benefit at this size. Postgres also lets us join structured columns with vector search in a single query — a *requirement*, not a nice-to-have, given the agent will need `WHERE channel='X' AND date > ... ORDER BY embedding <=> $query`. pgvectorscale (DiskANN) only matters >10M vectors.
  - Index choice: **HNSW** (not IVFFlat); 30× higher QPS at 99% recall, build time penalty (30s vs 15s) is irrelevant at 5K rows.

- **D8 — Streamlit for UI**: **CONFIRM with caveats**.
  - Rationale: Streamlit fits the v1 reality — single technical-but-non-dev analyst, primary surface is exploration dashboard, chat is one panel. It is the lowest-friction path to a usable POC. Its weaknesses (full-script rerun, weak multi-user, weak streaming) do not bind in v1.
  - Caveats / when to revise:
    - If v1 user testing shows >70% of analyst time spent in the chat panel, **migrate chat to Chainlit in v1.5** (keep Streamlit for non-chat tabs). The `agent.run()` function is UI-agnostic.
    - If we need RBAC, multi-tenant, or full audit UI before v2, plan a **Reflex or React+FastAPI** rebuild. Do not try to harden Streamlit for these.
    - Conversational self-service over free SQL: **out of scope for v1**, deferred to v1.5+ behind a semantic layer.

### ADRs affected

- **ADR (UI choice)**: Streamlit accepted for v1, with explicit migration trigger ("chat-time > 70% of session" → Chainlit for chat tab). Conversational self-service is a *stretch goal*, not v1.
- **ADR (Vector store)**: pgvector confirmed. HNSW index. No separate vector DB.
- **ADR (Agent framework)**: native Anthropic tool-calling for v1. LangGraph evaluated for v1.5 only if multi-step retry/parallelism becomes load-bearing. DSPy deferred to v2 (needs eval set we don't have yet).
- **ADR (text-to-SQL surface)**: NOT exposed in v1. Curated typed tools only.

## Market Intelligence

### Financial services OpRisk tooling — what's actually deployed

- **Capgemini Invent** offers two named OpRisk products that mirror our scope: *Taxonomy Rationalization & Classification* (auto-classifies incidents into a dynamic risk taxonomy via NLP) and *Weak Signals Analysis* (surfaces emerging risks and KRIs from incident descriptions). Both are NLP-based per public docs; no LLM mention; no published architecture. Validates our scope; offers no implementation reference.
- **IBM watsonx.governance ORM** integrates model risk with operational risk and uses gen AI to evaluate control descriptions vs. RCSA framework. Narrower scope than our POC (compliance workflow, not free-form incident analytics).
- **Anthropic Claude for Financial Services** (GA July 2025): the first industry-specific Claude offering. Sonnet 4.5 = 55.3% on Finance Agent benchmark (vs GPT-5 46.9%, Gemini 2.5 Pro 29.4%). Goldman Sachs, Moody's, Bridgewater, AIG all named customers. The pattern they describe is *MCP servers + semantic layer + Claude tool-calling* — same shape we're recommending for v1.
- **Goldman Sachs**: co-developing autonomous Claude agents for trade/transaction accounting and KYC. Architecture not public; "embedded Anthropic engineers" implies bespoke.
- **Moody's**: serves data to Claude via MCP servers fronted by a semantic layer. Closest public peer to a "well-engineered" tool-calling architecture for finance.
- **CFPB / OCC** have explicitly declared chatbots are regulated compliance systems. Audit trail is not optional.

### FAANG / fintech incident analysis practices

- **Zalando** (Sept 2025) — **the single best public peer to our POC**. Two years of LLM-powered postmortem analysis. Names the gotchas: Surface Attribution Error, hallucination, need for human curation. Techniques: just-in-time injection, tool masking, staged compaction, sub-agent context isolation, file system offloading, specialized embeddings. Used Google's NotebookLM as toolbox.
- **Stripe**: incident response tooling ("Big Red Button") and Incident Review meetings; no public AI-powered analysis tool.
- **Monzo**: open-sourced `monzo/response`; transparent postmortem culture; no public AI-powered analysis tool.
- **Google SRE**: standard postmortem template + manual trend analysis on root-cause and trigger types; AI being added but specifics not public.
- **Meta**: stated focus on ML for incident response; specifics not public.
- **LinkedIn SQL Bot**: ~95% user satisfaction on internal text-to-SQL using LangGraph + RAG + KG + LLM rerank + self-correction. "Fix with AI" used in 80% of sessions.
- **Vendor SaaS** (incident.io, Rootly, FireHydrant, PagerDuty): all ship LLM-driven postmortem drafting and root-cause suggestion in 2025. This is the de-facto baseline analysts will compare us against.

### Conversational analytics platforms

- **Databricks AI/BI Genie** (GA 2025): NL → SQL with knowledge stores (annotated tables, columns, measures, filters, dimensions); SQL execution result summaries; thinking-step visualization; Conversation API for Slack/Teams embedding. Strong reference for what "good conversational BI UX" looks like in 2025.
- **Snowflake Intelligence**: NL over structured + unstructured, role-based access, audit-friendly.
- Both validate the *agent + semantic layer + tool-calling* architecture but are heavyweight for a 5K-incident POC.

## Open Questions

1. **Will the analyst actually live in chat, or in the dashboard?** Need v1 user testing. This determines whether to migrate to Chainlit in v1.5 or stay on Streamlit.
2. **Do we need Spanish/Portuguese language support in the conversation?** If the corpus is multilingual, prompt engineering and embedding choice (Plan 1) interact with the agent prompt here.
3. **What is the analyst's tolerance for "I don't know" answers?** Calibrating the agent to abstain rather than hallucinate is hard. Need an explicit "low-confidence response" template and user-acceptance testing.
4. **MCP vs. direct tool-calling**: should the tool layer be an MCP server (mirrors Moody's/Goldman pattern, future-proofs for Claude Skills / external agents) or in-process Python? MCP adds a process boundary; for v1 in-process is simpler but MCP makes the v2 reuse story stronger.
5. **Audit-trail requirements from the institution's compliance team**: what level of trace persistence and reproducibility is required? CFPB/OCC posture suggests at least full tool-call logging with retention.
6. **Eval harness**: we have no labeled question-answer set yet. Building one is the precondition for ever introducing DSPy / GEPA optimization. Should be sized at 50-100 hand-curated analyst questions before v1.5.

## References

### Papers

- [2024-12] Anthropic — "Building Effective Agents" — https://www.anthropic.com/research/building-effective-agents
- [2025-02] Snowflake-Labs et al. — "ReFoRCE: A Text-to-SQL Agent with Self-Refinement, Consensus, Column Exploration" — https://arxiv.org/abs/2502.00675
- [2025] Spider 2.0 (ICLR 2025 Oral) — "Evaluating Language Models on Real-World Enterprise Text-to-SQL Workflows" — https://spider2-sql.github.io/
- [2025-07] RetrySQL — "Text-to-SQL Training with Retry Data for Self-Correcting Query Generation" — https://arxiv.org/abs/2507.02529
- [2025-09] SQL-of-Thought — "Multi-agentic Text-to-SQL with Guided Error Correction" — https://arxiv.org/html/2509.00581v2
- [2023] DSPy — Khattab et al. — "Compiling Declarative Language Model Calls into Self-Improving Pipelines" — https://arxiv.org/pdf/2310.03714
- BIRD-bench — https://bird-bench.github.io/
- [2025] "Practical Text-to-SQL for Data Analytics" — LinkedIn Engineering — https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics

### Repositories

- pgvector/pgvector — open-source vector similarity search for Postgres — https://github.com/pgvector/pgvector
- timescale/pgvectorscale — Postgres extension for vector search at scale (DiskANN) — https://github.com/timescale/pgvectorscale
- Snowflake-Labs/ReFoRCE — top of Spider 2.0 leaderboard — https://github.com/Snowflake-Labs/ReFoRCE
- xlang-ai/Spider2 — Spider 2.0 benchmark — https://github.com/xlang-ai/Spider2
- monzo/response — Monzo's incident response tool — https://github.com/monzo/response
- stanfordnlp/dspy — https://dspy.ai/
- LangGraph (langchain-ai) — https://docs.langchain.com/oss/python/langchain/

### Blog Posts / Engineering Case Studies

- "Dead Ends or Data Goldmines? Two Years of AI-Powered Postmortem Analysis" — Zalando Engineering, Sept 2025 — https://engineering.zalando.com/posts/2025/09/dead-ends-or-data-goldmines-ai-powered-postmortem-analysis.html
- "Building a Production Text-to-SQL Assistant with Multi-Agent Architecture" — LinkedIn / ZenML LLMOps Database — https://www.zenml.io/llmops-database/building-a-production-text-to-sql-assistant-with-multi-agent-architecture
- "Why 90% Accuracy in Text-to-SQL is 100% Useless" — Towards Data Science — https://towardsdatascience.com/why-90-accuracy-in-text-to-sql-is-100-useless/
- "The Six Failures of Text-to-SQL (And How to Fix Them with Agents)" — Karl Weinmeister, Google Cloud — https://medium.com/google-cloud/the-six-failures-of-text-to-sql-and-how-to-fix-them-with-agents-ef5fd2b74b68
- "Headless vs. native semantic layer: 90%+ text-to-SQL accuracy" — VentureBeat — https://venturebeat.com/ai/headless-vs-native-semantic-layer-the-architectural-key-to-unlocking-90-text
- "Streamlit vs Gradio vs Chainlit: Best UI Framework for LLMs in 2025" — Markaicode — https://markaicode.com/vs/streamlit-vs-gradio-vs-chainlit/
- "Best Streamlit Alternatives for Production-Grade Data Apps in 2025" — Plotly Blog — https://plotly.com/blog/best-streamlit-alternatives-production-data-apps/
- "Reflex vs Streamlit" — Reflex Blog — https://reflex.dev/blog/reflex-streamlit/
- "Rapid Prototyping of Chatbots with Streamlit and Chainlit" — Towards Data Science — https://towardsdatascience.com/rapid-prototyping-of-chatbots-with-streamlit-and-chainlit/
- "How Meta and Google use AI to improve incident response" — Rootly — https://rootly.com/blog/how-meta-and-google-use-ai-to-improve-incident-response
- "Automated post-mortems compared: incident.io vs FireHydrant vs PagerDuty in 2025" — incident.io — https://incident.io/blog/incident-io-vs-firehydrant-vs-pagerduty-automated-postmortems-2025
- "Checklist to service: scaling Stripe's incident response" — Retool — https://retool.com/blog/incident-response-tools-stripe
- Google SRE Postmortem Analysis — https://sre.google/workbook/postmortem-analysis/
- "How generative AI can help banks manage risk and compliance" — McKinsey — https://www.mckinsey.com/capabilities/risk-and-resilience/our-insights/how-generative-ai-can-help-banks-manage-risk-and-compliance
- "Managing the new wave of risks from AI agents in banking" — Deloitte — https://www.deloitte.com/us/en/insights/industry/financial-services/agentic-ai-risks-banking.html
- "PGVector: HNSW vs IVFFlat — A Comprehensive Study" — https://medium.com/@bavalpreetsinghh/pgvector-hnsw-vs-ivfflat-a-comprehensive-study-21ce0aaab931
- "Optimize generative AI applications with pgvector indexing" — AWS Database Blog — https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/

### Products / Vendors

- Capgemini Invent — Operational Risk service — https://www.capgemini.com/service/operational-risk/
- IBM watsonx.governance ORM — https://www.ibm.com/docs/en/watsonx/saas?topic=components-operational-risk-management-solution
- Anthropic Claude for Financial Services — https://www.anthropic.com/news/advancing-claude-for-financial-services
- Databricks AI/BI Genie — https://www.databricks.com/blog/aibi-genie-now-generally-available
- Snowflake Intelligence / Data Agents — https://www.snowflake.com/en/product/use-cases/data-agents/
- incident.io (AI postmortems) — https://incident.io/
- Rootly (AI postmortems) — https://rootly.com/
- Streamlit — https://streamlit.io/
- Chainlit — https://chainlit.io/
- Evidence.dev — https://evidence.dev/
- Gradio — https://gradio.app/
- Reflex — https://reflex.dev/
- Retool — https://retool.com/
