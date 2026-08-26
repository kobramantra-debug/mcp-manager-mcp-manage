"""Multi-harness configuration manager for MCP servers.

Handles reading, writing, and migrating MCP configuration files across
different harnesses (OpenCode, Claude Desktop, Cursor, Windsurf, Cline, Zed, Continue).
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .harness import (
    HARNESSES,
    Harness,
    detect_installed,
    from_universal,
    get_harness,
    list_harnesses,
    to_universal,
    _get_windows_path,
)


class ConfigManager:
    """Manages MCP server configurations across multiple harnesses."""

    def __init__(self, harness_id: Optional[str] = None, config_path: Optional[str] = None):
        self._harness_id = harness_id or "opencode"
        self._config_path_override = config_path
        self._config: dict[str, Any] = {}
        self._harness: Optional[Harness] = get_harness(self._harness_id)

    @property
    def harness_id(self) -> str:
        """Currently active harness ID."""
        return self._harness_id

    @harness_id.setter
    def harness_id(self, value: str):
        """Switch the active harness."""
        h = get_harness(value)
        if not h:
            raise ValueError(f"Unknown harness: {value}. Available: {list(HARNESSES.keys())}")
        self._harness_id = value
        self._harness = h
        self._config = {}

    @property
    def config_path(self) -> Path:
        """Resolved path to the config file for the active harness."""
        if self._config_path_override:
            return Path(self._config_path_override)
        if self._harness:
            return Path(_get_windows_path(self._harness.config_path))
        return Path("~/.config/opencode/opencode.json").expanduser()

    def load(self) -> dict[str, Any]:
        """Load the config file from disk."""
        path = self.config_path
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = {}
        return self._config

    def save(self, config: Optional[dict[str, Any]] = None):
        """Save the config file with automatic backup."""
        if config is not None:
            self._config = config

        if not self._config:
            raise ValueError("No config loaded. Call load() first.")

        path = self.config_path

        # Create backup before overwriting
        if path.exists():
            backup = path.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            shutil.copy2(path, backup)

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    @property
    def config(self) -> dict[str, Any]:
        """The loaded configuration data."""
        if not self._config:
            self.load()
        return self._config

    # ── Server Operations ────────────────────────────────────────────────────

    def _get_servers_key(self) -> str:
        """Return the top-level key that contains MCP servers."""
        if self._harness:
            return self._harness.top_level_key
        return "mcp"

    def list_servers(self) -> dict[str, dict[str, Any]]:
        """List all MCP servers in universal format."""
        key = self._get_servers_key()
        raw_servers = self.config.get(key, {})
        servers = {}

        if isinstance(raw_servers, list):
            # Continue.dev uses an array format
            for entry in raw_servers:
                name = entry.get("name", "unknown")
                servers[name] = to_universal(entry, self._harness_id)
        elif isinstance(raw_servers, dict):
            for name, cfg in raw_servers.items():
                servers[name] = to_universal(cfg, self._harness_id)

        return servers

    def get_server(self, name: str) -> Optional[dict[str, Any]]:
        """Get a specific server config in universal format."""
        servers = self.list_servers()
        return servers.get(name)

    def add_server(self, name: str, universal_config: dict[str, Any]) -> bool:
        """Add a server in universal format to the config."""
        key = self._get_servers_key()
        if key not in self._config:
            self._config[key] = {}

        harness_config = from_universal(universal_config, self._harness_id)

        if self._harness and self._harness.server_shape == "array":
            # Continue.dev array format
            if key not in self._config:
                self._config[key] = []
            harness_config["name"] = name
            self._config[key].append(harness_config)
        else:
            if name in self._config[key]:
                return False
            self._config[key][name] = harness_config

        self.save()
        return True

    def update_server(self, name: str, universal_config: dict[str, Any]) -> bool:
        """Update an existing server configuration."""
        key = self._get_servers_key()
        servers = self.config.get(key, {})

        if self._harness and self._harness.server_shape == "array":
            for i, entry in enumerate(self._config.get(key, [])):
                if entry.get("name") == name:
                    harness_config = from_universal(universal_config, self._harness_id)
                    harness_config["name"] = name
                    self._config[key][i] = harness_config
                    self.save()
                    return True
            return False
        else:
            if name not in servers:
                return False
            harness_config = from_universal(universal_config, self._harness_id)
            self._config[key][name] = harness_config
            self.save()
            return True

    def remove_server(self, name: str) -> bool:
        """Remove a server from the config."""
        key = self._get_servers_key()

        if self._harness and self._harness.server_shape == "array":
            arr = self._config.get(key, [])
            new_arr = [e for e in arr if e.get("name") != name]
            if len(new_arr) == len(arr):
                return False
            self._config[key] = new_arr
        else:
            servers = self._config.get(key, {})
            if name not in servers:
                return False
            del self._config[key][name]

        self.save()
        return True

    def enable_server(self, name: str) -> bool:
        """Enable a disabled server."""
        return self._set_server_enabled(name, True)

    def disable_server(self, name: str) -> bool:
        """Disable a server without removing it."""
        return self._set_server_enabled(name, False)

    def _set_server_enabled(self, name: str, enabled: bool) -> bool:
        """Internal method to toggle server enabled/disabled state."""
        key = self._get_servers_key()
        if self._harness and self._harness.server_shape == "array":
            for entry in self._config.get(key, []):
                if entry.get("name") == name:
                    entry["disabled"] = not enabled
                    self.save()
                    return True
            return False
        else:
            server = self._config.get(key, {}).get(name)
            if not server:
                return False
            if self._harness_id == "opencode":
                server["enabled"] = enabled
            else:
                server["disabled"] = not enabled
            self.save()
            return True

    # ── Export / Import ──────────────────────────────────────────────────────

    def export_config(self, include_tokens: bool = False) -> str:
        """Export the config as JSON. Tokens are redacted by default."""
        export = json.loads(json.dumps(self.config))
        if not include_tokens:
            self._redact_tokens(export)
        return json.dumps(export, indent=2, ensure_ascii=False)

    def import_config(self, json_str: str, merge: bool = True) -> dict[str, Any]:
        """Import config from a JSON string. Optionally merge with existing."""
        imported = json.loads(json_str)
        if merge and self._config:
            key = self._get_servers_key()
            existing = self._config.get(key, {})
            new = imported.get(key, {})
            if isinstance(existing, dict) and isinstance(new, dict):
                existing.update(new)
                imported[key] = existing
        self._config = imported
        self.save()
        return self._config

    def backup(self) -> str:
        """Create a timestamped backup of the current config."""
        path = self.config_path
        backup = path.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(path, backup)
        return str(backup)

    # ── Cross-Harness Operations ─────────────────────────────────────────────

    def export_for_harness(self, target_harness_id: str) -> str:
        """Export config converted to the format of another harness."""
        servers = self.list_servers()
        target = get_harness(target_harness_id)
        if not target:
            raise ValueError(f"Unknown harness: {target_harness_id}")

        result: dict[str, Any] = {}
        key = target.top_level_key

        if target.server_shape == "array":
            result[key] = [
                {"name": name, **from_universal(cfg, target_harness_id)}
                for name, cfg in servers.items()
            ]
        else:
            result[key] = {
                name: from_universal(cfg, target_harness_id)
                for name, cfg in servers.items()
            }

        return json.dumps(result, indent=2, ensure_ascii=False)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _redact_tokens(obj: Any):
        """Recursively redact sensitive values with {REDACTED}."""
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if isinstance(obj[key], str) and any(
                    t in key.lower() for t in ["token", "key", "secret", "password", "apikey"]
                ):
                    obj[key] = "{REDACTED}"
                elif isinstance(obj[key], (dict, list)):
                    ConfigManager._redact_tokens(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                ConfigManager._redact_tokens(item)
