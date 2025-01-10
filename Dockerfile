FROM python:3.13 AS builder

RUN pip install poetry
# ENV POETRY_NO_INTERACTION=true \
#     POETRY_VIRTUALENVS_IN_PROJECT=true \
#     POETRY_VIRTUALENVS_CREATE=true \
#     POETRY_CACHE_DIR=/tmp/poetry_cache

COPY poetry.lock pyproject.toml ./

RUN poetry export --without-hashes --format=requirements.txt > requirements.txt

WORKDIR /app

FROM python:3.13-slim as runner

COPY pyvie_bot .
COPY --from=builder /app/requirements.txt .

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "pyvie_bot" ]

# RUN pip install poetry && \
#     poetry install --no-root --no-directory && \
#     rm -rf $POETRY_CACHE_DIR

# ENTRYPOINT [ "poetry", "run", "python", "pyvie_bot/"]