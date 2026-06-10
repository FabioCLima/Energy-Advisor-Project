# Learning Path — EcoHome como curso de AI Engineering

> Para engenheiros de IA juniores usando este repositório como material de
> estudo. Cada linha conecta **um módulo do código** a **um conceito da
> disciplina** e à **pergunta de entrevista** que esse conceito responde.
> Leia o código com o ADR correspondente aberto ao lado ([índice](adr/README.md)).

## Trilha sugerida (ordem de leitura)

### Nível 1 — O agente

| Módulo | Conceito | Pergunta de entrevista que isso responde | ADR |
|---|---|---|---|
| `energy_advisor/agent.py` (grafo) | ReAct como máquina de estados explícita: nós, arestas condicionais, estado mínimo | "Como funciona um agente de tool-calling por dentro, sem a mágica do framework?" | [001](adr/adr-001-explicit-langgraph-graph.md) |
| `energy_advisor/tools/` + `services/` | Fronteira LLM/dados: tools retornam agregados, nunca dados crus; cálculo determinístico fica em código | "Como você evita que o LLM alucine números?" | [002](adr/adr-002-aggregation-inside-tools.md) |
| `energy_advisor/prompts.py` + `profile.py` | Prompt = estrutura estável + política; fatos voláteis vêm de tools; persona é objeto, não prosa | "O que pertence ao system prompt e o que não pertence?" | [009](adr/adr-009-no-prices-in-prompt.md) |
| `energy_advisor/agent.py` (checkpointer) | Estado do grafo (uma execução) vs memória entre execuções (thread do checkpointer) | "Como você implementaria memória de conversa num agente?" | [008](adr/adr-008-conversation-memory-checkpointer.md) |

### Nível 2 — Confiabilidade

| Módulo | Conceito | Pergunta de entrevista que isso responde | ADR |
|---|---|---|---|
| `energy_advisor/guardrails.py` | Camadas de defesa; severidade; rollout AUDIT→BLOCK; por que regex é a primeira camada e não a única | "Como você protege um agente contra prompt injection e vazamento de PII?" | [003](adr/adr-003-deterministic-guardrails-audit-block.md) |
| `energy_advisor/agent.py` (`stream`) | Streaming muda o modelo de segurança: não existe "resposta final" para validar antes de enviar | "Quais riscos o streaming introduz que o invoke não tem?" | [007](adr/adr-007-streaming-under-same-controls.md) |
| `energy_advisor/observability.py` | Custo de agente = loop + contexto acumulado, não a resposta final; proveniência de métricas (`cost_source`) | "Como você controlaria o custo de um agente em produção?" | [006](adr/adr-006-real-token-accounting-and-budget.md) |
| `energy_advisor/agent.py` (`recursion_limit`, `_enforce_cost_budget`) | Limites operacionais: iteração máxima, timeout, budget que interrompe | "O que acontece se o modelo entrar em loop de tools?" | [006](adr/adr-006-real-token-accounting-and-budget.md) |

### Nível 3 — Avaliação e operação

| Módulo | Conceito | Pergunta de entrevista que isso responde | ADR |
|---|---|---|---|
| `energy_advisor/evaluation/` | Trajetória (determinística, gate) vs judge (informativa, não-gate); viés de família do judge | "Como você avalia um agente? O que entra no CI?" | [004](adr/adr-004-two-dimensional-evaluation.md) |
| `evaluation/runner.py` (`artifact_versions`) | Reprodutibilidade = versionar o trio modelo + prompt + dados de eval | "Dois evals deram notas diferentes — o que você verifica primeiro?" | [004](adr/adr-004-two-dimensional-evaluation.md) |
| `.github/workflows/eval.yml` | Eval como gate: quando roda (label/semanal), o que bloqueia, quanto custa | "Você rodaria LLM em CI? Como decide?" | [004](adr/adr-004-two-dimensional-evaluation.md) |
| `tests/test_agent.py` | Testar a *máquina* com modelo fake e determinístico; a *qualidade* é trabalho do eval harness | "Como você testa código que depende de um LLM?" | [001](adr/adr-001-explicit-langgraph-graph.md) |
| `energy_advisor/api/app.py` | Fronteira de serviço: auth, rate limit, erros sanitizados com request_id, mapeamento de exceções para status HTTP | "O que falta para esse agente virar um serviço?" | — |
| `services/database.py` + `migrations/` | ORM como ponto de troca de banco; schema versionado por migração | "Como você evoluiria o schema sem quebrar o ambiente de ninguém?" | [005](adr/adr-005-sqlite-with-migration-path.md) |
| `services/drift_monitor.py` | Drift de dados e de erro de forecast: baseline vs janela atual | "Como você detecta que o modelo degradou em produção?" | — |

## Como estudar este repositório

1. **Leia o teste antes do módulo.** `tests/test_agent.py` explica o contrato
   do agente melhor que qualquer doc — e mostra como isolar o LLM.
2. **Procure o padrão repetido.** AUDIT/BLOCK aparece em guardrails *e* em
   budget; `data_source`/`fallback_used` aparece em weather *e* em ANEEL.
   Padrões reutilizados são a assinatura de uma arquitetura, não de um script.
3. **Pergunte "o que fecha o ciclo?"** Para cada métrica ou check, identifique
   o que *age* sobre ela (gate, exceção, 429). Métrica sem consequência é
   dashboard, não controle.
4. **Faça os [exercícios](EXERCISES.md)** — cada um é um item real do backlog,
   com critérios de aceitação.
