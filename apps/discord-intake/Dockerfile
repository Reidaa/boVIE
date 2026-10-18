FROM ghcr.io/astral-sh/uv:python3.15-trixie-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps ./apps
RUN uv sync --frozen --no-dev --no-editable --package bovie-discord-intake

FROM python:3.15-slim-trixie
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
CMD ["discord-intake"]
