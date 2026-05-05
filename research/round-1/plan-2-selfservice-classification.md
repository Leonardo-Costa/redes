---
plan: 2
title: "Self-Service Classification: Runtime Taxonomy Definition and Refinement"
date: 2026-05-05
status: complete
decisions_addressed: [D1, D2, D3]
adr_changes: ["ADR-NEW: Hybrid LLM-zero-shot + SetFit for runtime taxonomies", "ADR-NEW: Argilla as HITL annotation surface", "ADR-REVIEW: D3 — embed faceted summaries AND keep raw narratives reachable for re-classification"]
---

# Plan 2 — Self-Service Classification: Runtime Taxonomy Definition and Refinement

## Executive Summary

- **Finding 1 — LLM zero-shot is "good enough" for the *first pass* of a user-defined taxonomy, but not for the production answer.** On Banking77 and similar fine-grained financial intent datasets, fine-tuned smaller models (BERT/MPNet/SetFit) still beat zero-shot GPT-4 by **10–25 F1 points** on fine-grained classes; GPT-4 only catches up with retrieval-augmented few-shot prompting. Zero-shot LLM accuracy is highly task-dependent (88% agreement on simple stance tasks, much lower on fine-grained taxonomies). For 5k narratives + 8 user-defined categories that change frequently, the zero-shot LLM is the *bootstrap*, not the destination.
- **Finding 2 — The right loop is "LLM-suggested labels → human validates a small confident-vs-borderline sample → SetFit head retrained in seconds."** This is a teacher-student pattern where the LLM is the teacher and a SetFit / sentence-transformer + logistic-regression head is the student. SetFit reaches GPT-3-comparable accuracy with **8–16 examples per class** and trains in seconds on CPU, which is exactly what "the user just defined 8 categories at runtime" requires.
- **Finding 3 — Classical active learning (uncertainty sampling, query-by-committee) is no longer dominant for LLM-era pipelines.** The 2025 ACL survey "From Selection to Generation" and Amazon's "Random Is Hard to Beat" both find that random + similarity-based sampling often matches or beats uncertainty sampling once a strong pre-trained prior is involved. The modern equivalent is **logprob-confidence-based routing**: auto-accept if logprob > 0.98, route to human if 0.60–0.98, abstain if < 0.60.
- **Finding 4 — Snorkel / weak supervision is overkill for v1** with 5k narratives and a frequently-changing taxonomy. Labeling functions need to be rewritten every time the taxonomy changes; the cost-per-iteration is too high vs. simply re-running the LLM. Keep Snorkel-style programmatic rules as an *optional* layer for stable categories with regulatory definitions (e.g., Basel ORX taxonomy buckets).
- **Finding 5 — Argilla 2.x (open-source, Apache-2.0, Hugging Face stewardship since June 2024) is the correct HITL surface.** Label Studio is broader but heavier; Prodigy is excellent but commercial and single-developer; Argilla integrates natively with sentence-transformers/SetFit and accepts LLM-generated suggestions out of the box. Self-hosting is straightforward and matches the regulated-bank constraint.

## Findings by Sub-Question

### SQ1: LLM zero-shot classifier accuracy vs traditional supervised methods?

**Answer**: For coarse, well-separated taxonomies, zero-shot GPT-4-class models are roughly competitive with — and sometimes better than — fine-tuned SVMs/RoBERTa. For fine-grained, financial, domain-specific taxonomies (the relevant case here), **fine-tuned smaller models still win by 10–25 F1 points**, and the gap *widens* as the number of classes grows.

