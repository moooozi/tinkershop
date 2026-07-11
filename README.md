# tinkershop

A local [Model Context Protocol](https://modelcontextprotocol.io) (MCP) toolkit that
exposes additional tools to AI agents.

## Install as a standalone tool

```bash
uvx tinkershop
```

Or install and invoke directly

```bash
uv tool install tinkershop
tinkershop
```

## Developement

For local development, install from the working tree:

```bash
uv tool install .
tinkershop
```

### Lint & format

```bash
uv run ruff check
uv run ruff format
```

### Test

```bash
uv run pytest
```
