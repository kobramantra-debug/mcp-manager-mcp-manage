# MCP Manager

Universal MCP Server Manager - add, remove, monitor and configure all your MCP servers from one place.

## Features

- **List servers** - See all configured MCP servers and their status
- **Add/Remove servers** - Manage your MCP configuration without editing JSON
- **Health monitoring** - Check if your MCP servers are running
- **Token management** - Securely store and rotate API tokens
- **Export/Import** - Transfer your configuration between machines
- **Server catalog** - Browse known MCP servers and add them with one command

## Supported Server Types

- `local` - Local command execution
- `npx` - Node.js package execution (via npx)
- `docker` - Docker container execution
- `remote` - Remote HTTP endpoints

## Installation

### Docker (recommended)

```bash
docker build -t mcp-manager .
```

### pip

```bash
pip install .
```

## Usage

### OpenCode

Add to your `opencode.json`:

```json
{
  "mcp": {
    "mcp-manager": {
      "type": "local",
      "command": ["docker", "run", "-i", "--rm",
        "-v", "C:\\Users\\you\\.config\\opencode:/config:ro",
        "mcp-manager"],
      "enabled": true,
      "environment": {
        "MCP_CONFIG_PATH": "/config/opencode.json"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-manager": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
        "-v", "~/.config/opencode:/config:ro",
        "mcp-manager"],
      "env": {
        "MCP_CONFIG_PATH": "/config/opencode.json"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_servers` | List all configured MCP servers |
| `add_server` | Add a new MCP server |
| `remove_server` | Remove an MCP server |
| `get_server_detail` | Get detailed info about a server |
| `test_connection` | Test if a server responds |
| `health_check` | Check health of all servers |
| `export_config` | Export configuration as JSON |
| `import_config` | Import configuration from JSON |
| `rotate_token` | Update API token for a server |
| `get_logs` | Get health check logs |
| `search_catalog` | Browse known MCP servers |
| `add_from_catalog` | Add server from built-in catalog |

## Server Catalog

The built-in catalog includes:

- **github** - GitHub MCP Server (51 tools)
- **supabase** - Supabase MCP Server
- **playwright** - Playwright browser automation
- **context7** - Library documentation lookup
- **chrome-devtools** - Chrome DevTools
- **stitch** - UI/UX design generation
- **alza-scraper** - Alza.cz price scraper

## Security

- Tokens are stored in a local SQLite database
- Export redacts tokens by default
- Config changes create automatic backups
- All operations are logged for audit

## License

MIT
