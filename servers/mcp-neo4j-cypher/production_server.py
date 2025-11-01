#!/usr/bin/env python3
"""
Production Neo4j MCP Server - Uses lazy driver initialization for Databricks
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 80)
print("MCP NEO4J CYPHER SERVER (Production)")
print("=" * 80)

print("\nStep 1: Import modules")
from mcp_neo4j_cypher.server import create_mcp_server
print("✓ Modules imported")

print("\nStep 2: Read configuration from environment")
# Neo4j credentials (validated at startup, used by get_driver() on first tool call)
neo4j_uri = os.getenv("NEO4J_URI")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")

# Server configuration
neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")
port = int(os.getenv("PORT", os.getenv("DATABRICKS_APP_PORT", "8000")))
namespace = os.getenv("NEO4J_NAMESPACE", "")
read_timeout = int(os.getenv("NEO4J_READ_TIMEOUT", "30"))
read_only = os.getenv("NEO4J_READ_ONLY", "false").lower() == "true"
schema_sample_size = int(os.getenv("NEO4J_SCHEMA_SAMPLE_SIZE", "1000"))

# Parse token limit (optional)
token_limit_str = os.getenv("NEO4J_RESPONSE_TOKEN_LIMIT")
token_limit = int(token_limit_str) if token_limit_str else None

print(f"  Neo4j URI: {neo4j_uri}")
print(f"  Neo4j Database: {neo4j_database}")
print(f"  Server Port: {port}")
print(f"  Namespace: '{namespace}'")
print(f"  Read Timeout: {read_timeout}s")
print(f"  Read Only: {read_only}")
print(f"  Schema Sample Size: {schema_sample_size}")
print(f"  Token Limit: {token_limit if token_limit else 'None'}")

# Validate Neo4j credentials at startup (fail-fast)
if not neo4j_uri or not neo4j_username or not neo4j_password:
    print("\n❌ ERROR: Missing required Neo4j credentials!")
    print("  Required environment variables: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
    print("  These should be provided via Databricks secrets in app.yaml")
    sys.exit(1)

print("✓ Configuration loaded and validated")

print("\nStep 3: Create MCP server")
print("  Note: Neo4j driver will be created lazily on first tool call")
print("  Credentials passed as parameters (read from environment at startup)")
mcp = create_mcp_server(
    neo4j_uri=neo4j_uri,
    neo4j_username=neo4j_username,
    neo4j_password=neo4j_password,
    database=neo4j_database,
    namespace=namespace,
    read_timeout=read_timeout,
    token_limit=token_limit,
    read_only=read_only,
    config_sample_size=schema_sample_size
)
print("✓ MCP server created successfully")

print("\nStep 4: Start FastMCP HTTP server")
print(f"  Host: 0.0.0.0")
print(f"  Port: {port}")
print(f"  Path: /mcp/")
print("\n  🚀 Starting server (this will block)...")

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=port)
