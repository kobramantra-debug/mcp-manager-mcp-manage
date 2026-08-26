"""MCP Manager - Comprehensive Test Suite.

Run with: python -m pytest tests/test_all.py -v
Or directly: python tests/test_all.py
"""

import json
import os
import sys
import tempfile

# Ensure the src directory is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config_manager import ConfigManager
from src.harness import (
    HARNESSES,
    detect_installed,
    from_universal,
    get_harness,
    list_harnesses,
    to_universal,
)
from src.server_registry import ServerRegistry
from src.token_store import TokenStore
from src.health_checker import HealthChecker

PASS = 0
FAIL = 0


def test(name: str, condition: bool, detail: str = ""):
    """Assert a test condition and print the result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK  {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def test_harness_module():
    """Test harness definitions, detection, and format conversion."""
    print("\n--- 1. HARNESS MODULE ---")

    test("7 harnesses defined", len(HARNESSES) == 7)
    test("list_harnesses returns 7", len(list_harnesses()) == 7)
    test("detect_installed returns list", isinstance(detect_installed(), list))
    test("get_harness('opencode') exists", get_harness("opencode") is not None)
    test("get_harness('claude-desktop') exists", get_harness("claude-desktop") is not None)
    test("get_harness('cursor') exists", get_harness("cursor") is not None)
    test("get_harness('windsurf') exists", get_harness("windsurf") is not None)
    test("get_harness('cline') exists", get_harness("cline") is not None)
    test("get_harness('zed') exists", get_harness("zed") is not None)
    test("get_harness('continue') exists", get_harness("continue") is not None)
    test("get_harness('invalid') returns None", get_harness("invalid") is None)

    # Claude/Cursor/Windsurf/Cline format conversion
    claude_universal = to_universal({"command": "npx", "args": ["-y", "pkg"], "env": {"KEY": "val"}}, "claude-desktop")
    test("Claude format to universal", claude_universal.get("command") == ["npx", "-y", "pkg"])
    test("Claude env to universal", claude_universal.get("env", {}).get("KEY") == "val")

    # Zed format conversion
    zed_universal = to_universal({"source": "custom", "command": {"path": "npx", "args": ["-y", "pkg"], "env": {"K": "V"}}}, "zed")
    test("Zed format to universal", zed_universal.get("command") == ["npx", "-y", "pkg"])

    # Continue format conversion
    continue_universal = to_universal({"command": "npx", "args": ["-y", "pkg"], "name": "test"}, "continue")
    test("Continue format to universal", continue_universal.get("command") == ["npx", "-y", "pkg"])

    # Universal to Claude format
    claude_out = from_universal({"command": ["npx", "-y", "pkg"], "env": {"A": "B"}}, "claude-desktop")
    test("Universal to Claude command", claude_out.get("command") == "npx")
    test("Universal to Claude args", claude_out.get("args") == ["-y", "pkg"])

    # Universal to Zed format
    zed_out = from_universal({"command": ["npx", "-y", "pkg"]}, "zed")
    test("Universal to Zed source", zed_out.get("source") == "custom")
    test("Universal to Zed command.path", zed_out.get("command", {}).get("path") == "npx")

    # Universal to Continue format
    continue_out = from_universal({"command": ["npx", "-y", "pkg"]}, "continue")
    test("Universal to Continue command", continue_out.get("command") == "npx")
    test("Universal to Continue args", continue_out.get("args") == ["-y", "pkg"])


def test_config_manager():
    """Test config reading, writing, and cross-harness operations."""
    print("\n--- 2. CONFIG MANAGER ---")

    # OpenCode config
    cm = ConfigManager(harness_id="opencode")
    cm.load()
    servers = cm.list_servers()
    test("OpenCode config loaded", len(servers) > 0, f"got {len(servers)} servers")

    # Switch harness
    cm.harness_id = "claude-desktop"
    test("Switch to claude-desktop", cm.harness_id == "claude-desktop")

    # Switch back
    cm.harness_id = "opencode"
    test("Switch back to opencode", cm.harness_id == "opencode")

    # Temp config operations
    temp_config = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump({"mcp": {}}, temp_config)
    temp_config.close()

    cm2 = ConfigManager(config_path=temp_config.name)
    cm2.load()
    ok = cm2.add_server("test-srv", {"type": "local", "command": ["echo", "hello"], "enabled": True})
    test("Add server to temp config", ok)
    test("Server appears in list", "test-srv" in cm2.list_servers())

    ok = cm2.update_server("test-srv", {"type": "npx", "command": ["npx", "pkg"], "enabled": True})
    test("Update server", ok)
    test("Server updated", cm2.list_servers()["test-srv"].get("command") == ["npx", "pkg"])

    ok = cm2.remove_server("test-srv")
    test("Remove server", ok)
    test("Server gone", "test-srv" not in cm2.list_servers())

    # Enable/disable
    cm2.add_server("toggle-srv", {"type": "local", "command": ["echo"], "enabled": True})
    cm2.disable_server("toggle-srv")
    test("Disable server", cm2.list_servers()["toggle-srv"].get("enabled") == False)
    cm2.enable_server("toggle-srv")
    test("Enable server", cm2.list_servers()["toggle-srv"].get("enabled") == True)
    cm2.remove_server("toggle-srv")

    # Export/import
    cm2.add_server("export-test", {"type": "local", "command": ["echo"]})
    exported = cm2.export_config()
    test("Export returns JSON", len(exported) > 10)

    # Cross-harness export
    cross = cm2.export_for_harness("claude-desktop")
    test("Cross-harness export works", "mcpServers" in cross or "command" in cross)

    os.unlink(temp_config.name)


def test_token_store():
    """Test encrypted token storage and retrieval."""
    print("\n--- 3. TOKEN STORE ---")

    ts = TokenStore(master_password="test-password-123")
    test("TokenStore initialized", ts is not None)
    test("Is encrypted", ts.is_encrypted)

    ts.store("srv-a", "ghp_secret_token_abc123")
    test("Store token", ts.has_valid_token("srv-a"))

    info = ts.get_token_info("srv-a")
    test("Token info exists", info is not None)
    test("Token preview", info["token_preview"].startswith("ghp_"))
    test("Backend is encrypted_sqlite", info["storage_backend"] == "encrypted_sqlite")

    retrieved = ts.retrieve("srv-a")
    test("Retrieve token", retrieved == "ghp_secret_token_abc123")

    # Rotate
    ts.store("srv-a", "ghp_new_token_xyz789")
    test("Rotate token", ts.retrieve("srv-a") == "ghp_new_token_xyz789")

    history = ts.get_history("srv-a")
    test("History has 1 entry", len(history) == 1)

    # Multiple servers
    ts.store("srv-b", "sk-ant-api-key-123")
    test("Multiple servers", ts.has_valid_token("srv-a") and ts.has_valid_token("srv-b"))

    all_tokens = ts.list_all()
    test("List all shows 2", len(all_tokens) == 2)

    # Revoke
    ts.revoke("srv-a")
    test("Revoke token", not ts.has_valid_token("srv-a"))
    test("Other token still valid", ts.has_valid_token("srv-b"))

    # Revoke all
    ts.clear_all()
    test("Clear all", len(ts.list_all()) == 0)

    # Plaintext mode
    ts_plain = TokenStore()
    test("Plaintext mode", not ts_plain.is_encrypted)
    ts_plain.store("plain-srv", "token123")
    test("Plaintext store/retrieve", ts_plain.retrieve("plain-srv") == "token123")
    ts_plain.clear_all()


def test_server_registry():
    """Test the server catalog."""
    print("\n--- 4. SERVER REGISTRY ---")

    reg = ServerRegistry()
    all_servers = reg.list_available()
    test("Registry has 20 servers", len(all_servers) == 20)

    for server_id in ["github", "supabase", "playwright", "filesystem", "git", "postgres", "docker", "brave-search", "fetch", "memory", "slack"]:
        test(f"{server_id} in catalog", server_id in all_servers)

    # Search
    browser_results = reg.search("browser")
    test("Search 'browser' finds results", len(browser_results) >= 2)
    test("Playwright in browser results", any(r["id"] == "playwright" for r in browser_results))

    db_results = reg.search("database")
    test("Search 'database' finds results", len(db_results) >= 1)

    template = reg.get_template("github")
    test("Get template github", template is not None)
    test("Template has command", "command" in template)
    test("Template has description", "description" in template)


def test_health_checker():
    """Test health check functionality."""
    print("\n--- 5. HEALTH CHECKER ---")

    hc = HealthChecker()
    test("HealthChecker initialized", hc is not None)

    result = hc.check_server("nonexistent", {"type": "npx", "command": ["echo"]})
    test("Check returns result", result is not None)
    test("Check has status", hasattr(result, "to_dict"))

    history = hc.get_history("nonexistent")
    test("History returns list", isinstance(history, list))


def test_integration():
    """Test full workflow: create config, add servers, export, sync."""
    print("\n--- 6. INTEGRATION TEST ---")

    import shutil

    temp_opencode = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump({"mcp": {}}, temp_opencode)
    temp_opencode.close()

    temp_cursor = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
    json.dump({"mcpServers": {}}, temp_cursor)
    temp_cursor.close()

    # OpenCode manager
    cm_src = ConfigManager(config_path=temp_opencode.name)
    cm_src.load()
    cm_src.add_server("github", {"type": "docker", "command": ["docker", "run", "ghcr"]})
    cm_src.add_server("playwright", {"type": "npx", "command": ["npx", "playwright"]})
    test("Integration: add 2 servers", len(cm_src.list_servers()) == 2)

    # Cursor manager
    cm_dst = ConfigManager(harness_id="cursor", config_path=temp_cursor.name)
    cm_dst.load()

    # Sync
    servers = cm_src.list_servers()
    for name, cfg in servers.items():
        cm_dst.add_server(name, cfg)
    test("Integration: sync to cursor", len(cm_dst.list_servers()) == 2)

    # Verify format conversion
    cursor_servers = cm_dst.list_servers()
    github_cfg = cursor_servers.get("github", {})
    test("Integration: cursor format has command", "command" in github_cfg)

    # Cleanup
    os.unlink(temp_opencode.name)
    os.unlink(temp_cursor.name)


if __name__ == "__main__":
    print("=" * 60)
    print("MCP MANAGER - COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    test_harness_module()
    test_config_manager()
    test_token_store()
    test_server_registry()
    test_health_checker()
    test_integration()

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)

    if FAIL > 0:
        sys.exit(1)
