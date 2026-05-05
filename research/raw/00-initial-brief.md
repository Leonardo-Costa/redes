# Operational Risk Incident Intelligence — POC Brief

> Documento de especificação para implementação via Claude Code.
> Versão 1.0 — pronta para refinamento e codificação.

-----

## 0. TL;DR

Construir uma POC de **análise ad-hoc e topic modeling self-service sobre uma base de incidentes**, validando múltiplas abordagens antes de comprometer arquitetura. A POC deve demonstrar capabilities sobre uma base de incidentes:

1. **Classificação self-service** — usuário define ou ajusta categorias dinamicamente, sem depender de taxonomia engessada.
1. **Topic modeling ad-hoc** — descoberta de temas, recorrências, padrões e causas-raiz emergentes diretamente da base.
1. **Análise relacional** — busca semântica, causal, correlacional e por inter-relação entre incidentes.
1. **Detecção de tendências** — o que aumenta, o que diminui, o que surge, e separação de sinal vs ruído.
1. **Mapeamento regulatório** — alinhamento opcional com Basileia/4557 quando relevante.

**Dataset:** CFPB Consumer Complaint Database (real, serviços financeiros, narrativa + ground truth).

**Stack inicial (sujeita a revisão pós-pesquisa):** Python + Anthropic API/Bedrock (Sonnet/Opus) + pgvector + HDBSCAN + Streamlit + Graphify.

**Objetivo final:** validar arquitetura em dataset público, depois aplicar na base interna do BTG em PT-BR.

-----

## 1. Contexto e Motivação

### 1.1 Origem do problema

O time de dados de risco operacional do BTG (divisão de Seguros e Previdência) solicitou ajuda para classificar uma base histórica de **1000+ incidentes**. A motivação declarada é "BI" — saber o percentual de incidentes por categoria por mês.

### 1.2 Por que classificação pura é uma ideia fraca

- **Não tem caso de uso claro além de percentual.** "Quantos % são fraude" não informa decisão concreta — nem mitigação, nem KRI, nem investigação.
- **Locks-in taxonomia.** Quando aparecer a próxima pergunta ("quantos envolveram terceiros?", "quais afetaram PIX?"), você re-classifica tudo.
- **Não escala como capability.** Cada nova pergunta = novo trabalho manual.
- **Não cria valor para investigação de incidentes novos** — que é onde o time de risco realmente gasta tempo.

### 1.3 Reframe proposto

Em vez de uma classificação, construir uma **plataforma de inteligência sobre a base de incidentes** com três produtos coerentes:

| Capability | Pergunta que responde | Análogo de mercado |
|---|---|---|
| 1. Classificação regulatória | "Qual a distribuição por categoria Basileia/4557?" | Capgemini Invent — "Taxonomy Rationalization & Classification" |
| 2. Weak signal discovery | "Que padrões recorrentes aparecem que ninguém nomeou?" | Capgemini Invent — "Weak Signals Analysis" |
| 3. Investigação self-service | "Aconteceu algo parecido antes? Como foi resolvido?" | IncidentAI (Cinnamon, ACL) — "similar incident retrieval" |

### 1.4 Motivação central — análise ad-hoc e topic modeling self-service

O coração do que esta POC precisa validar não é "qual taxonomia usar". É como construir uma interface que permita ao analista de risco fazer **análises ad-hoc** sobre a base de incidentes sem depender de um modelo pré-treinado, de uma taxonomia rígida ou de um cientista de dados intermediando.

#### Exploração temática
- "Quais são os principais temas que aparecem nesta base?"
- "Existe um tema relacionado a `<conceito X>`? Quão prevalente é?"
- "Como esse tema se decompõe em sub-temas?"
- "Quais são os 10 motivos mais recorrentes de reclamação relacionada a `<produto Y>`?"

#### Análise causal e relacional
- "Quais causas raiz mais frequentemente coocorrem com `<produto Z>`?"
- "Esse padrão de incidente está correlacionado com algum sistema, processo ou período específico?"
- "Quando aparece `<sintoma A>`, qual a causa raiz mais provável historicamente?"
- "Quais incidentes estão semanticamente próximos deste, mas com causa raiz diferente?"

#### Análise temporal e de tendência
- "Que temas estão crescendo nos últimos 3/6/12 meses?"
- "Que temas estão diminuindo? Por quê?"
- "Que temas surgiram nos últimos N meses que não existiam antes?"
- "Esse pico no mês passado é sinal de algo novo ou ruído estatístico?"

#### Classificação self-service
- "Reclassifique a base usando estas 8 categorias que acabei de definir."
- "Crie sub-categorias dentro do cluster X seguindo este critério."
- "Quero refinar a classificação só para incidentes envolvendo terceiros."
- "Mostre os incidentes que ficaram entre duas categorias e me ajude a decidir."

