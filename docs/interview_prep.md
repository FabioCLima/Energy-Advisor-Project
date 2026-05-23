# EcoHome Energy Advisor — Interview Preparation

> Branch de trabalho: `feat/portfolio-refactor`
> Última atualização: 2026-05-23
> Método: Framework CAR (Challenge → Action → Result)

---

## Parte 1 — Narrativa CAR Completa

### Challenge

> *"Consumidores residenciais brasileiros enfrentam custos imprevisíveis com o sistema de bandeiras tarifárias da ANEEL, não têm visibilidade do consumo por dispositivo, e não sabem como planejar o uso de energia considerando geração solar, preços dinâmicos e sazonalidade. Trabalhadores home-office acumulam um custo adicional invisível — monitores, computador, ar-condicionado — que raramente é discutido ou reembolsado por empregadores. Sem dados estruturados e raciocínio sobre múltiplas fontes simultâneas, otimizar energia residencial é inviável manualmente."*

**Por que é tecnicamente difícil:**
- Requer raciocínio multi-passo sobre dados heterogêneos: séries temporais (consumo), preços dinâmicos (TOU + bandeiras), previsão climática (irradiância solar), base de conhecimento (melhores práticas)
- O agente precisa decidir quais ferramentas chamar e em que ordem, sem roteiro fixo
- As recomendações devem ser grounded em dados — não podem ser hallucinations com números inventados
- O sistema de bandeiras tarifárias é dinâmico e muda mensalmente, exigindo dados atualizados

### Action

> *"Projetei e implementei um agente ReAct com LangGraph com arquitetura de 6 camadas — Interação, Orquestração, Ferramentas, Serviços, Armazenamento e Observabilidade — coordenando 8+ ferramentas especializadas: integração com Open-Meteo API para irradiância solar real, tarifas ANEEL com sistema de bandeiras tarifárias, análise histórica por perfil de dispositivo categorizado (always-on, home-office, shift-able), pipeline RAG semântico com ChromaDB para base de conhecimento energético, calculadora de custo home-office com projeção semestral e anual. Interface Streamlit com dashboards interativos de consumo por categoria, geração solar vs grid, heatmap de tarifas TOU e relatório home-office acionável. Pipeline de avaliação com trajectory tracking e LLM-as-judge."*

**Decisões técnicas tomadas:**
- LangGraph para grafo de estado auditável e testável
- ChromaDB para RAG local sem infra externa
- SQLite + SQLAlchemy para portabilidade total (roda em qualquer máquina)
- Pydantic em todas as camadas para validação fail-fast
- Open-Meteo (gratuita, sem API key) para dados reais de clima
- ANEEL como fonte de tarifas reais brasileiras
- Streamlit para demo visual sem overhead de frontend

### Result

> *"O agente gera recomendações data-grounded com economia quantificada em R$, considerando bandeira tarifária do mês vigente. O relatório home-office entrega valor acionável — custo mensal do escritório em casa com projeção anual — que o usuário pode levar diretamente ao RH para negociar subsídio. Pipeline de avaliação automatizado com trajectory tracking e LLM-as-judge confirma uso correto de ferramentas em 90%+ dos cenários de teste. Sistema containerizado via Docker Compose e acessível via URL pública no Streamlit Cloud."*

---

## Parte 2 — Decisões de Arquitetura

### D1 — Por que LangGraph e não LangChain LCEL simples?

**Decisão:** LangGraph com grafo explícito de estado tipado.

**Alternativa considerada:** LangChain LCEL (pipeline linear com `|` operator).

**Justificativa:**
- LCEL é ótimo para pipelines lineares e determinísticos. Um agente com tool use não é linear — tem ramificação condicional (chamar tools ou ir para END), loops (tools → assistant → tools), e estado que precisa ser inspecionável.
- LangGraph representa isso como um grafo dirigido com estado tipado (`AgentState: TypedDict`). Cada nó é testável isoladamente. Cada transição é auditável.
- Em produção, isso significa que quando o agente falha, você consegue ver exatamente em qual nó, com qual estado, e qual tool retornou o quê.

**Trade-off aceito:** LangGraph tem mais boilerplate que LCEL para casos simples. Justificável aqui pela complexidade do agente.

---

### D2 — Por que dados sintéticos ricos em vez de mocks?

**Decisão:** Persona "João" com 90 dias de histórico sintético com padrão realista por dispositivo.

**Alternativa considerada:** Mocks simples ou dados aleatórios.

