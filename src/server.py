"""MCP Manager - Universal MCP Server Manager.

FastMCP server that manages all your other MCP servers:
add, remove, monitor, export/import, and manage tokens.
"""

import json
import os
import sys
from typing import Optional

from mcp.server.mcpserver import MCPServer

from .config_manager import ConfigManager
from .health_checker import HealthChecker
from .server_registry import ServerRegistry
from .token_store import TokenStore

# ── Inicializace ──────────────────────────────────────────────────────────────

mcp = MCPServer(
    "MCP Manager",
    instructions=(
        "Universal MCP Server Manager. Use these tools to add, remove, "
        "configure, monitor and manage all your MCP servers from one place. "
        "Supports OpenCode, Claude Desktop, and other MCP-compatible clients."
    ),
)

CONFIG_PATH = os.environ.get("MCP_CONFIG_PATH", None)
config_mgr = ConfigManager(CONFIG_PATH)
registry = ServerRegistry()
token_store = TokenStore()
health_checker = HealthChecker()


# ── 1. list_servers ───────────────────────────────────────────────────────────

@mcp.tool()
def list_servers(verbose: bool = False) -> str:
    """List all configured MCP servers and their status.

    Args:
        verbose: If true, include full config details for each server.
    """
    config_mgr.load()
    servers = config_mgr.list_servers()

    if not servers:
        return json.dumps({"servers": [], "message": "No MCP servers configured."}, indent=2)

    result = []
    for name, cfg in servers.items():
        entry = {
            "name": name,
            "enabled": cfg.get("enabled", True),
            "type": cfg.get("type", "unknown"),
        }
        if verbose:
            entry["config"] = cfg
            # Token info
            token_info = token_store.get_token_info(name)
            if token_info:
                entry["token"] = {
                    "preview": token_info.get("token_preview", "N/A"),
                    "expires_at": token_info.get("expires_at"),
                }
            else:
                entry["token"] = None

        result.append(entry)

    return json.dumps({"servers": result, "count": len(result)}, indent=2)


# ── 2. add_server ─────────────────────────────────────────────────────────────

@mcp.tool()
def add_server(
    name: str,
    server_type: str = "local",
    command: str = "",
    url: str = "",
    env_vars: str = "",
    enabled: bool = True,
    force: bool = False,
) -> str:
    """Add a new MCP server to the configuration.

    Args:
        name: Unique name for the server (e.g. "github", "my-db-server").
        server_type: One of: local, npx, docker, remote.
        command: Command to run (for local/npx/docker). Comma-separated for array.
        url: URL for remote servers.
        env_vars: Environment variables as KEY=VALUE, comma-separated.
        enabled: Whether the server is enabled.
        force: If true, overwrite existing server with same name.
    """
    config_mgr.load()

    # Kontrola existence
    existing = config_mgr.get_server(name)
    if existing and not force:
        return json.dumps({
            "error": f"Server '{name}' already exists. Use force=true to overwrite.",
            "existing_config": existing,
        }, indent=2)

    # Sestavení konfigurace
    server_config: dict = {
        "type": server_type,
        "enabled": enabled,
    }

    if command:
        server_config["command"] = [c.strip() for c in command.split(",")]

    if url:
        server_config["url"] = url

    if env_vars:
        env = {}
        for pair in env_vars.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                env[k.strip()] = v.strip()
        if env:
            server_config["environment"] = env

    # Zápis
    if existing:
        config_mgr.update_server(name, server_config)
        action = "updated"
    else:
        config_mgr.add_server(name, server_config)
        action = "added"

    return json.dumps({
        "success": True,
        "action": action,
        "server": name,
        "config": server_config,
    }, indent=2)


# ── 3. remove_server ──────────────────────────────────────────────────────────

