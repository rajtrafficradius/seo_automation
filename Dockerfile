FROM node:22-alpine AS frontend-builder

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/portal/package.json /app/apps/portal/package.json
COPY apps/portal/tsconfig.json /app/apps/portal/tsconfig.json
COPY apps/portal/tsconfig.app.json /app/apps/portal/tsconfig.app.json
COPY apps/portal/vite.config.ts /app/apps/portal/vite.config.ts
COPY apps/portal/tailwind.config.ts /app/apps/portal/tailwind.config.ts
COPY apps/portal/postcss.config.cjs /app/apps/portal/postcss.config.cjs
COPY apps/portal/index.html /app/apps/portal/index.html
COPY apps/portal/src /app/apps/portal/src

RUN pnpm install --frozen-lockfile --filter tr-seo-portal...
RUN pnpm --filter tr-seo-portal build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . /app

COPY --from=frontend-builder /app/apps/portal/dist /app/apps/portal/dist

RUN uv sync --frozen --all-packages

EXPOSE 8000

CMD ["sh", "-c", "uv run --package tr-seo-api uvicorn tr_seo_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
