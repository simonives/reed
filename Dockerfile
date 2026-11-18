# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

# Stage 1: build Vue frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python application
FROM python:3.12-slim AS app
WORKDIR /app

# Install the locked dependency set first (exact versions from uv.lock), then
# the application itself without re-resolving anything.
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv \
    && uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y uv && rm /tmp/requirements.txt
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV REED_FRONTEND_PATH=/app/frontend/dist
# glibc keeps a malloc arena per thread and rarely returns freed pages to the OS,
# which makes lxml and Kuzu allocations look like a leak in a long-running process.
ENV MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=131072

EXPOSE 8000
CMD ["reed", "serve"]
