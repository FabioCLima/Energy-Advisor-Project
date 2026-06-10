# Onboarding — AI Engineer Júnior no EcoHome

> **Objetivo:** em ~5 dias úteis, sair de "clonei o repo" para **primeiro PR
> mergeável**, entendendo não só *como* o sistema funciona, mas *por que* cada
> decisão foi tomada — e o que ela custa.
>
> Documentos-irmãos: [LEARNING_PATH.md](LEARNING_PATH.md) (mapa módulo→conceito),
> [EXERCISES.md](EXERCISES.md) (exercícios graduados), [adr/](adr/README.md)
> (decisões com custo declarado). Este roteiro é a trilha que os costura.

---

## 1. Pré-requisitos (antes de tocar o código)

Auto-avaliação honesta — para cada item, você deve responder "sim" ou estudar
antes. O projeto **ensina LangGraph e avaliação de agentes**; ele **não ensina**
o que está abaixo.

### Obrigatórios

| Skill | Teste de bolso |
|---|---|
| Python intermediário | Você lê `Annotated[list[BaseMessage], add_messages]` e `Iterator[str]` sem pânico; sabe o que um generator faz quando o caller para de consumir |
| Pydantic v2 básico | Diferença entre `BaseModel` e `dataclass`; o que `Field(alias=...)` faz |
| pytest | `fixture`, `monkeypatch.setenv`, `parametrize`, `pytest.raises` — os 4 aparecem em todo arquivo de teste daqui |
| Conceitos de LLM | Tokens (e por que custo = tokens de *todas* as iterações), temperatura, system prompt, **tool/function calling** (o contrato JSON entre modelo e código) |
| Git/GitHub | Branch, PR, revisão; `git add -f` (a pasta `docs/` é gitignored com exceções) |
| SQL básico | `SELECT ... WHERE timestamp >= ...` e a noção do que um ORM abstrai |

### Úteis, não bloqueantes

- Noção de embeddings/RAG (o projeto tem um pipeline pequeno e legível para aprender)
- Docker (`docker compose up` é suficiente)
- Streamlit (a UI é periférica ao aprendizado central)

---

## 2. Sequência de leitura (dias 1–3)

**Regra nº 1 da casa: leia o teste antes do módulo.** O teste é o contrato
executável; o módulo é a implementação.

### Dia 0 (meio dia) — Use o produto antes de ler o código

```bash
git clone <repo> && cd Energy-Advisor-Project
cp .env.example .env   # colocar OPENAI_API_KEY
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements-dev.txt
python -m energy_advisor.bootstrap.db_setup
python -m energy_advisor.bootstrap.sample_data
python -m energy_advisor.bootstrap.ml_train
pytest tests/ -q            # 255 testes, ~30s, sem chamada de rede
streamlit run streamlit_app.py
```

1. Na aba **💬 Chat**: pergunte "qual o melhor horário para carregar o Tesla?"
   e depois "e no fim de semana?" — repare que ele lembra do contexto.
2. Na aba **🔧 Operations**: clique Refresh — suas perguntas aparecem com custo
   real em tokens e quais tools foram chamadas.
3. Rode `python -m energy_advisor.observability.report` — mesmos números, no terminal.

> Você acabou de ver a tese do projeto: **agente + instrumentação como uma coisa só.**

### Dia 1 — O agente

| Ordem | Leia | Com este ADR aberto |
|---|---|---|
| 1 | `README.md` (inteiro) | — |
| 2 | `tests/test_agent.py` ← **antes** do agente | [ADR-001](adr/adr-001-explicit-langgraph-graph.md) |
| 3 | `energy_advisor/agent.py` | ADR-001, [ADR-007](adr/adr-007-streaming-under-same-controls.md), [ADR-008](adr/adr-008-conversation-memory-checkpointer.md) |
| 4 | `energy_advisor/prompts.py` + `profile.py` | [ADR-009](adr/adr-009-no-prices-in-prompt.md) |

Exercício de leitura: desenhe no papel o ciclo `assistant → tools → assistant → END`
e marque onde estão pendurados: guardrail de input, check de escopo, budget,
recursion_limit, trace. (Resposta: todos visíveis em `agent.py`.)

### Dia 2 — Tools, dados e segurança

