# Dockerfile.backend
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first (better caching)
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies (no dev, no edit)
RUN uv sync --frozen --no-dev --no-editable

# Copy the rest of the backend code
COPY backend/ .

# Expose port
EXPOSE 8000

# Run the server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]