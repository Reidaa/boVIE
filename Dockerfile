FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS workspace
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps ./apps

FROM workspace AS build-collector-business-france
RUN uv sync --frozen --no-dev --no-editable --package bovie-collector-business-france

FROM workspace AS build-collector-wttj
RUN uv sync --frozen --no-dev --no-editable --package bovie-collector-wttj

FROM workspace AS build-discord-intake
RUN uv sync --frozen --no-dev --no-editable --package bovie-discord-intake

FROM workspace AS build-discord-sender
RUN uv sync --frozen --no-dev --no-editable --package bovie-discord-sender

FROM workspace AS build-nats-setup
RUN uv sync --frozen --no-dev --no-editable --package bovie-nats-setup

FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

FROM runtime AS collector-business-france
COPY --from=build-collector-business-france /app/.venv /app/.venv
CMD ["collector-business-france"]

FROM runtime AS collector-wttj
COPY --from=build-collector-wttj /app/.venv /app/.venv
CMD ["collector-wttj"]

FROM runtime AS discord-intake
COPY --from=build-discord-intake /app/.venv /app/.venv
CMD ["discord-intake"]

FROM runtime AS discord-sender
COPY --from=build-discord-sender /app/.venv /app/.venv
CMD ["discord-sender"]

FROM runtime AS nats-setup
COPY --from=build-nats-setup /app/.venv /app/.venv
CMD ["nats-setup"]

FROM collector-business-france AS default
