FROM python:3.13-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

COPY bovie/ bovie/
COPY bovie.py .
COPY pyproject.toml .
COPY uv.lock .

RUN uv sync --frozen --no-dev

ENTRYPOINT [ "uv", "run", "bovie.py" ]
