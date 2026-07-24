# syntax=docker/dockerfile:1
#
# Build context is the monorepo root (apps/web is an npm workspace sharing
# the root package-lock.json) -- build with:
#   docker build -f apps/web/Dockerfile .

FROM node:22-alpine AS deps

WORKDIR /repo
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY package.json package-lock.json ./
COPY apps/web ./apps/web

ARG NEXT_PUBLIC_CONTROL_API_URL
ENV NEXT_PUBLIC_CONTROL_API_URL=${NEXT_PUBLIC_CONTROL_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build --workspace apps/web

# Standalone output traces exactly the files each page needs -- the
# runtime stage needs no node_modules install of its own, no package.json,
# and no build tooling.
FROM node:22-alpine AS runtime

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

WORKDIR /app
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/public ./apps/web/public

ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

USER nextjs

EXPOSE 3000

ENTRYPOINT ["node", "apps/web/server.js"]
