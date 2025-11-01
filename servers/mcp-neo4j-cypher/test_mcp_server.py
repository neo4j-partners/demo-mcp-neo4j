#!/usr/bin/env -S uv run
"""
Test MCP Neo4j Cypher Server - Databricks Deployment Validation
================================================================

This script tests the deployed MCP Neo4j Cypher server on Databricks Apps.

What This Script Does:
----------------------
1. Discovers your deployed MCP app on Databricks
2. Tests connectivity to the MCP endpoint
3. Lists all available tools from the server
4. Runs basic tests on Neo4j tools including aircraft structure query
5. Validates responses and error handling

MCP Endpoint Information:
-------------------------
The MCP server uses HTTP transport and serves at:
  - Endpoint path: /mcp/
  - Full URL: https://your-app-url.com/mcp/

Usage:
------
# Test the default app (mcp-neo4j-cypher)
uv run test_mcp_server.py

# Or make it executable and run directly
chmod +x test_mcp_server.py
./test_mcp_server.py

# Test a specific app by name
uv run test_mcp_server.py --app my-neo4j-mcp-server

# Test a specific URL directly
uv run test_mcp_server.py --url https://my-app.databricksapps.com/mcp/

Requirements:
-------------
This script uses uv for dependency management. Dependencies are automatically
installed from pyproject.toml when you run with 'uv run'.

Required packages:
- databricks-sdk
- databricks-mcp
- mcp

Authentication:
--------------
This script uses your Databricks CLI OAuth credentials.
Make sure you've run: databricks auth login
"""

import argparse
import asyncio
import json
import sys
from typing import Optional

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksOAuthClientProvider
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client as connect


# ==============================================================================
# MCP Client Functions
# ==============================================================================

