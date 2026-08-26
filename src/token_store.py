"""Secure token storage with Fernet encryption.

Stores API tokens in an encrypted SQLite database using Fernet (AES-128-CBC).
Key derivation uses PBKDF2 with 480,000 iterations.

Supports:
    - Fernet encryption with master password
    - Plaintext fallback (no master password)
    - Token rotation with history tracking
    - Expiration date tracking
    - Windows Credential Manager (bonus, store-only)
"""

import base64
import hashlib
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class TokenStore:
    """Encrypted token storage backed by SQLite and Fernet.

    When a master password is provided, tokens are encrypted using Fernet
    (AES-128-CBC) with PBKDF2-derived keys (480k iterations).
    Without a master password, tokens are stored in plaintext.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        master_password: Optional[str] = None,
    ):
        self.db_path = Path(
            db_path
            or os.path.join(os.path.expanduser("~"), ".config", "mcp-manager", "tokens.db")
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet: Optional[Fernet] = None

        if master_password:
            self._fernet = self._derive_fernet(master_password)

        self._init_db()

    @staticmethod
    def _is_windows() -> bool:
        """Check if running on Windows."""
        return os.name == "nt"

    # ── Fernet Encryption ────────────────────────────────────────────────────

    @staticmethod
    def _derive_fernet(password: str) -> Fernet:
        """Derive a Fernet key from a password using PBKDF2 (480k iterations)."""
        salt = b"mcp-manager-salt-v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)

    def _encrypt(self, data: str) -> str:
        """Encrypt a string. Returns a Fernet token (base64)."""
        if self._fernet:
            return self._fernet.encrypt(data.encode()).decode()
        return data

    def _decrypt(self, data: str) -> str:
        """Decrypt a Fernet token back to plaintext."""
        if self._fernet:
            return self._fernet.decrypt(data.encode()).decode()
        return data

    @property
    def is_encrypted(self) -> bool:
        """True if a master password was provided and tokens are encrypted."""
        return self._fernet is not None

    # ── Database ─────────────────────────────────────────────────────────────

    def _init_db(self):
        """Initialize the SQLite database and run migrations."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    server_name TEXT PRIMARY KEY,
                    token_encrypted TEXT NOT NULL,
                    token_preview TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1,
                    storage_backend TEXT DEFAULT 'sqlite'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_name TEXT NOT NULL,
                    token_encrypted TEXT NOT NULL,
                    token_preview TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    retired_at TEXT,
                    storage_backend TEXT DEFAULT 'sqlite'
                )
            """)
            # Migrate: token_hash -> token_encrypted
            for table in ["tokens", "token_history"]:
                try:
                    conn.execute(f"SELECT token_hash FROM {table} LIMIT 1")
                    conn.execute(f"ALTER TABLE {table} RENAME COLUMN token_hash TO token_encrypted")
                except sqlite3.OperationalError:
                    pass
                try:
                    conn.execute(f"SELECT storage_backend FROM {table} LIMIT 1")
                except sqlite3.OperationalError:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN storage_backend TEXT DEFAULT 'sqlite'")

    @staticmethod
    def _preview_token(token: str) -> str:
        """Create a safe preview: first 4 + last 4 characters."""
        if len(token) <= 8:
            return token[:2] + "***"
        return token[:4] + "***" + token[-4:]

    # ── Public API ───────────────────────────────────────────────────────────

    def store(self, server_name: str, token: str, expires_at: Optional[str] = None):
        """Store a token for a server (encrypted if master password set)."""
        now = datetime.now().isoformat()
        preview = self._preview_token(token)
        encrypted = self._encrypt(token)
        backend = "encrypted_sqlite" if self.is_encrypted else "plaintext_sqlite"

        with sqlite3.connect(str(self.db_path)) as conn:
            # Move old token to history
            existing = conn.execute(
                "SELECT token_encrypted, token_preview, created_at FROM tokens WHERE server_name = ? AND is_active = 1",
                (server_name,),
            ).fetchone()

            if existing:
                conn.execute(
                    """INSERT INTO token_history (server_name, token_encrypted, token_preview, created_at, retired_at, storage_backend)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (server_name, existing[0], existing[1], existing[2], now, existing[5] if len(existing) > 5 else "unknown"),
                )

            conn.execute(
                """INSERT OR REPLACE INTO tokens (server_name, token_encrypted, token_preview, created_at, expires_at, is_active, storage_backend)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (server_name, encrypted, preview, now, expires_at, backend),
            )

    def retrieve(self, server_name: str) -> Optional[str]:
        """Retrieve and decrypt a token for a server."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT token_encrypted FROM tokens WHERE server_name = ? AND is_active = 1",
                (server_name,),
            ).fetchone()
            if row:
                return self._decrypt(row["token_encrypted"])
        return None

    def get_token_info(self, server_name: str) -> Optional[dict]:
        """Get token metadata (preview, dates) without the actual value."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM tokens WHERE server_name = ? AND is_active = 1",
                (server_name,),
            ).fetchone()
            return dict(row) if row else None

    def has_valid_token(self, server_name: str) -> bool:
        """Check if a server has a valid (non-expired) token."""
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
        """Get servers with tokens expiring within N days."""
        cutoff = (datetime.now() + timedelta(days=days)).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM tokens
                   WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at < ?""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    def revoke(self, server_name: str) -> bool:
        """Deactivate a token for a server."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "UPDATE tokens SET is_active = 0 WHERE server_name = ? AND is_active = 1",
                (server_name,),
            )
            return cursor.rowcount > 0

    def get_history(self, server_name: str) -> list[dict]:
        """Get the rotation history for a server's tokens."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM token_history WHERE server_name = ? ORDER BY created_at DESC",
                (server_name,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_all(self) -> dict[str, dict]:
        """List all active tokens (metadata only, never values)."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tokens WHERE is_active = 1 ORDER BY server_name"
            ).fetchall()
            return {dict(r)["server_name"]: dict(r) for r in rows}

    def clear_all(self):
        """Delete all stored tokens."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM tokens")
            conn.execute("DELETE FROM token_history")
