FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.11.14-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra test --no-install-project
COPY . .
RUN uv sync --locked --extra test --offline --no-build-isolation --no-editable && useradd --uid 10001 --create-home harvester \
    && mkdir -p /app/output && chown -R harvester:harvester /app/output
USER harvester
ENTRYPOINT ["iris-oek"]
CMD ["run", "--config", "tests/fixtures/config.json", "--fixture", "tests/fixtures/parcels.geojson"]
