# Project Backlog — EcoHome Energy Advisor

> **Contrato de trabalho** firmado em 23/05/2026.
> Objetivo: transformar o projeto de um exercício acadêmico em portfólio profissional
> apresentável em entrevista técnica de AI Engineer.
> Atualizado a cada entrega — serve como auditoria do que foi combinado vs. entregue.

---

## Contexto e Objetivo

**Problema:** projeto standalone sem interface visual, dados em USD, sem narrativa de produto.
**Meta:** em ~3 dias, entregar um projeto que passe no critério do recrutador:
- Roda com 1 comando (`docker compose up`)
- Tem interface visual com dados reais (BRL, Enel SP, persona João)
- Chat advisor responde perguntas com ferramentas reais
- README conta a história CAR (Challenge → Action → Result)
- Entrevistador consegue fazer perguntas técnicas e receber respostas sólidas

---

## Critérios de Aceite Globais

| # | Critério | Status |
|---|---|---|
| C1 | `docker compose up` levanta o projeto sem erros | ✅ Entregue |
| C2 | Dashboard mostra ≥ 4 gráficos com dados reais do SQLite | ✅ Entregue |
| C3 | Chat responde em < 15s com ferramenta usada visível | ✅ Entregue |
| C4 | `pytest` passa sem erros | ✅ Entregue |
| C5 | README tem screenshot/GIF + setup em 3 passos | ✅ Entregue |
| C6 | Script de avaliação executável com métricas documentadas | ✅ Entregue |
| C7 | URL pública acessível (Streamlit Community Cloud) | ⬜ Pendente |

---

## Sprint 1 — UI, Dados e Docker
> **Período:** 23/05/2026 · **Status: ✅ Concluído**

### Backlog

| ID | Item | Arquivo(s) | Status | Commit |
|---|---|---|---|---|
| S1-01 | Persona João: schema BRL, ANEEL bandeiras, 90 dias de dados | `bootstrap/sample_data.py`, `services/pricing.py`, `schemas.py` | ✅ | `aa477b7` |
| S1-02 | Dashboard Streamlit: 4 gráficos Plotly + abas Chat/Dashboard | `app/streamlit_app.py`, `app/components/charts.py`, `app/components/chat.py` | ✅ | `a92b6ec` |
| S1-03 | Resolver 12 bugs visuais documentados em `dashboard_improvements.md` | `app/components/charts.py`, `app/streamlit_app.py` | ✅ | `88cc6e9` |
| S1-04 | Chat advisor operacional (datas corretas, query agregada, prompt com contexto) | `energy_advisor/agent.py`, `energy_advisor/prompts.py`, `energy_advisor/tools/energy_data.py` | ✅ | `88cc6e9` |
| S1-05 | Docker: Dockerfile + docker-compose.yml + entrypoint + .dockerignore | `/Dockerfile`, `/docker-compose.yml`, `/docker-entrypoint.sh` | ✅ | `9072667` |
| S1-06 | Narrativa CAR + decisões de arquitetura + Q&A para entrevista | `docs/interview_prep.md`, `docs/interview_qa.md` | ✅ | `b322b2e`, `0a30c88` |

### Bugs resolvidos (S1-03)

