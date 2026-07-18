# GRIDKEEP web — Next.js frontend. Built from the monorepo root so pnpm
# workspace packages (@gridkeep/ui, @gridkeep/security-contracts, ...)
# resolve correctly.
FROM node:20-slim AS base
RUN corepack enable

FROM base AS deps
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/ui/package.json packages/ui/package.json
COPY packages/security-contracts/package.json packages/security-contracts/package.json
COPY packages/config/package.json packages/config/package.json
RUN pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# NEXT_PUBLIC_* variables are inlined into the client bundle at build
# time — setting this only in docker-compose.yml's runtime `environment:`
# (as opposed to `build.args`) would have no effect on what actually
# ships to the browser. Must be a build ARG, not a runtime ENV alone.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN pnpm --filter @gridkeep/web build

FROM base AS runtime
WORKDIR /repo/apps/web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /repo/apps/web/.next ./.next
COPY --from=build /repo/apps/web/public ./public
COPY --from=build /repo/apps/web/package.json ./package.json
COPY --from=build /repo/node_modules /repo/node_modules
COPY --from=build /repo/apps/web/node_modules ./node_modules

RUN useradd --create-home --uid 1000 gridkeep && chown -R gridkeep:gridkeep /repo
USER gridkeep

EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD node -e "require('http').get('http://localhost:3000', r => process.exit(r.statusCode < 500 ? 0 : 1))" || exit 1

CMD ["npx", "next", "start", "-p", "3000"]
