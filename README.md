# TR SEO Automation System

Module 0-first monorepo scaffold for the Traffic Radius SEO Automation System.

## Stack

- Backend: Python, FastAPI, uv
- Frontend: React, TypeScript, TailwindCSS, pnpm
- Data: PostgreSQL, pgvector, Redis
- Local orchestration: Docker Compose

## Current Scope

This workspace is scaffolded for:

- shared contracts and database models
- Module 0 onboarding and CDD upload flow
- Module 0 backend service skeleton
- local development containers

## Workspace Layout

```text
apps/
  api/
  portal/
services/
  module0-discovery/
packages/
  contracts/
  db/
docs/
tests/
infra/
```

## Local Development

### Single local server

Build the frontend and serve the whole app from FastAPI with one command:

```bash
python app.py
```

Windows shortcut:

```bash
run_local.bat
```

Then open `http://127.0.0.1:8000`.

### Backend only

```bash
uv sync --all-packages
uv run --package tr-seo-api uvicorn tr_seo_api.main:app --reload --port 8000
```

### Frontend

```bash
pnpm install
pnpm --filter tr-seo-portal dev
```

If the backend is not running yet, the frontend still falls back to mock Module 0 data in dev mode.

### Full stack

```bash
docker compose up --build
```

## Module 0 Inputs

The frontend provides:

- `website_url`
- `domain` optional
- `target_country`
- structured CDD fields
- CDD upload in `.pdf`, `.docx`, `.xlsx`, `.xls`, or `.csv`

The backend derives:

- domain normalization
- site classification
- sitemap inspection targets
- SEMrush-driven intelligence
- keyword universe generation
- TAM summary
- URL architecture map
- downloadable `.xlsx` exports for the keyword universe and URL architecture map

## Notes

- No API keys are required just to run the project locally.
- Module 0 always attempts real SEMrush first when `SEMRUSH_API_KEY` is available.
- If SEMrush fails because of credits, quota, 403, timeout, empty response, or API access issues, Module 0 automatically uses estimated fallback data for that run only.
- If `OPENAI_API_KEY` is configured, OpenAI generates the estimated fallback keyword and competitor set first.
- OpenAI fallback data is labeled as estimated and uses `data_source = openai_mock_fallback`.
- Set `MODULE0_FORCE_MOCK_SEMRUSH=true` if you want to force fallback mode even when a SEMrush key exists; restore normal SEMrush-first behavior with `MODULE0_FORCE_MOCK_SEMRUSH=false`.
- If OpenAI is not configured or fails, Module 0 falls back one more level to deterministic synthetic fallback data.
- The fallback warning is: `SEMrush data unavailable due to credits/API access issue. Estimated fallback data was used for this run.`
- When SEMrush becomes available again, Module 0 automatically returns to real SEMrush without code changes.
- In test and development mode, the keyword universe is capped by `MODULE0_TEST_KEYWORD_LIMIT` and defaults to `200`.
- In production, `MODULE0_PRODUCTION_KEYWORD_LIMIT` can be used to set a higher cap.
- CDD parsing is implemented for PDF, DOCX, XLSX/XLS, and CSV inputs.
- Database models are scaffolded but migrations are not yet executed in this workspace.
