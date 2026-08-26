"""MCP Manager - Universal Multi-Harness MCP Server Manager.

An MCPServer that manages MCP servers across multiple harnesses:
OpenCode, Claude Desktop, Cursor, Windsurf, Cline, Zed, Continue.dev.

Features:
    - Add/remove/enable/disable servers
    - Monitor server health
    - Rotate and encrypt API tokens
    - Export/import configs
    - Sync servers between harnesses
    - Built-in catalog of 20+ popular MCP servers
"""

import json
import os
import sys
from typing import Optional

from mcp.server.mcpserver import MCPServer

from .config_manager import ConfigManager
from .health_checker import HealthChecker
from .harness import (
    HARNESSES,
    detect_installed,
    from_universal,
    get_harness,
    list_harnesses,
    to_universal,
)
from .server_registry import ServerRegistry
from .token_store import TokenStore

# ── Initialization ─────────────────────────────────────────────────────────────

mcp = MCPServer(
    "MCP Manager",
    instructions=(
        "Universal Multi-Harness MCP Server Manager. "
        "Manage MCP servers across OpenCode, Claude Desktop, Cursor, Windsurf, "
        "Cline, Zed, and Continue.dev from a single place. "
        "Add/remove/monitor/configure servers, rotate tokens, export/import configs, "
        "and sync servers between harnesses."
    ),
)

CONFIG_PATH = os.environ.get("MCP_CONFIG_PATH", None)
DEFAULT_HARNESS = os.environ.get("MCP_HARNESS", "opencode")
MASTER_PASSWORD = os.environ.get("MCP_MANAGER_MASTER_PASSWORD", None)

config_mgr = ConfigManager(harness_id=DEFAULT_HARNESS, config_path=CONFIG_PATH)
registry = ServerRegistry()
token_store = TokenStore(master_password=MASTER_PASSWORD)
health_checker = HealthChecker()


def _harness_name() -> str:
    """Return the display name of the active harness."""
    h = get_harness(config_mgr.harness_id)
    return h.name if h else config_mgr.harness_id


# ══════════════════════════════════════════════════════════════════════════════
# HARNESS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_harnesses_info() -> str:
    """List all supported MCP client harnesses and whether they are installed.

    Shows config file paths and detected installation status for:
    OpenCode, Claude Desktop, Cursor, Windsurf, Cline, Zed, Continue.dev.
    """
    harnesses = list_harnesses()
    installed = detect_installed()
    active = config_mgr.harness_id

    result = []
    for h in harnesses:
        result.append({
            **h,
            "installed": h["id"] in installed,
            "is_active": h["id"] == active,
        })

    return json.dumps({
        "harnesses": result,
        "active": active,
        "count": len(result),
        "installed_count": len(installed),
    }, indent=2)


