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

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV REED_FRONTEND_PATH=/app/frontend/dist

EXPOSE 8000
CMD ["reed", "serve"]
