---
plan: 4
title: "Temporal Analysis and Novelty Detection: DTM, Drift, and Signal vs. Noise"
date: 2026-05-05
status: complete
decisions_addressed: [D4, D5]
adr_changes:
  - id: ADR-005
    title: "Replace Prophet/z-score with a layered temporal stack (Poisson GLM + BOCPD + BERTrend-style popularity metric)"
    status: proposed
  - id: ADR-006
    title: "Adopt Benjamini-Hochberg FDR correction for multi-cluster monitoring"
    status: proposed
  - id: ADR-007
    title: "Use BERTopic topics_over_time for visualization only; rely on a recurring re-fit + topic-merging loop (BERTrend pattern) for emergence detection"
    status: proposed
---

# Plan 4 — Temporal Analysis and Novelty Detection: DTM, Drift, and Signal vs. Noise

## Executive Summary

- **Finding 1 — Prophet/z-score is the wrong primary tool for this problem.** Prophet was designed for forecasting with rich seasonality and holidays; multiple credible sources document it overfits/underfits trend changes, has documented poor accuracy versus simpler baselines (~16-44% worse than exponential smoothing in some benchmarks), and its anomaly mode silently swallows anomalies inside its 95% intervals. Worse, ~5,000 narratives spread over (likely) 2-3 years and split across ~50-200 clusters yield monthly counts close to zero per cluster — a regime where Gaussian z-scores and Prophet's additive normal model are mis-specified. Use a Poisson/Negative-Binomial GLM (the right likelihood for sparse counts) for growth detection.

- **Finding 2 — BERTopic's `topics_over_time` does NOT do novelty detection.** It is a c-TF-IDF visualization layer over a fixed global clustering. Topics are frozen at fit time. A 2024 emergence-detection benchmark found BERTopic underperforms LDA by ~24 F1 points specifically at detecting newly emerging topics. For Section 1.4 ("themes that emerged in the last N months that didn't exist before") this is disqualifying as a sole solution.

- **Finding 3 — BERTrend (Boutaleb et al., 2024, RTE France, MPL-2.0) is the closest off-the-shelf match for the brief.** It re-fits BERTopic per time batch, merges topics by similarity threshold across batches, and classifies each topic as **noise / weak signal / strong signal** using a popularity metric that combines document count, update frequency, and an exponential decay penalty for stale topics. This is precisely the "small cluster of unrelated outliers vs genuinely emerging problem" distinction the brief asks for.

- **Finding 4 — BOCPD (Bayesian Online Changepoint Detection) outperforms Prophet and PELT for the analyst-facing "is this spike signal or noise?" question.** It returns a calibrated *probability* of changepoint per timestep — directly answerable in plain language ("there is a 78% probability that the rate of authentication-failure incidents changed in March"). PELT remains useful for retrospective segmentation; Prophet should be retained only for one specific role (long-horizon seasonality on aggregate volume), not as the primary engine.

- **Finding 5 — Multiple-testing correction is non-negotiable when monitoring 50+ clusters.** Naive z>2 alerting produces ~2.5 false alerts/month per 50 clusters at α=0.05. Apply Benjamini-Hochberg FDR on per-cluster Poisson p-values (target FDR=0.10). For online use, switch to LORD/SAFFRON (online FDR) — there is established 2023-2024 literature on online FDR for anomaly detection (arXiv 2312.01969).

- **Finding 6 — Vocabulary drift vs semantic drift requires two different mechanisms.** Vocabulary drift (new words for an existing problem) is detected by tracking c-TF-IDF keyword churn within an existing cluster. Semantic drift (existing words denote a new problem) is detected by tracking centroid movement and intra-cluster cosine variance over time. Both should be lightweight monthly jobs.

## Findings by Sub-Question

### SQ1: DTM and BERTopic temporal mode — state of the art in 2025?

