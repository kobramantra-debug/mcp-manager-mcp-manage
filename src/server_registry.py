"""Registry of known MCP servers with default configurations.

Provides a catalog of popular MCP servers (GitHub, Supabase, Playwright, etc.)
with their default commands, environment variables, and documentation links.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class ServerRegistry:
    """Catalog of known MCP servers with pre-configured templates."""

    def __init__(self):
        self._catalog: dict[str, dict[str, Any]] = {}
        self._load_builtin_catalog()

    def _load_builtin_catalog(self):
        """Load the built-in catalog from servers.json."""
        catalog_path = Path(__file__).parent / "templates" / "servers.json"
        if catalog_path.exists():
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._catalog = data.get("servers", {})

    def list_available(self) -> dict[str, dict[str, Any]]:
        """Return all servers in the catalog."""
        return dict(self._catalog)

    def get_template(self, server_id: str) -> Optional[dict[str, Any]]:
        """Get the configuration template for a server."""
        return self._catalog.get(server_id)

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search servers by name, description, or category."""
        query_lower = query.lower()
        results = []
        for server_id, info in self._catalog.items():
            if (query_lower in server_id.lower() or
                query_lower in info.get("name", "").lower() or
                query_lower in info.get("description", "").lower() or
                query_lower in info.get("category", "").lower()):
                results.append({"id": server_id, **info})
        return results

    def list_categories(self) -> dict[str, list[str]]:
        """Return servers grouped by category."""
        categories: dict[str, list[str]] = {}
        for server_id, info in self._catalog.items():
            cat = info.get("category", "other")
            categories.setdefault(cat, []).append(server_id)
        return categories

    def add_to_catalog(self, server_id: str, config: dict[str, Any]):
        """Add a custom server to the catalog at runtime."""
        self._catalog[server_id] = config

    def remove_from_catalog(self, server_id: str) -> bool:
        """Remove a server from the catalog at runtime."""
        if server_id in self._catalog:
            del self._catalog[server_id]
            return True
        return False

    def get_config_for_add(
        self,
        server_id: str,
        custom_name: Optional[str] = None,
        custom_env: Optional[dict[str, str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Generate a config dict for adding this server to a harness."""
        template = self.get_template(server_id)
        if not template:
            return None

        config: dict[str, Any] = {
            "type": template.get("type", "local"),
            "enabled": True,
        }

        if template.get("command"):
            config["command"] = list(template["command"])

        if template.get("url"):
            config["url"] = template["url"]

        if template.get("headers"):
            config["headers"] = dict(template["headers"])

        env: dict[str, str] = {}
        for var in template.get("env_vars", []):
            env[var] = f"{{env:{var}}}"
        if custom_env:
            env.update(custom_env)
        if env:
            config["environment"] = env

        return config
