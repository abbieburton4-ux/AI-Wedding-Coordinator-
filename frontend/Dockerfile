# Vite dev-server container for the VenueFlow frontend (local orchestration only).
# Production builds go to GitHub Pages via `npm run build`; this image exists so
# `docker compose up` brings up the full stack offline.
FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching. The source tree is
# bind-mounted at runtime (see docker-compose.yml) so edits hot-reload.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Bind to 0.0.0.0 so the dev server is reachable from the host browser.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