@mcp.tool()
def remove_server(name: str) -> str:
    """Remove an MCP server from the configuration.

    Args:
        name: Name of the server to remove.
    """
    config_mgr.load()

    if not config_mgr.get_server(name):
        return json.dumps({"error": f"Server '{name}' not found."}, indent=2)

    config_mgr.remove_server(name)
    token_store.revoke(name)

    return json.dumps({
        "success": True,
        "action": "removed",
        "server": name,
    }, indent=2)


# ── 4. get_server_detail ──────────────────────────────────────────────────────

@mcp.tool()
def get_server_detail(name: str) -> str:
    """Get detailed information about a specific MCP server.

    Args:
        name: Name of the server.
    """
    config_mgr.load()
    server = config_mgr.get_server(name)

    if not server:
        return json.dumps({"error": f"Server '{name}' not found."}, indent=2)

    result = {
        "name": name,
        "config": server,
    }

    # Token info
    token_info = token_store.get_token_info(name)
    if token_info:
        result["token"] = {
            "preview": token_info.get("token_preview", "N/A"),
            "created_at": token_info.get("created_at"),
            "expires_at": token_info.get("expires_at"),
        }

    # Health history
    history = health_checker.get_history(name, limit=5)
    if history:
        result["health_history"] = history

    # Catalog info
    catalog_info = registry.get_template(name)
    if catalog_info:
        result["catalog"] = {
            "description": catalog_info.get("description"),
            "docs_url": catalog_info.get("docs_url"),
            "category": catalog_info.get("category"),
        }

    return json.dumps(result, indent=2)


# ── 5. test_connection ────────────────────────────────────────────────────────

@mcp.tool()
def test_connection(name: str) -> str:
    """Test connection to an MCP server by sending an initialize request.

    Args:
        name: Name of the server to test.
    """
    config_mgr.load()
    server = config_mgr.get_server(name)

    if not server:
        return json.dumps({"error": f"Server '{name}' not found."}, indent=2)

    status = health_checker.check_server(name, server)

    return json.dumps({
        "server": name,
        "result": status.to_dict(),
    }, indent=2)


# ── 6. health_check ───────────────────────────────────────────────────────────

@mcp.tool()
def health_check() -> str:
    """Run health check on all configured MCP servers."""
    config_mgr.load()
    servers = config_mgr.list_servers()

    if not servers:
        return json.dumps({"results": {}, "message": "No servers configured."}, indent=2)

    results = health_checker.check_all(servers)

    # Summary
    healthy = sum(1 for r in results.values() if r.get("status") == "healthy")
    unhealthy = sum(1 for r in results.values() if r.get("status") == "unhealthy")
    unknown = sum(1 for r in results.values() if r.get("status") == "unknown")
    timeout = sum(1 for r in results.values() if r.get("status") == "timeout")

    return json.dumps({
        "summary": {
            "total": len(results),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unknown": unknown,
            "timeout": timeout,
        },
        "results": results,
    }, indent=2)


# ── 7. export_config ──────────────────────────────────────────────────────────

@mcp.tool()
def export_config(include_tokens: bool = False) -> str:
    """Export the entire MCP configuration as JSON.

    Args:
        include_tokens: If true, include token values (DANGEROUS - only use for backups).
    """
    config_mgr.load()
    exported = config_mgr.export_config(include_tokens=include_tokens)

    return json.dumps({
        "config": json.loads(exported),
        "note": "Tokens included" if include_tokens else "Tokens redacted (use include_tokens=true for full export)",
    }, indent=2)


# ── 8. import_config ──────────────────────────────────────────────────────────

