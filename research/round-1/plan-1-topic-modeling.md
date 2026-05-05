---
plan: 1
title: "Modern Topic Modeling: Which Approach Wins on Incident Corpora?"
date: 2026-05-05
status: complete
decisions_addressed: [D1, D2, D3, D4]
adr_changes: ["ADR-1 reinforced (LLM pre-extraction); ADR-2 reinforced (multi-faceted, not single label); new follow-on ADR proposed: replace HDBSCAN with MiniBatch K-Means for the bottom-up hierarchical reduction stage on summaries, keep HDBSCAN only for raw-text outlier discovery"]
---

# Plan 1 — Modern Topic Modeling: Which Approach Wins on Incident Corpora?

## Executive Summary

- **Finding 1 — The "Clio-style" pipeline (LLM facet extraction → embed summary → cluster) is now the best-supported approach for short, boilerplate-heavy, multi-axis text such as incident narratives.** It is the production pipeline at Anthropic for analyzing tens of millions of conversations and has at least three independent open-source reproductions (OpenClio, Kura, HERCULES). For ~5k texts the cost is small (~$15–40 of Sonnet) and the gain over raw BERTopic on this class of corpus is qualitative, not just incremental.
- **Finding 2 — The naive BERTopic critique in the brief is correct, but the standard remediation is wrong.** The literature does not support "throw a bigger generic model (bge-large-en) at the problem". Domain-tuned embeddings (FinTextSim, FinBERT) deliver +81% intratopic similarity over MiniLM on financial text, which is the larger lever. However, fine-tuning a sentence transformer is out of scope for a POC; LLM pre-extraction achieves a similar effect by construction (the summary is already domain-distilled).
- **Finding 3 — Top2Vec should not be in the v1 design.** Multiple 2022–2025 benchmarks (Twitter, adolescent health, Springer 2024) show Top2Vec produces fragmented clusters, low topic diversity, and weak NPMI on short texts (NPMI = -0.21 in the 2025 BERTopic_Teen benchmark vs +0.22 for tuned BERTopic). It also has no good story for hierarchy or for incremental update.
- **Finding 4 — The clustering primitive should be split.** Use HDBSCAN once on raw narrative embeddings to surface outliers / novel weak signals (it is purpose-built for that), and use MiniBatch K-Means + recursive LLM relabeling on summary embeddings to build the human-facing hierarchical taxonomy. This is the Clio recipe and it sidesteps HDBSCAN's well-known fragility on small samples.
- **Finding 5 — Hierarchical decomposition ("decompose cluster X into sub-themes") is non-trivial in vanilla BERTopic.** BERTopic's `.hierarchical_topics()` is a post-hoc agglomeration of c-TF-IDF vectors and tends to produce trees that domain experts find unintuitive. The Clio/Kura/SC-Taxo line of work — recursive LLM-driven re-clustering — is now the state of the art and directly answers the brief's "decompose theme X into sub-themes" requirement.

## Findings by Sub-Question

### SQ1: What quality benchmarks exist for topic modeling on financial/legal corpora?

**Answer**: The community-standard infrastructure is **OCTIS** (MIND-Lab, EACL 2021, still maintained), which provides NPMI / C_V / U_Mass / topic diversity / Inverted-RBO and Bayesian hyperparameter optimisation across LDA, NMF, ProdLDA, ETM, CTM, and BERTopic. There is **no canonical public English benchmark for financial incidents specifically**; the closest things are (a) the CFPB consumer-complaint topic-modeling paper (arXiv 2205.07259) using ~684k complaints with FinBERT vs DistilBERT vs BERT, and (b) the FinTextSim paper (arXiv 2504.15683) on S&P 500 10-K filings (2016–2022, Item 7/7A). These give us the right order-of-magnitude expectation: on financial corpora, NPMI in the 0.05–0.25 range is "good"; topic diversity above 0.85 is "good".