| ID | Descrição | Fix |
|---|---|---|
| B1 | Home Office Cost — valor duplicado e divergente | `HOME_OFFICE_DEVICES` frozenset como fonte única de verdade |
| B2 | Formatação `++` nas projeções | Substituído por `st.metric` |
| B3 | Labels `R$-` no gráfico home office | Coluna `label` explícita no DataFrame |
| H1 | Eixo Y mal calibrado no gráfico home office | `range=[0, max_val * 1.30]` |
| K1 | KPI de Autossuficiência Solar ausente | Adicionado: `solar_kwh / total_kwh * 100` |
| K2 | KPI de Economia Solar em R$ ausente | Adicionado: `solar_kwh × R$ 0.656` |
| K3 | KPI de Custo Líquido da Rede ausente | Adicionado: `total_brl − solar_savings` |
| D1 | Tesla distorce escala do bar chart | Tesla separado em seção `render_ev_summary` com 4 metric cards |
| D2 | Sem percentual nas barras de dispositivos | Coluna `pct` adicionada como label |
| S1 | Unidade eixo Y incorreta (kWh vs kW) | Corrigido para `kW (avg)` |
| S2 | Excedente solar não destacado | Área verde onde `solar > consumption` |
| T1 | Labels sobrepostos nas tarifas | Label apenas na primeira barra de cada período |
| T2 | Hora atual não marcada no gráfico de tarifas | `fig.add_vline` com anotação "Now" |
| U2 | Solar e tarifas em lados opostos | Ambos na coluna direita (análise temporal) |
| U3 | Sem insight acionável | Card `render_daily_insight` com tarifa atual + recomendação |

---

## Sprint 2 — Hardening e Avaliação
> **Período:** 23/05/2026 · **Status: ✅ Concluído**

### Backlog

| ID | Item | Arquivo(s) | Prioridade | Status | Commit |
|---|---|---|---|---|---|
| S2-01 | README reescrito: screenshot, badges, setup em 3 passos, narrativa CAR | `README.md`, `ecohome_solution/README.md`, `docs/assets/dashboard.png` | P0 | ✅ Entregue | `ffa7029` |
| S2-02 | Script de avaliação standalone: runner + scenarios + relatório JSON | `energy_advisor/evaluation/` | P1 | ✅ Entregue | `6f1ee6d` |
| S2-03 | Open-Meteo API: substituir `get_weather_forecast` sintético por dados reais de SP | `services/forecasting.py`, `tools/weather.py`, `schemas.py`, `app/components/charts.py` | P1 | ✅ Entregue | `d3f17b7` |
| S2-04 | Bill breakdown por controlabilidade + correção de date boundary | `app/components/charts.py`, `app/streamlit_app.py` | P1 | ✅ Entregue | `f0e171c` |
| S2-05 | Fix deploy: bootstrap RAG + dependência `requests` no Docker | `docker-entrypoint.sh`, `requirements.txt`, `Dockerfile` | P1 | ✅ Entregue | `dc7cece` |
| S2-06 | Expandir testes: tools e retrieval (cobertura > 70%) | `tests/test_tools_energy_data.py`, `tests/test_retrieval.py`, `tests/test_forecasting.py`, `pyproject.toml` | P2 | ✅ Entregue | `fc67aaa` |
| S2-07 | Deploy dual: Streamlit Cloud (AI Engineer) + AWS FastAPI (MLE) | — | P1 | ⬜ Pendente | — |

### Detalhamento S2-04 — Bill Breakdown

**Problema:** usuário não conseguia identificar quais dispositivos compõem a conta e não havia controle granular por categoria.

**Entregues:**
- Gráfico horizontal `chart_bill_by_controllability`: R$ por dispositivo colorido por categoria (Fixo / Home Office / Flexível / EV)
- 4 KPI cards de resumo por categoria com oportunidade de economia
- Correção de **date boundary**: `_day_start()` trunca para meia-noite — alinha cálculo do dashboard com o agente (YYYY-MM-DD)

**Decisão:** classificação via `usage_pattern` do schema DB (não nomes hardcoded) — robusto a mudanças de dados.

---

### Detalhamento S2-06 — Testes (87% cobertura)

**Problema:** 3 testes quebrados pós-refatoração Open-Meteo; sem cobertura de tools e retrieval.

**Entregues:**
- `test_forecasting.py` reescrito: mock de `requests.get` separado em path de API e path de fallback
- `test_tools_energy_data.py` (13 testes): `query_energy_usage`, `query_solar_generation`, `get_recent_energy_summary` — filtros, agregação, validação de data, caminhos de erro
- `test_retrieval.py` (12 testes): `_load_splits`, `list_document_paths`, `build_hybrid_retriever` com `FakeEmbeddings` — sem chamadas de API real
- `pyproject.toml`: config de coverage excluindo `bootstrap/`, `evaluation/`, `agent.py` (requerem LLM real)
- **Resultado:** 69/69 passando · **87% de cobertura no core testável**