@mcp.tool()
def import_config(config_json: str, merge: bool = True) -> str:
    """Import MCP configuration from a JSON string.

    Args:
        config_json: JSON string with MCP configuration.
        merge: If true, merge with existing config. If false, replace entirely.
    """
    try:
        config_mgr.load()
        result = config_mgr.import_config(config_json, merge=merge)
        servers = config_mgr.list_servers()

        return json.dumps({
            "success": True,
            "action": "merged" if merge else "replaced",
            "servers_count": len(servers),
            "servers": list(servers.keys()),
        }, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


# ── 9. rotate_token ───────────────────────────────────────────────────────────

@mcp.tool()
def rotate_token(
    server_name: str,
    new_token: str,
    expires_at: str = "",
) -> str:
    """Update the API token for an MCP server.

    Args:
        server_name: Name of the server.
        new_token: The new API token.
        expires_at: Optional expiration date (ISO format, e.g. "2026-12-31").
    """
    token_store.store(
        server_name=server_name,
        token=new_token,
        expires_at=expires_at if expires_at else None,
    )

    # Update env var in config if applicable
    config_mgr.load()
    server = config_mgr.get_server(server_name)
    if server:
        env = server.get("environment", {})
        for key in list(env.keys()):
            if any(t in key.lower() for t in ["token", "key", "secret"]):
                env[key] = new_token
        config_mgr.save()

    info = token_store.get_token_info(server_name)
    preview = info["token_preview"] if info else "N/A"

    return json.dumps({
        "success": True,
        "action": "token_rotated",
        "server": server_name,
        "preview": preview,
        "expires_at": expires_at or "not set",
    }, indent=2)


# ── 10. get_logs ──────────────────────────────────────────────────────────────

@mcp.tool()
def get_logs(server_name: str = "", limit: int = 20) -> str:
    """Get health check logs for servers.

    Args:
        server_name: If specified, return logs only for this server. Otherwise, all.
        limit: Max number of log entries per server.
    """
    if server_name:
        history = health_checker.get_history(server_name, limit=limit)
        return json.dumps({
            "server": server_name,
            "logs": history,
            "count": len(history),
        }, indent=2)

    # All servers
    config_mgr.load()
    servers = config_mgr.list_servers()
    all_logs = {}
    for name in servers:
        history = health_checker.get_history(name, limit=limit)
        if history:
            all_logs[name] = history

    return json.dumps({
        "logs": all_logs,
        "servers_with_logs": len(all_logs),
    }, indent=2)


# ── Bonus: catalog tools ──────────────────────────────────────────────────────

@mcp.tool()
def search_catalog(query: str = "") -> str:
    """Search the built-in catalog of known MCP servers.

    Args:
        query: Search query (matches name, description, category). Empty = list all.
    """
    if query:
        results = registry.search(query)
    else:
        results = [{"id": k, **v} for k, v in registry.list_available().items()]

    return json.dumps({
        "results": results,
        "count": len(results),
    }, indent=2)


@mcp.tool()
def add_from_catalog(
    server_id: str,
    custom_name: str = "",
    env_vars: str = "",
) -> str:
    """Add an MCP server from the built-in catalog by its ID.

    Args:
        server_id: ID from the catalog (e.g. "github", "supabase", "playwright").
        custom_name: Override the default name.
        env_vars: Additional env vars as KEY=VALUE, comma-separated.
    """
    template = registry.get_template(server_id)
    if not template:
        available = list(registry.list_available().keys())
        return json.dumps({
            "error": f"Server '{server_id}' not in catalog.",
            "available": available,
        }, indent=2)

    # Build config from template
    server_config: dict = {
        "type": template.get("type", "local"),
        "enabled": True,
    }

    if template.get("command"):
        server_config["command"] = list(template["command"])

    if template.get("url"):
        server_config["url"] = template["url"]

    if template.get("headers"):
        server_config["headers"] = dict(template["headers"])

    env: dict = {}
    if env_vars:
        for pair in env_vars.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                env[k.strip()] = v.strip()
    if env:
        server_config["environment"] = env

    name = custom_name or server_id

    config_mgr.load()
    existing = config_mgr.get_server(name)
    if existing:
        config_mgr.update_server(name, server_config)
        action = "updated"
    else:
        config_mgr.add_server(name, server_config)
        action = "added"

    return json.dumps({
        "success": True,
        "action": action,
        "server": name,
        "catalog_entry": server_id,
        "config": server_config,
        "note": template.get("description", ""),
    }, indent=2)


# ── Spuštění ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