**Evidence**: OCTIS implements all major coherence and diversity metrics and is the substrate of most 2023–2025 papers comparing topic models. The CFPB paper specifically reports that FinBERT-tuned BERTopic produces more distinct C_V scores than vanilla BERT on the same complaint corpus. The FinTextSim paper reports concrete numbers: vs `all-MiniLM-L6-v2`, the finance-tuned encoder lifts intratopic similarity by 81% and reduces intertopic similarity by 100%, and BERTopic only forms clear and distinct economic topic clusters when paired with FinTextSim embeddings. 2024–2025 benchmark papers (BERTopic_Teen Frontiers 2025, Twitter PMC9120935) consistently use NPMI as primary metric and topic diversity as the secondary check.

**Implication for the POC**: We should adopt **NPMI + topic diversity as the headline coherence metrics**, computed via OCTIS on the final cluster→top-N-words representation. We will not have a public benchmark to compare against, so we will operate the same way the FinTextSim and BERTopic_Teen papers do: ablation on our own corpus (5k CFPB), with three baselines: (i) raw narrative + bge-large-en + BERTopic, (ii) summary embedding (Clio-style), (iii) FinBERT/finance-tuned embedding on raw narrative. This triad lets us decisively answer "does the LLM pre-extraction step pay for itself".

### SQ2: Does fine-tuned BERTopic (FinBERT) outperform generic bge-large-en?

**Answer**: **Yes, when applied directly, but the gain comes mostly from removing financial-jargon noise — which is exactly what the LLM pre-extraction step also achieves.** The two interventions are partial substitutes, not complements. For a POC at 5k narratives, paying for an LLM extraction pass once is far cheaper than fine-tuning a sentence-transformer, and it generalises across product domains (PIX, previdência, etc.) in a way that a single-domain fine-tune does not.

**Evidence**: The CFPB-specific BERTopic paper (arXiv 2205.07259, Bashar & Nayak, 2022) directly tested this: across BERT / FinBERT / DistilBERT / RoBERTa as the BERTopic backbone on 684k CFPB complaints, **FinBERT produced the most diverse and distinct topics** with the best C_V scores. FinTextSim (arXiv 2504.15683, 2025) is even stronger: triplet-loss fine-tuning of a sentence-transformer on a labelled financial dataset produced **+81% intratopic similarity, –100% intertopic similarity** versus generic MiniLM, and was the *necessary condition* for BERTopic to form clean economic topics on 10-K filings. The same paper notes that without domain tuning, BERTopic clusters are "muddy" — exactly the failure mode the brief diagnoses as "boilerplate dominance".

**Implication for the POC**: We should **not** commit to "bigger generic embedder = better". For v1, the LLM-extraction step is the cheaper and more flexible substitute for FinBERT-tuning, *and* it helps with axes (root cause vs impact) that a domain encoder still mixes. For the post-POC migration to PT-BR client data, we should keep open the option of fine-tuning `bge-m3` on labeled internal incidents using triplet loss (the FinTextSim recipe is well documented and runs on a single GPU). Recommendation: bge-large-en-v1.5 in v1 with summaries; revisit domain fine-tuning at the same time as the PT-BR migration.

### SQ3: Does Top2Vec have advantages over BERTopic+HDBSCAN for emergent topic discovery?

**Answer**: **No.** On every axis that matters for this POC (interpretability, hierarchy support, short-text robustness, NPMI coherence, library maturity), BERTopic dominates Top2Vec in the 2022–2025 literature. Top2Vec's only remaining differentiator — joint word/doc embedding — is now obsoleted by LLM-driven labeling.

**Evidence**: Three independent comparisons converge on the same verdict. Egger & Yu (Frontiers 2022, PMC9120935) on Twitter posts: BERTopic > NMF > Top2Vec > LDA on coherence and interpretability. The Springer 2024 chapter "Experimental Comparison of Three Topic Modeling Methods" reports BERTopic at least 34.2% better than Top2Vec on standard clustering metrics, and explicitly calls Top2Vec results "uninterpretable" in their experiment. The 2025 BERTopic_Teen study (Frontiers Public Health 2025) measured Top2Vec on adolescent-health social-media text: **Top2Vec produced 396 topics, NPMI = –0.2111, topic diversity = 0.8745** — i.e. negatively coherent and fragmented — while a tuned BERTopic produced NPMI = +0.2184. Top2Vec is also sensitive to embedding quality in specialised domains (per its own docs and the KDnuggets review), exactly the regime we are in.

