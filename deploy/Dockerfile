# Two stages. The first builds a wheel from the source tree; the second
# installs only that wheel, so the image carries no build backend, no test
# suite and no .git directory.
#
# The wheel already contains the computed tables, so the runtime image needs no
# data volume, no download on boot and no network access at all. See
# docs/architecture/decisions/0006-shipping-computed-tables.md.

FROM python:3.12-slim AS build

# uv resolves and builds faster than pip and is what the repository uses.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN uv build --wheel --out-dir /dist


FROM python:3.12-slim

# Nothing in this image should run as uid 0. A compromised request handler
# inherits whatever the process can do, and root inside a container is root on
# the host kernel for anything that escapes the namespace.
RUN useradd --create-home --uid 10001 pippen

# PYTHONDONTWRITEBYTECODE keeps .pyc files out of a read-only filesystem.
# PYTHONUNBUFFERED makes logs appear when the platform reads them rather than
# when the buffer fills, which matters on a free tier that sleeps.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY --from=build /dist/*.whl /tmp/
# The wheel name is resolved first: `/tmp/*.whl[api]` reads as a glob character
# class to the shell, matches nothing, and hands pip the literal string.
RUN wheel="$(ls /tmp/*.whl)" \
 && pip install --no-cache-dir "${wheel}[api]" \
 && rm -f /tmp/*.whl

USER pippen
WORKDIR /home/pippen

# 7860 is the port Hugging Face Spaces expects. Overridable for other hosts.
ENV PORT=7860
EXPOSE 7860

# Exec form, so uvicorn is pid 1 and receives SIGTERM directly. Without it the
# shell is pid 1, swallows the signal, and the platform waits out its grace
# period before killing the container on every deploy.
CMD ["sh", "-c", "exec uvicorn pippen.api.app:app --host 0.0.0.0 --port ${PORT}"]
