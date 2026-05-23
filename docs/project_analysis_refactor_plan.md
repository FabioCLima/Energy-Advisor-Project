# Plano de Análise e Refatoração — EcoHome Energy Advisor

> **Contexto:** Análise técnica realizada em 23/05/2026. Objetivo: transformar o projeto de um exercício acadêmico em um portfólio profissional apresentável em entrevista nos próximos dias, usando o framework CAR (Challenge → Action → Result).

---

## 1. Estado Atual do Projeto

### O que já existe (pontos fortes)

| Componente | Status | Qualidade |
|---|---|---|
| Agente LangGraph ReAct | ✅ Implementado | Sólido — grafo explícito com estado tipado |
| 7 ferramentas (tools) | ✅ Implementadas | Bem separadas por domínio |
| Pipeline RAG com ChromaDB | ✅ Funcional | Ingestion + similarity search |
| Camada de dados SQLite + SQLAlchemy | ✅ Funcional | ORM correto, session-safe |
| Configuração centralizada (Pydantic Settings) | ✅ Implementado | Validação robusta |
| Logging estruturado (Loguru) | ✅ Implementado | Observabilidade básica |
| Integração LangSmith (tracing) | ✅ Opcional | Configurável via .env |
| Testes unitários (5 suites) | ✅ Presentes | config, db, forecasting, pricing, savings |
| CLI via `main.py` | ✅ Funcional | Entrada de linha de comando |
| Notebooks de desenvolvimento | ✅ Presentes | Setup, RAG, avaliação |
| Separação de camadas | ✅ Clara | agent → tools → services → storage |

### O que está faltando (gaps críticos para entrevista)

| Gap | Impacto na Entrevista | Prioridade |
|---|---|---|
| **Sem interface visual** | Alto — recrutador não consegue "usar" o projeto | P0 |
| **Dados 100% sintéticos** | Médio — não demonstra integração real | P1 |
| **Sem Docker / deployment** | Alto — projeto não é "rodável" em 1 comando | P0 |
| **Sem visualizações de dados** | Alto — energia é um domínio visual | P0 |
| **Avaliação apenas em notebook** | Médio — não demonstra rigor de engenharia | P1 |
| **README sem demo** | Alto — primeira impressão no GitHub | P0 |
| **Sem streaming de respostas** | Médio — UX moderna requer SSE/stream | P1 |
| **Sem persistência de sessão** | Baixo — memória entre conversas | P2 |
| **Sem CI/CD** | Médio — demonstra maturidade DevOps | P2 |

---

## 2. Narrativa CAR para a Entrevista

O framework CAR (Challenge → Action → Result) transforma o projeto em uma história profissional convincente.

### Challenge — O Problema Real

> *"Residências inteligentes geram dados ricos de consumo energético, geração solar, preços dinâmicos e climatologia — mas esses dados vivem em silos desconectados. O morador não tem como responder perguntas como 'quando devo carregar meu carro elétrico para minimizar custo e maximizar uso solar?' sem análise manual de múltiplas fontes."*

**Por que é tecnicamente difícil:**
- Requer raciocínio multi-passo sobre dados heterogêneos (timeseries, preços TOU, previsão climática, base de conhecimento)
- O agente precisa decidir *quais* ferramentas chamar e *em que ordem*
- As recomendações devem ser fundamentadas em dados, não em hallucination

### Action — O que foi construído

> *"Projetei e implementei um agente LangGraph com arquitetura ReAct de 6 camadas: Interação → Orquestração → Ferramentas → Serviços → Armazenamento → Observabilidade. O agente coordena 7 ferramentas especializadas, um pipeline RAG semântico e uma camada de dados com SQLite + ChromaDB."*

**Decisões técnicas justificáveis:**

| Decisão | Alternativa Considerada | Por que essa escolha |
|---|---|---|
| LangGraph (grafo explícito) | LangChain LCEL | Grafo torna o fluxo de decisão auditável e testável |
| ChromaDB | Pinecone, FAISS | Persistência local, zero infra externa para demo |
| SQLite + SQLAlchemy | PostgreSQL | Portabilidade total — roda em qualquer máquina |
| Pydantic Settings | `os.getenv()` direto | Validação em tempo de carregamento, fail-fast |
| Loguru | logging stdlib | Structured logging com contexto sem boilerplate |
| Streamlit (a adicionar) | FastAPI + React | Time-to-demo mínimo para portfólio |

### Result — Resultados Mensuráveis