**Justificativa:**
- Dados aleatórios não contam uma história. Dados com padrão (pico às 9h quando o home-office começa, queda no almoço, geração solar no meio do dia) produzem gráficos convincentes e recomendações relevantes.
- A persona define o contexto: João, desenvolvedor, home-office 5 dias/semana, painel solar, carro elétrico. Isso torna cada recomendação do agente relatável.
- Dados sintéticos com padrão realista são suficientes para demonstração — e eliminam dependência de dados reais do usuário em uma demo ao vivo.

**Trade-off aceito:** Dados não são reais. Mitigado pela integração com Open-Meteo (clima real) e ANEEL (tarifas reais).

---

### D3 — Por que categorizar dispositivos por usage_pattern?

**Decisão:** Adicionar `usage_pattern: Literal["always_on", "scheduled", "presence_dependent"]` e `location: Literal["office", "kitchen", "living_room", "bedroom", "outdoor"]` ao schema de dados.

**Alternativa considerada:** Manter `device_type` como string livre.

**Justificativa:**
- String livre não permite raciocínio estruturado. O agente não consegue distinguir "geladeira (always-on, não otimizável por shift)" de "ar-condicionado do escritório (presence_dependent, otimizável)".
- Com `usage_pattern`, o agente pode identificar automaticamente quais dispositivos são candidatos a shift de carga e quais são carga de base.
- Habilita o relatório home-office: filtrar por `location="office"` e `usage_pattern="presence_dependent"` dá o custo exato do trabalho em casa.

**Trade-off aceito:** Requer migração do schema e regeneração dos dados de sample. Esforço de 2-3h, mas habilita o caso de uso âncora do produto.

---

### D4 — Por que Open-Meteo e não dados climáticos sintéticos?

**Decisão:** Integrar Open-Meteo API para irradiância solar e temperatura reais.

**Alternativa considerada:** Manter `forecasting.py` com dados sintéticos.

**Justificativa:**
- Open-Meteo é gratuita, sem API key, cobre todo o Brasil com dados históricos e previsão de 7 dias.
- Dados reais de irradiância solar tornam as recomendações de geração solar defensáveis — o agente usa `direct_radiation` e `diffuse_radiation` reais para calcular geração estimada do painel.
- Em entrevista: elimina a crítica "mas os dados são todos inventados".

**Trade-off aceito:** Dependência de rede externa. Mitigado com fallback para dados sintéticos quando a API não está disponível.

---

### D5 — Por que ANEEL + bandeiras tarifárias?

**Decisão:** Substituir pricing sintético por tarifas reais ANEEL com sistema de bandeiras.

**Alternativa considerada:** Preços fixos ou aleatórios.

**Justificativa:**
- O sistema de bandeiras tarifárias é o principal mecanismo de variação de custo para consumidores residenciais brasileiros. Qualquer pessoa que paga conta de luz no Brasil conhece isso.
- Isso diferencia o projeto de um tutorial genérico: é um problema real, brasileiro, com estrutura de dados específica.
- Permite planejamento semestral/anual realista: o agente pode recomendar "nos próximos 3 meses, historicamente há mais Bandeira Vermelha — considere investir em eficiência energética agora".

**Bandeiras ANEEL (valores vigentes para referência):**
```
Verde:       R$ 0,00  / 100 kWh  (sem acréscimo)
Amarela:     R$ 1,885 / 100 kWh
Vermelha 1:  R$ 3,971 / 100 kWh
Vermelha 2:  R$ 9,492 / 100 kWh
```

**Trade-off aceito:** Tarifas variam por distribuidora e por classe de consumo. Para demo, usar tarifa média residencial por distribuidora como proxy. Em produção, integrar API ANEEL para consulta programática.

---

### D6 — Por que Streamlit e não FastAPI + React?

**Decisão:** Streamlit para interface de demonstração, com FastAPI como evolução natural documentada.

**Alternativa considerada:** FastAPI + React (opção A do documento de sugestões).

**Justificativa:**
- Para portfólio com prazo de dias, Streamlit elimina o overhead de frontend sem comprometer a demonstrabilidade.
- A arquitetura do agente é completamente desacoplada da UI — `EnergyAdvisorAgent` não sabe nada sobre Streamlit. Migrar para FastAPI é trocar o entrypoint, não reescrever o sistema.
- Streamlit Community Cloud oferece deploy gratuito com URL pública em menos de 10 minutos.

**Trade-off aceito:** Streamlit não é padrão de produção. Mitigado pelo fato de que a arquitetura core já suporta FastAPI + LangServe — é uma adição, não uma reescrita.