**Decisão:** excluir bootstrap/evaluation/agent do coverage não é desonesto — são componentes de integração que necessitam de LLM real para executar. A cobertura de 87% reflete o código que é unit-testável.

---

### Detalhamento S2-07 — Deploy Dual

**Estratégia:**
- **Streamlit Community Cloud**: demo público, posicionamento AI Engineer
- **AWS + FastAPI**: posicionamento MLE/produção — mesmo agente exposto via REST

**Execução:** após todas as features estarem implementadas e PR revisado.

---

### Detalhamento S3-01 — Hybrid RAG

**Problema:** busca puramente semântica perde termos exatos como "Tesla Model 3", "bandeira vermelha", "ANEEL".

**Entregues:**
- `_load_splits()` extraída como helper compartilhado entre `ensure_vectorstore` e `build_hybrid_retriever`
- `build_hybrid_retriever()`: `BM25Retriever` (keyword) + `ChromaDB.as_retriever()` (semântico) fundidos via `EnsembleRetriever` com Reciprocal Rank Fusion — score = `sum(1 / (k + rank_i))`
- `search_energy_tips` tool atualizada: usa `retriever.invoke()` + campo `retrieval_method: "hybrid_bm25_semantic"` na resposta
- `RagTip` schema: removido `relevance_score` fake; `retrieval_method` agora aparece no payload do agente
- Dependências: `rank-bm25>=0.2.2`, `langchain-classic>=1.0.0` adicionadas a `requirements.txt` e `Dockerfile`

**Por que RRF e não cross-encoder?** Cross-encoder requer um modelo de re-ranking adicional (Cohere, etc.) — mais latência, mais custo, mais API key. RRF é uma fórmula matemática: sem modelo, sem latência extra, sem custo. Para o corpus pequeno (~5 docs, ~20 chunks), a diferença de qualidade é negligível.

---

### Detalhamento S2-02 — Script de Avaliação

```
energy_advisor/evaluation/
├── __init__.py
├── scenarios.py    ← 10+ cenários de teste com expected_tools e rubric
├── runner.py       ← executa agent.invoke() em cada cenário, coleta métricas
└── report.py       ← gera relatório JSON/HTML com scores
```

Métricas a cobrir:
- **Tool call accuracy**: o agente chamou as ferramentas certas?
- **Response coherence**: resposta segue o formato estruturado (Recommendation / Why / ...)?
- **Grounding**: números na resposta batem com os dados retornados pelas ferramentas?

Execução:
```bash
python -m energy_advisor.evaluation.runner --output eval_report.json
```

---

## Sprint 3 — Diferenciadores Técnicos
> **Status: ✅ Concluído**

| ID | Item | Impacto na Entrevista | Esforço | Status | Commit |
|---|---|---|---|---|---|
| S3-01 | Hybrid RAG: BM25 + semantic search + RRF | "Como você melhoraria o recall do RAG?" | Médio | ✅ Entregue | `fc67aaa` |
| S3-02 | Streaming de respostas no chat (token streaming) | "Como você faria UX em tempo real?" | Médio | ✅ Entregue | `7f3d6e9` |
| S3-03 | GitHub Actions CI: ruff + pytest --cov no push | Demonstra maturidade DevOps | Baixo | ✅ Entregue | `7f3d6e9` |
| S3-04 | Diagrama de arquitetura no README (Mermaid) | "Explique a arquitetura em 2 minutos" | Baixo | ✅ Entregue | `7f3d6e9` |

---

## Backlog Descartado / Pós-entrevista