**Implication for the POC**: Drop Top2Vec from the candidate list. The original argument for Top2Vec ("joint word-doc-topic embedding gives free topic labels") is now strictly dominated by either c-TF-IDF on cluster members (BERTopic) or LLM cluster labeling (Clio/Kura/TopicGPT). Ship-time risk of Top2Vec for a regulated bank POC is too high given the consistent fragmentation evidence.

### SQ4: Do hierarchical topic models support "decompose cluster X into sub-themes"?

**Answer**: **Yes, but the right mechanism is recursive LLM-driven re-clustering, not BERTopic's built-in hierarchical method.** BERTopic's `.hierarchical_topics()` is post-hoc agglomerative clustering on the c-TF-IDF matrix and tends to merge semantically distinct clusters when their bag-of-words happens to overlap. The Clio / Kura / TopicGPT / SC-Taxo / CobwebTM line of work explicitly addresses this and is now the state of the art.

**Evidence**: BERTopic's official docs describe `hierarchical_topics(docs)` as: "approximates topic hierarchy by using the topic-term matrix... using ward linkage by default, computed via scipy". The CobwebTM paper (arXiv 2604.14489) specifically critiques this, noting that "nearest-neighbor clustering on c-TF-IDF can conflate semantically distinct senses of ambiguous terms" — a real risk in incident text where "transaction failed" can mean fraud, system outage, or user error. Kura (567-labs/kura) implements the Clio recipe explicitly: summarize → embed → MiniBatch K-Means → recursive LLM-driven cluster merging, producing a navigable tree (individual issues → feature categories → business themes). TopicGPT (NAACL 2024, Pham et al.) reaches harmonic-mean purity 0.74 vs human annotations on Wikipedia, beating the strongest neural baseline by 10 absolute points. SC-Taxo (arXiv 2605.00620) and the EMNLP 2025 "Context-Aware Hierarchical Taxonomy" paper formalise the top-down LLM-driven approach with semantic-consistency constraints to avoid drift between levels.

**Implication for the POC**: For the brief's requirement *"how does theme X decompose into sub-themes"*, build the hierarchy the Clio/Kura way: at level k, ask the LLM to label each k-cluster; at level k+1, re-cluster the documents inside each parent cluster (still on summary embeddings) and re-label. This trivially answers "decompose cluster X" — just call the same routine on the documents inside cluster X. Do **not** ship `BERTopic.hierarchical_topics()` as the primary hierarchy; use it at most as a sanity check.

### SQ5: Does Clio-style summarize→embed→cluster have documented cost/benefit for ~5k texts?

**Answer**: **Yes — and the evidence flips the naïve "summaries lose information" intuition for this specific class of corpus (boilerplate-heavy, multi-axis, short narratives).** The 2024 ScienceDirect study on free-text summaries vs raw text *does* warn that summaries can hurt clustering, but only when (a) the summarizer is small (LLaMA-2-7B / Falcon-7B), (b) summaries are unstructured free-text, and (c) the source corpus is already clean and not boilerplate-heavy. The Clio approach is structurally different: it uses **multiple short structured facets, each extracted by a strong model, each embedded separately**, and the gain is exactly the brief's diagnosis — boilerplate is removed by construction, orthogonal axes are physically separated into different fields.