#### Detecção de padrões e recorrências
- "Que padrões temporais (sazonalidade, picos, ciclos) aparecem na base?"
- "Esse mesmo problema está sendo reportado por múltiplos clientes/canais simultaneamente?"
- "Existe uma cadeia causal recorrente (incidente A → incidente B → incidente C)?"

#### Sinal vs ruído
- "Esse aumento aparente é estatisticamente significativo ou flutuação?"
- "Esse cluster pequeno representa um problema real emergente ou outliers não-relacionados?"
- "Qual a confiança de que essa correlação não é espúria?"

-----

## 2. Workflow de Pesquisa-Primeiro

Esta seção é o roteiro imediato. Antes de implementar, o Claude Code deve operar como **agente copiloto de pesquisa**, executando o workflow abaixo.

### 2.1 Por que pesquisa-primeiro

A motivação central (análise ad-hoc, topic modeling self-service) é um espaço de design rico e ativamente pesquisado. Existem muitas abordagens concorrentes — BERTopic, Top2Vec, contextualized topic models, Clio-style faceted summarization, GraphRAG, dynamic topic models, causal discovery, embedding-based exploration, agentes conversacionais.

### 2.3 Território de pesquisa

Os 5 planos devem cobrir:
- **Topic modeling moderno** — BERTopic, Top2Vec, contextualized topic models, hierarchical, dynamic topic models
- **LLM-driven topic induction** — Clio (Anthropic), faceted summarization, taxonomy induction com LLMs
- **Self-service classification** — few-shot, zero-shot, active learning, weak supervision, teacher-student loops
- **Análise causal e relacional em event data** — causal discovery, sequence mining, process mining
- **Análise temporal e detecção de novidade** — DTM, Prophet/changepoint, drift detection, novelty detection
- **Knowledge graphs e GraphRAG** — Microsoft GraphRAG, LightRAG, Graphiti, grafos temporais
- **Interfaces conversacionais** — text-to-SQL, RAG sobre dados estruturados, agentes com tools mistas
- **Práticas de mercado** — bancos, FAANG, consultorias (Capgemini, Deloitte, BCG GAMMA)

-----

## 3. Fundamentação Acadêmica e Regulatória

### 3.1 Framework regulatório

**Basileia II/III** define sete tipos canônicos de eventos de risco operacional:
1. Internal Fraud
2. External Fraud
3. Employment Practices and Workplace Safety
4. Clients, Products & Business Practices
5. Damage to Physical Assets
6. Business Disruption and System Failures
7. Execution, Delivery & Process Management

**Resolução 4557 do BCB** herda essa estrutura.

### 3.2 Literatura acadêmica relevante

- **Pakhchanyan et al. (2022)** — ML supervisionado para classificar eventos OpRisk em tipos Basileia
- **arXiv 2212.01285** — Text analysis for Operational Risk loss descriptions (SOA/CAS)
- **SemiORC (ACL 2020)** — Classificação semi-supervisionada interpretável de risco operacional
- **arXiv 2310.12074 (IncidentAI)** — NER + Cause-Effect extraction + Similar incident retrieval (manufatura)
- **arXiv 2301.05663** — NLP of Aviation Occurrence Reports for Safety Management
- **Anthropic Clio** — clusteriza summaries facetados, não documentos brutos

### 3.3 Referências de mercado

- **Capgemini Invent**: Taxonomy Rationalization & Classification Tool + Weak Signals Analysis Tool

-----

## 4. Por que clustering ingênuo (BERTopic) decepciona

1. **Boilerplate domina o embedding** — "usuário relatou", "ocorrência registrada" empurram tudo para mesma região
2. **Eixos de interesse são ortogonais** — causa raiz, sistema, processo, impacto são dimensões independentes
3. **Modelo genérico não captura semântica do domínio**

**As três correções:**
1. Pré-extração com LLM, depois clusteriza (Clio approach)
2. Cluster por faceta, não global
3. Indução de taxonomia via LLM

-----

## 5. Dataset

### 5.1 CFPB Consumer Complaint Database

- Reclamações reais sobre bancos, cartões, hipotecas, transferências
- Narrativa rica + classificação multi-nível já feita (Product → Sub-product → Issue → Sub-issue)
- ~4-5 GB, centenas de milhares de narrativas, 2011–presente
- HuggingFace: `CFPB/consumer-finance-complaints`

**Sample inicial:** 5.000 narrativas (narrativa não-nula, mínimo 100 caracteres, seed=42)

### 5.2 Datasets secundários

- UCI Incident Management Process Event Log — 24.918 incidentes ServiceNow
- Public postmortems — `github.com/danluu/post-mortems`

-----

## 6. Arquitetura Proposta (hipótese de trabalho)

### 6.1 Pipeline

```
CFPB Dataset → Stage 1: Structured Extraction (LLM) → Postgres (source of truth)
→ BI Drill-down | Cluster per facet (weak signal) | Vector Search | NL Q&A Agent
```

### 6.2 Schema Pydantic