**Evidence**: The arXiv 2024 study "Fine-Tuned 'Small' LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification" (arxiv.org/abs/2406.08660) demonstrates the gap consistently across multiple text classification datasets. On the Banking77 fine-grained intent dataset, the 2023 "Breaking the Bank with ChatGPT" paper (arxiv.org/abs/2308.14634) and the 2023 ACM AI-in-Finance paper "Making LLMs Worth Every Penny" (dl.acm.org/doi/10.1145/3604237.3626891) both report that fine-tuned MPNet outperforms zero-shot LLMs by ~10–25 points; GPT-4 only matches the fine-tuned baseline once retrieval-augmented few-shot prompting is added (per the 2024 ASRJETS retrieval-augmented prompting study). Conversely, Sage's 2025 paper "Large Language Models for Text Classification: From Zero-Shot Learning to Instruction-Tuning" (journals.sagepub.com/doi/10.1177/00491241251325243) and the PMC breast cancer pathology comparison (pmc.ncbi.nlm.nih.gov/articles/PMC10889046/) show GPT-4 zero-shot beating SVMs in 5/6 health-text tasks — so the answer depends heavily on whether the task is coarse-semantic or fine-grained-taxonomic.

A nuanced 2025 SLM-ensemble paper (sciencedirect.com/article/abs/pii/S1566253525007389) and Refuel's RefuelLLM-2 benchmark (refuel.ai) further show that **ensembles of zero-shot small models** can equal GPT-4-Turbo at a fraction of the cost on labeling-style tasks (RefuelLLM-2 83.8% vs GPT-4-Turbo 80.9% on a 30-task labeling benchmark).

**Implication for the POC**: Treat the LLM-zero-shot classifier as the *bootstrap layer*: when a user defines 8 categories at runtime, the LLM produces an immediate first-pass labeling of all 5k narratives in minutes. Critically, never publish those labels as "the answer" — they are *suggestions*. The system must explicitly carry confidence (logprobs) and route the bottom-confidence tail to human review. Once the user has validated ~16–32 examples per category, **train a SetFit head in seconds** to produce the production classifier. Re-running this loop when the taxonomy changes is cheap.

### SQ2: Is active learning still competitive vs LLM few-shot in 2025?

**Answer**: Classical uncertainty-sampling active learning is **largely obsolete** as the primary paradigm in LLM pipelines. It is being replaced by (a) similarity/diversity-based sampling, (b) logprob-confidence routing, and (c) "LLM-as-active-learning-guide" patterns. Random sampling is a surprisingly strong baseline.

**Evidence**: The 2025 ACL survey "From Selection to Generation: A Survey of LLM-based Active Learning" (aclanthology.org/2025.acl-long.708/, arxiv.org/abs/2502.11767) explicitly frames the shift: AL has moved from *selection* of unlabeled instances to *generation* by LLMs of new training instances and labels. The 2024 TACL paper "ActiveLLM" (direct.mit.edu/tacl/article/doi/10.1162/TACL.a.63/134746) shows that using GPT-4 to *guide* active selection beats traditional uncertainty sampling for BERT few-shot fine-tuning. The 2026 paper "Random Is Hard to Beat: Active Selection in online DPO with Modern LLMs" (arxiv.org/html/2604.02766v1) is even blunter: with strong pre-trained priors, uncertainty-based active selection provides little consistent advantage over a random baseline. CoverICL (cited in the same survey) and similar approaches integrate uncertainty sampling with semantic coverage rather than using uncertainty alone.

**Implication for the POC**: Don't build a query-by-committee or BALD-style AL loop. Instead implement a **logprob-confidence stratified sampling**: when the user wants to "review what the system is unsure about," surface incidents whose top-1 vs top-2 class margin is small (entropy-based), and pair them with a few diverse high-confidence exemplars per class for context. This gives the user the same value as classical AL with one tenth the engineering and matches the borderline-cases UX requirement (SQ4).

### SQ3: Is Snorkel/weak supervision viable for frequently-changing taxonomies?

**Answer**: Not as the primary mechanism for v1. Weak supervision shines when (i) labeling functions are stable for months, (ii) the dataset is much larger than 5k, and (iii) heuristic rules from SMEs can be expressed compactly. None of those hold for the operational-risk POC where the analyst literally invents categories on the fly.