**Evidence**: The Clio paper (Tamkin et al., arXiv 2412.13678, Anthropic Dec 2024) describes the production pipeline: extract multiple facets (topic, language, task, safety) per conversation with Claude, embed each facet, cluster each facet **independently** with k-means, then recursively summarise and re-cluster to build a hierarchy. Anthropic uses this in production on tens of millions of conversations and uses it as their primary lens for emerging-misuse detection and trust-and-safety analysis. OpenClio (Phylliida) reports running the same pipeline on ~400k Wildchat English conversations using vLLM + Qwen3-8B + `all-mpnet-base-v2`. Kura (567-labs) reports ~22 seconds end-to-end on 190 conversations, and uses MiniBatch K-Means specifically for speed. HERCULES (arXiv 2506.19992) generalises the pattern as "Hierarchical Embedding-based Recursive Clustering Using LLMs". For our 5k corpus, extraction cost with Sonnet is ~$15–40 (per the brief's own ADR-5) and the resulting summary corpus is ~10× smaller in tokens, so all downstream steps are cheap.

**Implication for the POC**: Confirm the Clio-style pipeline as the v1 architecture. The cost/benefit dominates in our regime: 5k narratives is small enough that one-pass extraction is affordable, *and* short enough that summaries don't lose much (a 200-word complaint is faithfully represented by a 30-word root-cause summary). The single biggest pitfall to avoid is **using a small/cheap model for extraction** — the ScienceDirect 2024 paper is clear that summary quality is the binding constraint. Sonnet-class is the floor; Haiku is risky; GPT-4o-mini-class is risky. This reinforces ADR-5 of the brief.

### SQ6: Which method best supports novelty detection (discovering genuinely new topics)?

**Answer**: **Two complementary mechanisms, both worth shipping in v1.** (a) **HDBSCAN on raw narrative embeddings** to surface "noise" points that are semantically far from all existing clusters — these are candidates for genuinely new themes. (b) **BERTrend-style temporal weak-signal scoring on top of the cluster taxonomy** — a topic that is small but accelerating is the canonical "weak signal". K-Means alone, as used in Clio, does not give you (a) for free because every point is forced into a cluster.

**Evidence**: BERTrend (arXiv 2411.05930, FUTURED workshop 2024, by RTE-France) is the most directly applicable paper: it runs BERTopic in an online learning setting, merges per-time-slice topics using a similarity threshold, and classifies each topic as **noise / weak signal / strong signal** based on a popularity metric that combines document count and update frequency. It is open source (`pypi.org/project/bertrend`, `github.com/rte-france/BERTrend`). The HDBSCAN docs explicitly position HDBSCAN's noise label and the GLOSH outlier score as a novelty-detection primitive (`hdbscan.readthedocs.io/.../outlier_detection.html`); the 2024 Towards Data Science article "Understanding Outliers in Text Data" makes the same point: HDBSCAN noise points are often the most interesting documents, not the least. The 2024 unsupervised-outlier-detection paper (arXiv 2411.08867) formalises HDBSCAN* outlier profiles for parameter-free novelty detection. Note: BERTopic's k-means option, like Clio's pipeline, *forces* every doc into a cluster — that is why Clio uses recursive re-clustering and human inspection rather than relying on noise points.

**Implication for the POC**: Run **two clustering passes** rather than one. Pass A: HDBSCAN on raw narrative embeddings, with the noise set explicitly preserved as the "review queue" for new emerging themes. Pass B: K-Means + recursive LLM labeling on summary-facet embeddings to build the navigable hierarchy. Pass A gives the analyst novel-theme candidates; Pass B gives the analyst a stable map. For temporal signal-vs-noise (brief's question 6), adopt the BERTrend popularity score on top of Pass B clusters in v1.1; v1 can ship with the simpler z-score on cluster counts (the brief's Prophet/z-score plan is fine for a first pass, but flag for replacement — see Plan 4).

## Approach Comparison

| Approach | Pros (max 3) | Cons (max 3) | Maturity (1-5) | Cost | Recommendation |
|---|---|---|---|---|---|
| BERTopic + generic embedding (bge-large-en) | Battle-tested library; built-in c-TF-IDF labeling; fast on 5k | Boilerplate dominates; orthogonal axes collapse; "muddy" topics on financial text | 5 | $0 inference / GPU only | Baseline only — must beat this |
| BERTopic + FinBERT/finance-tuned embedding | +81% intratopic similarity on financial text (FinTextSim); same library | Domain lock-in (English only, doesn't generalise to PT-BR client); fine-tuning needs labeled triplets we don't have | 4 | Fine-tune ~$0–50 GPU; inference $0 | ⚠️ Defer to PT-BR migration phase |
| Top2Vec | Single dependency; auto-determines K | NPMI = –0.21 on short text (2025 benchmark); fragmented (~400 clusters); poor hierarchy | 3 | $0 | ❌ Drop |
| NTMs (ProdLDA / ETM / FASTopic) | FASTopic is faster and more stable than BERTopic; competitive on coherence | Smaller community; harder to debug; weaker tooling for hierarchy and labels | 3 | $0 GPU | ⚠️ Hold as fallback if BERTopic baseline is bad |
| Clio-style (LLM facet extraction → embed summary → cluster → recursive label) | Removes boilerplate by construction; faceted = orthogonal axes preserved; hierarchy is native; novelty via inspection | Requires LLM extraction pass ($15–40); two-stage system to operate; summary quality is the binding risk | 4 (production at Anthropic + 3 open-source impls) | $15–40 LLM + $0 ops | ✅ Adopt as primary |
| hBERTopic / `BERTopic.hierarchical_topics()` | Free with BERTopic; documented | Post-hoc, c-TF-IDF based; domain experts find tree unintuitive; conflates senses (CobwebTM critique) | 4 | $0 | ⚠️ Sanity check only, not primary hierarchy |
| TopicGPT (NAACL 2024) | Most interpretable labels; +10 purity points vs neural baselines on Wikipedia | Pure-LLM (no embeddings) → expensive to run on 5k docs; less control over granularity | 3 | High LLM $$ at scale | ⚠️ Borrow the labelling prompts only |
| BERTrend (online weak-signal layer) | Purpose-built for emerging-signal detection; classifies noise vs weak vs strong; open source | Adds a second clustering pass per time slice; tuning-heavy | 3 | $0 ops | ✅ Adopt for v1.1 (Plan 4) |

## Recommended Architecture

**Adopt the Clio-style pipeline as the v1 primary, with a HDBSCAN sidecar for novelty.**

```
CFPB narrative
  ├─► [extraction pass: Sonnet, structured Pydantic schema]
  │     ├─ one_sentence_summary
  │     ├─ root_cause_summary
  │     ├─ customer_impact_summary
  │     └─ enums + booleans + keywords (already in brief 6.2)
  │
  ├─► [embed each summary field separately with bge-large-en-v1.5]
  │     → 3 vectors per incident in pgvector (one column per facet)
  │
  ├─► [Pass A: HDBSCAN on raw-narrative embedding → noise queue = novelty candidates]
  │
  └─► [Pass B: per facet (Clio recipe)]
        UMAP(n_components=15) → MiniBatch K-Means(k≈40 at level 1)
        → LLM cluster labeling (Sonnet, prompted with 10 representative summaries)
        → recursive: inside each level-1 cluster, re-cluster the summaries
          to build level 2; stop when a child cluster has <30 docs
```

Concretely this means:
1. **D1 (LLM pre-extraction): CONFIRM.** The cost is bounded ($15–40), the gain is structural (boilerplate + axis separation), and the literature on free-text-summary clustering pitfalls (ScienceDirect 2024) does *not* apply to short, structured, strong-model facet extractions.
2. **D2 (cluster per facet): CONFIRM.** Clio does exactly this in production; the brief's instinct is correct. Add the small refinement that we *also* keep one global pass on the raw narrative for outlier/novelty detection.
3. **D3 (summaries as embedding unit): CONFIRM.** The corpus is short and boilerplate-heavy — exactly the regime where summaries help, not hurt. Caveat: the extraction model must be Sonnet-class or better.
4. **D4 (UMAP + HDBSCAN): REVISE.** Keep HDBSCAN for the raw-narrative novelty sidecar (Pass A), where its "noise" semantics are a feature. For the human-facing hierarchical taxonomy (Pass B), switch to **MiniBatch K-Means + recursive LLM labeling** following Clio/Kura — HDBSCAN's instability on small samples and its tendency to label 30–60% of documents as noise hurts the analyst-facing experience. This is the only material change to the brief's pipeline.

**Integration with other plans:**
- **Feeds into Plan 2 (Self-Service Classification)** because: the same per-facet embedding space and the LLM-labeling prompt are the substrate for "reclassify with these 8 categories I just defined" — replacing automatic labels with user-supplied labels is a one-prompt change. The HDBSCAN novelty sidecar also feeds Plan 2's "show me the items between two categories" use case.
- **Feeds into Plan 4 (Temporal Analysis)** because: the cluster IDs from Pass B are the unit of temporal aggregation, and the BERTrend popularity score (mentioned in SQ6) plugs in directly above the cluster IDs. Without stable cluster IDs you cannot ask "is theme X growing"; the Clio-style stable hierarchy gives that for free, while raw HDBSCAN per-time-slice does not (cluster IDs change each run).

## Architectural Decisions

### Hypotheses from the brief

- **D1 — LLM pre-extraction before clustering: CONFIRM.**
  Rationale: The 2024 ScienceDirect "summarisation hurts clustering" finding does not apply when (a) the summariser is strong and (b) summaries are short structured facets, not free-text. The Clio production deployment (Anthropic, tens of millions of conversations) and three independent open-source reproductions (OpenClio, Kura, HERCULES) all use this pattern. For our 5k-narrative POC, the cost is bounded ($15–40 with Sonnet, per ADR-5) and the structural gain (boilerplate removal + axis separation) is exactly what the brief's failure-mode diagnosis calls for.

- **D2 — Cluster per facet: CONFIRM.**
  Rationale: This is the central architectural insight of Clio. Independent clustering of `root_cause_summary` vs `customer_impact_summary` lets the analyst ask "what causes co-occur with what impacts?" — the brief's question 2 — which is impossible if the two axes are mashed into a single embedding. Risk that facets are correlated and produce redundant clusters: small in practice (Clio reports clean separation between e.g. "language" and "task" facets); to be measured on our corpus.

- **D3 — Summaries as embedding unit: CONFIRM.**
  Rationale: Short narratives + boilerplate = exactly the regime where summarisation helps. The summary discards "usuário relatou" and keeps "PIX falhou por timeout no sistema X". Caveat: requires Sonnet-class extraction (Haiku risky per ADR-5; we agree).

- **D4 — UMAP + HDBSCAN: REVISE (split into two passes).**
  Rationale: HDBSCAN is the right tool for "find me anomalies / novel items" because its noise-point semantics is a feature for that use case. It is the *wrong* tool for building a stable analyst-facing hierarchy on summary embeddings: it is fragile at small N, it forces noise points out of the taxonomy (so the analyst sees "60% uncategorised"), and its cluster IDs are unstable across runs (a problem for temporal trend analysis). Adopt MiniBatch K-Means + recursive LLM labeling for the analyst-facing taxonomy (Pass B), and keep HDBSCAN as a novelty sidecar on raw narrative (Pass A). UMAP stays in both passes but with different `n_components` (15 for K-Means; 5 for HDBSCAN, per the BERTopic docs guidance).

### ADRs affected

- **ADR-1 (Extração estruturada antes de clustering)**: REINFORCED. New evidence: Clio paper, Kura, OpenClio, HERCULES, FinTextSim. Add citations.
- **ADR-2 (Múltiplas facetas em vez de label única)**: REINFORCED. Same set of citations; explicitly anchor to Clio's "facet-independent clustering" production pattern.
- **NEW ADR proposed (ADR-7?)**: *"Two-pass clustering: HDBSCAN for novelty, K-Means + LLM labels for taxonomy"*. This is a deviation from Section 6.4 of the brief (which proposes UMAP + HDBSCAN globally) and should be its own ADR.

## Open Questions

1. **Empirical question for v1**: on our 5k CFPB sample, by how much does Clio-style summary-embedding outperform raw-narrative bge-large-en BERTopic on NPMI / topic diversity / human coherence rating? Without an in-corpus ablation we are recommending the architecture on theoretical grounds + literature, not measurement. Need to run this in Phase 2 of the implementation plan.
2. **Will K-Means on summary embeddings produce good cluster boundaries when the underlying structure is non-spherical?** Clio uses K-Means in production at scale, but their summaries are conversation-task descriptions (homogeneous shape). Incident summaries may have more dialect / register variation. Fallback: use Spherical K-Means or HDBSCAN on summary embeddings if vanilla K-Means produces obviously bad clusters.
3. **Do we need a BERTopic baseline at all in v1, or is the Clio-style pipeline directly the v1?** Recommendation: ship Clio-style as v1 *and* compute a BERTopic-baseline reference in parallel (cheap, ~30 min of compute) so the validation report (Phase 4) has a number to compare against.
4. **For the PT-BR migration, when does fine-tuning bge-m3 on internal labeled triplets pay off?** The FinTextSim recipe is documented and runs on a single GPU; the question is whether the client's labeled-incident data is large enough (need ≥10k triplets to be worth it). Defer to a post-POC ADR.

## References

### Papers
- **Tamkin et al., "Clio: Privacy-Preserving Insights into Real-World AI Use", arXiv 2412.13678** (Anthropic, Dec 2024). Production system; faceted extraction + per-facet k-means + recursive hierarchy. https://arxiv.org/abs/2412.13678
- **Pham et al., "TopicGPT: A Prompt-based Topic Modeling Framework", NAACL 2024**. Pure-LLM topic induction; +10 purity points over strongest neural baseline. https://aclanthology.org/2024.naacl-long.164/
- **FinTextSim: Enhancing Financial Text Analysis with BERTopic, arXiv 2504.15683** (2025). Triplet-loss fine-tuned sentence-transformer for financial text; +81% intratopic similarity over MiniLM. https://arxiv.org/abs/2504.15683
- **Bashar & Nayak, "Topic Modelling on CFPB Data: A BERT-based Approach", arXiv 2205.07259** (2022). Direct CFPB benchmark; FinBERT > DistilBERT > BERT for BERTopic. https://arxiv.org/abs/2205.07259
- **Boutaleb et al., "BERTrend: Neural Topic Modeling for Emerging Trends Detection", arXiv 2411.05930 / FUTURED 2024** (RTE-France). Online BERTopic + popularity-based weak/strong signal classification. https://arxiv.org/abs/2411.05930
- **Wu et al., "FASTopic: Pretrained Transformer is a Fast, Adaptive, Stable, and Transferable Topic Model", NeurIPS 2024**. Faster + more stable than BERTopic via optimal-transport DSR. https://neurips.cc/virtual/2024/poster/96416
- **"LLM-Guided Semantic-Aware Clustering for Topic Modeling" (LiSA), ACL 2025**. https://aclanthology.org/2025.acl-long.902/
- **HERCULES: Hierarchical Embedding-based Recursive Clustering Using LLMs, arXiv 2506.19992** (2025). Generalisation of the Clio recipe. https://arxiv.org/abs/2506.19992
- **BERTopic_Teen: Multi-module optimisation for short-text topic modeling, Frontiers Public Health 2025**. NPMI benchmark numbers for BERTopic / Top2Vec / LDA / NMF. https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2025.1608241/full
- **Egger & Yu, "Topic Modeling Comparison Between LDA, NMF, Top2Vec, and BERTopic", Frontiers in Sociology 2022 / PMC9120935**. https://pmc.ncbi.nlm.nih.gov/articles/PMC9120935/
- **Petukhova et al., "Text Clustering with LLM Embeddings", arXiv 2403.15112** (2024). Caveat paper: free-text summaries can hurt clustering when summariser is small. https://arxiv.org/abs/2403.15112
- **OCTIS: Comparing and Optimizing Topic Models is Simple!, EACL 2021 demo + ongoing**. https://aclanthology.org/2021.eacl-demos.31/
- **Grootendorst, "BERTopic: Neural Topic Modeling with a Class-based TF-IDF Procedure", arXiv 2203.05794** (original BERTopic paper). https://arxiv.org/abs/2203.05794
- **CobwebTM: Probabilistic Concept Formation for Lifelong and Hierarchical Topic Modeling, arXiv 2604.14489**. Critique of c-TF-IDF agglomerative hierarchies. https://arxiv.org/abs/2604.14489
- **"Unsupervised Parameter-free Outlier Detection using HDBSCAN* Outlier Profiles", arXiv 2411.08867** (2024). https://arxiv.org/abs/2411.08867
- **"Improving HDBSCAN on Short-Text Clustering by UMAP", IEEE 2021**. https://ieeexplore.ieee.org/document/9640285/

### Repositories
- **maartengr/BERTopic** — primary BERTopic library; hierarchical_topics, k-means option, c-TF-IDF. https://github.com/MaartenGr/BERTopic
- **Phylliida/OpenClio** — open-source Clio reproduction; vLLM + Qwen3 + all-mpnet-base-v2 + recursive hierarchy. https://github.com/Phylliida/OpenClio
- **567-labs/kura** (and `jxnl/kura`) — production-oriented Clio reproduction; OpenAI text-embedding-3-small + MiniBatch K-Means + recursive LLM labeling. https://github.com/567-labs/kura
- **rte-france/BERTrend** — online weak-signal detection on top of BERTopic. https://github.com/rte-france/BERTrend
- **JehnenS/FinTextSim** — code to reproduce FinTextSim training recipe. https://github.com/JehnenS/FinTextSim
- **MIND-Lab/OCTIS** — topic-model evaluation framework with NPMI / C_V / diversity. https://github.com/MIND-Lab/OCTIS
- **ddangelov/Top2Vec** — Top2Vec library (for completeness; recommend not adopting). https://github.com/ddangelov/Top2Vec
- **chtmp223/topicGPT** — TopicGPT reference implementation. https://github.com/chtmp223/topicGPT
- **BobXWu/FASTopic** — NeurIPS 2024 FASTopic implementation. https://github.com/BobXWu/FASTopic
- **scikit-learn-contrib/hdbscan** — HDBSCAN with GLOSH outlier scores. https://github.com/scikit-learn-contrib/hdbscan

### Blog Posts / Engineering Case Studies
- **Anthropic — "Clio: Privacy-preserving insights into real-world AI use"**. Official deployment writeup. https://www.anthropic.com/research/clio
- **Maarten Grootendorst — "Interactive Topic Modeling with BERTopic"** + the BERTopic Best Practices page. https://www.maartengrootendorst.com/blog/bertopictutorial/ , https://maartengr.github.io/BERTopic/getting_started/best_practices/best_practices.html
- **Simon Willison — "Clio: A system for privacy-preserving insights into real-world AI use"** (clearest plain-English walk-through of the Clio paper). https://simonwillison.net/2024/Dec/12/clio/
- **Ivan Leo — "Understanding User Conversations" (Kura design notes)**. https://ivanleo.com/blog/clio
- **KDnuggets — "Topic Modeling Approaches: Top2Vec vs BERTopic" (2023)**. Comparison piece. https://www.kdnuggets.com/2023/01/topic-modeling-approaches-top2vec-bertopic.html
- **Towards Data Science — "Understanding Outliers in Text Data with Transformers, Cleanlab, and Topic Modeling"**. Argument that HDBSCAN noise = signal for novelty. https://towardsdatascience.com/understanding-outliers-in-text-data-with-transformers-cleanlab-and-topic-modeling-db3585415a19/
- **Towards Data Science — "Topic Modelling in BI: FASTopic and BERTopic in Code"**. https://towardsdatascience.com/topic-modelling-in-business-intelligence-fastopic-and-bertopic-in-code-2d3949260a37/
- **MarkTechPost — "Anthropic Introduces Clio"** (summary). https://www.marktechpost.com/2024/12/12/anthropic-introduces-clio-a-new-ai-system-that-automatically-identifies-trends-in-claude-usage-across-the-world/

### Products / Vendors
- **Anthropic Claude API (Sonnet)** — extraction-pass model per ADR-5 of brief.
- **HuggingFace `BAAI/bge-large-en-v1.5`** — recommended English embedding for v1. https://huggingface.co/BAAI/bge-large-en-v1.5
- **HuggingFace `BAAI/bge-m3`** — recommended embedding for PT-BR migration. https://huggingface.co/BAAI/bge-m3
- **MTEB Leaderboard** — for ongoing embedding-model selection. https://modal.com/blog/mteb-leaderboard-article
- **pgvector** (per ADR-4) — fits the per-facet design (one column per facet, separate ANN indexes).
