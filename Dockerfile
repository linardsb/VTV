# syntax=docker/dockerfile:1

# Multi-stage build for optimized production image
# Using official uv images and Python 3.12 on Debian Bookworm Slim

# Stage 1: Builder - Install dependencies
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Set working directory
WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Use copy link mode for cache mounts
ENV UV_LINK_MODE=copy

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies only (not the project itself)
# This layer is cached unless dependencies change
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# Copy application source code
COPY . .

# Install the project itself with non-editable install
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --no-dev

# Stage 2: Runtime - Minimal production image
FROM python:3.12-slim-bookworm

# SECURITY: Create non-root user
RUN groupadd --gid 1001 vtv && \
    useradd --uid 1001 --gid vtv --shell /bin/false --create-home vtv

# Set working directory
WORKDIR /app

# Copy only the virtual environment from builder
# This significantly reduces the final image size
COPY --from=builder --chown=vtv:vtv /app/.venv /app/.venv

# Copy application code
COPY --chown=vtv:vtv . .

# Ensure the virtual environment is used
ENV PATH="/app/.venv/bin:$PATH"

# SECURITY: Run as non-root user
USER vtv

EXPOSE 8123

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