> *"O agente responde queries complexas multi-ferramenta em < 15 segundos, produz estimativas de economia com premissas explícitas, e cita fontes da base de conhecimento. O pipeline de avaliação cobre N cenários com métricas de coerência, uso de ferramentas e qualidade da recomendação."*

**Métricas para preparar antes da entrevista:**
- Tempo médio de resposta por tipo de query
- Taxa de uso correto de ferramentas (tool call accuracy)
- Score de avaliação no notebook 03
- Cobertura de testes unitários

---

## 3. Stack Recomendada (Versão Portfolio)

### Stack Atual → Stack Alvo

```
ATUAL                          ALVO (portfolio)
─────────────────────────────────────────────────────
CLI (main.py)              →   Streamlit UI + FastAPI opcional
Dados sintéticos           →   APIs reais mockáveis + seed realista
Notebooks de avaliação     →   Script de eval com relatório HTML
Sem containerização        →   Docker Compose (1 comando para tudo)
Sem visualizações          →   Plotly/Altair charts no Streamlit
README estático            →   README com GIF demo + badges
```

### Stack Completa Proposta

| Camada | Tecnologia | Justificativa |
|---|---|---|
| **UI/Demo** | Streamlit | Zero-frontend, deploy gratuito, visual para recrutador |
| **API** | FastAPI + LangServe | Padrão da indústria, auto-gera docs Swagger |
| **Agente** | LangGraph 0.2+ | Já implementado, grafo auditável |
| **LLM** | OpenAI GPT-4o-mini / Anthropic Claude | Já configurado, multi-provider |
| **RAG** | ChromaDB + LangChain | Já implementado |
| **Dados** | SQLite → PostgreSQL-ready via SQLAlchemy | Já implementado, ORM portável |
| **Visualização** | Plotly Express | Integrado nativo no Streamlit |
| **Testes** | pytest + pytest-cov | Já tem base, expandir |
| **Containerização** | Docker + Docker Compose | Um comando para rodar tudo |
| **Observabilidade** | LangSmith + Loguru | Já configurado |
| **CI** | GitHub Actions | Linting + testes automáticos |
| **Deploy** | Streamlit Community Cloud | Gratuito, URL pública em minutos |

---

## 4. Features a Implementar (de `11_Sugestions.md`)

Priorizadas por impacto visual vs esforço de implementação:

### P0 — Alta Visibilidade, Baixo Esforço (para a entrevista)

#### 4.1 Interface Visual com Streamlit + Visualizações (Sugestão A + B)

Dashboard com duas abas:
- **Aba "Chat"**: interface conversacional com o agente, streaming de respostas
- **Aba "Dashboard"**: gráficos de consumo vs geração solar (Plotly), horários de pico, estimativas de economia

```
Arquivos novos:
├── app/
│   ├── streamlit_app.py       ← entrypoint: `streamlit run app/streamlit_app.py`
│   ├── components/
│   │   ├── chat.py            ← componente de chat
│   │   └── charts.py         ← componente de visualizações Plotly
│   └── __init__.py
```

Gráficos prioritários:
- Consumo por dispositivo (últimos 7 dias) — bar chart
- Geração Solar vs Consumo — área stackada por hora
- Janelas de preço TOU — heatmap de tarifas
- Projeção de economia — linha de tendência