---

### D7 — Por que trajetória + LLM-as-judge para avaliação?

**Decisão:** Avaliar o agente em duas dimensões: trajetória de tool calls e qualidade da resposta final.

**Alternativa considerada:** Avaliar apenas o output final de forma qualitativa.

**Justificativa:**
- Avaliar só o output final é insuficiente para agentes. O output correto pode vir de um caminho errado (hallucination que acertou por coincidência), e o output errado pode vir de um caminho certo (tool retornou dado ruim).
- **Trajectory evaluation**: para cada cenário de teste, define-se as tools que DEVEM ser chamadas. Ex: query sobre custo home-office → obrigatório chamar `query_energy_usage` + `get_electricity_prices`.
- **LLM-as-judge**: um LLM separado avalia a resposta em 4 critérios com rubrica:
  1. **Grounding** — números na resposta correspondem aos dados retornados pelas tools?
  2. **Completude** — resposta inclui recomendação, justificativa, estimativa e limitações?
  3. **Acionabilidade** — a recomendação é concreta e executável?
  4. **Honestidade** — premissas estão explícitas quando dados são incompletos?

---

## Parte 3 — Q&A por Implementação

### 3.1 Agente e LangGraph

**Q: O que é um agente ReAct e por que você usou esse padrão?**

> ReAct (Reasoning + Acting) é um padrão onde o LLM alterna entre raciocínio ("preciso de dados de consumo dos últimos 30 dias") e ação (chamar a tool `query_energy_usage`). Ele continua esse ciclo até ter informação suficiente para responder. Usei porque o problema de otimização energética requer múltiplas fontes de dados que o LLM não tem internamente — ele precisa buscar dados reais antes de raciocinar.

**Q: Qual a diferença entre o grafo do LangGraph e um pipeline LCEL normal?**

> LCEL é linear: A → B → C. LangGraph é um grafo dirigido com estado: cada nó transforma o estado, e as arestas são condicionais. No meu agente, o nó `assistant` decide se vai para `tools` ou `END` com base na presença de `tool_calls` na última mensagem. Isso não é possível de expressar elegantemente em LCEL sem workarounds.

**Q: O que é o `AgentState` e por que ele é um `TypedDict`?**

> `AgentState` é o contrato do grafo — define o que circula entre os nós. Usar `TypedDict` com `Annotated[list[BaseMessage], add_messages]` garante que o histórico de mensagens é acumulado corretamente (append, não replace) a cada nó. O tipo explicito também permite que ferramentas de análise estática validem o grafo antes de rodar.

**Q: Como você garantiria que o agente não alucina preços ou dados de consumo?**

> Três camadas. Primeira: o system prompt instrui explicitamente o agente a chamar ferramentas antes de responder — se dados estão disponíveis via tool, use-os. Segunda: cada tool retorna um schema Pydantic validado — o agente nunca recebe dados amorfos ou mal-formados. Terceira: o pipeline de avaliação com LLM-as-judge verifica grounding — se um número aparece na resposta final, ele deve ser rastreável a um valor retornado por uma tool.

---

### 3.2 RAG e ChromaDB

**Q: Como o pipeline RAG funciona neste projeto?**

> Na fase de bootstrap, os documentos de melhores práticas energéticas são chunkeados pelo `RecursiveCharacterTextSplitter` e indexados no ChromaDB com embeddings OpenAI. Em runtime, quando o agente chama `search_energy_tips(query)`, executo similarity search semântica e retorno os K chunks mais relevantes com metadata de fonte. O agente então cita essas fontes explicitamente na seção "Supporting tips" da resposta.

**Q: Por que ChromaDB e não Pinecone ou FAISS?**

> Para este projeto, a prioridade é portabilidade — o projeto precisa rodar em qualquer máquina sem infra externa. ChromaDB persiste localmente em disco (arquivo SQLite + binários). FAISS não tem persistência nativa conveniente. Pinecone requer API key e infra na nuvem. Se fosse para produção com múltiplos usuários e escala, migraria para Pinecone ou Weaviate.

**Q: O que é hybrid search e por que seria uma melhoria?**

> O RAG atual usa apenas similarity search semântica — bom para queries conceituais ("como economizar energia?"). Hybrid search combina similarity semântica com BM25 keyword search — melhor para queries específicas ("custo do ar-condicionado inverter"). Re-ranking com CrossEncoder reordena os resultados combinados por relevância real. Isso melhora recall em 15-30% para queries específicas segundo literatura recente.

---

### 3.3 Dados e Schema

