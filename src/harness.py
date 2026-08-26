"""Harness definitions for supported MCP clients.

Each harness represents an AI coding application that uses MCP servers.
This module defines the config file paths, top-level keys, and format
converters for each harness.

Supported harnesses:
    - OpenCode
    - Claude Desktop
    - Cursor
    - Windsurf
    - Cline
    - Zed
    - Continue.dev
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Harness:
    """Definition of an MCP client harness."""

    id: str
    name: str
    description: str
    config_path: str  # Path template with env var placeholders
    top_level_key: str  # Key containing MCP servers in the config file
    server_shape: str  # "keyed_object", "array", or "nested_object"


def _get_windows_path(template: str) -> str:
    """Resolve environment variable placeholders in a path template.

    Supports %VAR% (Windows) and ${VAR} (Unix) notation.
    """
    result = template
    for var in ["APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME"]:
        val = os.environ.get(var, "")
        if val:
            result = result.replace(f"%{var}%", val)
            result = result.replace(f"${{{var}}}", val)
    return result


# ── Harness Definitions ────────────────────────────────────────────────────────

HARNESSES: dict[str, Harness] = {
    "opencode": Harness(
        id="opencode",
        name="OpenCode",
        description="OpenCode AI coding assistant",
        config_path="%USERPROFILE%/.config/opencode/opencode.json",
        top_level_key="mcp",
        server_shape="keyed_object",
    ),
    "claude-desktop": Harness(
        id="claude-desktop",
        name="Claude Desktop",
        description="Anthropic Claude Desktop application",
        config_path="%APPDATA%/Claude/claude_desktop_config.json",
        top_level_key="mcpServers",
        server_shape="keyed_object",
    ),
    "cursor": Harness(
        id="cursor",
        name="Cursor",
        description="Cursor AI code editor",
        config_path="%USERPROFILE%/.cursor/mcp.json",
        top_level_key="mcpServers",
        server_shape="keyed_object",
    ),
    "windsurf": Harness(
        id="windsurf",
        name="Windsurf",
        description="Codeium Windsurf AI editor",
        config_path="%USERPROFILE%/.codeium/windsurf/mcp_config.json",
        top_level_key="mcpServers",
        server_shape="keyed_object",
    ),
    "cline": Harness(
        id="cline",
        name="Cline",
        description="Cline VS Code extension (AI coding assistant)",
        config_path="%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
        top_level_key="mcpServers",
        server_shape="keyed_object",
    ),
    "zed": Harness(
        id="zed",
        name="Zed",
        description="Zed code editor with AI features",
        config_path="%APPDATA%/Zed/settings.json",
        top_level_key="context_servers",
        server_shape="nested_object",
    ),
    "continue": Harness(
        id="continue",
        name="Continue.dev",
        description="Continue.dev AI code assistant",
        config_path="%USERPROFILE%/.continue/config.json",
        top_level_key="mcpServers",
        server_shape="array",
    ),
}


def get_harness(harness_id: str) -> Optional[Harness]:
    """Return a harness by its ID."""
    return HARNESSES.get(harness_id)


def list_harnesses() -> list[dict[str, Any]]:
    """Return a list of all harnesses with their resolved config paths."""
    return [
        {
            "id": h.id,
            "name": h.name,
            "description": h.description,
            "config_path": _get_windows_path(h.config_path),
            "config_exists": Path(_get_windows_path(h.config_path)).exists(),
            "server_shape": h.server_shape,
        }
        for h in HARNESSES.values()
    ]


def detect_installed() -> list[str]:
    """Detect which harnesses have config files on the current system."""
    installed = []
    for h in HARNESSES.values():
        path = _get_windows_path(h.config_path)
        if Path(path).exists():
            installed.append(h.id)
    return installed


# ── Format Converters ──────────────────────────────────────────────────────────

def to_universal(server_config: dict[str, Any], harness_id: str) -> dict[str, Any]:
    """Convert a server config from harness format to universal format.

    Universal format:
        {
            "type": "local" | "npx" | "docker" | "remote",
            "command": ["cmd", "arg1", ...],
            "url": "...",
            "env": {"KEY": "val"},
            "enabled": true/false
        }
    """
    harness = get_harness(harness_id)
    if not harness:
        return server_config

    if harness_id == "opencode":
        return _from_opencode(server_config)
    elif harness_id == "zed":
        return _from_zed(server_config)
    elif harness_id == "continue":
        return _from_continue(server_config)
    elif harness.server_shape == "keyed_object":
        return _from_claude_format(server_config)
    return server_config


def from_universal(server_config: dict[str, Any], harness_id: str) -> dict[str, Any]:
    """Convert universal format to the format of a given harness."""
    harness = get_harness(harness_id)
    if not harness:
        return server_config

    if harness_id == "opencode":
        return _to_opencode(server_config)
    elif harness_id == "zed":
        return _to_zed(server_config)
    elif harness_id == "continue":
        return _to_continue(server_config)
    elif harness.server_shape == "keyed_object":
        return _to_claude_format(server_config)
    return server_config


# ── OpenCode Converters ────────────────────────────────────────────────────────

def _from_opencode(cfg: dict) -> dict:
    """Convert OpenCode format to universal format."""
    result = {}
    if cfg.get("type"):
        result["type"] = cfg["type"]
    if cfg.get("command"):
        result["command"] = cfg["command"]
    if cfg.get("url"):
        result["url"] = cfg["url"]
    if cfg.get("environment"):
        result["env"] = dict(cfg["environment"])
    if cfg.get("headers"):
        result["headers"] = dict(cfg["headers"])
    result["enabled"] = cfg.get("enabled", True)
    return result


def _to_opencode(cfg: dict) -> dict:
    """Convert universal format to OpenCode format."""
    result = {"enabled": cfg.get("enabled", True)}
    if cfg.get("type"):
        result["type"] = cfg["type"]
    if cfg.get("command"):
        result["command"] = cfg["command"]
    if cfg.get("url"):
        result["url"] = cfg["url"]
    if cfg.get("env"):
        result["environment"] = dict(cfg["env"])
    if cfg.get("headers"):
        result["headers"] = dict(cfg["headers"])
    return result


# ── Claude/Cursor/Windsurf/Cline Converters ───────────────────────────────────

def _from_claude_format(cfg: dict) -> dict:
    """Convert Claude/Cursor/Windsurf/Cline format to universal format.

    These harnesses use: {"command": "npx", "args": ["-y", "pkg"], "env": {...}}
    """
    result = {}
    if cfg.get("command"):
        cmd = cfg["command"]
        args = cfg.get("args", [])
        result["command"] = [cmd] + args
    if cfg.get("url"):
        result["url"] = cfg["url"]
    if cfg.get("env"):
        result["env"] = dict(cfg["env"])
    if cfg.get("headers"):
        result["headers"] = dict(cfg["headers"])
    result["enabled"] = not cfg.get("disabled", False)
    return result


def _to_claude_format(cfg: dict) -> dict:
    """Convert universal format to Claude/Cursor/Windsurf/Cline format."""
    result = {}
    command = cfg.get("command", [])
    if command:
        result["command"] = command[0]
        if len(command) > 1:
            result["args"] = command[1:]
    if cfg.get("url"):
        result["url"] = cfg["url"]
    if cfg.get("env"):
        result["env"] = dict(cfg["env"])
    if cfg.get("headers"):
        result["headers"] = dict(cfg["headers"])
    if not cfg.get("enabled", True):
        result["disabled"] = True
    return result


# ── Zed Converters ────────────────────────────────────────────────────────────

def _from_zed(cfg: dict) -> dict:
    """Convert Zed format to universal format.

    Zed uses: {"source": "custom", "command": {"path": "...", "args": [...], "env": {}}}
    """
    result = {}
    cmd = cfg.get("command", {})
    if isinstance(cmd, dict):
        path = cmd.get("path", "")
        args = cmd.get("args", [])
        result["command"] = [path] + args
        if cmd.get("env"):
            result["env"] = dict(cmd["env"])
    if cfg.get("url"):
        result["url"] = cfg["url"]
    result["enabled"] = True
    return result


def _to_zed(cfg: dict) -> dict:
    """Convert universal format to Zed format."""
    result: dict[str, Any] = {"source": "custom"}
    command = cfg.get("command", [])
    cmd_obj = {}
    if command:
        cmd_obj["path"] = command[0]
        if len(command) > 1:
            cmd_obj["args"] = command[1:]
    if cfg.get("env"):
        cmd_obj["env"] = dict(cfg["env"])
    if cmd_obj:
        result["command"] = cmd_obj
    return result


# ── Continue.dev Converters ───────────────────────────────────────────────────

def _from_continue(cfg: dict) -> dict:
    """Convert Continue.dev format to universal format.

    Continue uses: [{"name": "...", "command": "npx", "args": [...], "env": {...}}]
    """
    result = {}
    if cfg.get("command"):
        cmd = cfg["command"]
        args = cfg.get("args", [])
        result["command"] = [cmd] + args
    if cfg.get("url"):
        result["url"] = cfg["url"]
    if cfg.get("env"):
        result["env"] = dict(cfg["env"])
    result["enabled"] = not cfg.get("disabled", False)
    return result


def _to_continue(cfg: dict) -> dict:
    """Convert universal format to Continue.dev format."""
    result = {}
    command = cfg.get("command", [])
    if command:
        result["command"] = command[0]
        if len(command) > 1:
            result["args"] = command[1:]
    if cfg.get("url"):
        result["url"] = cfg["url"]
    if cfg.get("env"):
        result["env"] = dict(cfg["env"])
    return result