**Evidence**: The original Snorkel paper (arxiv.org/abs/1711.10160) and its VLDB Journal extension describe a workflow where analysts write Python labeling functions; the system then learns a generative label model. Snorkel AI's modern Snorkel Flow (snorkel.ai/data-centric-ai/weak-supervision/, docs.snorkel.ai/docs/25.4/user-guide/intro/active-learning-weak-supervision/) explicitly *combines* programmatic labeling with active learning for enterprise customers like BNY Mellon and Chubb — but its sweet spot is stable, regulator-defined taxonomies (e.g., Basel ORX event categories), where labeling functions amortize over months. Snorkel's own 2024 "LLM distillation demystified" guide (snorkel.ai/blog/llm-distillation-demystified-a-complete-guide/) describes a workflow where LLMs *generate* the initial labels and labeling functions encode rules — effectively conceding that for ad-hoc taxonomies, the LLM is the better bootstrap.

For the bank, the cost of rewriting labeling functions every time the analyst redefines a category is prohibitive. The teacher-LLM-then-SetFit pattern (SQ6) achieves the same outcome — programmatic-scale labeling — at lower marginal cost.

**Implication for the POC**: Defer Snorkel-style weak supervision to a **future stable-taxonomy module** (e.g., for mandatory regulatory ORX/Basel reporting). For self-service, do not include weak supervision in v1. If the bank later identifies stable categories that have hard rules (e.g., "any incident mentioning SWIFT and >USD 1M is a payment failure"), expose a simple "rule" UI that adds Python predicates as additional labeling sources, but this is v2+.

### SQ4: How to implement interpretable decision boundary ("show borderline incidents")?

**Answer**: Three complementary techniques, all cheap, all interpretable:
1. **Logprob margin** (top-1 minus top-2 probability) as the primary "borderline" score — surface incidents whose margin is below a threshold (e.g., 0.15).
2. **Embedding-space proximity** — for each category, compute the centroid of validated examples in the sentence-transformer space; show incidents that sit between two centroids (i.e., where cosine distance to the two nearest centroids is similar).
3. **LLM-generated rationale** — when surfacing a borderline case, ask the LLM for a *short rationale per candidate class*. The user reads two competing one-sentence justifications side by side. This is dramatically more useful than LIME/SHAP on embeddings, which produce token-level attributions that domain users cannot read.

**Evidence**: On logprobs, OpenAI's cookbook "Using logprobs" (cookbook.openai.com/examples/using_logprobs), Eric Jinks' practical guide (ericjinks.com/blog/2025/logprobs/), and Amazon Science's "Label with Confidence" paper (assets.amazon.science/9f/8f/5573088f450d840e7b4d4a9ffe3e/label-with-confidence-effective-confidence-calibration-and-ensembles-in-llm-powered-classification.pdf) consistently report that token-level logprobs are the most reliable confidence signal for LLM classification, while *self-reported* "I am 85% confident" verbal scores are unreliable. Refuel's "Improving data quality with confidence" blog (refuel.ai/blog-posts/labeling-with-confidence) operationalises this: route low-confidence labels to humans, auto-accept above a calibrated threshold.

On embedding-space prototypes, the 2024 paper "Embracing Diversity: Interpretable Zero-shot classification beyond one vector per class" (arxiv.org/html/2404.16717v1, dl.acm.org/doi/fullHtml/10.1145/3630106.3659039) shows that representing each class with multiple sub-prototypes and computing per-class similarity produces interpretable, audit-able boundaries. The OpenAI Cookbook entry "Zero-shot classification with embeddings" (cookbook.openai.com/examples/zero-shot_classification_with_embeddings) documents the basic prototype-cosine-similarity approach.

LIME/SHAP on text embeddings is technically possible (kdnuggets.com/2019/12/interpretability-part-3-lime-shap.html, christophm.github.io/interpretable-ml-book/shap.html) but produces feature attributions over individual tokens, which is poor UX for risk analysts who think in narrative semantics. Skip LIME/SHAP for v1.

**Implication for the POC**: Build a "between two categories" view that shows each borderline incident with: (a) margin score, (b) two nearest class centroids in embedding space, (c) two LLM-generated one-sentence rationales explaining why it could fit either class. Let the analyst click to assign — this validation feeds straight into the SetFit retrain loop.