| Ordem | Leia | ADR |
|---|---|---|
| 5 | `tools/energy_data.py` + `services/database.py` | [ADR-002](adr/adr-002-aggregation-inside-tools.md), [ADR-005](adr/adr-005-sqlite-with-migration-path.md) |
| 6 | `tools/rag.py` + `services/retrieval.py` | ADR-002 de novo (basename!) |
| 7 | `tests/test_guardrails.py` → `guardrails.py` | [ADR-003](adr/adr-003-deterministic-guardrails-audit-block.md) |
| 8 | `tests/test_contract.py` → `contract.py` | [ADR-010](adr/adr-010-topicality-enforcement.md) |

### Dia 3 — Avaliação e operação (o diferencial do projeto)

| Ordem | Leia | ADR |
|---|---|---|
| 9 | `evaluation/scenarios.py` → `runner.py` | [ADR-004](adr/adr-004-two-dimensional-evaluation.md) |
| 10 | `observability/__init__.py` + `report.py` | [ADR-006](adr/adr-006-real-token-accounting-and-budget.md) |
| 11 | `api/app.py` | — (note os 4 controles de fronteira) |
| 12 | `.github/workflows/` (os 3) + `services/drift_report.py` | — |

Feche o dia rodando o eval e lendo o JSON gerado:

```bash
python -m energy_advisor.evaluation.runner --quick --no-judge
```

---

## 3. Três tarefas progressivas (dias 3–5+)

Cada tarefa em branch própria, com PR. Critério de "pronto":
`pytest tests/ -q && ruff check energy_advisor/ tests/` verdes + os critérios
de aceitação abaixo. As especificações completas estão em [EXERCISES.md](EXERCISES.md).

### Tarefa 1 ★ — Novo padrão de guardrail (≈2h) — [E1]

