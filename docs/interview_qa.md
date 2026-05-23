# Interview Q&A — EcoHome Energy Advisor

> Prepared 2026-05-23. Based on actual decisions made during the build.
> Language: answers in English (for technical interviews), context in Portuguese.

---

## 1. Sobre o Projeto — Visão Geral

**Q: Tell me about this project. What problem does it solve?**

> Most Brazilian households with solar panels and EVs can't answer a simple question: "what's the cheapest time to charge my car, given my solar generation and current tariff?" They'd have to manually cross-reference three sources — the energy bill, weather forecast, and the ANEEL tariff schedule. EcoHome automates that reasoning. It's a LangGraph ReAct agent that coordinates 7 specialized tools over a real-world Brazilian energy context: Enel SP TOU rates, ANEEL bandeiras tarifárias, 90 days of synthetic household data for a persona named João (Python developer, 4kWp solar panel, Tesla Model 3, home-office Mon–Fri).

---

**Q: Por que usou LangGraph em vez de LangChain LCEL ou CrewAI?**

> LangGraph gives you an explicit state machine — you define nodes, edges, and the routing logic in code. With LCEL you compose chains but the control flow is implicit. For a tool-using agent that can loop (call tools, evaluate results, call more tools), an explicit graph makes the flow auditable: I can look at the state at any step, write assertions against it, and explain exactly what the agent decided. CrewAI is opinionated about multi-agent roles; here I needed a single-agent loop with clean state, not a crew abstraction.

---

**Q: What's in `AgentState` and why?**

> Just one field: `messages: Annotated[list[BaseMessage], add_messages]`. That's the minimal contract — the graph only needs to accumulate the conversation history. `add_messages` is a LangGraph reducer that appends new messages rather than replacing the list. Keeping state minimal means the graph is easy to test and easy to serialize. If I needed persistence across sessions I'd add a `thread_id` and use LangGraph's checkpointing.

---

## 2. Dados e Persona

**Q: The data is synthetic — how do you defend that in an interview?**

> The data is synthetic but structured to be realistic. Each device has a `DeviceProfile` with a `prob_fn: Callable[[datetime], float]` that encodes domain knowledge: the AC has an 85% usage probability in January (São Paulo summer) and 20% in May; the Tesla charges stochastically on Tue/Thu/Sun nights (0h–5h, off-peak); solar generation follows a Gaussian curve peaking at noon, scaled by monthly irradiance data. The result is 6,631 usage records and 1,081 solar records over 90 days that produce realistic patterns — not random noise. In a production system I'd swap the SQLite for a real meter API (e.g., Enel's API or a smart plug integration).

---

**Q: What are ANEEL bandeiras tarifárias and why do they matter?**

> ANEEL is Brazil's electricity regulator. The bandeira system is a monthly surcharge that signals grid stress: verde (green) = no surcharge, amarela (yellow) = +R$0.01885/kWh, vermelha nível 1 = +R$0.03971/kWh, vermelha nível 2 = higher. The surcharge compounds on top of the base TOU rate. For a household with an EV and solar, the bandeira changes the break-even point for battery storage or load shifting. Ignoring it means your cost estimates are wrong — I hardcoded historical bandeiras for 2026 and fall back to verde for unknown months.

---

**Q: Why does the home office cost matter as a product feature?**

> In Brazil, remote workers can negotiate a home-office allowance (ajuda de custo) with employers, but they need documentation. The dashboard shows the cost of exactly the three home-office devices — PC, monitor, and AC — broken down by day, with monthly and annual projections. It's a data artifact the user can print and bring to HR. That turns an energy dashboard into a financial planning tool, which is a much stronger product story.

---

## 3. Arquitetura e Decisões Técnicas

**Q: Walk me through the 6-layer architecture.**

> From user to storage:
> 1. **Interaction** — Streamlit UI with two tabs: Dashboard (Plotly charts) and Chat (ReAct agent)
> 2. **Orchestration** — `EnergyAdvisorAgent`: builds the LangGraph graph, injects system prompt + current date context, exposes a single `invoke()` method
> 3. **Tools** — 7 `@tool` decorated functions, each isolated by domain: `query_energy_usage`, `query_solar_generation`, `get_recent_energy_summary`, `get_electricity_prices`, `get_weather_forecast`, `search_energy_tips`, `calculate_energy_savings`
> 4. **Services** — business logic layer: `database.py` (SQLAlchemy ORM), `pricing.py` (ANEEL + TOU), `retrieval.py` (ChromaDB), `recommendations.py` (savings math)
> 5. **Storage** — SQLite for time-series records, ChromaDB for vector embeddings of the 5 knowledge-base documents
> 6. **Observability** — Loguru structured logs, optional LangSmith tracing via env vars

---

**Q: Why SQLite and not PostgreSQL?**

> Two reasons. First, portability: SQLite is a file — no connection string, no running server, no Docker volume coordination. The whole data layer is `data/energy_data.db`. Second, the ORM is already SQLAlchemy, so migrating to PostgreSQL is a one-line change in `Settings.db_path`. I'd make that migration when horizontal scaling or concurrent writes become a real requirement, not before.

---

**Q: How does the RAG pipeline work?**

> Five plain-text documents in `data/documents/` cover energy-saving tips by domain (EV charging, solar optimization, home appliances, cost reduction, device best practices). On first access, `ensure_vectorstore()` chunks them, generates embeddings via OpenAI `text-embedding-ada-002`, and persists the ChromaDB index to `data/vectorstore/`. On subsequent calls it loads from disk. When the agent calls `search_energy_tips`, it does a similarity search and returns the top-k chunks with source filenames — the system prompt instructs the agent to cite those sources in the "Supporting tips" section.

