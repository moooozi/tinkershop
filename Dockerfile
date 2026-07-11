# syntax=docker/dockerfile:1.7
FROM alpine:latest AS builder
RUN apk add --no-cache binutils
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
ENV UV_PYTHON_INSTALL_DIR=/app/python
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN printf 'from tinkershop.server import main; main()\n' > __main__.py \
 && uv sync --no-dev --frozen --no-editable \
 && uv pip install pyinstaller \
 && .venv/bin/pyinstaller --onedir --strip --name tinkershop --collect-all tinkershop __main__.py

FROM scratch
COPY --from=builder /app/dist/tinkershop /app/tinkershop
COPY --from=builder /lib/ld-musl-x86_64.so.1 /lib/
COPY --from=builder /usr/lib/libz.so.1 /lib/
USER 65532:65532
ENTRYPOINT ["/app/tinkershop/tinkershop"]