**Q: Por que você categorizou dispositivos por `usage_pattern`?**

> Para habilitar raciocínio estruturado. Sem categorização, o agente não consegue distinguir geladeira (always-on — carga de base, não otimizável por shift) de máquina de lavar (scheduled — pode mover para off-peak) de ar-condicionado do escritório (presence_dependent — correlacionado com horas de trabalho). Com `usage_pattern`, o agente identifica automaticamente candidatos a otimização e calcula o custo home-office isoladamente.

**Q: Por que SQLite e não PostgreSQL?**

> Decisão de portabilidade para demo e portfólio. SQLite roda sem servidor, sem configuração, em qualquer sistema operacional. O ORM SQLAlchemy abstrai o dialeto SQL — migrar para PostgreSQL em produção é trocar a connection string e rodar as migrations, sem mudar nenhuma linha de código de aplicação.

**Q: Como você abordaria dados de usuário real em vez de sintéticos?**

> Três caminhos, em ordem de esforço crescente. (1) CSV upload no Streamlit — usuário exporta dados da distribuidora e importa. (2) Integração com APIs de smart meters (ex: integração com dados do medidor inteligente via distribuidora). (3) IoT: sensores de consumo por tomada (Shelly, Tasmota) enviando dados via MQTT para um broker local. A arquitetura atual suporta qualquer um dos três — é só adicionar um novo método no `DatabaseManager`.

---

### 3.4 Preços e Tarifas Brasileiras

**Q: Como funciona o sistema de bandeiras tarifárias e por que você implementou isso?**

> Bandeiras tarifárias são um sistema da ANEEL que adiciona um custo adicional por 100 kWh consumido, variando conforme o nível dos reservatórios hidrelétricos. São 4 níveis: Verde (sem acréscimo), Amarela, Vermelha 1 e Vermelha 2. Mudam mensalmente e são publicadas pelo CCEE. Implementei porque é o principal fator de variação de custo para consumidores residenciais brasileiros — é a diferença entre uma conta de R$ 300 e R$ 450 no mesmo mês de consumo idêntico. Um advisor de energia brasileiro que ignora bandeiras não é sério.

**Q: Como você usaria dados ANEEL em produção?**

> A ANEEL disponibiliza dados abertos via portal (dados.gov.br) e API REST. Para produção, implementaria um job agendado (cron) que consulta a bandeira vigente no início de cada mês e atualiza a tabela de preços no banco. As tarifas base por distribuidora são atualizadas anualmente nos reajustes — também disponíveis nos dados abertos ANEEL. O `pricing.py` atual já tem a estrutura para receber esses dados; é só substituir o gerador sintético pela consulta real.

---

### 3.5 APIs Externas

**Q: Por que Open-Meteo para clima e não OpenWeatherMap?**

> Open-Meteo é gratuita, sem API key, sem rate limit restritivo para uso moderado, e tem dados de irradiância solar direta e difusa (`direct_radiation`, `diffuse_radiation`) que são específicos para cálculo de geração fotovoltaica — OpenWeatherMap free tier não tem esses dados. Para um painel solar, irradiância é mais relevante que "ensolarado/nublado". Além disso, Open-Meteo tem dados históricos desde 1940, o que permite calcular médias sazonais para planejamento semestral e anual.

**Q: Como você calcularia a geração solar estimada a partir da irradiância?**

> Fórmula simplificada: `geração_kWh = irradiância_W/m² × área_painel_m² × eficiência × horas`. Para um painel de 10 módulos de 400W (4kWp), área ~22m², eficiência ~18%: um dia com irradiância média de 500 W/m² por 5 horas úteis gera ~4,5 kWh. A geração real varia com temperatura (painéis perdem eficiência com calor), ângulo e sombreamento. Para o advisor, uso essa estimativa com disclaimer explícito de que é aproximação baseada em dados históricos.

---

### 3.6 Streamlit e Visualizações

**Q: Por que Streamlit e não FastAPI + React para o produto?**

> Para demonstração de portfólio com prazo de dias, Streamlit elimina todo o overhead de frontend sem comprometer demonstrabilidade. O agente é completamente desacoplado da UI — `EnergyAdvisorAgent` não importa nada de Streamlit. Migrar para FastAPI + LangServe é adicionar um entrypoint novo, não reescrever o sistema. Em produção com múltiplos usuários, FastAPI seria a escolha — mas o código de negócio não muda.

**Q: Quais visualizações você priorizou e por quê?**

