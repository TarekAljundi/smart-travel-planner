# backend/Dockerfile
# ---- Stage 1: Build dependencies ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Install production dependencies (PyTorch CPU will be used automatically)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --no-install-project

# ---- Stage 2: Runtime ----
FROM python:3.13-slim

WORKDIR /app
RUN useradd --create-home appuser
USER appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]