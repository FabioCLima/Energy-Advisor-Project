# AWS App Runner Deployment

## Recommended interview setup
Use the same container image for two optional services:
- `streamlit` for the demo UI
- `api` for the native FastAPI surface

For the interview, the strongest story is to deploy the Streamlit service first and mention that the image also supports an API mode through `SERVICE_MODE=api`.

## Container contract
- Image source: repository `Dockerfile`
- Default mode: `streamlit`
- Port env var: `PORT`
- Health endpoints:
  - Streamlit: `/healthz`
  - API: `/health`

## App Runner settings
### Service 1: Streamlit UI
- Port: `8501`
- Start command: use image default entrypoint
- Environment file: `deploy/aws/apprunner.env.example`

### Optional Service 2: API
- Port: `8000`
- Override environment:
  - `SERVICE_MODE=api`
  - `PORT=8000`

## Operational notes
On first boot, the entrypoint provisions:
- SQLite tables
- João sample data
- local forecasting model artifact(s)

Vectorstore bootstrap is off by default to keep cold starts short and avoid requiring embeddings for the dashboard path.

## Why this is a good interview trade-off
- same image for UI and API
- explicit runtime mode through env vars
- cloud-friendly stdout logging
- deterministic bootstrap for fresh environments
- low infrastructure overhead compared with ECS while still showing container deployment maturity
