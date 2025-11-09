# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim AS base

# --- Environment hardening / speed-ups ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Prefer wheels to avoid compiling (helps with numpy/pandas/strands)
    PIP_ONLY_BINARY=:all: \
    # Some packages try to use setuptools_scm; ensure it's present
    SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0

# --- System deps for scientific stacks and possible native builds ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc g++ \
    git \
    cmake \
    curl \
 && rm -rf /var/lib/apt/lists/*

# --- Create non-root user ---
RUN useradd -ms /bin/bash appuser
WORKDIR /app

# --- Separate layer for dependencies ---
# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .

# Upgrade pip tooling then install deps.
# --prefer-binary helps avoid compiling numpy/pandas/strands from source
RUN pip install --upgrade pip setuptools wheel \
 && pip install --upgrade --prefer-binary -r requirements.txt

# --- Copy app code ---
COPY main.py .

# Optional: if you later add packages/modules, copy the whole project:
# COPY . .

# --- Runtime config ---
# AgentCore default container port is commonly 8080
EXPOSE 8080
ENV PORT=8080

# Helpful for local dev; override at deploy-time if needed
# ENV AWS_REGION=us-west-2
# ENV BEDROCK_AGENTCORE_MEMORY_ID=

# Basic healthcheck; customize the path if your app exposes a different endpoint
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

USER appuser

# Start your AgentCore app (main.py calls app.run())
CMD ["python", "main.py"]