---

**Q: What's the `device_type == "ev"` vs `device_name` distinction in the tools?**

> During the refactor I found a bug: the original `query_energy_usage` tool filtered by `device_type` (e.g., `"EV"`, `"HVAC"`), but the agent was passing fictional type names. I changed the tool to return **aggregated data per device name** (not raw records) and added a `device_name` filter that requires the exact name. The system prompt now explicitly lists João's device names, so the agent knows to look for `"Tesla Model 3 Long Range"` and not `"EV"`. Sending 2,000 raw records to the LLM was also expensive — the aggregated response is ~15 rows.

---

## 4. Avaliação

**Q: How do you know the agent is working correctly?**

> Three levels:
> 1. **Unit tests** — 5 test suites covering DB operations, pricing logic (bandeiras, TOU boundaries), savings math, and schema validation
> 2. **Tool-level assertions** — I can call any `@tool` function directly and assert on its dict output without invoking the LLM
> 3. **Trajectory evaluation** — the `03_run_and_evaluate.ipynb` notebook runs the agent on 10+ scenarios and uses an LLM-as-judge to score tool selection accuracy (did it call the right tools?), recommendation coherence (does the answer follow from the data?), and grounding (no hallucinated numbers)

---

**Q: What is LLM-as-judge and when would you NOT use it?**

> LLM-as-judge means using a separate LLM call (usually a stronger model) to score the agent's output against a rubric. It's useful when the correct answer is hard to express as an exact-match assertion — e.g., "does this recommendation mention the off-peak window?" is easier to score with an LLM than with a regex. I wouldn't use it when: (a) the output is structured and deterministic (use exact-match or schema validation), (b) the evaluation budget is tight (each judge call costs money), or (c) the judge has the same blind spots as the agent (use human eval or a different model family as judge).

---

## 5. Dashboard e UX

**Q: You have 12 bugs documented in `dashboard_improvements.md`. How did you find them?**

> Visual inspection of the running dashboard against João's data. I categorized them by type: data inconsistencies (B1–B3), missing KPIs (K1–K3), chart scale/label problems (D1–D2, S1–S2, T1–T2), and UX layout issues (U1–U3). The most interesting bug was B1: the "Home Office Cost" KPI card showed R$57.34 but the report box showed R$52.57 for the same period. The KPI was filtering by `location == "office"` which included the router and modem — the report filtered by device name. I fixed it by defining a `HOME_OFFICE_DEVICES` frozenset as a single source of truth and using it everywhere.

---

**Q: Why separate the Tesla from the device bar chart?**

> The Tesla consumes ~58% of total household electricity (about 570 kWh/month for regular charging). Putting it on the same bar chart as the router (3 kWh/month) makes every other bar unreadable — they compress to near-zero. I separated it into metric cards: total kWh, total R$, charging days, and % of home consumption. This is a product decision: the EV is a distinct category that deserves its own section, just like "cloud costs" and "on-prem costs" would be separate in an infrastructure dashboard.

---

## 6. Docker e Deploy

**Q: Walk me through how someone runs this project from scratch.**

> ```bash
> git clone https://github.com/FabioCLima/Energy-Advisor-Project.git
> cd Energy-Advisor-Project
> echo "OPENAI_API_KEY=sk-..." > .env
> docker compose up
> # open http://localhost:8501
> ```
> On first run the entrypoint detects there's no `data/energy_data.db`, runs the bootstrap script (generates 90 days of João's data, ~10 seconds), then starts Streamlit. The data directory is mounted as a named Docker volume so it persists across restarts. The image is ~1.1GB due to chromadb's native dependencies.

---

**Q: What would you change for a production deploy?**

> Several things:
> - Replace SQLite with PostgreSQL and add connection pooling
> - Move the ChromaDB vectorstore to a managed vector DB (Pinecone or Weaviate) for scalability
> - Add authentication (even basic HTTP auth via Streamlit) — right now anyone with the URL can see João's data
> - Separate the data bootstrap into an init container or a management command, not the entrypoint
> - Add a GitHub Actions CI pipeline: `ruff` lint + `pytest` on every push to main
> - Deploy to Streamlit Community Cloud (free, URL public in ~5 minutes) or as a Cloud Run job

---

## 7. Perguntas Comportamentais

**Q: What was the hardest technical decision in this project?**

> Deciding how much context to give the LLM vs. how much to encode in tool design. The first version of `query_energy_usage` returned all 2,000+ raw records. The LLM couldn't process them and gave wrong answers. I refactored the tool to return aggregated data (per-device totals) and moved the filtering logic into the tool signature (`device_name`, `usage_pattern`). The lesson: tool output should be LLM-friendly — small, structured, and already at the right level of abstraction.

---

**Q: If you had one more week, what would you add?**

> The Open-Meteo API integration. Currently `get_weather_forecast` returns synthetic data. Open-Meteo is free, no API key required, and has hourly solar irradiance forecasts for São Paulo. Real irradiance data would make the "charge now vs. wait for solar" recommendation genuinely reliable. Second priority would be a GitHub Actions CI pipeline with `pytest --cov` reporting — right now tests only run manually.

---

**Q: This project uses only your own data. How would it scale to multiple users?**

> Three changes: (1) add a `user_id` foreign key to all DB tables and scope every query to the authenticated user; (2) move from SQLite to PostgreSQL; (3) make the agent stateless — pass `user_id` as context in each `invoke()` call and let the tools fetch the right data. The LangGraph graph itself is already stateless (it takes messages in, returns messages out). The agent's `_system_message` would become a template rendered with the user's profile at request time.