#### 4.2 Docker Compose (uma linha para rodar tudo)

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8501:8501"]
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./ecohome_solution/data:/app/data
```

```
Arquivos novos:
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
```

### P1 — Impacto Médio (implementar se houver tempo)

#### 4.3 Advanced RAG — Hybrid Search + Re-ranking (Sugestão D)

Upgrade do pipeline RAG atual:
- **Hybrid search**: combinar similarity search (ChromaDB) com BM25 keyword search
- **Re-ranking**: usar CrossEncoder para reordenar resultados antes de passar ao agente
- **Multi-step retrieval**: query expansion — o agente reformula a query para melhorar recall

```
Arquivos a modificar:
├── energy_advisor/services/retrieval.py  ← adicionar BM25 + CrossEncoder
├── energy_advisor/tools/rag.py           ← aceitar parâmetro `search_mode`
```

#### 4.4 Integração com APIs Externas Reais (Sugestão C)

- **Open-Meteo API** (gratuita, sem key): substituir `forecasting.py` sintético por dados reais de previsão climática
- **EIA API** (gratuita): dados reais de preços de energia elétrica por região nos EUA

```
Arquivos a modificar/criar:
├── energy_advisor/services/forecasting.py  ← adicionar Open-Meteo client
├── energy_advisor/services/pricing.py      ← adicionar EIA API client (opcional)
├── energy_advisor/tools/weather.py         ← aceitar modo real vs sintético
```

#### 4.5 Script de Avaliação Standalone com Relatório

Extrair a lógica do `03_run_and_evaluate.ipynb` para um script executável:

```
Arquivos novos:
├── energy_advisor/evaluation/
│   ├── __init__.py
│   ├── runner.py          ← executa cenários e coleta métricas
│   ├── scenarios.py       ← cenários de teste definidos
│   └── report.py          ← gera relatório HTML ou JSON
```

```bash
# Execução:
python -m energy_advisor.evaluation.runner --output eval_report.html
```

### P2 — Nice-to-Have (pós-entrevista)

#### 4.6 Personalização de Usuário (Sugestão B)

Adicionar perfil de usuário com preferências persistidas:
- Tolerância a desconforto térmico
- Prioridade: economia vs conforto
- Dispositivos elegíveis para shift de carga

#### 4.7 Machine Learning — Previsão de Consumo (Sugestão E)

Modelo simples de forecasting (Prophet ou sklearn) treinado nos dados históricos do SQLite para prever consumo nas próximas 24h.

#### 4.8 GitHub Actions CI (P2)

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    steps:
      - ruff check .
      - pytest ecohome_solution/tests/ --cov
```

---

## 5. Plano de Execução — Foco na Entrevista

### Critérios de sucesso verificáveis

1. `docker compose up` levanta o projeto sem erros
2. URL pública acessível via Streamlit Community Cloud
3. Chat responde em < 15s com ferramenta usada visível
4. Dashboard mostra pelo menos 3 gráficos com dados reais do SQLite
5. `pytest` passa com cobertura > 70%
6. README tem screenshot ou GIF do dashboard

---

### Sprint 1 — Streamlit UI + Docker (Dias 1-2)

**Objetivo:** projeto visualmente apresentável com 1 comando.

| Tarefa | Arquivo | Estimativa |
|---|---|---|
| Criar `app/streamlit_app.py` com abas Chat + Dashboard | `app/streamlit_app.py` | 3h |
| Implementar componente de chat com streaming | `app/components/chat.py` | 2h |
| Implementar gráficos Plotly (consumo, solar, TOU) | `app/components/charts.py` | 3h |
| Criar `Dockerfile` + `docker-compose.yml` | raiz do projeto | 1h |
| Verificar: `streamlit run app/streamlit_app.py` funciona | — | 30min |

**Verificação:** abrir `localhost:8501`, enviar pergunta, ver resposta + gráficos.

---

### Sprint 2 — Hardening e Avaliação (Dia 2-3)

**Objetivo:** demonstrar rigor de engenharia.

| Tarefa | Arquivo | Estimativa |
|---|---|---|
| Extrair avaliação do notebook para script standalone | `energy_advisor/evaluation/` | 2h |
| Integrar Open-Meteo API no `forecasting.py` | `services/forecasting.py` | 2h |
| Expandir testes para cobrir tools e retrieval | `tests/` | 2h |
| Atualizar README com screenshot + badges + setup em 3 passos | `README.md` | 1h |
| Deploy no Streamlit Community Cloud | streamlit.io | 30min |

**Verificação:** URL pública funciona, `pytest` verde, README tem imagem.

---

### Sprint 3 — Diferenciadores Técnicos (Dia 3, se houver tempo)

**Objetivo:** perguntas técnicas difíceis na entrevista viram respostas sólidas.

| Tarefa | Impacto na Entrevista |
|---|---|
| Hybrid RAG (BM25 + semantic) | "Como você melhoraria o recall do RAG?" |
| Streaming de respostas no chat | "Como você faria UX em tempo real?" |
| Relatório de avaliação em HTML | "Como você avalia a qualidade do agente?" |
| Diagrama de arquitetura no README | "Explique a arquitetura em 2 minutos" |

---

## 6. Estrutura de Arquivos Alvo