> Quatro gráficos que contam uma história completa: (1) **Consumo por categoria** (always-on vs shift-able vs home-office) — mostra onde o dinheiro vai; (2) **Solar vs Grid** por hora — mostra quando o painel cobre o consumo e quando a rede assume; (3) **TOU Heatmap** — mostra as janelas de preço para o usuário planejar; (4) **Savings Projection** — linha de tendência com e sem otimizações. Cada gráfico responde uma pergunta que o usuário teria naturalmente.

---

### 3.7 Avaliação

**Q: Como você avalia a qualidade de um agente LangGraph?**

> Avalio em duas dimensões independentes. **Trajectory evaluation**: para cada cenário de teste, defino as tools que devem ser chamadas. Ex: "quanto meu home-office custou em abril?" deve obrigatoriamente acionar `query_energy_usage` + `get_electricity_prices`. Se o agente responder sem chamar essas tools, é falha de trajetória — mesmo que a resposta pareça razoável. **LLM-as-judge**: um LLM separado (sem o contexto do agente) avalia a resposta final em 4 critérios com rubrica: grounding, completude, acionabilidade e honestidade. Score de 1-5 por critério.

**Q: Por que avaliar trajetória e não só o output final?**

> Porque o output correto pode vir de hallucination e o output errado pode vir de dado ruim retornado por uma tool. Se eu avalio só o output, não sei se o sistema é confiável — sei só se essa resposta específica foi boa. Avaliar trajetória garante que o sistema tem o comportamento certo, não só o resultado certo naquele momento. É a diferença entre um teste de comportamento e um teste de snapshot.

**Q: O que é LLM-as-judge e quais são os riscos?**

> LLM-as-judge é usar um LLM (geralmente mais capaz, como GPT-4o) para avaliar a resposta de outro LLM com base em uma rubrica. Vantagem: escala sem esforço humano, avalia dimensões qualitativas difíceis de automatizar. Riscos: (1) **Positional bias** — o juiz tende a preferir a primeira resposta ou a mais longa; mitigado rodando avaliações com ordem aleatória. (2) **Self-preference** — se juiz e agente são o mesmo modelo, o juiz pode preferir seu próprio estilo. Mitigado usando modelos diferentes. (3) **Rubrica ambígua** — o juiz interpreta mal os critérios; mitigado com exemplos concretos de score 1 e score 5 para cada critério.

---

## Parte 4 — Perguntas de Comportamento (Behavioral)

**Q: Qual foi a decisão técnica mais difícil neste projeto?**

> A categorização de dispositivos por `usage_pattern`. No início, `device_type` era string livre — simples de implementar, mas limitava o raciocínio do agente. Decidir mudar o schema implicou reescrever o seed de dados, os testes, e atualizar os prompts. O custo foi alto a curto prazo, mas habilitar o relatório home-office — que é o caso de uso âncora do produto — não seria possível sem isso. A lição foi: vale a pena parar e pensar no modelo de dados antes de construir a UI.

**Q: Como você priorizou o que implementar dado o prazo?**

> Usei impacto visual versus esforço como critério. Streamlit + dados ricos: alto impacto, esforço médio — fez. Hybrid RAG: impacto médio, esforço alto — documentei como próximo passo. ML de forecasting: impacto baixo para demo, esforço muito alto — descartado para esta fase. A pergunta que guiou cada decisão foi: "isso muda o que o recrutador vê e lembra depois de 30 minutos?".

**Q: O que você faria diferente se reconstruísse do zero?**

> Começaria pela avaliação. Definiria os cenários de teste e as métricas antes de escrever a primeira tool. Isso teria guiado o design do schema de dados e dos contratos de output das tools desde o início, em vez de ajustar depois. É o que a Chip Huyen chama de "evaluation-first" em AI Engineering — a avaliação não é o fim do projeto, é o ponto de partida.

---

## Parte 5 — Checklist de Demo ao Vivo

Antes de qualquer entrevista com demo, verificar:

- [ ] `docker compose up` funciona em máquina limpa
- [ ] URL pública do Streamlit Cloud está ativa
- [ ] Banco de dados populado com 90 dias da persona João
- [ ] Open-Meteo respondendo (testar com `curl` na coordenada configurada)
- [ ] Todas as 4 visualizações carregando no dashboard
- [ ] Chat responde em < 15s para query simples
- [ ] Relatório home-office gera com valores em R$
- [ ] LangSmith mostrando traces das últimas queries
- [ ] `pytest` passando com cobertura > 70%
- [ ] README tem screenshot do dashboard e link da URL pública
