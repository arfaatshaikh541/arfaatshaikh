FROM node:22-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./
COPY apps/web/package.json apps/web/package.json

RUN npm install --workspaces --include-workspace-root

COPY apps/web apps/web

EXPOSE 3000

CMD ["npm", "run", "dev", "--workspace", "apps/web"]
