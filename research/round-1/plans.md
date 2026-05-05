# Round 1 — 5 Planos de Pesquisa
Date: 2026-05-05
Status: AGUARDANDO APROVAÇÃO DO USUÁRIO

---

## Plano 1 — Topic Modeling Moderno: Qual Abordagem Vence em Corpus de Incidentes?

**Tese / pergunta central:**
Dado o diagnóstico de que BERTopic ingênuo falha em corpus de incidentes (boilerplate, eixos
ortogonais, semântica de domínio fraca), quais abordagens de topic modeling recentes superam
essa baseline, e sob quais condições? A hipótese a validar é se o pipeline "pré-extração LLM
→ embedding de summary → HDBSCAN" da Seção 6 é de fato superior a métodos end-to-end mais
recentes como Top2Vec, BERTopic com backbone fine-tuned, Neural Topic Models (NTMs) como
ProdLDA/ETM, ou a abordagem Clio de faceted summarization.

**Sub-perguntas:**
1. Quais são os benchmarks de qualidade (coerência, diversidade, NPMI) para topic modeling em
   corpus de domínio financeiro/legal? Existe benchmark público em inglês?
2. BERTopic com backbone fine-tuned (FinBERT, sector-specific) supera bge-large-en genérico?
   Em quanto?
3. Top2Vec (word2vec joint com doc2vec) tem vantagens sobre BERTopic+HDBSCAN para descoberta
   de tópicos emergentes sem supervisão?
4. Hierarchical topic models (hBERTopic, TreeOfTopics) suportam o caso de uso
   "decompor cluster X em sub-temas" da Seção 1.4?
5. Clio-style approach (LLM summarize → embed summary → cluster) tem custo/benefício
   documentado para corpus de ~5k textos curtos? Qual o ganho real vs embed direto?
6. Qual método melhor suporta "descoberta de tópicos novos" (novelty detection em tópicos),
   não apenas classificação em tópicos existentes?

**Tipos de fontes:**
- Papers: BERTopic original + citantes recentes (2023-2026), Top2Vec, ETM, ProdLDA, hBERTopic,
  Clio (Anthropic 2024), papers NTM em EMNLP/NAACL/ACL
- Repos: maartengr/BERTopic, ddangelov/Top2Vec, MIND-Lab/contextualized-topic-models
- Benchmarks: OCTIS, CLEF e-Risk, datasets financeiros em HuggingFace
- Blogs: Maarten Grootendorst (BERTopic), posts Anthropic Research

**Output esperado:**
Tabela comparativa: método × coerência × descoberta emergente × suporte hierárquico ×
latência × custo de adaptação ao domínio. Recomendação clara sobre qual(is) usar no pipeline
da POC e por quê.

**Dependências e adjacências:**
- Não cobre: self-service classification (Plano 2), análise causal (Plano 3)
- Adjacência crítica com Plano 2 (os métodos aqui são a base da classificação self-service)
- Resultado alimenta decisão D4 e D3 nas notas de leitura do brief

---

## Plano 2 — Self-Service Classification: Como o Usuário Define e Refina Taxonomia em Runtime

**Tese / pergunta central:**
O brief promete que o usuário pode "reclassificar a base usando 8 categorias que acabei de
definir" e "criar sub-categorias dentro do cluster X seguindo este critério". Isso é muito
mais complexo do que um classificador fixo. Qual é a arquitetura técnica mais madura para
suportar esse loop: usuário define categoria (linguagem natural) → sistema classifica →
usuário revisa casos borderline → sistema incorpora feedback → repete? Onde estão as
fronteiras entre zero-shot, few-shot, active learning, weak supervision, e "LLM-as-classifier"?

**Sub-perguntas:**
1. "Classifier-as-a-prompt" com LLM zero-shot: qual a acurácia real em classificação de
   incidentes financeiros comparada a métodos supervisionados tradicionais? Há estudos recentes?
2. Active learning clássico (uncertainty sampling, query-by-committee) ainda é competitivo
   em 2025, ou LLM few-shot torna obsoleto o loop de anotação tradicional?
3. Weak supervision (Snorkel, programmatic labeling) é uma alternativa viável para o caso
   do BTG, onde a taxonomia muda com frequência?
4. Como implementar "mostre incidentes que ficaram entre duas categorias" (fronteira de
   decisão) de forma interpretável? Abordagens: embedding space boundary visualization,
   calibrated classifiers, explanation methods (LIME/SHAP sobre embeddings)?
5. Qual é o padrão de UX mais eficaz para "human-in-the-loop classification"? Ferramentas
   como Argilla, Label Studio, Prodigy: qual se integra melhor a um pipeline LLM?
6. Existem abordagens de "self-labeling" ou "teacher-student" onde o LLM gera rótulos
   iniciais e o usuário valida amostras pequenas, escalando a anotação?

**Tipos de fontes:**
- Papers: Snorkel original + updates, active learning surveys 2023-2025, LLM-as-annotator
  (GPT-4 annotation papers ACL/EMNLP 2023-2024), few-shot classification in finance
