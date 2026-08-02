"""tinkershop MCP server entry point.

Run with::

    uv run tinkershop                      # stdio (default)
    uv run tinkershop --transport streamable-http --port 8000
"""

from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import BaseRoute, Route

from tinkershop import __version__
from tinkershop.tools.web_search import register

SERVER_NAME = "tinkershop"


def create_server() -> MCPServer:
    """Build a MCPServer instance and register all tools on it."""
    mcp = MCPServer(SERVER_NAME)
    register(mcp)
    return mcp


def _build_http_app(
    mcp: MCPServer,
    transports: set[str],
    host: str,
    port: int,
) -> Starlette:
    """Combine SSE and/or Streamable HTTP apps onto a single Starlette app."""
    sse_app = mcp.sse_app(host=host) if "sse" in transports else None
    http_app = mcp.streamable_http_app(host=host) if "streamable-http" in transports else None

    combined_routes: list[BaseRoute] = []
    added_routes: set[tuple[str, tuple[str, ...]]] = set()

    def _route_key(route: Route) -> tuple[str, tuple[str, ...]]:
        methods = tuple(sorted(route.methods or ["GET"]))
        return (route.path, methods)

    for app in (a for a in (sse_app, http_app) if a is not None):
        for route in app.routes:
            if isinstance(route, Route):
                key = _route_key(route)
                if key not in added_routes:
                    combined_routes.append(route)
                    added_routes.add(key)
            else:
                combined_routes.append(route)

    if sse_app is not None and http_app is not None:

        @asynccontextmanager
        async def _combined_lifespan(app: Starlette) -> AsyncIterator[None]:
            # Nested `async with` is intentional: the http lifespan starts inside
            # the sse one, so they must be entered in order.
            async with sse_app.router.lifespan_context(app):  # noqa: SIM117
                async with http_app.router.lifespan_context(app):
                    yield

        lifespan = _combined_lifespan
    elif http_app is not None:
        lifespan = http_app.router.lifespan_context
    elif sse_app is not None:
        lifespan = sse_app.router.lifespan_context
    else:
        msg = "no HTTP transport selected"
        raise RuntimeError(msg)

    app = Starlette(routes=combined_routes, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{SERVER_NAME} MCP server")
    parser.add_argument(
        "--transport",
        nargs="+",
        choices=["stdio", "sse", "streamable-http"],
        default=["stdio"],
        help="Transport protocol (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Bind address for HTTP transports (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port for HTTP transports (default: 8000).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{SERVER_NAME} {__version__}",
    )
    args = parser.parse_args()

    transports = set(args.transport)
    if "stdio" in transports and len(transports) > 1:
        parser.error("Cannot mix stdio with HTTP transports")
    if transports == {"stdio"} and (args.host is not None or args.port is not None):
        parser.error("--host / --port are only valid with HTTP transports")
    if transports != {"stdio"} and "stdio" in transports:
        parser.error("Cannot mix stdio with HTTP transports")

    mcp = create_server()

    if transports == {"stdio"}:
        mcp.run(transport="stdio")
        return

    host = args.host or "127.0.0.1"
    port = args.port or 8000
    app = _build_http_app(mcp, transports, host, port)

    print(f"{SERVER_NAME} {__version__} starting on {' and '.join(sorted(transports))}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