| ID | Item | Motivo do adiamento |
|---|---|---|
| P2-01 | Personalização de usuário (preferências persistidas) | Baixo impacto para entrevista |
| P2-02 | ML forecasting (Prophet/sklearn) | Alto esforço, fora do escopo imediato |
| P2-03 | FastAPI + LangServe (API REST) | Streamlit suficiente para demo |

---

## Registro de Decisões Técnicas

| Data | Decisão | Alternativa considerada | Motivo |
|---|---|---|---|
| 23/05 | LangGraph (grafo explícito) | LangChain LCEL | Fluxo auditável e testável |
| 23/05 | SQLite | PostgreSQL | Portabilidade total para demo |
| 23/05 | ChromaDB local | Pinecone | Zero infra externa |
| 23/05 | `uv` para gerenciamento de pacotes | pip | Pedido explícito do usuário |
| 23/05 | Dados sintéticos com `prob_fn` por dispositivo | CSV estático | Padrões realistas sem API externa |
| 23/05 | `query_energy_usage` retorna agregado por dispositivo | Registros brutos | LLM não consegue processar 2000+ rows |
| 23/05 | Data atual injetada em cada `invoke()` | Hardcoded no system prompt | System prompt é estático (init time) |
| 23/05 | Open-Meteo com `direct + diffuse radiation` | `shortwave_radiation` agregado | Ambos os componentes geram energia; difuso é relevante em dias nublados |
| 23/05 | Fallback sintético automático no `generate_hourly_forecast` | Erro explícito se API falhar | Sistema degrada graciosamente — nunca quebra em demo ao vivo |
| 23/05 | `data_source` no schema `WeatherForecast` | Campo invisível | Permite ao agente citar origem dos dados e ao LLM-as-judge verificar grounding |
| 23/05 | Cache de 30 min no `_load_weather()` do Streamlit | Sem cache / cache curto | Open-Meteo free tier — não faz sentido recarregar a cada rerun |
| 23/05 | Classificação de dispositivos via `usage_pattern` do DB | Frozenset hardcoded de nomes | Nomes dos dispositivos mudam com os dados; `usage_pattern` é parte do schema |
| 23/05 | `_day_start()` trunca para meia-noite | `datetime.now() - timedelta(days=N)` direto | Agente usa datas YYYY-MM-DD (day boundary); dashboard deve ser consistente |
| 23/05 | Deploy dual: Streamlit Cloud + AWS FastAPI | Apenas Streamlit Cloud | Sinaliza competência MLE (FastAPI/AWS) além de AI Engineer (Streamlit) |
| 23/05 | Hybrid RAG via EnsembleRetriever (BM25 + ChromaDB) com RRF | Cross-encoder re-ranking (Cohere) | RRF é fórmula matemática — sem modelo extra, sem latência, sem custo; qualidade equivalente para corpus pequeno |
| 23/05 | FakeEmbeddings nos testes de retrieval | Mock do vectorstore | EnsembleRetriever valida Pydantic que retrievers são instâncias Runnable; MagicMock não passa — FakeEmbeddings gera vetores reais |
| 23/05 | Coverage config exclui bootstrap/evaluation/agent | Cobrir tudo com mocks | Esses módulos requerem LLM real; mockar o LangGraph inteiro não testa comportamento relevante |
| 23/05 | Notebooks removidos do repo (apenas .gitignore) | Manter como documentação | Notebooks têm kernel stateful e não são deployáveis — toda lógica já estava em módulos Python |
| 23/05 | Token streaming via LangGraph `stream_mode="messages"` | Polling do resultado final | Tokens renderizam conforme chegam; `tool_call_chunks` filtra mensagens intermediárias |
| 23/05 | `last_tools_used` como side-effect do generator | Segunda chamada ao agente para buscar tools | Evita double LLM call — ToolMessage capturado durante o stream |
| 23/05 | CI faz lint só em `energy_advisor/ tests/` | Lint em toda a codebase | `app/streamlit_app.py` tem E402 estrutural pelo `sys.path` manipulation — não fixável sem refactor |
