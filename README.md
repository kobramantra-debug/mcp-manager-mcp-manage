# MCP Manager

[![CI](https://github.com/kobramantra-debug/mcp-manager-mcp-manage/actions/workflows/ci.yml/badge.svg)](https://github.com/kobramantra-debug/mcp-manager-mcp-manage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Universal MCP Server Manager — add, remove, monitor, and configure all your MCP servers from one place.

## Features

- **7 harnesses** — OpenCode, Claude Desktop, Cursor, Windsurf, Cline, Zed, Continue.dev
- **23 tools** — server management, health checks, token rotation, cross-harness sync
- **20+ server catalog** — GitHub, Supabase, Playwright, Docker, PostgreSQL, and more
- **Encrypted tokens** — Fernet AES-128-CBC with PBKDF2 key derivation
- **Cross-harness sync** — migrate servers between different AI coding tools

## Quick Start

```bash
git clone https://github.com/kobramantra-debug/mcp-manager-mcp-manage.git
cd mcp-manager-mcp-manage
pip install -e .
```

## Installation

### From source

```bash
git clone https://github.com/kobramantra-debug/mcp-manager-mcp-manage.git
cd mcp-manager-mcp-manage
pip install -e .
```

### Docker

```bash
docker build -t mcp-manager .
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_HARNESS` | `opencode` | Active harness to manage |
| `MCP_CONFIG_PATH` | *(auto-detected)* | Override config file path |
| `MCP_MANAGER_MASTER_PASSWORD` | *(none)* | Master password for Fernet encryption |

### OpenCode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "mcp-manager": {
      "type": "local",
      "command": ["python", "-m", "src"],
      "cwd": "/path/to/mcp-manager",
      "enabled": true
    }
  }
}
```

### Claude Desktop

Add to `%APPDATA%/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-manager": {
      "command": "python",
      "args": ["-m", "src"],
      "cwd": "/path/to/mcp-manager"
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mcp-manager": {
      "command": "python",
      "args": ["-m", "src"],
      "cwd": "/path/to/mcp-manager"
    }
  }
}
```

### Docker (STDIO)

```json
{
  "mcp": {
    "mcp-manager": {
      "type": "docker",
      "command": ["docker", "run", "-i", "--rm", "mcp-manager"],
      "enabled": true
    }
  }
}
```

## Examples

### 1. List all harnesses and see which are installed

```python
list_harnesses_info()
```

```json
{
  "harnesses": [
    {"id": "opencode", "name": "OpenCode", "installed": true, "is_active": true},
    {"id": "claude-desktop", "name": "Claude Desktop", "installed": true, "is_active": false},
    {"id": "cursor", "name": "Cursor", "installed": false, "is_active": false},
    {"id": "windsurf", "name": "Windsurf", "installed": false, "is_active": false},
    {"id": "cline", "name": "Cline", "installed": false, "is_active": false},
    {"id": "zed", "name": "Zed", "installed": false, "is_active": false},
    {"id": "continue", "name": "Continue.dev", "installed": false, "is_active": false}
  ],
  "active": "opencode",
  "installed_count": 2
}
```

### 2. Switch to Claude Desktop and list its servers

```python
switch_harness("claude-desktop")
list_servers()
```

```json
{
  "harness": "Claude Desktop",
  "servers": [
    {"name": "github", "enabled": true, "type": "docker"},
    {"name": "playwright", "enabled": true, "type": "npx"}
  ],
  "count": 2
}
```

### 3. Add GitHub MCP server from the catalog

```python
add_from_catalog("github")
```

```json
{
  "success": true,
  "action": "added",
  "server": "github",
  "harness": "OpenCode",
  "catalog_entry": "github",
  "config": {
    "type": "docker",
    "command": ["docker", "run", "-i", "--rm", "-e", "GITHUB_TOKEN={env:GITHUB_TOKEN}", "ghcr.io/github/github-mcp-server"],
    "enabled": true
  }
}
```

### 4. Add a custom remote server

```python
add_server(
    name="my-api",
    server_type="remote",
    url="https://api.example.com/mcp",
    env_vars="API_KEY=sk-123,BASE_URL=https://api.example.com"
)
```

```json
{
  "success": true,
  "action": "added",
  "server": "my-api",
  "config": {
    "type": "remote",
    "url": "https://api.example.com/mcp",
    "environment": {"API_KEY": "sk-123", "BASE_URL": "https://api.example.com"},
    "enabled": true
  }
}
```

### 5. Run health check on all servers

```python
health_check()
```

```json
{
  "harness": "opencode",
  "summary": {"total": 3, "healthy": 2, "unhealthy": 1, "unknown": 0, "timeout": 0},
  "results": {
    "github": {"status": "healthy", "message": "Server: github-mcp-server", "latency_ms": 1250.3},
    "playwright": {"status": "healthy", "message": "Server: playwright", "latency_ms": 890.1},
    "my-api": {"status": "unhealthy", "message": "No response (exit 1)", "latency_ms": 5000.0}
  }
}
```

### 6. Sync all servers from OpenCode to Cursor

```python
sync_to_harness("cursor")
```

```json
{
  "success": true,
  "source": "OpenCode",
  "target": "Cursor",
  "servers_synced": 3,
  "added": 3,
  "updated": 0
}
```

### 7. Rotate a token with expiration

```python
rotate_token("github", "ghp_new_token_abc123", expires_at="2026-12-31")
```

```json
{
  "success": true,
  "action": "token_rotated",
  "server": "github",
  "preview": "ghp_***abc123",
  "expires_at": "2026-12-31"
}
```

### 8. Search the server catalog

```python
search_catalog("database")
```

```json
{
  "results": [
    {"id": "postgres", "name": "PostgreSQL", "description": "PostgreSQL database server", "category": "database"},
    {"id": "sqlite", "name": "SQLite", "description": "SQLite database server", "category": "database"}
  ],
  "count": 2
}
```

### 9. Export config for a different harness

```python
export_for_harness("claude-desktop")
```

```json
{
  "source_harness": "opencode",
  "target_harness": "claude-desktop",
  "config": {
    "mcpServers": {
      "github": {"command": "docker", "args": ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"]},
      "playwright": {"command": "npx", "args": ["-y", "@anthropic/playwright-mcp"]}
    }
  },
  "note": "Import this JSON into Claude Desktop"
}
```

### 10. List all stored tokens (safe — previews only)

```python
list_all_tokens()
```

```json
{
  "tokens": {
    "github": {"token_preview": "ghp_***abc123", "storage_backend": "encrypted_sqlite"},
    "supabase": {"token_preview": "sb-***xyz789", "storage_backend": "encrypted_sqlite"}
  },
  "count": 2
}
```

## Tools Reference

### Harness Management
| Tool | Description |
|------|-------------|
| `list_harnesses_info` | List all harnesses and installation status |
| `switch_harness` | Switch active harness |
| `get_active_harness` | Get current harness info |

### Server Management
| Tool | Description |
|------|-------------|
| `list_servers` | List configured servers |
| `add_server` | Add a new server |
| `remove_server` | Remove a server |
| `get_server_detail` | Get server details |
| `enable_server` | Enable a disabled server |
| `disable_server` | Disable a server |

### Health & Monitoring
| Tool | Description |
|------|-------------|
| `test_connection` | Test a single server |
| `health_check` | Test all servers |
| `get_logs` | Get health check history |

### Token Management
| Tool | Description |
|------|-------------|
| `rotate_token` | Update API token |
| `retrieve_token` | Get decrypted token (use with caution) |
| `list_all_tokens` | List stored tokens (previews only) |
| `get_token_history` | Get rotation history |
| `list_token_backends` | Show encryption status |

### Export / Import / Sync
| Tool | Description |
|------|-------------|
| `export_config` | Export config as JSON |
| `import_config` | Import config from JSON |
| `export_for_harness` | Export in another harness format |
| `sync_to_harness` | Sync servers to another harness |

### Catalog
| Tool | Description |
|------|-------------|
| `search_catalog` | Search server catalog |
| `add_from_catalog` | Add server from catalog |

## Supported Harnesses

| Harness | Config Path | Format |
|---------|-------------|--------|
| OpenCode | `~/.config/opencode/opencode.json` | `mcp` (keyed object) |
| Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` | `mcpServers` (keyed object) |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` (keyed object) |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` (keyed object) |
| Cline | `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | `mcpServers` (keyed object) |
| Zed | `%APPDATA%/Zed/settings.json` | `context_servers` (nested object) |
| Continue.dev | `~/.continue/config.json` | `mcpServers` (array) |

## Server Catalog

| Server | Type | Description |
|--------|------|-------------|
| github | docker | GitHub MCP Server |
| supabase | npx | Supabase MCP Server |
| playwright | npx | Playwright browser automation |
| chrome-devtools | npx | Chrome DevTools Protocol |
| context7 | npx | Context7 documentation lookup |
| filesystem | local | Filesystem access |
| git | local | Git operations |
| postgres | npx | PostgreSQL database |
| sqlite | npx | SQLite database |
| docker | local | Docker management |
| brave-search | npx | Brave Search API |
| fetch | npx | HTTP fetch tool |
| memory | local | Knowledge graph memory |
| slack | npx | Slack workspace integration |
| gdrive | npx | Google Drive access |
| google-maps | npx | Google Maps API |
| puppeteer | npx | Puppeteer browser automation |
| everything | npx | Universal search |
| stitch | npx | Stitch UI design |

## Token Security

Tokens are stored in an encrypted SQLite database using Fernet (AES-128-CBC).

Set `MCP_MANAGER_MASTER_PASSWORD` to enable encryption:

```bash
# Linux/macOS
export MCP_MANAGER_MASTER_PASSWORD="your-secure-password"

# Windows
set MCP_MANAGER_MASTER_PASSWORD=your-secure-password
```

Without a master password, tokens are stored in plaintext (not recommended for production).

## License

MIT License — see [LICENSE](LICENSE) for details.