### SQ5: Best UX pattern for human-in-the-loop classification (Argilla vs Prodigy vs Label Studio)?

**Answer**: **Argilla 2.x** is the right choice for this POC. It is open-source (Apache-2.0), self-hostable (which matters for a regulated bank's data residency), maintained by Hugging Face since June 2024, integrates natively with sentence-transformers/SetFit, and has first-class support for LLM-suggested labels that the human only validates/corrects rather than annotating from scratch.

**Evidence**: John Snow Labs' 2024 "Top 6 Annotation Tools for HITL LLMs" (johnsnowlabs.com/top-6-annotation-tools-for-hitl-llms-evaluation-and-domain-specific-ai-model-training/) and the 2024 "Comparing Open Source Data Annotation Tools" piece (ai.gopubby.com/comparing-open-source-data-annotation-tools-customised-model-and-llm-api-integration-for-e59a51efe056) compare the three tools head-to-head. Argilla's strengths: native preference/instruction dataset support, push-to-Hub integration, sort-by-prediction-score, custom HTML/CSS/JS fields. Argilla 2.0 (huggingface.co/blog/dvilasuero/argilla-2-0) and 2.4 (huggingface.co/blog/argilla-ui-hub) added no-code dataset creation and automatic task distribution. The "LLM suggestions in Argilla" guide (huggingface.co/blog/alvarobartt/argilla-suggestions-via-inference-endpoints, argilla.io/blog/argilla-suggestions-with-inference-endpoints/) shows the pattern: LLM produces suggestions, humans validate — turning annotation into a fast review/correction task.

Label Studio is broader (vision + audio + text, label studio also offers LLM eval features at labelstud.io/blog/how-to-evaluate-and-compare-llms-using-prompts-in-label-studio/) but heavier and less NLP-LLM-native. Prodigy from Explosion (the spaCy team) has the best classical-AL UX with a one-time $490/dev license, but is single-user/local-machine and not SaaS or enterprise-shared, making it a poor fit for a multi-analyst risk team.

**Implication for the POC**: Self-host Argilla on the bank's internal infrastructure (Docker; supports Postgres backend). Wire it so that:
- The Streamlit UI calls a "create classification task" endpoint that pushes the corpus + LLM suggestions into an Argilla dataset.
- Risk analysts review/correct in Argilla's UI.
- A nightly job (or on-demand) pulls validated labels back, retrains the SetFit head, and updates pgvector with new class predictions.

### SQ6: Self-labeling / teacher-student approaches for annotation scaling?

**Answer**: Yes — the **LLM-teacher → SetFit-student** pattern is the recommended core of self-service classification. The LLM acts as a high-recall but expensive teacher; a SetFit head distilled from validated LLM outputs becomes the cheap, fast, locally-hosted production classifier. This is the one approach in this plan that solves cost, latency, and "frequently-changing taxonomy" simultaneously.

**Evidence**: The 2024 arXiv survey "A Survey on Knowledge Distillation of Large Language Models" (arxiv.org/html/2402.13116v3) and Snorkel's 2024 "LLM distillation demystified" guide (snorkel.ai/blog/llm-distillation-demystified-a-complete-guide/) both describe the "LLM labels unlabeled data → student model trains on synthetic labels" workflow as the dominant 2024 distillation paradigm for classification. The 2024 paper "Learning with Less: Knowledge Distillation from Large Language Models via Unlabeled Data" (arxiv.org/html/2411.08028) formalises the data-efficient version.

For the student model itself, SetFit (huggingface.co/blog/setfit, github.com/huggingface/setfit, arxiv.org/abs/2209.11055) is uniquely well-suited: with **8–16 labeled examples per class**, contrastive fine-tuning of a sentence transformer plus a logistic-regression head, SetFit reaches accuracy comparable to fine-tuning RoBERTa-Large on the full ~3k training set on benchmarks like CR sentiment. Training takes seconds on CPU.

Refuel AI's autolabel library (github.com/refuel-ai/autolabel) and their 2024 technical report (refuel.ai/blog-posts/llm-labeling-technical-report) operationalise the pattern: LLMs label datasets at human-level quality, ~20× faster, ~7× cheaper, with calibrated confidence scores so that low-confidence labels are routed to humans. Their RefuelLLM-2 (83.8%) outperforms GPT-4-Turbo (80.9%) on labeling tasks.

**Implication for the POC**: This is the spine of the architecture. Concretely:
1. User defines categories in natural language (Streamlit form).
2. LLM (Claude/GPT-4) labels all 5k narratives in batch with logprobs → ~minutes.
3. System surfaces (a) high-confidence sample for spot-validation, (b) low-confidence/borderline sample for required validation, in Argilla.
4. After ≥8 validated examples per class, train SetFit head on validated labels. Use SetFit predictions as production answer; keep LLM logits as a secondary signal.
5. Track agreement between LLM-teacher and SetFit-student; significant divergence on a category is itself a useful "this category may be ill-defined" signal.

## Approach Comparison

| Approach | Pros (max 3) | Cons (max 3) | Maturity (1-5) | Cost | Recommendation |
|----------|--------------|---------------|----------------|------|----------------|
| LLM zero-shot classifier (only) | Instant; no training data; arbitrary natural-language categories | 10–25 F1 below fine-tuned on fine-grained finance taxonomies; expensive at 5k×N reclassifications; calibration weak | 5 | $$ per re-class | Yes for **bootstrap**, no as final answer |
| LLM few-shot (examples in prompt) | Big jump over zero-shot with retrieval-augmented examples; still no training | Long prompts → cost/latency; context-window bound; still calibration-weak | 5 | $$$ per call | Use as fallback when SetFit unsure |
| Active learning loop (uncertainty sampling) | Proven; principled | Beaten by random + similarity in LLM era; engineering heavy; UX-unfriendly | 4 | $ engineering | No — superseded by logprob-confidence routing |
| Snorkel / weak supervision | Scales; encodes SME rules; good for stable taxonomies | LF rewrite cost when taxonomy changes; overkill at 5k; long ramp | 5 | $$$ engineering | No for v1; revisit for stable Basel/ORX modules |
| Teacher-student (LLM → SetFit) | Cheap inference once distilled; 8–16 examples/class; CPU retrain in seconds | Needs ≥8 validated examples per class; SetFit ceiling below SOTA fine-tune | 4 | $ training, $ inference | YES — core production loop |
| LLM-as-active-learning-guide | Beats classical AL in TACL 2024; minimal infra | Adds an LLM call to selection step | 3 | $ | Use as the borderline-sample selector |
| Embedding-prototype + cosine | Fully interpretable, fast, no LLM dep | Plateaus quickly; not great on subtle distinctions | 4 | $ | Use as a **cheap second opinion** alongside SetFit |

## Recommended Architecture

A three-stage runtime loop, triggered any time the analyst (re)defines categories:

```
USER ACTION                       SYSTEM RESPONSE                        TIME
───────────────────────────────   ───────────────────────────────────   ─────
1. Define 8 categories            LLM zero-shot labels all 5k           ~5 min
   (natural language + optional   narratives with logprobs.
   one-sentence definition)       Per-incident: top-1 class,
                                  margin to top-2, brief rationale.
                                  Stored in pgvector + Argilla.

2. Review in Argilla              UI shows: (a) ~5 high-conf            ~15 min
   (validate / correct)           samples/class for spot check,         per round
                                  (b) all margin<0.15 borderline cases
                                  with side-by-side rationales.
                                  Analyst confirms or reassigns.

3. System trains SetFit head      As soon as ≥8 validated examples      ~30 sec
   on validated labels            per class exist, train SetFit on      training
                                  sentence-transformer embeddings of    + ~10s
                                  the faceted summaries.                inference

4. Production classification      SetFit becomes primary classifier.    Real-time
                                  LLM kept as second opinion on
                                  SetFit low-margin cases.
                                  Disagreement (LLM≠SetFit) flagged
                                  as "fragile category" signal.

5. Iterate (refine subcategories  Repeat with subset filtered by        Same
   within cluster X)              parent category. Same loop.           timing
```

**Embedding choice for SetFit / prototypes:** reuse the existing `one_sentence_summary` facet (D3) — it is already the most compact, classification-friendly representation. The `root_cause_summary` and `customer_impact_summary` facets remain available as separate views for the user to *also* classify by, which is exactly the "reclassify the corpus by root cause vs by impact" question the brief envisages.

**Borderline view ("incidents that fell between two categories"):** for each pair of classes (A, B), surface all incidents whose top-2 SetFit probabilities are A and B with margin < 0.15. Show LLM rationale per class. Analyst clicks to assign or to *split* category B into B1/B2.

**Integration with other plans:**
- Depends on **Plan 1 (topic modeling/clustering)** because: when the user has no taxonomy yet, HDBSCAN clusters of `one_sentence_summary` embeddings serve as the *suggested* starting categories. The user names the clusters; those names become the runtime taxonomy this plan classifies into. Without that scaffolding, "define 8 categories" is a blank-page problem.
- Feeds into **Plan 5 (conversational interface)** because: the conversational layer must expose this whole loop in natural language. ("Reclassify by these 8 categories" → trigger stage 1; "show me what fell between Fraud and Operational Error" → stage 4 borderline view; "which categories does the model find fragile?" → SetFit-vs-LLM disagreement signal).
- Feeds into **Plan 3 (temporal trends)** because: a stable, validated SetFit classifier produces the per-incident category tags that the temporal/Prophet analysis uses as group-by keys. Trends are only meaningful once classification is stable.
- Feeds into **Plan 4 (causal/relational queries)** because: "when symptom A appears, what's the root cause" requires consistent class labels on the symptom and root_cause facets — provided by this loop.

## Architectural Decisions

### Hypotheses from the brief

- **D1 — LLM pre-extraction before clustering**: **CONFIRM**.
  - Rationale: For self-service classification, pre-extracted faceted summaries are dramatically easier for the LLM to classify than raw narratives. Shorter inputs → cheaper logprob extraction, more stable classification, better SetFit features. This plan's recommended architecture *requires* the LLM-extracted summaries; if you only had raw narratives, the zero-shot bootstrap and the SetFit student would both degrade.

- **D2 — Cluster per facet**: **CONFIRM**, with a refinement.
  - Rationale: Different facets answer different classification questions. Classifying by `root_cause_summary` produces a "root cause taxonomy"; classifying by `customer_impact_summary` produces an impact taxonomy; these are intentionally different views the analyst can switch between. Plan 2 inherits this: each runtime taxonomy operates on *one* facet at a time. Refinement: also allow the user to compose taxonomies across facets (e.g., "categories defined by root_cause but reported by impact-severity bucket") — this is a 2D classification view.

- **D3 — Summaries as embedding unit**: **CONFIRM**, with one important caveat.
  - Rationale: Summaries are the right embedding unit for clustering and SetFit. **Caveat**: the system MUST keep raw narratives reachable. When SetFit/LLM disagree on a borderline case, the analyst will want to read the original narrative to adjudicate. Argilla must be configured to display both the summary (for the classification decision) and a "show full narrative" affordance.

### ADRs affected

- **NEW ADR — Hybrid zero-shot LLM (bootstrap) + SetFit (production) for runtime taxonomies.** Replaces any implicit assumption that a single classifier serves all stages. The LLM is the teacher; SetFit is the student; both run, and disagreement is a feature.
- **NEW ADR — Argilla 2.x (self-hosted, Apache-2.0) as the sole HITL annotation surface.** Rejects Label Studio (too generic, heavier) and Prodigy (single-developer, commercial) for v1. Re-evaluate at scale > 50 analysts.
- **NEW ADR — No Snorkel / weak supervision in v1.** Defer to a future stable-taxonomy module (e.g., regulatory ORX/Basel mapping).
- **NEW ADR — Logprob-margin routing replaces classical active learning.** Borderline = top-1 vs top-2 margin < 0.15. No BALD, no query-by-committee.
- **REVIEW ADR for D3** — explicit requirement that raw narratives remain reachable from the classification UI even though embedding/clustering is on summaries.

## Open Questions

1. **Calibration**: how badly miscalibrated are GPT-4-class logprobs on financial-incident text specifically? Need an empirical calibration step (Platt scaling or isotonic regression on a 200-incident validation set) before trusting the 0.15 margin threshold. Plan to measure on round-2.
2. **Multi-label vs single-label**: the brief implies single-label ("8 categories"), but real incidents often have multiple causes. Should SetFit be multi-label by default, with the user opting into single-label? Recommend multi-label with a minimum-probability threshold; needs UX decision.
3. **Drift**: when new incident types appear (e.g., a new fraud pattern), the SetFit classifier may quietly route them to the closest existing category without flagging. Need an OOD-detection mechanism (e.g., max-cosine to any class centroid below a threshold ⇒ "novel / unmapped"). Open whether to implement in v1 or v2.
4. **Audit trail for regulators**: every reclassification changes per-incident labels. Need an immutable audit log of (timestamp, user, taxonomy version, incident-id, old label, new label, rationale). Argilla logs annotations but not the system-level reclassifications; will need additional pgvector-side audit table.
5. **LLM-vs-SetFit blending**: when they disagree, do we trust SetFit (validated by humans) or LLM (more recent semantic understanding)? Recommend: SetFit wins when training set ≥ 16/class; LLM wins below; surface disagreement either way.
6. **Cost ceiling for LLM bootstrap**: at 5k narratives × ~500 tokens × N taxonomy iterations × $X per million tokens, what is the monthly LLM bill? Need a cost model and an internal cache (re-use prior labelings when possible).

## References

### Papers

- Bucher & Martini (2024). *Fine-Tuned 'Small' LLMs (Still) Significantly Outperform Zero-Shot Generative AI Models in Text Classification*. arXiv. https://arxiv.org/abs/2406.08660 / https://arxiv.org/html/2406.08660v1
- Loukas et al. (2023). *Breaking the Bank with ChatGPT: Few-Shot Text Classification for Finance*. arXiv. https://arxiv.org/abs/2308.14634 / https://arxiv.org/pdf/2308.14634
- Loukas et al. (2023). *Making LLMs Worth Every Penny: Resource-Limited Text Classification in Banking*. ACM AI in Finance. https://dl.acm.org/doi/10.1145/3604237.3626891 / https://arxiv.org/pdf/2311.06102
- Chae & Davidson (2025). *Large Language Models for Text Classification: From Zero-Shot Learning to Instruction-Tuning*. Sociological Methods & Research. https://journals.sagepub.com/doi/10.1177/00491241251325243
- Xia et al. (2025). *From Selection to Generation: A Survey of LLM-based Active Learning*. ACL 2025. https://aclanthology.org/2025.acl-long.708/ / https://arxiv.org/abs/2502.11767
- Bayer et al. (2024). *ActiveLLM: Large Language Model-based Active Learning for Textual Few-Shot Scenarios*. TACL. https://direct.mit.edu/tacl/article/doi/10.1162/TACL.a.63/134746/ActiveLLM-Large-Language-Model-Based-Active / https://arxiv.org/html/2405.10808v1
- *Random Is Hard to Beat: Active Selection in online DPO with Modern LLMs* (2026). arXiv. https://arxiv.org/html/2604.02766v1
- Tunstall et al. (2022). *SetFit: Efficient Few-Shot Learning Without Prompts*. arXiv. https://arxiv.org/abs/2209.11055
- Ratner et al. (2017/2019). *Snorkel: Rapid Training Data Creation with Weak Supervision*. arXiv / VLDB Journal. https://arxiv.org/abs/1711.10160 / https://link.springer.com/article/10.1007/s00778-019-00552-1
- *Survey on Knowledge Distillation of Large Language Models* (2024). arXiv. https://arxiv.org/html/2402.13116v3
- Hsieh et al. (2024). *Learning with Less: Knowledge Distillation from Large Language Models via Unlabeled Data*. arXiv. https://arxiv.org/html/2411.08028
- *Embracing Diversity: Interpretable Zero-shot classification beyond one vector per class* (2024). https://arxiv.org/html/2404.16717v1 / https://dl.acm.org/doi/fullHtml/10.1145/3630106.3659039
- Törnberg (2024). *GPT-4 as an X data annotator: Unraveling its performance on a stance classification task*. PLOS One. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0307741
- Amazon Science. *Label with Confidence: Effective Confidence Calibration and Ensembles in LLM-Powered Classification*. https://assets.amazon.science/9f/8f/5573088f450d840e7b4d4a9ffe3e/label-with-confidence-effective-confidence-calibration-and-ensembles-in-llm-powered-classification.pdf
- *A comparative study of zero-shot inference with large language models and supervised modeling in breast cancer pathology classification*. PMC. https://pmc.ncbi.nlm.nih.gov/articles/PMC10889046/

### Repositories

- huggingface/setfit — https://github.com/huggingface/setfit
- argilla-io/argilla — https://github.com/argilla-io/argilla
- snorkel-team/snorkel — https://github.com/snorkel-team/snorkel
- refuel-ai/autolabel — https://github.com/refuel-ai/autolabel

### Blog Posts / Engineering Case Studies

- HuggingFace SetFit announcement — https://huggingface.co/blog/setfit
- Argilla 2.0 launch — https://huggingface.co/blog/dvilasuero/argilla-2-0
- Argilla 2.4 (no-code dataset creation) — https://huggingface.co/blog/argilla-ui-hub
- LLM suggestions in Argilla via HF Inference Endpoints — https://huggingface.co/blog/alvarobartt/argilla-suggestions-via-inference-endpoints / https://argilla.io/blog/argilla-suggestions-with-inference-endpoints/
- Argilla joins Hugging Face — https://argilla.io/blog/argilla-joins-hugggingface/
- Refuel — Improving data quality with confidence — https://www.refuel.ai/blog-posts/labeling-with-confidence
- Refuel — LLM labeling technical report — https://www.refuel.ai/blog-posts/llm-labeling-technical-report
- Snorkel — LLM distillation demystified — https://snorkel.ai/blog/llm-distillation-demystified-a-complete-guide/
- Snorkel — Active learning + weak supervision integration — https://docs.snorkel.ai/docs/25.4/user-guide/intro/active-learning-weak-supervision/
- Hamel Husain — Your AI Product Needs Evals — https://hamel.dev/blog/posts/evals/
- Hamel Husain — LLM-as-a-Judge — https://hamel.dev/blog/posts/llm-judge/
- OpenAI Cookbook — Using logprobs — https://cookbook.openai.com/examples/using_logprobs
- OpenAI Cookbook — Zero-shot classification with embeddings — https://cookbook.openai.com/examples/zero-shot_classification_with_embeddings
- Eric Jinks — Estimating LLM classification confidence with logprobs — https://ericjinks.com/blog/2025/logprobs/
- John Snow Labs — Top 6 Annotation Tools for HITL LLMs — https://www.johnsnowlabs.com/top-6-annotation-tools-for-hitl-llms-evaluation-and-domain-specific-ai-model-training/
- Comparing Open Source Data Annotation Tools (2024) — https://ai.gopubby.com/comparing-open-source-data-annotation-tools-customised-model-and-llm-api-integration-for-e59a51efe056
- Label Studio — LLM Evaluation and Comparison — https://labelstud.io/blog/how-to-evaluate-and-compare-llms-using-prompts-in-label-studio/

### Products / Vendors

- Argilla (Apache-2.0, HuggingFace) — https://docs.argilla.io/ — recommended HITL surface
- Snorkel Flow (commercial, enterprise) — https://snorkel.ai/ — defer to v2 stable-taxonomy module
- Prodigy (Explosion, $490/dev) — https://prodi.gy/ — rejected for multi-analyst use
- Label Studio (HumanSignal) — https://labelstud.io/ — rejected as broader-than-needed
- Refuel (commercial autolabeling) — https://www.refuel.ai/ — useful reference for LLM-labeling-with-confidence patterns; not a buy recommendation for v1
