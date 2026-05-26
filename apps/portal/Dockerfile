FROM node:22-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-workspace.yaml /app/
COPY apps/portal/package.json /app/apps/portal/package.json

RUN pnpm install --filter tr-seo-portal... --no-frozen-lockfile

COPY . /app

EXPOSE 3000

CMD ["pnpm", "--filter", "tr-seo-portal", "dev"]
