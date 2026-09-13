FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# postgresql-client-18 comes from the PGDG archive: Debian's own archive does not carry
# 18. The major version must match the server, because pg_dump refuses to dump a server
# newer than itself. TENANT-09 (plan 02-07) runs pg_dump and pg_restore from inside this
# image, so installing it now avoids a late rebuild of the whole image.
#
# WeasyPrint's system libraries are deliberately absent — Phase 6 owns those.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
    install -d /usr/share/postgresql-common/pgdg; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc; \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-18; \
    apt-get purge -y --auto-remove gnupg; \
    rm -rf /var/lib/apt/lists/*; \
    pg_dump --version

COPY --from=ghcr.io/astral-sh/uv:0.8.19 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, so a source change does not re-resolve the stack.
# --frozen: fail if uv.lock disagrees with pyproject.toml rather than silently re-locking
# and shipping a different set of versions than the one the test suite ran against.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "8"]
