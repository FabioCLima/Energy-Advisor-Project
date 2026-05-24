# 5-Minute CAR Talk Track

## Context
I built EcoHome Energy Advisor to simulate a real AI product problem: combining household consumption, solar generation, energy pricing, and user questions into one decision-support experience. I wanted something stronger than a notebook or single model demo, so I treated it as a production-style ML + AI application.

## Action
I designed the system in three layers.

1. **ML layer**
   - built hourly usage forecasting with a seasonal baseline and a `HistGradientBoostingRegressor`
   - added hold-out evaluation and persisted RMSE / MAE in the model artifact

2. **AI application layer**
   - wrapped the domain logic in a LangGraph ReAct agent with 9 tools
   - added trajectory evaluation and LLM-as-judge evaluation for the agent
   - implemented provenance-aware fallback for ANEEL pricing so the app does not pretend external data is fresh when it is not

3. **MLOps / deployment layer**
   - added CI and test coverage
   - containerized the app
   - created a reproducible bootstrap so a fresh environment can provision the SQLite demo data and local forecasting artifacts on first boot
   - packaged the same image to support both `streamlit` and `api` runtime modes for cloud deployment

## Result
The current version has:
- `85` tests passing
- `12/12` scenario trajectory pass rate
- `4.31/5.00` judged response quality
- a public-demo-friendly Streamlit surface
- an AWS-friendly single-image deployment story with runtime mode selection and env-based configuration

## Close
The main thing I learned was to treat AI as an operable system, not just a model. The parts that mattered most were evaluation, honest fallback behavior, reproducible bootstrap, and deployment surfaces that make the project easy to demo and easy to reason about in production.