- Repos: snorkel-team/snorkel, argilla-io/argilla, explosion/prodigy (docs), hwchase17/langchain
  classifiers
- Blogs: Hamel Husain (human-in-the-loop), parlance.ai, Explosion AI
- Produtos: Prodigy, Argilla, Scale AI platform docs

**Output esperado:**
Diagrama do loop de classificação self-service recomendado. Comparação de ferramentas de
anotação. Decisão sobre: LLM zero-shot suficiente ou precisa de loop de feedback?
Custo estimado de cada abordagem para 5k exemplos.

**Dependências e adjacências:**
- Não cobre: topic modeling (Plano 1), análise temporal (Plano 4)
- Adjacência com Plano 1: os tópicos descobertos são inputs da classificação self-service
- Resultado alimenta decisão D1, D2, D3 e a pergunta "como implementar active learning"

---

## Plano 3 — Análise Causal e Relacional: Além de Busca Semântica

**Tese / pergunta central:**
Seção 1.4 exige perguntas causais e relacionais que busca semântica pura não responde:
"quando aparece sintoma A, qual causa raiz mais provável?", "quais causas raiz coocorrem
com produto Z?", "existe cadeia causal recorrente A→B→C?". Qual é o estado da arte de
análise causal em event logs / texto de incidentes? Quando Knowledge Graphs (GraphRAG,
Graphiti, Neo4j) ganham de vector search para esse tipo de pergunta? E quando não ganham?

**Sub-perguntas:**
1. Causal discovery em texto (não time-series): existe método robusto para extrair relações
   causais de narrativas de incidentes? EMNLP/ACL têm benchmarks de causa-efeito em inglês?
2. Process mining (Disco, ProM, PM4Py) é relevante para analisar logs de incidentes
   ServiceNow/ITSM? O que o campo entrega que NLP não entrega?
3. Microsoft GraphRAG (2024): o que ele realmente faz que RAG clássico não faz? Quando
   a estrutura de grafo é decisiva para qualidade de resposta?
4. Graphiti (getzep): "memória em grafo temporal para agentes" — como ele diferencia de
   GraphRAG estático? Relevante para análise de incidentes com dimensão temporal?
5. Coocorrência e correlação: para "causas raiz que coocorrem com produto Z", qual abordagem
   é mais interpretável e estatisticamente sólida: PMI em event logs, embedding similarity,
   ou extração de relações com LLM?
6. LightRAG (2024): claims de superar GraphRAG em benchmarks. Tem código aberto, integração
   com LLMs. Vale considerar para a POC?

**Tipos de fontes:**
- Papers: GraphRAG (Microsoft 2024), LightRAG (2024), CASIE dataset (causal event extraction),
  FinCausal shared task, IncidentAI arXiv:2310.12074 (já no brief)
- Repos: microsoft/graphrag, getzep/graphiti, HKUDS/LightRAG, buzheng/CASIE
- Blogs: Microsoft Research Blog (GraphRAG), papers with code (causal IE)
- Ferramentas: PM4Py docs, Neo4j AuraDB

**Output esperado:**
Mapa de decisão: para cada classe de pergunta causal/relacional da Seção 1.4, qual técnica
usar (busca semântica pura, grafo explícito, extração de relações + grafo, process mining).
Decisão sobre incluir ou não KG na v1 da POC (reconsiderando ADR 6).

**Dependências e adjacências:**
- Não cobre: topic modeling (Plano 1), temporal (Plano 4), UI/conversacional (Plano 5)
- Adjacência: Plano 5 usa os resultados de análise causal para construir a interface
- Resultado alimenta diretamente a revisão do ADR 6 (sem grafo na v1)

---

## Plano 4 — Análise Temporal e Detecção de Novidade: DTM, Drift e Sinal vs Ruído

**Tese / pergunta central:**
A hipótese atual para análise temporal (Seção 6.6) é rudimentar: count por cluster por mês
+ z-score/Prophet. A Seção 1.4 exige mais: detectar temas emergentes, distinguir sinal de
ruído estatístico, identificar drift de vocabulário (não só volume). Qual é o estado da arte
em dynamic topic modeling e temporal anomaly detection para corpus de incidentes? Qual
abordagem entrega as perguntas da Seção 1.4 sem requerer re-treino constante?

**Sub-perguntas:**
1. Dynamic Topic Models (DTM, Blei & Lafferty 2006): ainda competitivo em 2025 vs abordagens
   neurais? BERTopic tem modo temporal? Top2Vec suporta análise de drift?
2. Concept drift em texto: qual a diferença entre drift de vocabulário (novas palavras para
   mesmo problema) e drift semântico (novo problema com palavras antigas)? Como detectar ambos?
3. Novelty detection em tópicos: como distinguir "cluster pequeno de outliers não-relacionados"
   de "cluster pequeno de problema real emergente" (pergunta explícita da Seção 1.4)?
