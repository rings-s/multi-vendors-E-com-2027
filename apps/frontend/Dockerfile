# syntax=docker/dockerfile:1.7
# Development image for the SvelteKit frontend (Vite dev server with HMR).
# docker-compose bind-mounts the source over /app and keeps node_modules and
# .svelte-kit in named volumes, so the host checkout is never touched.
FROM node:24-slim AS dev
ENV CI=true \
    PNPM_HOME=/home/node/.local/share/pnpm
RUN npm install --global --no-fund --no-audit pnpm@11.21.0 \
    && mkdir -p /app/node_modules /app/.svelte-kit \
    && chown -R node:node /app
WORKDIR /app
USER node
COPY --chown=node:node package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY --chown=node:node . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