Campos principais:
- `one_sentence_summary`, `root_cause_summary`, `customer_impact_summary` (campos embeddados)
- `basel_category` (BaselCategory enum)
- `product_domain` (ProductDomain enum)
- `root_cause_type` (RootCauseType enum)
- `financial_impact` (FinancialImpact enum)
- `detection_stage` (DetectionStage enum)
- Booleanos: `third_party_involved`, `automated_system_involved`, `customer_facing`, `regulatory_implication`, `suggests_recurring_pattern`
- `affected_systems: list[str]`, `keywords: list[str]`

### 6.3 Estratégia de embeddings

Embeddar 3 campos separados:
- `one_sentence_summary` → busca geral por similaridade
- `root_cause_summary` → cluster de causas raiz
- `customer_impact_summary` → cluster de impactos

Modelo: `BAAI/bge-large-en-v1.5` (inglês), `BAAI/bge-m3` ou `intfloat/multilingual-e5-large` (PT-BR)

### 6.4 Clustering por faceta

UMAP (n_components=15, n_neighbors=15) → HDBSCAN (min_cluster_size=15, min_samples=5) → Cluster naming via LLM

### 6.5 Detecção temporal de sinais fracos

Z-score / Prophet sobre contagem por cluster por mês → candidatos a KRI emergente

### 6.6 Self-service: busca por similaridade

`find_similar_incidents(query_text, facet, top_k, filters)` — embedding + pgvector cosine similarity

### 6.7 Self-service: Q&A em linguagem natural (stretch goal)

Agente com tools: `run_sql(query)` + `semantic_search(query, filters)`

-----

## 7. Plano de Implementação Faseado (hipótese)

- **Fase 0** — Setup (0.5 dia): repo, docker-compose, .env
- **Fase 1** — Ingestão e Extração (2-3 dias): CFPB ingestão, schema Pydantic, batch extraction
- **Fase 2** — Embeddings e Clustering (2 dias): pipeline embedding, pgvector, UMAP+HDBSCAN
- **Fase 3** — Busca e UI (2 dias): semantic search, Streamlit app
- **Fase 4** — Validação e Documentação (1 dia): métricas, custos, README

Total estimado: ~8-9 dias

-----

## 8. Stack Técnica

Python 3.11+, uv, ruff, pytest

Bibliotecas: anthropic, instructor, pydantic, datasets (HF), pandas, duckdb, psycopg[binary], pgvector, sentence-transformers, umap-learn, hdbscan, streamlit, plotly, tenacity, loguru, tqdm

Infra: `pgvector/pgvector:pg16` Docker

-----

## 9. Validação e Métricas

- Classificação: ≥85% top-1 em product_domain vs CFPB ground truth
- Clustering: ≥70% pontos não-ruído, coerência manual em 20 clusters
- Busca: precision@10 em 30 queries-âncora
- Custo: alvo abaixo de $100 (extração 5k com Sonnet ~$15-40)

-----

## 10. Migração para BTG (post-POC)

- Prompt de extração → PT-BR
- `ProductDomain` → domínios BTG (PIX, conta investimento, previdência, multimercado, crédito imobiliário)
- Embedding model → `bge-m3` ou `multilingual-e5-large`
- Anthropic API → Bedrock via proxy interno
- Aprovações: DPO, segurança da informação, compliance (anonimização PII)

-----

## 11. ADRs Documentadas

- **ADR 1**: Extração estruturada antes de clustering (boilerplate + eixos ortogonais)
- **ADR 2**: Múltiplas facetas em vez de label única
- **ADR 3**: CFPB em vez de dataset sintético (dado real, ground truth, domínio banco)
- **ADR 4**: pgvector em vez de Pinecone/Weaviate (POC local, stack BTG já tem Postgres)
- **ADR 5**: Sonnet (Haiku falha em nuance regulatória, Opus caro demais para 5k)
- **ADR 6**: Sem grafo na v1 (ROI baixo em 5k, evolução futura documentada)

-----

## 12. Referências

### Papers
- arXiv 2212.01285 — Text analysis for Operational Risk loss descriptions
- arXiv 2310.12074 — IncidentAI dataset (Cinnamon)
- arXiv 2301.05663 — NLP of Aviation Occurrence Reports
- arXiv 2407.06399 — Predictive Analysis of CFPB Consumer Complaints
- arXiv 2308.11138 — NLP-based detection of systematic anomalies in CFPB narratives
- ACL 2020 — SemiORC

### Regulatório
- BCBS 195 — Principles for Sound Management of Operational Risk
- Resolução 4557 — Banco Central do Brasil

### Datasets
- CFPB Consumer Complaint Database
- UCI ML Repository — Incident Management Process Event Log
- danluu/post-mortems

### Bibliotecas de referência
- Graphify, Graphiti, Microsoft GraphRAG, Instructor, BERTopic, Top2Vec, HDBSCAN, pgvector