async def list_tools(server_url: str, ws: WorkspaceClient):
    """
    List all available tools from the MCP server.

    Args:
        server_url: The MCP server endpoint URL (must include /mcp/ path)
        ws: WorkspaceClient for OAuth authentication

    Returns:
        List of tool objects from the MCP server

    Raises:
        Exception: If connection fails or tools cannot be listed
    """
    try:
        async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                return tools_response.tools
    except Exception as e:
        print(f"\n❌ Error connecting to {server_url}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        print(f"\nTroubleshooting:")
        print(f"   1. Verify the app is running: databricks apps get mcp-neo4j-cypher")
        print(f"   2. Check the URL includes /mcp/ endpoint")
        print(f"   3. Ensure OAuth is configured: databricks auth login")
        print(f"   4. Verify Neo4j credentials are set in Databricks secrets")
        raise


async def call_tool(server_url: str, tool_name: str, ws: WorkspaceClient, **kwargs):
    """
    Call a specific tool on the MCP server.

    Args:
        server_url: The MCP server endpoint URL
        tool_name: Name of the tool to call
        ws: WorkspaceClient for OAuth authentication
        **kwargs: Arguments to pass to the tool

    Returns:
        Tool response as a string

    Raises:
        Exception: If tool call fails
    """
    async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.call_tool(tool_name, kwargs)
            return "".join([c.text for c in response.content])


# ==============================================================================
# App Discovery and URL Construction
# ==============================================================================

def get_mcp_server_url(ws: WorkspaceClient, app_name: Optional[str] = None) -> tuple[str, dict]:
    """
    Get the MCP server URL for a Databricks App.

    Args:
        ws: WorkspaceClient instance
        app_name: Optional app name (defaults to "mcp-neo4j-cypher")

    Returns:
        Tuple of (mcp_url, app_info_dict)

    Raises:
        Exception: If app is not found or not running
    """
    if app_name is None:
        app_name = "mcp-neo4j-cypher"

    print(f"📋 Looking up app: {app_name}")

    try:
        app_info = ws.apps.get(app_name)
    except Exception as e:
        print(f"\n❌ Error: App '{app_name}' not found")
        print(f"   {str(e)}")
        print(f"\nAvailable apps:")
        try:
            apps = list(ws.apps.list())
            for app in apps:
                print(f"   • {app.name}")
        except:
            print(f"   (Could not list apps)")
        sys.exit(1)

    # Check app status
    app_status = app_info.app_status.state if app_info.app_status else "UNKNOWN"

    # Convert enum to string for comparison
    app_status_str = str(app_status).split('.')[-1] if hasattr(app_status, 'name') else str(app_status)

    if app_status_str != "RUNNING":
        print(f"\n❌ Error: App is not running (status: {app_status_str})")
        if app_info.app_status and app_info.app_status.message:
            print(f"   Message: {app_info.app_status.message}")
        print(f"\n   Please deploy the app first: ./deploy.sh")
        sys.exit(1)

    # Construct MCP URL
    # Important: This server uses HTTP transport at /mcp/ endpoint
    mcp_url = f"{app_info.url}/mcp/"

    app_data = {
        "name": app_name,
        "url": app_info.url,
        "mcp_endpoint": mcp_url,
        "status": app_status_str,
        "workspace": ws.config.host,
    }

    return mcp_url, app_data


# ==============================================================================
# Tool Testing Functions
# ==============================================================================

async def run_tool_tests(server_url: str, ws: WorkspaceClient):
    """
    Run comprehensive tests on MCP Neo4j Cypher tools.

    This demonstrates how to:
    - List available tools
    - Call tools with different parameter types
    - Handle Neo4j schema and query responses
    - Validate tool behavior

    Args:
        server_url: The MCP server endpoint URL
        ws: WorkspaceClient for authentication
    """
    print(f"\n🔌 Connecting to MCP server: {server_url}\n")

    # Test 1: List available tools
    print("=" * 70)
    print("📋 STEP 1: List Available Tools")
    print("=" * 70)

    tools = await list_tools(server_url, ws)
    print(f"✅ Found {len(tools)} tools\n")

    for tool in tools:
        print(f"  🔧 {tool.name}")
        print(f"     Description: {tool.description}")
        params = tool.inputSchema.get('properties', {})
        if params:
            print(f"     Parameters: {', '.join(params.keys())}")
        print()

    # Test 2: Test get_neo4j_schema (if available)
    print("=" * 70)
    print("🧪 STEP 2: Test Neo4j MCP Tools")
    print("=" * 70)
    print()

    # Find the schema tool (may have namespace prefix)
    schema_tool = None
    read_tool = None
    write_tool = None

    for tool in tools:
        if tool.name.endswith("get_neo4j_schema"):
            schema_tool = tool.name
        elif tool.name.endswith("read_neo4j_cypher"):
            read_tool = tool.name
        elif tool.name.endswith("write_neo4j_cypher"):
            write_tool = tool.name

    # Test: get_neo4j_schema
    if schema_tool:
        print(f"Test 1: {schema_tool}(sample_size=100)")
        print("  Purpose: Test Neo4j schema retrieval with small sample")
        try:
            result = await call_tool(server_url, schema_tool, ws, sample_size=100)
            print(f"  Result length: {len(result)} characters")

            # Try to parse as JSON
            try:
                schema_data = json.loads(result)
                if isinstance(schema_data, dict):
                    print(f"  ✅ Schema retrieved successfully")
                    print(f"  📊 Schema contains {len(schema_data)} entries")
                    # Show first few keys
                    keys = list(schema_data.keys())[:3]
                    if keys:
                        print(f"  Sample entries: {', '.join(keys)}")
                else:
                    print(f"  ℹ️  Schema format: {type(schema_data)}")
            except json.JSONDecodeError:
                print(f"  ⚠️  Response is not JSON (may be text description)")
                print(f"  Preview: {result[:200]}...")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
        print()
    else:
        print("⚠️  get_neo4j_schema tool not found")
        print()

    # Test: read_neo4j_cypher - Basic test
    if read_tool:
        print(f"Test 2: {read_tool}(query='RETURN 1 AS test')")
        print("  Purpose: Test basic Cypher read query")
        try:
            result = await call_tool(
                server_url,
                read_tool,
                ws,
                query="RETURN 1 AS test",
                params={}
            )
            print(f"  Result: {result}")

            # Try to parse as JSON
            try:
                query_result = json.loads(result)
                if query_result and isinstance(query_result, list):
                    print(f"  ✅ Query executed successfully")
                    print(f"  📊 Returned {len(query_result)} rows")
            except json.JSONDecodeError:
                print(f"  ℹ️  Response: {result}")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
        print()

        # Test: Aircraft Structure Query
        print(f"Test 3: {read_tool} - Aircraft Structure View")
        print("  Purpose: Query complete system hierarchy for aircraft N95040A")

        # Aircraft structure Cypher query
        aircraft_query = """
        MATCH path = (aircraft:Aircraft {registration: 'N95040A'})-[:HAS_SYSTEM*]->(component)
        RETURN
            aircraft.registration AS aircraft,
            [node in nodes(path) | {
                type: labels(node)[0],
                name: CASE
                    WHEN 'Aircraft' in labels(node) THEN node.registration
                    WHEN 'System' in labels(node) THEN node.name
                    WHEN 'Component' in labels(node) THEN node.name
                    ELSE node.id
                END,
                properties: properties(node)
            }] AS hierarchy
        LIMIT 10
        """

        try:
            result = await call_tool(
                server_url,
                read_tool,
                ws,
                query=aircraft_query,
                params={}
            )

            # Try to parse and display results
            try:
                query_result = json.loads(result)
                if query_result and isinstance(query_result, list):
                    print(f"  ✅ Aircraft structure query executed successfully")
                    print(f"  📊 Found {len(query_result)} system hierarchies")

                    # Display sample results
                    if query_result:
                        print(f"\n  Sample hierarchy path:")
                        first_result = query_result[0]
                        if 'hierarchy' in first_result:
                            hierarchy = first_result['hierarchy']
                            for i, node in enumerate(hierarchy):
                                indent = "    " * (i + 1)
                                node_type = node.get('type', 'Unknown')
                                node_name = node.get('name', 'N/A')
                                print(f"{indent}↳ {node_type}: {node_name}")

                        print(f"\n  Full result preview (first 500 chars):")
                        print(f"  {json.dumps(query_result, indent=2)[:500]}...")
                else:
                    print(f"  ℹ️  Query returned: {result[:200]}")
            except json.JSONDecodeError:
                print(f"  ⚠️  Could not parse JSON response")
                print(f"  Raw response: {result[:300]}...")
            except Exception as e:
                print(f"  ⚠️  Error processing results: {str(e)}")
                print(f"  Result: {result[:200]}...")
        except Exception as e:
            print(f"  ❌ Error executing aircraft query: {str(e)}")
        print()
    else:
        print("⚠️  read_neo4j_cypher tool not found")
        print()

    # Test: write_neo4j_cypher (if available and enabled)
    if write_tool:
        print(f"Test 4: {write_tool} availability")
        print("  Purpose: Check if write operations are enabled")
        print(f"  ✅ Write tool is available: {write_tool}")
        print("  ℹ️  Skipping write test (use with caution on production data)")
        print()
    else:
        print("ℹ️  write_neo4j_cypher tool not available (may be disabled)")
        print()

    # Summary
    print("=" * 70)
    print("✅ Tool Tests Completed!")
    print("=" * 70)


# ==============================================================================
# Main Entry Point
# ==============================================================================

async def main():
    """Main entry point for the test script."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Test MCP Neo4j Cypher server deployed on Databricks Apps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test default app
  python test_mcp_server.py

  # Test specific app by name
  python test_mcp_server.py --app my-neo4j-server

  # Test specific URL
  python test_mcp_server.py --url https://my-app.databricksapps.com/mcp/

Important Notes:
  - The server uses HTTP transport at /mcp/ endpoint
  - Ensure your Databricks CLI is authenticated: databricks auth login
  - The app must be in RUNNING state
  - Neo4j credentials must be configured in Databricks secrets
        """
    )
    parser.add_argument(
        "--app",
        type=str,
        help="App name to test (default: mcp-neo4j-cypher)"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Direct MCP server URL (overrides --app)"
    )

    args = parser.parse_args()

    # Print header
    print("\n" + "=" * 70)
    print("🚀 MCP Neo4j Cypher Server Test - Databricks Deployment")
    print("=" * 70)

    # Initialize Databricks client
    print("\n🔐 Initializing Databricks client...")
    try:
        ws = WorkspaceClient()
        print(f"✅ Connected to workspace: {ws.config.host}")
    except Exception as e:
        print(f"\n❌ Error: Could not initialize Databricks client")
        print(f"   {str(e)}")
        print(f"\n   Please run: databricks auth login")
        sys.exit(1)

    # Get MCP server URL
    if args.url:
        # Use provided URL directly
        server_url = args.url
        print(f"\n📍 Using provided URL: {server_url}")

        # Validate URL format
        if not server_url.startswith(("http://", "https://")):
            print(f"\n❌ Error: Invalid URL format (must start with http:// or https://)")
            sys.exit(1)

        if not server_url.endswith("/mcp/"):
            print(f"\n⚠️  Warning: URL should end with /mcp/ endpoint")
            print(f"   Proceeding anyway...")
    else:
        # Discover app and construct URL
        server_url, app_data = get_mcp_server_url(ws, args.app)

        print(f"\n✅ Found app: {app_data['name']}")
        print(f"   App URL: {app_data['url']}")
        print(f"   MCP Endpoint: {app_data['mcp_endpoint']}")
        print(f"   Status: {app_data['status']}")

    # Run tests
    try:
        await run_tool_tests(server_url, ws)

        print("\n" + "=" * 70)
        print("📊 Summary")
        print("=" * 70)
        print(f"\n✅ Successfully tested MCP server at: {server_url}")
        print(f"\nTo use this MCP server in your code:")
        print(f'  MCP_SERVER_URL = "{server_url}"')
        print(f"\nNext steps:")
        print(f"  1. Integrate with AI agents using this URL")
        print(f"  2. Use Neo4j tools to query your graph database")
        print(f"  3. Monitor with: databricks apps logs mcp-neo4j-cypher")
        print()

    except Exception as e:
        print(f"\n❌ Tests failed with error:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
