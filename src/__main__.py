"""Entry point for running as a module: python -m src"""
import sys
import os

# Ensure the src directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
