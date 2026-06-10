# Backlog — MVP Profissional, Auditável e Didático

> **Origem:** revisão técnica sênior do repositório (junho/2026), após a conclusão do
> backlog anterior ([mlops_observability_backlog.md](mlops_observability_backlog.md)).
> **Público:** o autor (DS em transição para AI Engineer) e engenheiros de IA juniores
> que usarão este repositório como fonte de estudo.

> **STATUS (10/jun/2026):** EPICs A–D **concluídos e publicados** (commits
> `342c664..2f77feb`): integridade, auditabilidade, evolução e didática. Gate de
> avaliação verde no CI; eval completo 12/12 com `cost_source=usage_metadata`.
> A fase atual é o **EPIC E (Profundidade)** — seção 8, criada pela reavaliação
> pós-implementação: o gap mudou de *"promete e não faz"* para *"faz, mas raso"*.

---

## 1. Racional

O projeto já cumpre o objetivo da fase anterior: todas as camadas de um produto de IA
existem (agente, tools, eval, observabilidade, guardrails, drift, Docker, CI). O
diagnóstico da revisão identificou o padrão que separa o estado atual de um MVP
profissional:

> **As features de confiabilidade existem como demonstração, mas não fecham o ciclo de
> enforcement.** O quality gate existe mas não bloqueia o CI; o guardrail existe mas não
> cobre o caminho de streaming; o budget de custo existe mas é só uma flag num JSONL.

Isso define o tema único desta fase: **fechar ciclos**. Cada item do backlog transforma
um mecanismo demonstrativo em um mecanismo que *age* — e, como segundo objetivo,
documenta o "porquê" de forma que um júnior aprenda o conceito ao ler o diff.

### Critério de priorização

1. **P0 — Integridade:** o código faz menos do que o README afirma, ou um caminho de
   produção (streaming) escapa dos controles. Quebra de confiança = bloqueia tudo.
2. **P1 — Auditabilidade:** fechar o loop de enforcement (CI gate, budget, versionamento
   de prompt). É o que torna o MVP "auditável" de verdade.
3. **P2 — Evolução:** multi-turno, multi-usuário, robustez. Importante, mas não bloqueia
   o selo de "MVP profissional".
4. **D — Didática:** transversal; transforma o repo em material de estudo (ADRs,
   learning path, exercícios).

### Regra de ouro desta fase

**Não adicionar nenhuma feature nova antes de fechar os P0.** Um repositório de estudo
que promete o que não cumpre ensina o hábito errado.

---

## 2. EPIC A — Integridade (P0)

### A1. Guardrail de saída e traces no caminho de streaming

- **Problema:** `EnergyAdvisorAgent.invoke()` valida a saída com
  `ensure_safe_model_output` (`agent.py:173`), mas `stream()` (`agent.py:195-230`)
  entrega tokens direto ao cliente sem validação e sem gravar trace. O chat do
  Streamlit e o endpoint SSE (`api/app.py:111`) usam exatamente esse caminho.
  Segurança que depende de qual método o caller escolheu não é segurança.
- **Mudança proposta:** validar em janela acumulada — bufferizar a resposta durante o
  streaming e rodar `validate_model_output` sobre o acumulado a cada chunk (regex é
  barato); ao detectar violação, interromper o stream com evento de erro SSE. Ao final
  do stream, gravar o `AgentTrace` igual ao `invoke()`.
- **Critérios de aceitação:**
  - Teste: resposta contendo CPF/segredo é bloqueada tanto via `invoke` quanto via `stream`.
  - Teste: um stream completo gera exatamente um registro em `agent_traces.jsonl`.
  - O evento de erro SSE segue o mesmo contrato JSON já usado (`{"error": ..., "status_code": 400}`).
- **O que o júnior aprende:** por que streaming muda o modelo de segurança (não existe
  "resposta final" para validar antes de enviar) e o trade-off buffer-tudo vs. validação
  incremental.
- **Esforço:** M

### A2. Suíte de testes do agente (`tests/test_agent.py`)