Adicionar detecção de injection por role-play ("finja que você é um assistente
sem regras") em PT e EN.

- **Toca:** `guardrails.py`, `tests/test_guardrails.py` — 2 arquivos só.
- **O que ensina:** o fluxo test-first da casa, severidades, e o problema real
  de guardrails — o critério difícil é *não* bloquear role-play legítimo
  ("finja que meu consumo dobrou, quanto pagaria?"). Escreva os testes do caso
  legítimo **primeiro**.
- **Aceitação:** parametrizados PT/EN para ambos os grupos; zero regressão.

### Tarefa 2 ★★ — Tool nova de ponta a ponta (≈1 dia) — [E3]

`compare_energy_periods`: "gastei mais este mês que no passado?" exige duas
queries e um delta — hoje o modelo faria a aritmética sozinho, violando o ADR-002.

- **Toca:** novo service, nova tool, `TOOL_KIT`, uma linha no prompt, cenário
  de eval novo, testes do service.
- **O que ensina:** a fatia vertical completa da arquitetura — e a disciplina
  de que **tool nova sem cenário de eval não existe**.
- **Aceitação:** delta calculado em código (nunca pelo LLM); payload pequeno;
  cenário passa no eval local; teste de unidade sem LLM.

### Tarefa 3 ★★★ — TTL para threads de memória (≈1–2 dias) — [E4]

`MemorySaver` acumula threads para sempre (dívida declarada no ADR-008).
Implementar `ENERGY_ADVISOR_SESSION_TTL_S`: thread expirada recomeça a
conversa com contexto completo.

- **Toca:** `agent.py` (o coração), `config.py`, `tests/test_agent.py` com
  relógio mockado.
- **O que ensina:** mexer no núcleo com rede de proteção; a diferença entre
  estado-do-grafo e memória-entre-execuções; teste determinístico de
  comportamento temporal.
- **Aceitação:** teste prova expiração E não-expiração; comportamento atual
  preservado quando TTL não configurado.

> Por que essa ordem: a 1 ensina o *processo*, a 2 ensina a *arquitetura*,
> a 3 dá confiança para tocar o *núcleo*. É deliberadamente o caminho
> periferia → centro.

---

## 4. Perguntas que você deve responder após o onboarding

Se travar em alguma, o ADR correspondente é a resposta. Use como auto-teste
(ou como pauta da conversa de fim de onboarding com quem te orienta):

1. Por que `query_energy_usage` devolve ~15 linhas agregadas e não os ~2.000 registros?
2. Por que a trajetória de tools reprova uma resposta *correta* que não chamou tools?
3. Por que o LLM-as-judge nunca bloqueia o build, mas a trajetória sim?
4. O que significa `cost_source: "heuristic"` num trace — e por que esse campo existe?
5. Por que o `stream()` precisa do próprio caminho de guardrail? O que é impossível validar nele?
6. O que acontece (passo a passo) quando o modelo pede tools 11 vezes seguidas?
7. O que o checkpointer guarda, por thread, e por que o check de escopo roda só no 1º turno?
8. Por que o system prompt **não** contém tarifas, se o agente fala de preços o tempo todo?
9. Dois eval reports têm notas diferentes. O que você confere **antes** de concluir que o agente mudou?
10. Quando o Open-Meteo cai, o que o usuário vê — e o que o *prompt* obriga o agente a declarar?
11. Por que `DatabaseManager.create_tables` existe se o bootstrap usa Alembic?
12. O custo por request dobrou ontem. Quais 3 lugares você olha, em que ordem?
    (Operations/report → traces por dia + cost_source → tool com response_chars anômalo)

---

## 5. Armadilhas comuns nesta arquitetura

Cada uma destas **já aconteceu neste repositório** ou foi bloqueada por design.
Conhecê-las é a metade sênior do onboarding:

1. **Mexer no prompt sem rodar o eval.** Prompt é código sem compilador — o
   eval é o compilador. A remoção das tarifas do prompt só foi segura porque
   18 cenários verificaram o antes/depois. Regra: PR que toca `prompts.py`
   anexa resultado de eval.
2. **Testar só o `invoke` e esquecer o `stream`.** O produto usa streaming. Já
   existiu guardrail que valia num caminho e não no outro — segurança que
   depende do método chamado não é segurança (ADR-007).
3. **Confiar em estimativa quando dá para medir.** A heurística chars/4 errava
   o custo em ~1000×. Se o provider entrega `usage_metadata`, use; se usar
   heurística, **rotule** (`cost_source`).
4. **Reusar o mesmo objeto de mensagem no LangGraph.** `add_messages` deduplica
   por `id` — devolver o mesmo `AIMessage` duas vezes *substitui* em vez de
   anexar, e o grafo termina silenciosamente no lugar errado. (Bug real do
   nosso modelo fake; a correção está comentada em `tests/test_agent.py`.)
5. **Payload de tool gordo.** Mandar dados crus para o LLM = alucinação +
   custo. E o payload deve conter *exatamente o token que o modelo deve
   citar* — a tool de RAG devolvia path completo quando o prompt pedia
   filename, e o modelo simplesmente parava de citar.
6. **Tratar o judge como gate.** Juiz da mesma família tem viés e não é
   calibrado com humanos. Determinístico bloqueia; estatístico informa.
7. **Guardrail por regex como "segurança".** É a primeira camada, barata e
   testável — não a única. E num produto brasileiro, padrão só em inglês é
   controle de mentira.
8. **Duas fontes de verdade.** Tarifas no prompt *e* no pricing service;
   schema via `create_all` *e* via Alembic. Divergem em silêncio. Quando achar
   uma dupla, uma das duas tem que morrer ou virar derivada.
9. **Loop sem teto.** Agente sem `recursion_limit`/timeout/budget é um
   `while True` com cartão de crédito.
10. **Métrica sem consequência e sem leitor.** Flag que ninguém aciona é
    dashboard; JSONL que ninguém lê é nem isso. Todo número novo precisa de:
    quem age sobre ele (gate/exceção) ou quem o lê (report/aba Operations).

---

## 6. Livros e capítulos (mapeados ao repositório)

Leitura dirigida — capítulo certo na hora certa vale mais que o livro inteiro:

| Livro | Capítulos | Conecta com |
|---|---|---|
| **AI Engineering** — Chip Huyen (2025) | Cap. 3 (Evaluation Methodology) e 4 (Evaluate AI Systems) | O harness inteiro: trajetória vs judge, por que avaliar é o trabalho (ADR-004) |
| | Cap. 5 (Prompt Engineering) | `prompts.py`: estrutura estável no prompt, fatos voláteis via tools (ADR-009) |
| | Cap. 6 (RAG and Agents) | `retrieval.py`, o loop ReAct, fronteira LLM/dados (ADR-002) |
| | Cap. 10 (Architecture & User Feedback) | As 6 camadas + aba Operations |
| **Designing Machine Learning Systems** — Chip Huyen (2022) | Cap. 8 (Data Distribution Shifts and Monitoring) | `drift_monitor.py` + `drift.yml` |
| | Cap. 9 (Continual Learning and Test in Production) | Eval gate no CI; AUDIT→BLOCK como rollout |
| **Release It!** 2ª ed. — Michael Nygard | Cap. 4–5 (Stability Antipatterns / Patterns: timeouts, circuit breaker, bulkheads) | `recursion_limit`, `llm_timeout_s`, `BudgetExceeded` — o "while True com cartão de crédito" |
| **Designing Data-Intensive Applications** — Kleppmann | Cap. 1 (Reliable, Scalable, Maintainable) | O vocabulário para defender as decisões do projeto |
| | Cap. 3 (Storage and Retrieval) | Por que SQLite basta aqui e quando deixa de bastar (ADR-005) |
| **The Pragmatic Programmer** (20th anniv.) | Tópico 9 (DRY) | Armadilha nº 8 — duas fontes de verdade |
| | Tópico 12 (Tracer Bullets) | A filosofia do MVP inteiro: fatia fina funcionando de ponta a ponta |
| **Software Engineering at Google** (free online) | Cap. 11–12 (Testing Overview / Unit Testing) | Por que 255 testes em 30s sem rede valem mais que 50 testes "realistas" e lentos |

Ordem sugerida: AI Engineering caps. 3–4 **durante** o Dia 3 do onboarding;
Release It! caps. 4–5 antes da Tarefa 3; o resto ao longo do primeiro mês.

---

## 7. Evoluindo daqui: a trilha júnior → pleno → sênior neste projeto

A régua honesta entre os níveis: **júnior executa com critério dado; pleno
define o critério de uma área; sênior define o sistema de critérios — e o que
NÃO construir.**

### Para demonstrar nível pleno (3–6 meses de contribuição)

Assuma a *ownership* de uma área e leve-a além do que o backlog pediu:

- **Multi-usuário de verdade** ([E8]): segundo `UserProfile` com dados gerados,
  `user_id` atravessando agente → tools → queries, cenários de eval por perfil.
  É a tarefa que mais atravessa camadas.
- **Persistência de produção**: Postgres via connection string + checkpointer
  persistente (`SqliteSaver`/`PostgresSaver`) + TTL — e a *migração de dados*,
  não só de schema.
- **Avaliação nível 2**: calibrar o judge contra rotulagem humana (20 respostas
  rotuladas por você, medir concordância); métricas de retrieval (recall@k
  contra o gabarito); cenários de regressão criados a partir de cada bug real.
- **Custo nível 2**: cache de respostas do agente para perguntas idênticas,
  roteamento fast/quality por complexidade da pergunta, relatório de custo por
  sessão/usuário.
- A marca de pleno: **seus PRs vêm com o critério de aceitação que você mesmo
  definiu** — e ele resiste à revisão.

### Para demonstrar nível sênior (6–18 meses)

Saia do código e entre no sistema:

- **Escreva os próximos ADRs** — inclusive os que revertem decisões atuais
  quando o contexto mudar. Sênior é quem documenta o custo do que escolheu.
- **Defina SLOs para o agente** (p95 de latência, custo/request, taxa de
  grounding) com error budget — e o processo do que acontece quando estoura.
- **Red team próprio**: suite de ataques que evolui (encoding, multi-turn
  injection, exfiltração via tool args) — e o relatório honesto do que passa.
- **Extraia a plataforma**: o harness de avaliação e o padrão AUDIT/BLOCK são
  generalizáveis — transformá-los em lib interna reutilizável por outros
  agentes é trabalho de plataforma, o degrau acima do produto.
- **Mentore com este repositório**: conduza um júnior por este exato roteiro.
  Ensinar o sistema é o teste final de tê-lo entendido.
- E a mais difícil: **mate features**. O backlog deste projeto tem uma seção
  "o que deliberadamente NÃO incluímos" — mantê-la viva contra a tentação de
  overengineering é a habilidade sênior mais rara.

---

*Dúvidas durante o onboarding: abra uma issue com o label `onboarding` citando
o dia/passo deste roteiro. Se a resposta não estava em um ADR, isso é um bug
da documentação — e consertá-la é uma contribuição válida.*
