FROM python:3.13-alpine

# Install uv package manager from ghcr.io/astral-sh/uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY bovie/ bovie/
COPY bovie.py uv.lock pyproject.toml ./

RUN uv sync --frozen --no-dev

ENTRYPOINT [ "uv", "run",  "bovie.py" ]
CMD [ "bot", "--continuous"]
