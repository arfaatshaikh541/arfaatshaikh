FROM node:20-slim AS base
RUN corepack enable

FROM base AS deps
WORKDIR /srv
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared-types/package.json packages/shared-types/package.json
COPY packages/ui/package.json packages/ui/package.json
COPY packages/config/package.json packages/config/package.json
RUN pnpm install --frozen-lockfile --filter @leadflow/web...

FROM base AS build
WORKDIR /srv
COPY --from=deps /srv /srv
COPY . .
RUN pnpm --filter @leadflow/web build

FROM base AS runner
WORKDIR /srv
ENV NODE_ENV=production
COPY --from=build /srv/apps/web/.next/standalone ./
COPY --from=build /srv/apps/web/.next/static ./apps/web/.next/static
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