**Answer:** Classical Blei-Lafferty DTM (2006) is still cited but rarely deployed in industry — it is slow, requires a fixed K, assumes Gaussian random walks on topic-word distributions, and provides no first-class story for the *birth* and *death* of topics. The 2025 SOTA for production use cases like ours is the **"re-fit + match"** pattern, exemplified by BERTrend (Boutaleb et al., 2024, ACL FuturED workshop): run BERTopic on each time batch, merge topics across batches by embedding similarity, and use a popularity metric to classify topics. BERTopic's native `topics_over_time` is *not* dynamic topic modeling in the strict sense — it freezes the global clustering and only recomputes c-TF-IDF keywords per timestamp, so it cannot detect topic birth.

**Evidence:**
- BERTrend paper: ["BERTrend: Neural Topic Modeling for Emerging Trends Detection"](https://arxiv.org/abs/2411.05930), ACL 2024 FuturED workshop. Code: [rte-france/BERTrend](https://github.com/rte-france/BERTrend) (MPL-2.0, Python ≥3.13).
- BERTopic dynamic mode caveat: ["the global representation is used to define the main topics that can be found at different timesteps"](https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html) — i.e., topics are fixed at fit.
- Emergence detection benchmark: ["Evaluation of unsupervised static topic models' emergence detection ability"](https://pmc.ncbi.nlm.nih.gov/articles/PMC12192802/) — LDA outperforms BERTopic by ~24 F1 points on emergence detection, exposing the static-clustering limitation.
- 2025 dynamic topic modeling benchmark: ["Experimental Evaluation of Dynamic Topic Modeling Algorithms"](https://arxiv.org/html/2508.00710v1).

**Implication for the POC:** Adopt BERTrend's pattern (we can run a stripped-down version directly: monthly BERTopic re-fit + topic-merging by cosine similarity + popularity metric). Use `topics_over_time` only for the analyst-facing visualization tab. Do not build on classical DTM.

### SQ2: Vocabulary drift vs semantic drift — how to detect both?

**Answer:** These are distinct phenomena and need distinct detectors:

- **Vocabulary drift** (cluster meaning is stable, surface words change — e.g., "wire transfer fraud" → "ACH fraud" → "real-time-payment fraud"): detect by computing the **Jaccard / rank-biased overlap** of the top-N c-TF-IDF terms of a cluster across consecutive months. Sharp drops trigger a "vocabulary churn" alert.
- **Semantic drift** (surface vocabulary is stable, the cluster has *absorbed* a new sub-problem — e.g., the "system outage" cluster suddenly contains 3rd-party-API-latency narratives): detect by tracking **centroid movement** (cosine distance between this month's mean embedding and last month's) and **intra-cluster variance**. A jump in either is a semantic-drift signal.

The 2024 ACM TIST systematic review on text-stream concept drift formalizes this split and recommends embedding-distance methods for semantic drift, lexical-overlap methods for vocabulary drift.

**Evidence:**
- ["Concept Drift Adaptation in Text Stream Mining Settings: A Systematic Review"](https://arxiv.org/html/2312.02901v2) (ACM TIST 2024).
- ["Drift Detection in Text Data with Document Embeddings"](https://link.springer.com/chapter/10.1007/978-3-030-91608-4_11), Feldhans & Wilke — cosine-distance and JS-divergence methods on document embedding distributions.
- Periti & Montanelli 2024 survey on lexical semantic change with deep LMs (referenced in the ACM TIST review).
- Production tools: [Evidently AI embedding drift module](https://learn.evidentlyai.com/ml-observability-course/module-3-ml-monitoring-for-unstructured-data/monitoring-embeddings-drift) and [NannyML data drift docs](https://nannyml.readthedocs.io/en/v0.8.0/tutorials/detecting_data_drift.html) — both are open-source and battle-tested for embedding drift in production.

**Implication for the POC:** Add two cheap monthly jobs per cluster: (a) RBO/Jaccard on c-TF-IDF top-20 (vocabulary drift); (b) centroid-cosine-shift + intra-cluster variance (semantic drift). Both feed the same alert channel as count-based anomalies. Reuse Evidently for the embedding-drift component if possible; do not reinvent it.

### SQ3: Novelty detection — distinguishing real emerging problems from outlier noise?

**Answer:** This is *the* hardest question in the brief, and the answer is BERTrend's popularity metric, paraphrased and adapted:

A new small cluster is classified as a **weak signal** (genuinely emerging) rather than **noise** when it satisfies three conditions simultaneously:

1. **Persistence**: the cluster appears (or grows) in ≥ K consecutive time windows (the BERTrend metric grows with update frequency and decays exponentially when the topic stops receiving documents).
2. **Coherence**: intra-cluster cosine similarity is above a calibrated threshold (real problems have semantically tight narratives; outlier noise is by definition scattered).
3. **Growth significance**: the per-window count is statistically anomalous under a Poisson null with rate = global incident growth × cluster's prior share (so we account for general volume changes).

Conditions (1) + (2) eliminate "incoherent outliers". Condition (3) eliminates "small but stationary niche topics that have always been there". A cluster that satisfies all three is what an analyst would call an emerging theme.

A complementary tool for the *bursty* version of the same question is **Kleinberg's burst detection** (2003), which uses a 2-state HMM to model "background rate" vs "burst rate" and produces hierarchical bursts. It is much simpler than BERTrend and well-suited for keyword-level emergence (e.g., "token-impersonation appears 0 times for 14 months, then 6 times in 1 month").

**Evidence:**
- BERTrend popularity metric description: ["dynamically classifying topics as noise, weak signals, or strong signals based on their popularity trends ... incorporating an exponentially growing decay if no updates occur for an extended period"](https://arxiv.org/abs/2411.05930).
- Kleinberg, ["Bursty and Hierarchical Structure in Streams"](https://www.cs.cornell.edu/home/kleinber/bhs.pdf), KDD 2002 / DMKD 2003. Python implementation: [nmarinsek/burst_detection](https://github.com/nmarinsek/burst_detection).
- ["Online Density-Based Clustering for Real-Time Narrative Evolution Monitoring"](https://arxiv.org/html/2601.20680v1) — argues HDBSCAN's batch-only nature forces full recompute per window; recommends DenStream/CF-tree for incremental settings.

**Implication for the POC:** Implement a 3-test gate (persistence ≥ 2 windows, intra-cluster cosine ≥ 0.55, Poisson p-value < BH-corrected threshold). This is the analyst's "noise vs emerging problem" filter. Document the exact thresholds in the dashboard so the analyst can lower them and re-rank.

### SQ4: Multiple testing correction for 50+ parallel cluster monitors?

**Answer:** Required, and the right knob is **Benjamini-Hochberg FDR (q ≈ 0.10)**, not Bonferroni. With ~50-200 clusters monitored monthly, Bonferroni is too conservative (kills real emerging signals) and uncorrected α=0.05 produces ~5-10 expected false alarms per month — enough to destroy analyst trust within 3 months. BH controls the *expected proportion of false discoveries* among the alerts, which is the right semantics ("of the 7 alerts you got this month, on average ≤ 0.7 are spurious").

For online/sequential use (streaming as new incidents arrive within a month, not just monthly batch), use **LORD** or **SAFFRON** — online FDR procedures with established 2023-2024 literature applied to anomaly detection.

**Evidence:**
- BH original: Benjamini & Hochberg 1995. Survey: [Wikipedia: False Discovery Rate](https://en.wikipedia.org/wiki/False_discovery_rate).
- ["FDR Control for Online Anomaly Detection"](https://arxiv.org/abs/2312.01969) (2023) — directly applicable to our streaming-cluster-monitoring case.
- Tutorial reference: [Genovese, "A Tutorial on False Discovery Control"](https://www.stat.cmu.edu/~genovese/talks/hannover1-04.pdf) (CMU).
- OpRisk-specific FDR literature is sparse; the methodology transfers from biomedical multiple testing without modification.

**Implication for the POC:** After computing per-cluster Poisson p-values for monthly counts, sort, apply BH at q=0.10. Surface only the BH-passing clusters as "alerts". Always show the full list with raw counts so analysts can override.

### SQ5: Changepoint detection (PELT vs BOCPD vs Prophet) for incident count series?

**Answer:**

| Property | Prophet anomaly | PELT (`ruptures`) | BOCPD |
|---|---|---|---|
| Model family | Additive Gaussian + seasonality | Cost-function based segmentation | Bayesian online posterior over run-length |
| Output | Yhat ± interval | Set of changepoints (offline, batch) | Per-timestep changepoint probability |
| Online? | No (batch refit) | No | Yes |
| Sparse Poisson counts? | Poor (Gaussian assumption) | OK with appropriate cost (Poisson) | Excellent (any likelihood) |
| Interpretability for analyst | "Anomalous because outside 95% interval" | "The series broke at month 14" | "78% probability of regime change in March" |
| Library | `prophet` | `ruptures` (MIT) | `bocd` (multiple impl.), `bayesian_changepoint_detection` |

**BOCPD wins on interpretability** because analysts respond to probabilities ("78% chance the rate changed") far better than residual-from-prediction-interval framings. BOCPD also handles low-count regimes natively when paired with a Poisson/Negative-Binomial likelihood — exactly our regime. PELT remains valuable for retrospective "find all the regime breaks in the last 24 months" narratives. Prophet should be demoted to: corpus-level seasonality decomposition only.

**Evidence:**
- Adams & MacKay, ["Bayesian Online Changepoint Detection"](https://arxiv.org/abs/0710.3742) (2007).
- 2024 generalization: ["Bayesian Autoregressive Online Change-Point Detection with Time-Varying Parameters"](https://arxiv.org/html/2407.16376v1).
- 2025 financial-time-series application: ["Bayesian Online Changepoint Detection for Financial Time Series"](https://dl.acm.org/doi/10.1145/3795154.3795291).
- PELT in `ruptures`: [paper](https://arxiv.org/abs/1801.00826), [docs](https://centre-borelli.github.io/ruptures-docs/user-guide/detection/pelt/), 2024 tutorial at PyConDE/PyData Berlin.
- Prophet limitations: Tyler Blume, ["Fixing Prophet's Forecasting Issue"](https://towardsdatascience.com/fixing-prophets-forecasting-issue-b473afe2cc70/); Hyndman, ["Forecasting: Principles and Practice (3e), §12.2 Prophet"](https://otexts.com/fpp3/prophet.html); ["Is Facebook's Prophet the Time-Series Messiah, or Just a Very Naughty Boy?"](https://medium.com/geekculture/is-facebooks-prophet-the-time-series-messiah-or-just-a-very-naughty-boy-8b71b136bc8c). Prophet anomaly mode silently swallows anomalies in the 95% interval ([github issue 1518](https://github.com/facebook/prophet/issues/1518)).
- Low-count anomaly detection: ["Low-count Time Series Anomaly Detection"](https://arxiv.org/abs/2308.12925); ["Poisson-FOCuS: An Efficient Online Method for Detecting Count Bursts"](https://www.tandfonline.com/doi/full/10.1080/01621459.2023.2235059) (JASA 2023).

**Implication for the POC:** BOCPD as primary changepoint engine (analyst-facing). PELT for retrospective views. Prophet for corpus-level volume seasonality only.

### SQ6: Seasonal decomposition with limited history?

**Answer:** With ~5,000 narratives over 2-3 years and 50-200 clusters, *per-cluster* seasonal decomposition is infeasible — you do not have ≥ 2 full annual cycles per cluster. Two practical strategies:

1. **Pool seasonality at the corpus or facet level**, not at the cluster level. Decompose total monthly incident volume (and per-facet volumes) with **STL** (statsmodels). STL is more robust than Prophet's seasonality at small samples and supports any periodicity.
2. **For per-cluster analysis, use rolling 3-month medians and YoY comparisons** rather than full STL. If a cluster has < 24 monthly observations, do not try to model seasonality at all; flag this in the UI.

For the December-card-fraud example in the brief: the cluster-level signal will be too noisy on its own, but the *facet*-level signal (e.g., facet = "Fraud / external") will have enough mass to expose the seasonal pattern, and the corpus-level STL trend gives the analyst the "is this December bigger than last December?" comparison directly.

**Evidence:**
- [statsmodels STL documentation](https://www.statsmodels.org/dev/examples/notebooks/generated/stl_decomposition.html) — recommended `s.window ≥ 7` (months) and `t.window=21` for monthly data; needs ≥ 2 full cycles.
- Hyndman, ["FPP3 §3.6 STL decomposition"](https://otexts.com/fpp3/stl.html).

**Implication for the POC:** STL on corpus and per-facet aggregate volumes (good signal). YoY-delta on per-cluster volumes (avoids the small-sample failure mode). Surface "insufficient history" warnings explicitly when a cluster has < 24 months.

## Approach Comparison

| Approach | Pros (max 3) | Cons (max 3) | Maturity (1-5) | Cost | Recommendation |
|---|---|---|---|---|---|
| **Prophet + z-score on cluster counts (current hypothesis)** | Familiar; quick to set up; built-in seasonality | Gaussian assumption wrong for sparse counts; documented to under/overfit trends; analyst-unfriendly framing ("outside 95% interval") | 5 | Low | ⚠️ DEMOTE to corpus-volume seasonality only |
| **BERTopic `topics_over_time`** | Easy; nice Plotly viz; stays inside BERTopic ecosystem | Cannot detect topic birth (clustering is frozen at fit); benchmarked 24 F1 below LDA on emergence; no signal/noise classification | 4 | Low | ⚠️ KEEP for visualization only |
| **Classical DTM (Blei-Lafferty 2006)** | Theoretically principled; handles smooth topic evolution | Slow; fixed K; no native topic birth/death; rarely used in industry post-2020 | 3 | Medium | ❌ SKIP |
| **BERTrend (re-fit + merge + popularity metric)** | Built specifically for emerging-trend detection; signal/noise/strong classification matches brief verbatim; open-source MPL-2.0 | Python ≥3.13 dependency; heavy if run frequently; topic merging threshold is hand-tuned | 3 | Medium-High | ✅ ADOPT (as the emergence-detection layer) |
| **BOCPD changepoint detection** | Probabilistic output is analyst-friendly; works with Poisson likelihood for sparse counts; online | Requires hazard rate prior; less familiar to engineers than Prophet | 4 | Medium | ✅ ADOPT (as primary changepoint engine) |
| **PELT (`ruptures`)** | Fast, well-documented, MIT license; supports custom Poisson cost | Offline only; analyst gets segments, not probabilities; harder to communicate uncertainty | 5 | Low | ✅ ADOPT (for retrospective regime analysis) |
| **Embedding drift detection (cosine shift / Evidently)** | Cheap monthly job; catches semantic drift other methods miss; production-grade tooling exists | Requires baseline window; can be noisy at small N | 4 | Low | ✅ ADOPT (for vocabulary + semantic drift) |
| **Kleinberg burst detection** | Hierarchical bursts; great for keyword-level emergence; tiny data requirements | Single time series at a time; no cluster-level semantics | 4 | Low | ✅ OPTIONAL (for keyword-level burst on top of cluster-level emergence) |
| **Poisson GLM + BH-FDR for monthly count anomalies** | Correct likelihood for sparse counts; FDR controls multi-cluster false-alarm rate; transparent stats | Requires careful covariate design (corpus volume offset); not "AI-shiny" | 5 | Low | ✅ ADOPT (replaces z-score) |

## Recommended Architecture

A **layered temporal stack** with each layer answering a different brief question:

```
Layer 0 — Corpus / facet volume seasonality
  Method: STL (statsmodels) on monthly aggregate counts
  Question: "What is the underlying seasonality? Is December always heavier?"

Layer 1 — Per-cluster growth-anomaly detection (the "is this signal or noise?" engine)
  Method: Poisson/Negative-Binomial GLM with corpus-volume offset
          → per-cluster monthly p-value
          → Benjamini-Hochberg FDR at q=0.10
  Question: "Which clusters are growing more than expected this month?"

Layer 2 — Per-cluster regime-change detection
  Method: BOCPD with Poisson likelihood (online, probabilistic)
          + PELT (ruptures) for retrospective batch view
  Question: "When did this cluster's rate change? With what probability?"

Layer 3 — Drift detection (vocabulary + semantic)
  Method (a): RBO / Jaccard on c-TF-IDF top-20 keywords (vocabulary drift)
  Method (b): centroid cosine shift + intra-cluster variance (semantic drift)
              Reuse Evidently's embedding drift module if practical
  Question: "Did this cluster's meaning change while keeping the same name?"

Layer 4 — Emergence detection (the "themes that didn't exist before" engine)
  Method: BERTrend pattern — monthly BERTopic re-fit + topic-merging by cosine
          + popularity metric (count × update-frequency × exp-decay)
          + 3-test gate: persistence, coherence, Poisson significance
  Optional: Kleinberg burst detection on keywords for sub-cluster bursts
  Question: "Which themes emerged in the last N months that didn't exist before?"

Layer 5 — Visualization
  Method: BERTopic.topics_over_time + Plotly for the analyst tab
  Purpose: exploration only, never the source of alerts
```

**Multiple-testing discipline** is the cross-cutting concern. Every layer that produces alerts (Layer 1, Layer 2, Layer 4) feeds a single alert pipeline that applies BH-FDR at q=0.10 monthly. Online ingestion uses LORD/SAFFRON if real-time alerting is added in v2.

**Integration with other plans:**
- **Depends on Plan 1 (topic modeling)** because topics are the unit of temporal analysis. BERTrend's re-fit cadence implies topics are *not* static between months — Plan 1 must accept that the analyst will see topic identity rebound across months unless the merge layer is reliable.
- **Constrains Plan 2 (faceting)** because seasonality decomposition is feasible at facet but not cluster level. Facets (e.g., "fraud", "system outage", "process failure") become the natural granularity for STL.
- **Feeds Plan 5 (conversational interface)** because each Layer's output is a structured fact ("cluster 17 has BOCPD changepoint probability 0.78 at 2026-03; BH-corrected Poisson p<0.05; popularity metric jumped from weak to strong signal") that the LLM can verbalize directly. The temporal layer is what makes the assistant capable of answering Section 1.4 questions truthfully rather than hallucinating from cluster snapshots.

## Architectural Decisions

### Hypotheses from the brief

- **D4 — UMAP + HDBSCAN: CONFIRM with caveat.**
  - Rationale: UMAP+HDBSCAN remains the right batch clustering choice for the v1 POC corpus size (5k narratives). The temporal complication is that HDBSCAN is offline and forces a full re-fit each month if we follow the BERTrend pattern. For 5k narratives this is fine (seconds). At >100k narratives, switch to FISHDBC (incremental HDBSCAN) or DenStream. **Document this scaling cliff explicitly so the team is not surprised.**

- **D5 — Prophet/z-score for temporal analysis: REPLACE.**
  - Rationale: This is the critical decision of this plan. Prophet/z-score is rejected for **three concrete reasons**: (a) Prophet is mis-specified for sparse cluster counts (Gaussian likelihood vs. Poisson reality) and has documented forecasting failures (Hyndman FPP3, Blume); (b) z-score on counts gives invalid p-values when counts are < ~10/month, which is our regime; (c) neither tool answers the brief's primary questions ("is this signal or noise?", "is this an emerging theme?") in a form an analyst can act on.
  - **REPLACEMENT (concrete):**
    - **Growth detection:** Poisson/Negative-Binomial GLM on monthly cluster counts with a corpus-volume offset. Output a p-value per cluster, then apply Benjamini-Hochberg FDR at q=0.10. This *is* the new "z-score" — same role, correct math, multi-cluster-safe.
    - **Changepoint detection:** BOCPD (primary, online, probabilistic) + PELT via `ruptures` (retrospective batch). This *is* the new "Prophet anomaly mode" — same role, interpretable, sparse-count-safe.
    - **Emergence detection:** BERTrend pattern (monthly BERTopic re-fit, topic merging by cosine threshold, popularity metric, signal/noise/strong classification with the 3-test gate). This is *new functionality* not present in the original hypothesis but explicitly required by Section 1.4.
    - **Seasonality:** STL (statsmodels) on corpus and facet-level aggregate volumes only — never per-cluster. Prophet kept only as an optional backup at this aggregate level.
    - **Drift:** RBO on c-TF-IDF top-20 (vocabulary) + centroid-cosine-shift (semantic). Optional integration with Evidently for production observability.

### ADRs affected

- **ADR-005 (proposed):** Replace Prophet/z-score with the layered temporal stack (Poisson GLM + BOCPD + BERTrend-style popularity metric + STL for aggregate seasonality).
- **ADR-006 (proposed):** Adopt Benjamini-Hochberg FDR correction (q=0.10) as the standard for any multi-cluster alerting layer; LORD/SAFFRON if v2 adds online alerting.
- **ADR-007 (proposed):** Use BERTopic `topics_over_time` for visualization only; rely on a recurring re-fit + topic-merging loop (BERTrend pattern) for emergence detection.

## Open Questions

1. **What is the actual incident volume per month and per cluster in the real corpus?** The Poisson regime assumption is critical. If average count per cluster per month is ≥ 30, simpler Gaussian methods become defensible. We should spike this with the real data before final commitment.
2. **Do we have ≥ 24 months of history for STL to be meaningful at facet level?** If not, Layer 0 (seasonality) starts as a placeholder and matures over time.
3. **What is the correct cadence?** Monthly is the default in this plan, but if narratives arrive in low daily volume, BOCPD on weekly bins may yield faster anomaly detection at the cost of more false alarms.
4. **Should we adopt BERTrend wholesale or re-implement its popularity metric?** BERTrend is MPL-2.0 and Python ≥3.13, which may conflict with the rest of the stack. A 200-line re-implementation of just the popularity metric + topic merging may be cleaner.
5. **Hazard-rate prior for BOCPD** — needs calibration on real data; default 1/250 is fine for daily, 1/12 for monthly, but should be tuned against ground-truth changepoints once the analyst labels a few historical examples.
6. **Embedding-drift integration with Evidently** — is the operational overhead worth it for 50-200 clusters, or is a custom 50-line cosine-shift job sufficient?

## References

### Papers
- Boutaleb, Picault, Grosjean (2024). *BERTrend: Neural Topic Modeling for Emerging Trends Detection.* ACL 2024 FuturED workshop. https://arxiv.org/abs/2411.05930 / https://aclanthology.org/2024.futured-1.1/
- Adams, MacKay (2007). *Bayesian Online Changepoint Detection.* https://arxiv.org/abs/0710.3742
- Truong, Oudre, Vayatis (2018). *ruptures: change point detection in Python.* https://arxiv.org/abs/1801.00826
- Kleinberg (2003). *Bursty and Hierarchical Structure in Streams.* DMKD. https://www.cs.cornell.edu/home/kleinber/bhs.pdf
- Benjamini, Hochberg (1995). *Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing.* JRSS-B.
- *Concept Drift Adaptation in Text Stream Mining Settings: A Systematic Review.* ACM TIST 2024. https://arxiv.org/html/2312.02901v2
- Feldhans, Wilke et al. *Drift Detection in Text Data with Document Embeddings.* https://link.springer.com/chapter/10.1007/978-3-030-91608-4_11
- *FDR Control for Online Anomaly Detection.* 2023. https://arxiv.org/abs/2312.01969
- *Low-count Time Series Anomaly Detection.* 2023. https://arxiv.org/abs/2308.12925
- *Poisson-FOCuS: An Efficient Online Method for Detecting Count Bursts.* JASA 2023. https://www.tandfonline.com/doi/full/10.1080/01621459.2023.2235059
- *Bayesian Autoregressive Online Change-Point Detection with Time-Varying Parameters.* 2024. https://arxiv.org/html/2407.16376v1
- *Evaluation of unsupervised static topic models' emergence detection ability* (LDA vs BERTopic on emergence). https://pmc.ncbi.nlm.nih.gov/articles/PMC12192802/
- *Experimental Evaluation of Dynamic Topic Modeling Algorithms.* 2025. https://arxiv.org/html/2508.00710v1
- *Online Density-Based Clustering for Real-Time Narrative Evolution Monitoring.* https://arxiv.org/html/2601.20680v1

### Repositories
- BERTrend (RTE France, MPL-2.0): https://github.com/rte-france/BERTrend
- BERTopic: https://github.com/MaartenGr/BERTopic
- ruptures (PELT et al., MIT): https://github.com/deepcharles/ruptures
- Kleinberg burst detection (Python): https://github.com/nmarinsek/burst_detection
- BOCPD reference impl.: https://github.com/dtolpin/bocd
- Facebook Prophet: https://github.com/facebook/prophet
- HDBSCAN: https://hdbscan.readthedocs.io/

### Blog Posts / Engineering Case Studies
- BERTopic dynamic topic modeling docs: https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html
- Hyndman, *Forecasting: Principles and Practice (3e)*, §12.2 on Prophet: https://otexts.com/fpp3/prophet.html
- Tyler Blume, *Fixing Prophet's Forecasting Issue*: https://towardsdatascience.com/fixing-prophets-forecasting-issue-b473afe2cc70/
- *Is Facebook's Prophet the Time-Series Messiah, or Just a Very Naughty Boy?* https://medium.com/geekculture/is-facebooks-prophet-the-time-series-messiah-or-just-a-very-naughty-boy-8b71b136bc8c
- *Forecasting at scale with Facebook Prophet — case study on merits & limitations:* https://towardsdatascience.com/forecasting-at-scale-with-facebook-prophet-a-case-study-on-its-merits-limitations-b24a694dd7c7/
- Gundersen, *Bayesian Online Changepoint Detection* tutorial: https://gregorygundersen.com/blog/2019/08/13/bocd/
- Marinsek, *Detecting bursts with Kleinberg's algorithm:* https://nikkimarinsek.com/blog/kleinberg-burst-detection-algorithm
- statsmodels STL example: https://www.statsmodels.org/dev/examples/notebooks/generated/stl_decomposition.html
- Genovese, *A Tutorial on False Discovery Control* (CMU): https://www.stat.cmu.edu/~genovese/talks/hannover1-04.pdf
- Evidently AI embedding drift module: https://learn.evidentlyai.com/ml-observability-course/module-3-ml-monitoring-for-unstructured-data/monitoring-embeddings-drift
- NannyML data drift docs: https://nannyml.readthedocs.io/en/v0.8.0/tutorials/detecting_data_drift.html
- Prophet GitHub issue documenting anomalies-swallowed-by-95%-interval problem: https://github.com/facebook/prophet/issues/1518

### Products / Vendors
- Evidently AI (open-source, embedding drift in production): https://www.evidentlyai.com/
- NannyML (open-source, post-deployment drift + perf est.): https://www.nannyml.com/
- BERTrend (RTE France, open-source under MPL-2.0): https://github.com/rte-france/BERTrend / https://pypi.org/project/bertrend/
