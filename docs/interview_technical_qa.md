# Perguntas Técnicas — EcoHome Energy Advisor

> Três perguntas que qualquer recrutador técnico vai fazer.
> Responda com o seu projeto, não com definições genéricas.

---

## Ponto Central a Internalizar

**Você é o engenheiro do sistema em torno do modelo, não do modelo em si.**

O modelo (GPT-4o) é a inteligência — uma commodity acessada via API.
Você construiu a arquitetura que direciona essa inteligência para o problema certo,
com os dados certos, e com garantia de qualidade mensurável.

```
Foundation Model (GPT-4o)  ← não é seu
Orquestração (LangGraph)   ← você construiu
Ferramentas (7 tools)      ← você construiu
Dados (SQLite + ChromaDB)  ← você construiu
Avaliação (eval pipeline)  ← você construiu
Deploy (Docker + Streamlit)← você construiu
```

---

## Pergunta 1 — "O que é um agente ReAct?"

**Resposta:**

ReAct alterna entre **Raciocinar** e **Agir**.

O modelo gera um pensamento, escolhe uma tool, executa, observa o resultado,
e repete até ter informação suficiente para responder.

No EcoHome, o LangGraph implementa esse loop como um grafo de estados:
- Nó `agent`: o GPT-4o raciocina e decide qual tool chamar
- Nó `tools`: a tool executa e retorna dados reais (SQLite, Open-Meteo, ChromaDB)
- Aresta condicional: se o modelo ainda precisa de dados → volta ao `tools`; se tem a resposta → finaliza

O usuário pergunta "quanto custou meu home office?",
o agente chama `query_energy_usage` com os filtros certos,
lê o resultado, e responde com o valor real — sem alucinação.

---

## Pergunta 2 — "Como você avalia um agente?"

**Resposta:**

Tenho dois níveis de avaliação implementados em `energy_advisor/evaluation/`:

**Trajectory evaluation** — verifico se o agente chamou as ferramentas certas
para cada tipo de pergunta. Cada cenário tem uma lista de `required_tools`;
extraio os `tool_calls` do estado LangGraph e comparo.

**LLM-as-judge** — um GPT-4o (modelo mais forte que o agente) pontua a resposta
em quatro dimensões via Pydantic structured output:
- `grounding` (1–5): os números batem com os dados retornados pelas tools?
- `completeness` (1–5): a pergunta foi respondida por completo?
- `actionability` (1–5): a resposta diz o que o usuário deve fazer?
- `honesty` (1–5): o agente admite incerteza quando não tem dados?

Isso me dá métricas quantitativas, não impressão subjetiva.
Posso rodar `python -m energy_advisor.evaluation.runner` e ver degradação entre versões.

---

## Pergunta 3 — "Por que LangGraph e não LangChain puro?"

**Resposta:**

LangGraph me dá um **grafo explícito e auditável**.

Com LCEL puro, o fluxo de um agente fica implícito dentro de uma chain —
difícil de inspecionar em produção, difícil de estender sem quebrar o fluxo.

Com LangGraph:
- O estado do agente (`AgentState` TypedDict) é explícito e inspecionável em cada passo
- Posso adicionar nós de verificação entre `agent` e `tools` sem refatorar tudo
- O histórico de mensagens fica no estado — facilita o eval de trajetória
- A aresta condicional (`should_continue`) é código Python, não mágica da chain

Na prática: quando o chat do João não estava retornando datas corretas,
consegui inspecionar o estado intermediário e ver exatamente qual mensagem
estava com o contexto errado. Com uma chain opaca, teria sido muito mais difícil.
