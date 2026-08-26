"""Configuration manager for opencode.json."""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """Správa konfigurace opencode.json."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or self._find_config())
        self._config: dict[str, Any] = {}

    @staticmethod
    def _find_config() -> str:
        """Najde opencode.json v běžných lokacích."""
        candidates = [
            os.path.join(os.path.expanduser("~"), ".config", "opencode", "opencode.json"),
            os.path.join(os.getcwd(), "opencode.json"),
            os.path.join(os.getcwd(), ".opencode", "opencode.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return candidates[0]

    def load(self) -> dict[str, Any]:
        """Načte konfiguraci ze souboru."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = {"$schema": "https://opencode.ai/config.json", "mcp": {}}
        return self._config

    def save(self, config: Optional[dict[str, Any]] = None):
        """Uloží konfiguraci do souboru (s backup)."""
        if config is not None:
            self._config = config

        if not self._config:
            raise ValueError("No config loaded. Call load() first.")

        # Backup před zápisem
        if self.config_path.exists():
            backup_path = self.config_path.with_suffix(
                f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            shutil.copy2(self.config_path, backup_path)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    @property
    def config(self) -> dict[str, Any]:
        if not self._config:
            self.load()
        return self._config

    @property
    def mcp_servers(self) -> dict[str, Any]:
        """Vrátí MCP sekci z konfigurace."""
        return self.config.get("mcp", {}) or {}

    def get_server(self, name: str) -> Optional[dict[str, Any]]:
        """Vrátí konfiguraci konkrétního MCP serveru."""
        return self.mcp_servers.get(name)

    def list_servers(self) -> dict[str, dict[str, Any]]:
        """Vrátí seznam všech MCP serverů."""
        return dict(self.mcp_servers)

    def add_server(self, name: str, server_config: dict[str, Any]) -> bool:
        """Přidá MCP server do konfigurace."""
        cfg = self.config
        if "mcp" not in cfg:
            cfg["mcp"] = {}

        if name in cfg["mcp"]:
            return False  # Server již existuje

        cfg["mcp"][name] = server_config
        self.save()
        return True

    def update_server(self, name: str, server_config: dict[str, Any]) -> bool:
        """Aktualizuje konfiguraci MCP serveru."""
        cfg = self.config
        if "mcp" not in cfg or name not in cfg["mcp"]:
            return False

        cfg["mcp"][name] = server_config
        self.save()
        return True

    def remove_server(self, name: str) -> bool:
        """Odebere MCP server z konfigurace."""
        cfg = self.config
        if "mcp" not in cfg or name not in cfg["mcp"]:
            return False

        del cfg["mcp"][name]
        self.save()
        return True

    def enable_server(self, name: str) -> bool:
        """Aktivuje MCP server."""
        server = self.get_server(name)
        if not server:
            return False
        server["enabled"] = True
        self.save()
        return True

    def disable_server(self, name: str) -> bool:
        """Deaktivuje MCP server."""
        server = self.get_server(name)
        if not server:
            return False
        server["enabled"] = False
        self.save()
        return True

    def export_config(self, include_tokens: bool = False) -> str:
        """Exportuje konfiguraci do JSON stringu."""
        export = json.loads(json.dumps(self.config))

        if not include_tokens:
            # Odstraní tokeny z exportu
            mcp = export.get("mcp", {})
            for name, server in mcp.items():
                env = server.get("environment", {})
                for key in list(env.keys()):
                    if any(t in key.lower() for t in ["token", "key", "secret", "password"]):
                        env[key] = "{REDACTED}"

        return json.dumps(export, indent=2, ensure_ascii=False)

    def import_config(self, json_str: str, merge: bool = True) -> dict[str, Any]:
        """Importuje konfiguraci z JSON stringu."""
        imported = json.loads(json_str)

        if merge and self._config:
            # Deep merge MCP sekcí
            imported_mcp = imported.get("mcp", {})
            existing_mcp = self._config.get("mcp", {})
            existing_mcp.update(imported_mcp)
            imported["mcp"] = existing_mcp

        self._config = imported
        self.save()
        return self._config

    def backup(self) -> str:
        """Vytvoří backup konfigurace."""
        backup_path = self.config_path.with_suffix(
            f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        shutil.copy2(self.config_path, backup_path)
        return str(backup_path)
