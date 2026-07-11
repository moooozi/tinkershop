# syntax=docker/dockerfile:1.7
FROM alpine:latest AS builder
RUN apk add --no-cache binutils
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_PYTHON_INSTALL_DIR=/app/python
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --no-dev --frozen --no-editable
RUN printf 'from tinkershop.server import main; main()\n' > __main__.py \
 && uv pip install pyinstaller \
 && .venv/bin/pyinstaller --onedir --strip --name tinkershop __main__.py

FROM alpine:latest
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app/dist/tinkershop /app/tinkershop
USER appuser
ENTRYPOINT ["/app/tinkershop/tinkershop"]