- **Problema:** 140 testes cobrem serviços, tools e guardrails, mas **não existe teste
  do agente** — o grafo, o roteamento condicional (`route_after_assistant`),
  `_build_messages`, o fluxo de erro que grava trace. É a peça central do projeto e a
  única sem rede de proteção.
- **Mudança proposta:** criar um `FakeChatModel` (ou usar `GenericFakeChatModel` do
  `langchain_core.language_models.fake_chat_models`) que devolve sequências roteirizadas
  de `AIMessage` com/sem `tool_calls`. Injetar via parâmetro no construtor (exige
  extrair a criação do `ChatOpenAI` para um factory injetável — refactor pequeno e
  saudável).
- **Critérios de aceitação:**
  - Testes sem API key e sem rede cobrem: (a) resposta direta sem tool; (b) ciclo
    tool→assistant→END; (c) guardrail de input bloqueando antes do grafo; (d) erro no
    grafo gera trace com `success=false`.
  - Cobertura de `agent.py` ≥ 85%.
- **O que o júnior aprende:** como testar um sistema orientado a LLM de forma
  determinística — separar "a lógica do grafo" (testável) de "a qualidade do modelo"
  (avaliada pelo eval harness, não por unit test).
- **Esforço:** M

### A3. Trajetória ordenada — alinhar código e README

- **Problema:** o README promete "the **ordered sequence** of tool calls", mas o runner
  só checa pertinência: `missing_tools = [t for t in scenario.required_tools if t not in
  called_tools]` (`evaluation/runner.py:129`). Agente que chama as tools na ordem errada
  passa. Num projeto cujo argumento central é disciplina de avaliação, a métrica
  principal estar mais fraca que o documentado é a falha mais grave de auditoria.
- **Mudança proposta:** implementar verificação de subsequência ordenada
  (`required_tools` deve aparecer em `called_tools` na ordem, permitindo intercalações).
  Adicionar campo `order_matters: bool = True` por cenário, para os casos em que ordem
  realmente não importa. Reportar `trajectory_pass` e `order_pass` separados no JSON.
- **Critérios de aceitação:**
  - Teste: `required=[A, B]`, `called=[B, A]` → falha quando `order_matters=True`,
    passa quando `False`.
  - README e código dizem a mesma coisa (atualizar a seção *Evaluation*).
- **O que o júnior aprende:** avaliação de agente é contrato — a métrica documentada e a
  métrica computada precisam ser idênticas, senão o eval vira teatro.
- **Esforço:** S

### A4. Contabilidade real de tokens e custo

- **Problema:** `estimate_llm_cost` usa chars/4 sobre `pergunta + resposta final`
  (`observability.py:88-97`), ignorando system prompt (~600 tokens), mensagens de tool e
  todas as iterações do loop ReAct — que são a maior parte do custo de um agente. O
  "cost control" do README mede a parte errada. A tabela de preços é hardcoded.
- **Mudança proposta:** somar `usage_metadata` (`input_tokens`/`output_tokens`) de cada
  `AIMessage` do resultado — o LangChain já entrega isso de graça em cada resposta da
  OpenAI. Manter chars/4 apenas como fallback rotulado (`cost_source: "usage_metadata" |
  "heuristic"`). Mover a tabela de preços para `config.py` (env-overridable).
- **Critérios de aceitação:**
  - Trace de uma execução com 2 iterações de tool reporta tokens ≥ 4× a heurística antiga
    (validar com fixture gravada).
  - Campo `cost_source` presente em todo trace e no eval report.
  - Eval report e dashboard usam a mesma função.
- **O que o júnior aprende:** onde o custo de um agente realmente está (loop + contexto
  acumulado, não a resposta final) e por que estimativas precisam declarar a própria
  proveniência.
- **Esforço:** S–M

### A5. Limites operacionais no loop ReAct

- **Problema:** nenhum `recursion_limit` explícito, sem timeout de LLM, sem retry com
  backoff. Um modelo que insiste em chamar tools roda até o default implícito do
  LangGraph estourar com erro críptico — e o budget de custo nunca interrompe nada.