@mcp.tool()
def switch_harness(harness_id: str) -> str:
    """Switch the active harness to manage a different MCP client.

    Args:
        harness_id: Target harness ID. One of: opencode, claude-desktop, cursor,
                    windsurf, cline, zed, continue.
    """
    if harness_id not in HARNESSES:
        return json.dumps({
            "error": f"Unknown harness: {harness_id}",
            "available": list(HARNESSES.keys()),
        }, indent=2)

    try:
        config_mgr.harness_id = harness_id
        config_mgr.load()
        servers = config_mgr.list_servers()

        return json.dumps({
            "success": True,
            "switched_to": harness_id,
            "harness": HARNESSES[harness_id].name,
            "config_path": str(config_mgr.config_path),
            "servers_found": len(servers),
            "servers": list(servers.keys()),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_active_harness() -> str:
    """Get the currently active harness and its configuration path."""
    h = get_harness(config_mgr.harness_id)
    if not h:
        return json.dumps({"error": "No active harness"}, indent=2)

    return json.dumps({
        "active": h.id,
        "name": h.name,
        "description": h.description,
        "config_path": str(config_mgr.config_path),
        "config_exists": config_mgr.config_path.exists(),
        "server_shape": h.server_shape,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# SERVER MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_servers(verbose: bool = False) -> str:
    """List all configured MCP servers for the active harness.

    Args:
        verbose: If true, include full config details for each server.
    """
    config_mgr.load()
    servers = config_mgr.list_servers()
    harness_name = _harness_name()

    if not servers:
        return json.dumps({
            "harness": harness_name,
            "servers": [],
            "message": "No MCP servers configured.",
        }, indent=2)

    result = []
    for name, cfg in servers.items():
        entry = {
            "name": name,
            "enabled": cfg.get("enabled", True),
            "type": cfg.get("type", "unknown"),
        }
        if verbose:
            entry["config"] = cfg
            token_info = token_store.get_token_info(name)
            if token_info:
                entry["token"] = {
                    "preview": token_info.get("token_preview", "N/A"),
                    "expires_at": token_info.get("expires_at"),
                }
            else:
                entry["token"] = None

        result.append(entry)

    return json.dumps({
        "harness": harness_name,
        "servers": result,
        "count": len(result),
    }, indent=2)


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
    """Add a new MCP server to the active harness configuration.

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

    existing = config_mgr.get_server(name)
    if existing and not force:
        return json.dumps({
            "error": f"Server '{name}' already exists. Use force=true to overwrite.",
            "existing_config": existing,
        }, indent=2)

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

    if existing:
        config_mgr.update_server(name, server_config)
        action = "updated"
    else:
        config_mgr.add_server(name, server_config)
        action = "added"

    harness_name = _harness_name()

    return json.dumps({
        "success": True,
        "action": action,
        "server": name,
        "harness": harness_name,
        "config": server_config,
    }, indent=2)


@mcp.tool()
def remove_server(name: str) -> str:
    """Remove an MCP server from the active harness configuration.

    Args:
        name: Name of the server to remove.
    """
    config_mgr.load()

    if not config_mgr.get_server(name):
        return json.dumps({"error": f"Server '{name}' not found."}, indent=2)

    config_mgr.remove_server(name)
    token_store.revoke(name)

    harness_name = _harness_name()

    return json.dumps({
        "success": True,
        "action": "removed",
        "server": name,
        "harness": harness_name,
    }, indent=2)


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
        "harness": config_mgr.harness_id,
        "config": server,
    }

    token_info = token_store.get_token_info(name)
    if token_info:
        result["token"] = {
            "preview": token_info.get("token_preview", "N/A"),
            "created_at": token_info.get("created_at"),
            "expires_at": token_info.get("expires_at"),
        }

    history = health_checker.get_history(name, limit=5)
    if history:
        result["health_history"] = history

    catalog_info = registry.get_template(name)
    if catalog_info:
        result["catalog"] = {
            "description": catalog_info.get("description"),
            "docs_url": catalog_info.get("docs_url"),
            "category": catalog_info.get("category"),
        }

    return json.dumps(result, indent=2)


@mcp.tool()
def enable_server(name: str) -> str:
    """Enable a disabled MCP server.

    Args:
        name: Name of the server to enable.
    """
    config_mgr.load()
    ok = config_mgr.enable_server(name)
    if not ok:
        return json.dumps({"error": f"Server '{name}' not found."}, indent=2)
    return json.dumps({"success": True, "action": "enabled", "server": name}, indent=2)


@mcp.tool()
def disable_server(name: str) -> str:
    """Disable an MCP server without removing it.

    Args:
        name: Name of the server to disable.
    """
    config_mgr.load()
    ok = config_mgr.disable_server(name)
    if not ok:
        return json.dumps({"error": f"Server '{name}' not found."}, indent=2)
    return json.dumps({"success": True, "action": "disabled", "server": name}, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH & MONITORING
# ══════════════════════════════════════════════════════════════════════════════

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
        "harness": config_mgr.harness_id,
        "result": status.to_dict(),
    }, indent=2)


@mcp.tool()
def health_check() -> str:
    """Run health check on all configured MCP servers in the active harness."""
    config_mgr.load()
    servers = config_mgr.list_servers()

    if not servers:
        return json.dumps({"results": {}, "message": "No servers configured."}, indent=2)

    results = health_checker.check_all(servers)

    healthy = sum(1 for r in results.values() if r.get("status") == "healthy")
    unhealthy = sum(1 for r in results.values() if r.get("status") == "unhealthy")
    unknown = sum(1 for r in results.values() if r.get("status") == "unknown")
    timeout = sum(1 for r in results.values() if r.get("status") == "timeout")

    return json.dumps({
        "harness": config_mgr.harness_id,
        "summary": {
            "total": len(results),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unknown": unknown,
            "timeout": timeout,
        },
        "results": results,
    }, indent=2)


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


# ══════════════════════════════════════════════════════════════════════════════
# TOKEN MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

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


@mcp.tool()
def retrieve_token(server_name: str) -> str:
    """Retrieve the decrypted API token for a server.

    USE WITH CAUTION - returns the actual token value.
    Only call when you need to inject the token into a server config.

    Args:
        server_name: Name of the server.
    """
    token = token_store.retrieve(server_name)
    if not token:
        return json.dumps({"error": f"No token found for '{server_name}'."}, indent=2)

    return json.dumps({
        "server": server_name,
        "token": token,
        "warning": "Token is decrypted. Do not log or share this value.",
    }, indent=2)


@mcp.tool()
def list_token_backends() -> str:
    """List available token storage backends and their status.

    Shows encryption status and storage backend info.
    """
    encrypted = token_store.is_encrypted

    return json.dumps({
        "backends": {
            "encrypted_sqlite": {
                "available": True,
                "encrypted": encrypted,
                "description": "Local SQLite with Fernet AES-128-CBC encryption",
                "status": "active" + (" (encrypted)" if encrypted else " (plaintext - set MCP_MANAGER_MASTER_PASSWORD!)"),
            },
            "windows_credential_manager": {
                "available": token_store._is_windows(),
                "description": "System keychain (bonus, not primary)",
                "status": "available on Windows" if token_store._is_windows() else "not Windows",
            },
        },
        "recommendation": "Set MCP_MANAGER_MASTER_PASSWORD env var for encryption" if not encrypted else "Tokens are encrypted with Fernet",
        "db_path": str(token_store.db_path),
    }, indent=2)


@mcp.tool()
def list_all_tokens() -> str:
    """List all stored tokens (previews only, never full values)."""
    tokens = token_store.list_all()
    return json.dumps({
        "tokens": tokens,
        "count": len(tokens),
    }, indent=2)


@mcp.tool()
def get_token_history(server_name: str) -> str:
    """Get the rotation history for a server's tokens.

    Args:
        server_name: Name of the server.
    """
    history = token_store.get_history(server_name)
    return json.dumps({
        "server": server_name,
        "history": history,
        "count": len(history),
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT / IMPORT / CROSS-HARNESS SYNC
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def export_config(include_tokens: bool = False) -> str:
    """Export the entire MCP configuration of the active harness as JSON.

    Args:
        include_tokens: If true, include token values (DANGEROUS - only use for backups).
    """
    config_mgr.load()
    exported = config_mgr.export_config(include_tokens=include_tokens)

    return json.dumps({
        "harness": config_mgr.harness_id,
        "config": json.loads(exported),
        "note": "Tokens included" if include_tokens else "Tokens redacted (use include_tokens=true for full export)",
    }, indent=2)


@mcp.tool()
def import_config(config_json: str, merge: bool = True) -> str:
    """Import MCP configuration from a JSON string into the active harness.

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
            "harness": config_mgr.harness_id,
            "servers_count": len(servers),
            "servers": list(servers.keys()),
        }, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def export_for_harness(target_harness: str) -> str:
    """Export the current servers in the format of a different harness.

    Use this to migrate servers between OpenCode, Claude Desktop, Cursor, etc.

    Args:
        target_harness: Target harness ID (e.g. "claude-desktop", "cursor", "windsurf").
    """
    if target_harness not in HARNESSES:
        return json.dumps({
            "error": f"Unknown harness: {target_harness}",
            "available": list(HARNESSES.keys()),
        }, indent=2)

    config_mgr.load()
    exported = config_mgr.export_for_harness(target_harness)
    target_info = get_harness(target_harness)

    return json.dumps({
        "source_harness": config_mgr.harness_id,
        "target_harness": target_harness,
        "target_name": target_info.name if target_info else target_harness,
        "config": json.loads(exported),
        "note": f"Import this JSON into {target_info.name if target_info else target_harness}" if target_info else "",
    }, indent=2)


@mcp.tool()
def sync_to_harness(target_harness: str, merge: bool = True) -> str:
    """Sync all servers from the active harness to another harness.

    Copies all server configs from the current harness to the target harness,
    converting formats automatically.

    Args:
        target_harness: Target harness ID (e.g. "claude-desktop", "cursor").
        merge: If true, merge with existing target config. If false, replace.
    """
    if target_harness not in HARNESSES:
        return json.dumps({
            "error": f"Unknown harness: {target_harness}",
            "available": list(HARNESSES.keys()),
        }, indent=2)

    config_mgr.load()
    servers = config_mgr.list_servers()

    target_mgr = ConfigManager(harness_id=target_harness)
    target_mgr.load()

    added = 0
    updated = 0
    for name, cfg in servers.items():
        existing = target_mgr.get_server(name)
        if existing:
            target_mgr.update_server(name, cfg)
            updated += 1
        else:
            target_mgr.add_server(name, cfg)
            added += 1

    target_mgr.save()

    source_name = _harness_name()
    _th = get_harness(target_harness)
    target_name = _th.name if _th else target_harness

    return json.dumps({
        "success": True,
        "source": source_name,
        "target": target_name,
        "servers_synced": len(servers),
        "added": added,
        "updated": updated,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# CATALOG
# ══════════════════════════════════════════════════════════════════════════════

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

    harness_name = _harness_name()

    return json.dumps({
        "success": True,
        "action": action,
        "server": name,
        "harness": harness_name,
        "catalog_entry": server_id,
        "config": server_config,
        "note": template.get("description", ""),
    }, indent=2)


# ── Startup ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
