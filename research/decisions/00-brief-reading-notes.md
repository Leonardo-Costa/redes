# Brief Reading Notes — Initial Pass
Date: 2026-05-05

## Top-10 conclusões mais importantes

1. **O problema declarado é fraco**: classificação para BI (% por categoria) não informa decisão.
   O reframe correto é plataforma de inteligência com três capabilities: classificação regulatória,
   weak signal discovery, investigação self-service.

2. **A motivação central (Seção 1.4) é o critério de sucesso real**: o sistema precisa suportar 6
   classes de pergunta ad-hoc — exploração temática, análise causal/relacional, análise temporal/
   tendência, classificação self-service, detecção de padrões/recorrências, e sinal vs ruído.
   Qualquer arquitetura que não cubra esse espectro é insuficiente.

3. **Diagnóstico correto sobre BERTopic ingênuo** (Seção 4): boilerplate domina embedding,
   eixos ortogonais colapsados num vetor, modelo genérico sem semântica de domínio.
   As três correções propostas (pré-extração LLM, cluster por faceta, taxonomia induzida) são
   defensáveis — mas precisam ser validadas contra alternativas recentes (Clio, Top2Vec, NTMs).

4. **Dataset CFPB é uma boa escolha** — proxy público mais próximo de OpRisk bancário, com ground
   truth multi-nível (Product → Issue) para validação. Caveats honestos documentados (inglês,
   reclamação ≠ incidente interno).

5. **Schema Pydantic com facetas ortogonais** é o núcleo arquitetural. A ideia de embeddar
   summaries destilados (não narrativa crua) em vez de texto completo é a lição central do Clio.
   Precisa de validação empírica do custo/benefício (extração 5k com Sonnet ~$15-40).

6. **Análise temporal é o gap mais crítico** na hipótese inicial: Prophet/z-score para z-score sobre
   counts de cluster é rudimentar. DTM (Dynamic Topic Models) e changepoint detection têm literatura
   rica que pode superar essa abordagem.

7. **Knowledge graph foi excluído da v1 (ADR 6)** por ROI baixo em 5k registros. Mas GraphRAG
   e Graphiti podem ser relevantes para análise causal/relacional (Seção 1.4 cobre isso), o que
   questiona a exclusão. A pesquisa deve investigar quando grafos ganham de busca semântica pura
   para esse tipo de pergunta.

8. **Self-service conversacional** (text-to-SQL + semantic search, Seção 6.7) está marcado como
   stretch goal, mas é provavelmente o diferenciador mais importante vs um dashboard de BI.
   A pesquisa deve priorizar isso.

9. **Migração para o cliente** requer: prompt PT-BR, troca de embedding model (bge-m3),
   adaptação do ProductDomain, aprovações DPO/compliance. Isso afeta design de abstração —
   o sistema deve ser parametrizado para troca de idioma/taxonomia sem reescrita.

10. **Graphify**: instalado com sucesso (hooks git + Claude Code). Extração LLM das Markdowns
    requer ANTHROPIC_API_KEY setada no ambiente. Sem a chave, o grafo permanece com extração
    AST-only (código Python) mas não processa os documentos de pesquisa. Ação necessária antes
    da próxima rodada de pesquisa: setar ANTHROPIC_API_KEY e rodar `graphify extract ./research`.

## Decisões que a pesquisa deve validar (críticas)

| # | Decisão | Hipótese atual | Risco se errada |
|---|---------|---------------|-----------------|
| D1 | Pré-extração LLM antes de clustering | Reduz boilerplate, melhora coerência | Custo alto, extração inconsistente entre runs |
| D2 | Cluster por faceta (não global) | Preserva ortogonalidade | Facetas podem ser correlacionadas, clusters redundantes |
| D3 | Summaries como unidade de embedding | Melhor signal-to-noise | Perda de contexto, summaries inconsistentes |
| D4 | UMAP + HDBSCAN para clustering | Padrão da literatura recente | Outros approaches (NTMs, Top2Vec) podem dominar em domínio específico |
| D5 | Prophet/z-score para temporal | Simples, interpretável | DTM ou changepoint detection capturam drift de vocabulário, não só volume |
| D6 | Sem grafo na v1 | ROI baixo em 5k | Perde análise causal/relacional real (Seção 1.4) |
| D7 | pgvector para vector store | Stack do cliente, zero custo adicional | Limitações em query complexa (faceted search, hybrid) |
| D8 | Streamlit para UI | Rápido de prototipar | Não escala para exploração conversacional real |

## Gaps identificados na especificação (precisam de pesquisa)

- **Active learning / weak supervision**: brief menciona (Seção 2.3) mas não especifica como
  implementar classificação self-service interativa. Isso é mais complexo do que dropdown de
  categorias no Streamlit.
- **Análise causal**: Seção 1.4 pede "quando aparece sintoma A, qual causa raiz mais provável
  historicamente?" — isso requer mais que busca semântica, precisa de estimativa causal.
- **Sinal vs ruído**: o brief pede significância estatística, mas a hipótese atual (z-score) é
  ingênua. Múltiplos testes simultâneos = inflação de falso positivo.
- **Hierarquia dinâmica de tópicos**: usuário pode pedir "decompor cluster X em sub-temas" —
  a arquitetura precisa suportar hierarquia online, não só flat clustering.

## Status do setup

- [x] Graphify instalado (graphifyy v0.7.5)
- [x] Hook Claude Code instalado (`PreToolUse` em `.claude/settings.json`)
- [x] Hook git instalado (`post-commit`, `post-checkout`)
- [x] Diretório `research/` criado com estrutura correta
- [x] Brief copiado para `research/raw/00-initial-brief.md`
- [x] Extração LLM do grafo: feita via skill `/graphify` (sem API key separada)