4. Múltiplos testes simultâneos: monitorar 50 clusters por mês = 50 testes em paralelo.
   Como controlar falso-positivo (Bonferroni, FDR/BH)? Existe literatura específica em
   OpRisk monitoring?
5. Changepoint detection (PELT, BOCPD, Prophet): adequados para séries de count de incidentes?
   Qual tem melhor interpretabilidade para analista de risco não-técnico?
6. Seasonal decomposition em incidentes: como separar sazonalidade (picos em dezembro para
   fraude de cartão) de tendência real? Requer histórico longo?

**Tipos de fontes:**
- Papers: DTM (Blei 2006), BERTopic temporal (Grootendorst 2022), temporal topic model surveys
  2023-2025, concept drift surveys (Gama et al.), BOCPD (Adams & MacKay)
- Repos: maartengr/BERTopic (topics_over_time), facebook/prophet, changeforest,
  ruptures (Python changepoint)
- Blogs: Rob Mulla (time series), Towards Data Science (temporal NLP)
- Domínio específico: papers de KRI em OpRisk, Basel Committee papers sobre monitoring

**Output esperado:**
Recomendação clara de pipeline temporal: qual método para cada uma das 3 perguntas temporais
da Seção 1.4 (crescimento, decrescimento, emergência). Código de referência/pseudocódigo
para integração no pipeline. Decisão: substituir z-score/Prophet por quê?

**Dependências e adjacências:**
- Não cobre: causal (Plano 3), UI (Plano 5)
- Adjacência forte com Plano 1: os tópicos descobertos são a unidade de análise temporal
- Resultado alimenta diretamente decisão D5 (Prophet/z-score) nas notas de leitura

---

## Plano 5 — Interface Conversacional e Práticas de Mercado: O que Bancos Realmente Fazem

**Tese / pergunta central:**
O diferenciador real desta plataforma vs um dashboard de BI é a interface de análise
conversacional: o analista digita "mostre incidentes parecidos com X" ou "qual tendência
no produto Y no último trimestre?" e recebe resposta útil. Qual é o padrão mais maduro
para construir essa interface — text-to-SQL, RAG sobre dados estruturados, agentes com
tools mistas, ou exploração via REPL? E o que bancos, fintechs e consultorias estão
efetivamente deployando em 2024-2026 para análise de OpRisk?

**Sub-perguntas:**
1. Text-to-SQL sobre dados estruturados de incidentes: qual é a acurácia real em 2025?
   (GPT-4o, Claude Sonnet, DeepSeek) Quais são os padrões de erro comuns que degradam
   confiança do usuário?
2. "Hybrid RAG" (semantic search + SQL no mesmo agente): quais são os padrões de
   orquestração mais confiáveis? LangGraph, DSPy, tool-calling nativo da Anthropic API?
3. Como construir uma interface que o analista de risco (não dev) consiga usar via chat
   sem conhecer SQL? Existem exemplos de deploy interno em bancos?
4. Capgemini Invent "Taxonomy Rationalization & Classification Tool" e "Weak Signals
   Analysis Tool": o que está documentado sobre a arquitetura técnica? Existem case studies
   publicados?
5. O que FAANG (Google, Meta, Stripe, Uber) publicou sobre análise ad-hoc de incident logs
   em escala? Postmortem analysis tooling interno (Monzo, Revolut, N26 têm publicações)?
6. Streamlit vs alternativas para interface de exploração (Gradio, Panel, React custom,
   Retool, Evidence.dev): qual é mais adequado para o caso de análise exploratória de
   incidentes com usuário técnico mas não dev?

**Tipos de fontes:**
- Papers: text-to-SQL benchmarks Spider/BIRD 2024, DSPy (Khattab et al.), DSPY-based agents
- Repos: langchain-ai/langchain, microsoft/semantic-kernel, langchain-ai/langgraph,
  stanfordnlp/dspy, evidence-dev/evidence
- Blogs engenharia: Stripe Engineering, Monzo Blog, Revolut Tech Blog, Martin Fowler
- Vendors: Capgemini Invent OpRisk page, IBM watsonx.data docs, Databricks Genie (text-to-SQL)
- Mercado: Gartner Magic Quadrant OpRisk Management 2024, Forrester OpRisk Wave

**Output esperado:**
Decisão sobre stack de interface conversacional. Comparação Streamlit vs alternativas para
o caso de uso. Digest de práticas reais de mercado (bancos/fintechs) em análise de OpRisk.
Resposta à pergunta: self-service conversacional é viável como MVP ou é escopo demais?

**Dependências e adjacências:**
- Consome outputs de Planos 1-4 (tópicos, causal, temporal são os "tools" do agente)
- Não cobre: topic modeling, análise causal, temporal
- Resultado alimenta diretamente o design da UI e a revisão do ADR 8 (Streamlit)
- Adjacência com Seção 6.7 do brief (Q&A em linguagem natural como stretch goal)
