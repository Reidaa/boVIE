FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS workspace
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY services ./services

FROM workspace AS build-business-france
RUN uv sync --frozen --no-dev --no-editable --package bovie-business-france

FROM workspace AS build-wttj
RUN uv sync --frozen --no-dev --no-editable --package bovie-wttj

FROM workspace AS build-outbox-relay
RUN uv sync --frozen --no-dev --no-editable --package bovie-outbox-relay

FROM workspace AS build-notification-intake
RUN uv sync --frozen --no-dev --no-editable --package bovie-notification-intake

FROM workspace AS build-discord-delivery
RUN uv sync --frozen --no-dev --no-editable --package bovie-discord-delivery

FROM workspace AS build-broker-setup
RUN uv sync --frozen --no-dev --no-editable --package bovie-broker-setup

FROM python:3.13-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

FROM runtime AS business-france
COPY --from=build-business-france /app/.venv /app/.venv
CMD ["bovie"]

FROM runtime AS wttj
COPY --from=build-wttj /app/.venv /app/.venv
CMD ["wttf"]

FROM runtime AS outbox-relay
COPY --from=build-outbox-relay /app/.venv /app/.venv
CMD ["outbox-relay"]

FROM runtime AS notification-intake
COPY --from=build-notification-intake /app/.venv /app/.venv
CMD ["notification-intake"]

FROM runtime AS discord-delivery
COPY --from=build-discord-delivery /app/.venv /app/.venv
CMD ["discord-delivery"]

FROM runtime AS broker-setup
COPY --from=build-broker-setup /app/.venv /app/.venv
CMD ["broker-setup"]

FROM business-france AS default
