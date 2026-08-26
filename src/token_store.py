"""Secure token storage using SQLite."""

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class TokenStore:
    """Bezpečné ukládání API tokenů v SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~"), ".config", "mcp-manager", "tokens.db"
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Inicializuje databázi."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    server_name TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL,
                    token_preview TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_name TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    token_preview TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    retired_at TEXT
                )
            """)

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hashuje token pro bezpečné uložení."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _preview_token(token: str) -> str:
        """Vytvoří bezpečný preview tokenu."""
        if len(token) <= 8:
            return token[:2] + "***"
        return token[:4] + "***" + token[-4:]

    def store(self, server_name: str, token: str, expires_at: Optional[str] = None):
        """Uloží token pro server."""
        now = datetime.now().isoformat()
        token_hash = self._hash_token(token)
        preview = self._preview_token(token)

        with sqlite3.connect(str(self.db_path)) as conn:
            # Pokud existuje aktivní token, přesuň do historie
            existing = conn.execute(
                "SELECT token_hash, token_preview, created_at FROM tokens WHERE server_name = ? AND is_active = 1",
                (server_name,),
            ).fetchone()

            if existing:
                conn.execute(
                    """INSERT INTO token_history (server_name, token_hash, token_preview, created_at, retired_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (server_name, existing[0], existing[1], existing[2], now),
                )

            # Ulož nový token
            conn.execute(
                """INSERT OR REPLACE INTO tokens (server_name, token_hash, token_preview, created_at, expires_at, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (server_name, token_hash, preview, now, expires_at),
            )

    def get_token_info(self, server_name: str) -> Optional[dict]:
        """Vrátí info o tokenu (ne samotný token)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tokens WHERE server_name = ? AND is_active = 1",
                (server_name,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    def has_valid_token(self, server_name: str) -> bool:
        """Zkontroluje zda server má platný token."""
        info = self.get_token_info(server_name)
        if not info:
            return False

        if info.get("expires_at"):
            try:
                expires = datetime.fromisoformat(info["expires_at"])
                if expires < datetime.now():
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def get_expiring_soon(self, days: int = 7) -> list[dict]:
        """Vrátí servery s expirujícími tokeny."""
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM tokens
                   WHERE is_active = 1
                   AND expires_at IS NOT NULL
                   AND expires_at < ?""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def revoke(self, server_name: str) -> bool:
        """Deaktivuje token pro server."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "UPDATE tokens SET is_active = 0 WHERE server_name = ? AND is_active = 1",
                (server_name,),
            )
            return cursor.rowcount > 0

    def get_history(self, server_name: str) -> list[dict]:
        """Vrátí historii tokenů pro server."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM token_history WHERE server_name = ? ORDER BY created_at DESC",
                (server_name,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_all(self) -> dict[str, dict]:
        """Vrátí všechny uložené tokeny (info, ne hodnoty)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tokens WHERE is_active = 1 ORDER BY server_name"
            ).fetchall()
            return {dict(r)["server_name"]: dict(r) for r in rows}

    def clear_all(self):
        """Vymaže všechny tokeny."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM tokens")
            conn.execute("DELETE FROM token_history")