```
Energy-Advisor-Project/
├── app/                              ← NOVO: Streamlit UI
│   ├── streamlit_app.py
│   └── components/
│       ├── chat.py
│       └── charts.py
├── ecohome_solution/
│   ├── energy_advisor/
│   │   ├── agent.py                  ← existente, pequenas melhorias
│   │   ├── config.py                 ← existente
│   │   ├── prompts.py                ← existente
│   │   ├── schemas.py                ← existente
│   │   ├── bootstrap/                ← existente
│   │   ├── evaluation/               ← NOVO: script standalone
│   │   │   ├── runner.py
│   │   │   ├── scenarios.py
│   │   │   └── report.py
│   │   ├── services/
│   │   │   ├── forecasting.py        ← UPGRADE: Open-Meteo API real
│   │   │   ├── pricing.py            ← existente
│   │   │   ├── retrieval.py          ← UPGRADE: hybrid search
│   │   │   └── recommendations.py   ← existente
│   │   └── tools/                    ← existente
│   └── tests/                        ← EXPANDIR: +3 suites
├── Dockerfile                        ← NOVO
├── docker-compose.yml                ← NOVO
├── .github/
│   └── workflows/ci.yml              ← NOVO (P2)
└── README.md                         ← REESCREVER com demo
```

---

## 7. Perguntas de Entrevista e Respostas Preparadas

### "Por que LangGraph em vez de LangChain LCEL simples?"

> *"LangGraph representa o fluxo de decisão como um grafo dirigido com estado tipado. Isso torna o comportamento do agente auditável — consigo ver exatamente quais nós foram visitados, o que cada ferramenta retornou e como o estado evoluiu. LCEL é ótimo para pipelines lineares, mas para agentes com ramificação condicional, o grafo explícito é mais testável e mais fácil de debugar."*

### "Como você garante que o agente não alucina?"

> *"Três camadas: (1) o system prompt instrui o agente a sempre chamar ferramentas antes de responder; (2) cada tool retorna um schema Pydantic validado — o agente nunca recebe dados amorfos; (3) o prompt exige que o agente declare premissas e limitações quando dados estão incompletos. O LangSmith me permite ver se o agente está pulando ferramentas."*

### "Como o RAG funciona no projeto?"

> *"Os documentos de melhores práticas energéticas são chunkeados e indexados no ChromaDB com embeddings OpenAI. Quando o agente chama `search_energy_tips`, executa similarity search semântica e retorna os K chunks mais relevantes com metadata de fonte. A evolução planejada é adicionar hybrid search (BM25 + semântico) e re-ranking com CrossEncoder para melhorar o recall."*

### "Como você avalia a qualidade do agente?"

> *"Tenho um pipeline de avaliação com N cenários cobrindo diferentes tipos de query: EV scheduling, análise histórica, estimativa de economia, melhores práticas. Métricas: (1) tool call accuracy — o agente chamou as ferramentas certas? (2) response coherence — a resposta segue o formato estruturado? (3) grounding — a resposta cita dados reais ou hallucina? Integrado com LangSmith para rastrear cada run."*

### "Por que Streamlit e não FastAPI + React?"

> *"Para portfólio, time-to-demo é crítico. Streamlit permite construir uma UI funcional com visualizações em horas, sem overhead de frontend. Para produção real, a escolha seria FastAPI + LangServe (opção A das sugestões do projeto) — o código do agente não muda, só o ponto de entrada. A arquitetura já antecipa isso com o `main.py` desacoplado do agente."*

---

## 8. Próximos Passos Imediatos

Execute nesta ordem:

```bash
# 1. Instalar dependências adicionais
pip install streamlit plotly altair

# 2. Criar a estrutura da UI
# (implementar app/streamlit_app.py conforme Sprint 1)

# 3. Testar localmente
streamlit run app/streamlit_app.py

# 4. Buildar Docker
docker compose up --build

# 5. Deploy
# Push para GitHub → conectar no streamlit.io → deploy em 1 clique
```

---

## 9. Resumo Executivo

| Dimensão | Hoje | Pós-refatoração |
|---|---|---|
| **Rodabilidade** | Notebooks + CLI manual | `docker compose up` → URL pública |
| **Demonstrabilidade** | Precisa de terminal | Dashboard visual interativo |
| **Rigor técnico** | Bom (arquitetura limpa) | Excelente (eval, CI, docs) |
| **Impressão no GitHub** | README básico | README com demo GIF + badges |
| **RAG** | Similarity search básico | Hybrid search + re-ranking |
| **Dados** | 100% sintéticos | Weather real (Open-Meteo) |
| **Narrativa CAR** | Implícita | Explícita no README e entrevista |

**O projeto já tem a espinha dorsal técnica certa. O trabalho dos próximos dias é transformar código funcional em produto demonstrável.**
