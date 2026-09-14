FROM node:22-alpine AS builder

ENV NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app

COPY . .

RUN pnpm install --no-frozen-lockfile

# NEXT_PUBLIC_* variables and basePath are inlined into the client bundle at
# build time, not read at container startup, so they must arrive as build
# args (wired from docker-compose.yml's build.args, sourced from .env) rather
# than as plain runtime environment variables.
ARG NEXT_PUBLIC_WOI_API_ORIGIN=http://localhost:8000
ARG WOI_BASE_PATH=
ENV NEXT_PUBLIC_WOI_API_ORIGIN=$NEXT_PUBLIC_WOI_API_ORIGIN
ENV WOI_BASE_PATH=$WOI_BASE_PATH

RUN pnpm --filter @world-of-islam/web build

FROM node:22-alpine AS runner

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

WORKDIR /app

COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