- **Mudança proposta:**
  - `recursion_limit` explícito vindo de `Settings` (ex.:
    `ENERGY_ADVISOR_MAX_AGENT_ITERATIONS`, default 10), passado no `config` do
    `graph.invoke/stream`.
  - `timeout` e `max_retries` no construtor do `ChatOpenAI` (parâmetros nativos).
  - Quando o limite estoura, devolver mensagem honesta ao usuário ("não consegui
    concluir com os dados disponíveis") em vez de stack trace.
- **Critérios de aceitação:**
  - Teste com FakeChatModel que sempre pede tool: execução termina no limite com
    mensagem controlada e trace `success=false, error="recursion_limit"`.
  - Settings documentados no `.env.example`.
- **O que o júnior aprende:** agente sem limite de iteração é um loop `while True` com
  cartão de crédito.
- **Esforço:** S

---

## 3. EPIC B — Auditabilidade (P1)

### B1. Avaliação no CI com gate de regressão

- **Problema:** o CI roda lint + pytest com `OPENAI_API_KEY: test-key-placeholder`
  (`.github/workflows/ci.yml:41`). O eval harness — o diferencial do projeto — nunca
  roda automaticamente; `quality_gates_pass` existe mas não bloqueia nada.
- **Mudança proposta:** workflow separado `eval.yml`:
  - Disparo: manual (`workflow_dispatch`) + agendado semanal + PRs com label `eval`.
  - Roda `--quick --no-judge` (4 cenários, sem judge = barato e determinístico o
    suficiente para gate).
  - Falha se `trajectory_pass_rate < 1.0` ou `errors > 0`.
  - Publica o report como artifact e o resumo no job summary do GitHub.
  - Requer `OPENAI_API_KEY` real via GitHub Secrets (documentar custo estimado por run
    no próprio workflow).
- **Critérios de aceitação:** um PR com label `eval` que quebre uma trajetória fica
  vermelho; o artifact contém o JSON completo.
- **O que o júnior aprende:** a diferença entre "ter eval" e "eval como gate" — e o
  trade-off custo/cobertura de rodar LLM em CI.
- **Esforço:** M

### B2. Versionamento de prompt e contrato nos artefatos de avaliação

- **Problema:** o eval report registra modelo e cenários, mas não *qual* system prompt e
  *qual* contrato produziram aquele resultado. Sem isso, comparar dois reports do
  `eval_history.jsonl` não é auditável — o prompt pode ter mudado entre eles.
- **Mudança proposta:** adicionar ao report e ao history: hash SHA-256 (curto) de
  `SYSTEM_INSTRUCTIONS`, `AgentContract.to_dict()` serializado, e o commit hash do git
  (se disponível). O `AgentContract` já foi desenhado para isso ("can be serialised and
  versioned alongside the model" — `contract.py:8`); este item cumpre a promessa.
- **Critérios de aceitação:** dois runs com prompts diferentes geram `prompt_hash`
  diferentes no history; teste cobre a serialização.
- **O que o júnior aprende:** reprodutibilidade em sistemas de LLM = versionar o trio
  (modelo, prompt, dados de eval), não só o código.
- **Esforço:** S

### B3. Enforcement de budget (de flag para ação)

- **Problema:** `over_cost_budget` e `over_latency_budget` são gravados no JSONL e
  nada mais acontece. "Cost control" sem controle.
- **Mudança proposta:** política configurável `ENERGY_ADVISOR_BUDGET_MODE` com a mesma
  semântica já estabelecida pelos guardrails (`AUDIT` default | `BLOCK`): em `BLOCK`,
  requisição que estoure o budget de custo *projetado* (com A4 implementado, o custo
  acumulado é conhecido durante o loop) é interrompida com erro 429/`BudgetExceeded`.
  Reutilizar o padrão `AUDIT/BLOCK` deliberadamente — consistência conceitual entre
  guardrails de segurança e guardrails operacionais.
- **Critérios de aceitação:** teste em modo BLOCK interrompe execução cara; modo AUDIT
  mantém comportamento atual; API devolve 429 com mensagem clara.
- **O que o júnior aprende:** o padrão "observe primeiro (AUDIT), aplique depois
  (BLOCK)" como estratégia de rollout de qualquer controle operacional.
- **Esforço:** M

### B4. Higiene da API (erros, auth mínima, rate limit)

- **Problema:** `detail=str(exc)` em 500 vaza internals (`api/app.py:95`); CORS `*`;
  sem autenticação nem rate limit. Para MVP demo é aceitável — mas então precisa estar
  *declarado*, e o mínimo viável de produção precisa existir atrás de flag.
- **Mudança proposta:**
  - 500 com mensagem genérica + `request_id`; o erro real vai para o log (correlação
    via request_id — a infraestrutura já existe).
  - API key opcional via header `X-API-Key` (`ENERGY_ADVISOR_API_KEY_REQUIRED=true`),
    validada por dependency do FastAPI.
  - Rate limit simples em memória (ex.: `slowapi`) — documentado como "por instância;
    produção real usaria Redis".
  - CORS restrito por env var, com `*` apenas como default de demo documentado.
- **Critérios de aceitação:** testes de API cobrem 401 sem key (quando exigida), 429 ao
  estourar limite, e 500 sem stack trace no corpo.
- **O que o júnior aprende:** a fronteira HTTP é onde o "projeto de agente" vira
  "serviço" — e quais são os 4 itens mínimos inegociáveis dessa fronteira.
- **Esforço:** M

### B5. Higiene do repositório

- **Problema:** três `eval_report*.json` versionados na raiz contêm respostas completas
  do modelo (ruído + risco de desatualização permanente); flag
  `aneel_allow_insecure_ssl` é um smell de segurança; `docs/` mistura material de
  entrevista pessoal com documentação do projeto.
- **Mudança proposta:**
  - Mover reports para `data/eval_reports/` (gitignored), manter **um** report de
    exemplo curado em `docs/examples/eval_report_sample.json`.
  - Remover `aneel_allow_insecure_ssl` ou documentar inline por que existe (se o
    endpoint da ANEEL tem cadeia SSL quebrada, dizer isso no código).
  - Separar `docs/` em `docs/project/` (arquitetura, ADRs, backlog) e
    `docs/learning/` (guias de estudo, material de entrevista). Remover o arquivo
    `*:Zone.Identifier` (artefato de download do Windows).
- **Critérios de aceitação:** `git ls-files` sem reports de eval na raiz; índice
  `docs/README.md` próprio (hoje é cópia do README raiz).
- **O que o júnior aprende:** repositório é interface — o que está versionado comunica
  o que o autor considera fonte de verdade.
- **Esforço:** S

---

## 4. EPIC C — Evolução de produto (P2)

### C1. Guardrails bilíngues (PT-BR primeiro)

- **Problema:** os padrões de prompt injection são só em inglês (`guardrails.py:40-45`)
  num produto cujo usuário fala português. "Ignore as instruções anteriores" passa
  ileso. É também o exemplo didático perfeito de que guardrail por regex é uma camada
  fraca por construção.
- **Mudança proposta:** adicionar padrões PT-BR equivalentes (ignorar/revelar/burlar +
  variações); documentar no módulo a limitação estrutural do regex e o caminho de
  evolução (classificador dedicado / moderation endpoint) — o docstring vira material
  de estudo.
- **Critérios de aceitação:** testes parametrizados PT/EN para cada categoria de injection.
- **Esforço:** S

### C2. Memória de conversa (checkpointer)

- **Problema:** o agente é single-turn — `AgentState` é reconstruído a cada `invoke`
  (`agent.py:139-156`); o "chat" não tem memória real. Para um advisor, follow-ups
  ("e se eu carregar só no fim de semana?") são o caso de uso natural.
- **Mudança proposta:** `MemorySaver` (in-memory) do LangGraph como checkpointer,
  `thread_id` derivado do `session_id` que a API já recebe. SQLite checkpointer como
  evolução documentada. Guardrails de input continuam por mensagem.
- **Critérios de aceitação:** teste de dois turnos onde o segundo referencia o primeiro;
  endpoint da API aceita `session_id` e mantém contexto.
- **O que o júnior aprende:** a distinção estado-do-grafo vs. memória-entre-execuções, e
  onde o LangGraph resolve isso (checkpointer, não prompt).
- **Esforço:** M

### C3. Persona desacoplada (caminho para multi-usuário)

- **Problema:** João está hardcoded no prompt, nos dados e nas tarifas
  (`prompts.py:4-12`). Pior: as tarifas no prompt duplicam a fonte de verdade do
  `pricing.py` — o prompt diz "não fabrique preços" e fornece preços que podem divergir
  do serviço.
- **Mudança proposta (em dois passos):**
  1. **Remover números do prompt** (tarifas saem; o prompt instrui a *sempre* obter
     preços via `get_electricity_prices`). Fonte de verdade única. Rodar o eval antes e
     depois para medir o impacto — este é o experimento didático mais valioso do backlog.
  2. **Extrair `UserProfile`** (Pydantic) com persona, dispositivos e localização;
     prompt renderizado por template a partir do profile; João vira o profile default.
- **Critérios de aceitação:** nenhuma tarifa literal em `prompts.py`; eval mantém
  trajectory pass 12/12 após a mudança (se cair, o resultado é registrado e analisado
  no ADR correspondente — falha documentada também é entregável).
- **Esforço:** M–L

### C4. Fallbacks transparentes

- **Problema:** quando Open-Meteo falha, o fallback sintético responde com a mesma cara
  de dado real. O agente pode recomendar com base em irradiância inventada sem avisar.
- **Mudança proposta:** toda resposta de tool com fallback carrega `data_source:
  "open-meteo" | "synthetic_fallback"`; o prompt instrui a declarar a limitação quando
  `synthetic_fallback` (a seção "Assumptions & limitations" já existe na estrutura de
  resposta). Mesmo padrão já usado pelo `aneel_client` (`fallback_used`) — generalizar.
- **Critérios de aceitação:** teste com Open-Meteo mockado como indisponível: a resposta
  final menciona a limitação; trace registra o `data_source`.
- **Esforço:** S
- **Nota:** este é o conceito de *provenance* que o projeto já acerta no ANEEL client —
  o item apenas aplica o próprio padrão da casa de forma consistente.

### C5. Migrações de schema (Alembic)

- **Problema:** `Base.metadata.create_all` não evolui schema existente. Primeiro
  `ALTER TABLE` necessário vai doer.
- **Mudança proposta:** Alembic com migração inicial baseline. Escopo mínimo — o valor
  é o júnior ver onde a peça se encaixa, não dominar Alembic.
- **Esforço:** S

---

## 5. EPIC D — Didática (transversal)

### D1. ADRs — Architecture Decision Records

- **Problema:** as decisões e trade-offs estão espalhados entre README e docstrings; um
  júnior não consegue distinguir "decisão deliberada" de "ficou assim".
- **Mudança proposta:** `docs/project/adr/` com um ADR curto (contexto → decisão →
  consequências) por decisão estrutural. Backlog inicial de ADRs:
  - ADR-001: LangGraph explícito vs. `create_react_agent`
  - ADR-002: agregação dentro da tool (fronteira LLM/dados)
  - ADR-003: guardrails determinísticos + padrão AUDIT/BLOCK
  - ADR-004: avaliação em duas dimensões (trajetória + judge) e limites do judge
  - ADR-005: SQLite e o caminho de migração
  - Novos ADRs para cada item P0/P1 deste backlog ao ser implementado.
- **Critérios de aceitação:** template fixo; cada ADR ≤ 1 página; README aponta para o índice.
- **Esforço:** S por ADR (escrever junto com o item correspondente)

### D2. Learning path por módulo

- **Mudança proposta:** um `docs/learning/LEARNING_PATH.md` que mapeia módulo → conceito
  de AI Engineering → pergunta de entrevista associada. Ex.: `observability.py` →
  "custo de agente = loop, não resposta" → "como você controlaria custo de um agente em
  produção?". Consolida os guias de entrevista já existentes em vez de criar mais um.
- **Esforço:** M (uma vez), S (manutenção)

### D3. Exercícios guiados como issues

- **Mudança proposta:** transformar 5–8 itens deste backlog (os S, principalmente C1,
  C4, B2, B5) em GitHub issues com contexto, arquivos-alvo, critérios de aceitação e
  dica — formato "good first issue". O repositório vira material de prática, não só de
  leitura.
- **Esforço:** S

---

## 6. Sequenciamento sugerido

| Fase | Itens | Tema | Resultado verificável |
|---|---|---|---|
| 1 | A3, A2 | "O que afirmamos é verdade" | README == código; agente testado sem API key |
| 2 | A1, A5 | "Nenhum caminho escapa dos controles" | Stream protegido e rastreado; loop limitado |
| 3 | A4, B2 | "Os números são reais e reproduzíveis" | Tokens reais; reports com prompt_hash |
| 4 | B1, B3 | "Os gates agem" | CI vermelho em regressão; budget interrompe |
| 5 | B4, B5 | "A fronteira é de serviço" | API com auth/limites; repo limpo |
| 6 | C1–C5 | Evolução de produto | Multi-turno, persona desacoplada, fallback transparente |
| — | D1–D3 | Contínuo: cada item fecha com seu ADR | Repo navegável como curso |

**Definition of Done do MVP auditável** (fim da fase 5):

1. Todo caminho de execução (invoke, stream, API) passa pelos mesmos guardrails e gera trace.
2. Toda métrica publicada no README é computada exatamente como descrita.
3. Todo número de custo/token tem proveniência declarada (`usage_metadata` ou heurística rotulada).
4. Todo eval report identifica modelo + prompt + contrato + commit que o produziram.
5. Existe pelo menos um gate automatizado que fica vermelho quando o agente regride.
6. Cada decisão estrutural tem um ADR de uma página.

---

## 7. EPIC E — Profundidade (Fase 3, pós-reavaliação)

> Origem: reavaliação sênior de 10/jun/2026, após os EPICs A–D. A barra de
> integridade passou; estes itens são a barra seguinte, medidos contra a
> promessa central do README ("MLE-grade evaluation and production-oriented
> controls"). **E1–E3 são must-have**; E4–E5 são evolução documentada.

### E1. Avaliação além do caminho feliz (must-have)

- **Problema:** os 12 cenários testam perguntas bem-comportadas com dados
  presentes. "MLE-grade evaluation" exige os casos que machucam — e a sessão de
  10/jun provou o valor disso por acidente: com o banco vazio, o agente foi
  honesto ("não consegui acessar os dados") e a trajetória reprovou. Esse
  comportamento correto sob falha hoje não tem cenário fixo que o proteja.
- **Mudança proposta:**
  1. **Cenários adversariais/negativos**: pergunta fora de escopo (ex.
     "recomende ações da bolsa"), tentativa de injection como cenário, e tool
     falhando de propósito (fixture com DB vazio) com asserção de honestidade —
     a resposta deve declarar a limitação, não inventar números.
  2. **Cenários multi-turno**: a memória (C2) tem zero cobertura de eval;
     mínimo de 2 cenários com follow-up que só faz sentido com contexto
     ("e no fim de semana?").
  3. **Avaliação do RAG**: medir se o documento recuperado era o relevante
     (gabarito doc-esperado por pergunta, os 5 docs permitem isso) e checagem
     de citação — toda dica citada deve existir no corpus.
- **Critérios de aceitação:** novas categorias separadas no report
  (`adversarial`, `multi_turn`, `rag`); cenário de falha de tool passa quando o
  agente declara a limitação e reprova quando inventa números; gate do CI
  continua quick (cenários novos rodam no full).
- **O que o júnior aprende:** avaliar um agente é majoritariamente avaliar
  como ele falha — o caminho feliz é a parte fácil.
- **Esforço:** M–L

### E2. Enforcement de topicalidade no AgentContract (must-have)

- **Problema:** `contract.py` declara `scope` e `allowed_topics` e o README o
  vende como "explicit, auditable scope" — mas nada verifica topicalidade.
  Pergunta sobre criptomoedas passa pelos guardrails (não é injection, não é
  PII) e chega ao modelo. Contrato sem check é o último resíduo da classe
  "decorativo" que esta fase existiu para eliminar.
- **Mudança proposta:** check de escopo determinístico (keywords/heurística
  por domínio de energia) rodando no padrão da casa — `AUDIT` primeiro (logar
  taxa de fora-de-escopo real), `BLOCK` depois, com mensagem que redireciona
  ("posso ajudar com energia, consumo, solar..."). Evolução documentada:
  classificador leve.
- **Critérios de aceitação:** fora-de-escopo claro é detectado; perguntas de
  energia legítimas (incluindo as 12 do eval) passam sem falso positivo;
  violação registrada no trace com severidade própria; cenário adversarial de
  E1 usa este check.
- **O que o júnior aprende:** escopo é guardrail de produto, não de segurança
  — e o rollout AUDIT→BLOCK serve para qualquer controle novo.
- **Esforço:** M

### E3. Alembic como único caminho de schema (must-have)

- **Problema:** C5 entregou as migrations pela metade do ciclo: o bootstrap
  (`db_setup`, entrypoint Docker) ainda cria schema via ORM
  `create_tables`/`create_all`, e o Alembic existe ao lado. Hoje coincidem; na
  primeira alteração de schema, divergem silenciosamente.
- **Mudança proposta:** bootstrap roda `alembic upgrade head` em vez de
  `create_all`; `create_tables` permanece apenas para os fixtures de teste
  (documentado no docstring). Entrypoint Docker incluído.
- **Critérios de aceitação:** ambiente novo provisiona schema exclusivamente
  via migration; teste de smoke do container (ou do bootstrap) prova que
  `alembic_version` existe na tabela após o boot.
- **Esforço:** S

### E4. Drift como processo agendado (evolução, não must-have)

- **Problema:** o README promete "drift checks"; `drift_monitor.py` existe e é
  testado, mas nada o executa — mesma classe de gap que o eval tinha antes do
  B1, numa camada menos crítica.
- **Mudança proposta:** workflow semanal (`drift.yml`, espelhando o eval.yml)
  que roda o monitor sobre janela baseline vs atual e publica o JSON como
  artifact; threshold violado = job amarelo/aviso, não bloqueio.
- **Esforço:** S–M

### E5. Leitor de traces (evolução, não must-have)

- **Problema:** o JSONL de observabilidade acumula números reais sem
  consumidor: nenhum resumo de custo/dia, erro, p95 de latência; sem rotação.
  Métrica sem leitor não informa decisão nenhuma.
- **Mudança proposta:** `python -m energy_advisor.observability.report`
  (agregados por dia/modelo/cost_source) e/ou aba no Streamlit; rotação simples
  por tamanho.
- **Esforço:** M

## 8. O que este backlog deliberadamente NÃO inclui

Para proteger o escopo de MVP (anti-overengineering, mantendo a filosofia do projeto):

- **Kubernetes, service mesh, IaC** — Docker + App Runner já demonstram o conceito.
- **Postgres/Redis reais** — os pontos de troca estão documentados; trocar não ensina nada novo.
- **Fine-tuning ou modelos próprios** — fora da tese do projeto (orquestração + grounding).
- **Frontend dedicado** — Streamlit cumpre a função de superfície de demo.
- **Guardrails por ML/LLM** — documentados como evolução no ADR-003, não implementados;
  a versão regex com limitação declarada tem mais valor didático que uma dependência a mais.
