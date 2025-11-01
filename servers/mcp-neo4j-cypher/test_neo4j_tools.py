#!/usr/bin/env -S uv run
"""
Simple Tool Tester for MCP Neo4j Cypher Server

This script directly tests the deployed MCP server tools without using an LLM.

Usage:
    uv run test_neo4j_tools.py

    # Or make executable and run directly
    chmod +x test_neo4j_tools.py
    ./test_neo4j_tools.py

Requirements:
    - databricks auth login (must be run first)
    - Your Neo4j MCP server deployed to Databricks Apps
"""

import asyncio
import json
from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksOAuthClientProvider
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client as connect

# Your deployed MCP server URL (note: no trailing slash)
MCP_SERVER_URL = "https://mcp-neo4j-cypher-1098933906466604.4.azure.databricksapps.com/mcp"


async def list_available_tools(server_url: str, ws: WorkspaceClient):
    """List all tools available from the MCP server."""
    print("=" * 80)
    print("LISTING AVAILABLE TOOLS")
    print("=" * 80)

    async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()

            print(f"\n✅ Found {len(tools_response.tools)} tools:\n")
            for tool in tools_response.tools:
                print(f"📌 {tool.name}")
                print(f"   Description: {tool.description}")
                if tool.inputSchema:
                    print(f"   Parameters: {json.dumps(tool.inputSchema.get('properties', {}), indent=2)}")
                print()

            return tools_response.tools


async def test_get_schema(server_url: str, ws: WorkspaceClient):
    """Test the get_neo4j_schema tool."""
    print("=" * 80)
    print("TEST 1: Get Neo4j Schema")
    print("=" * 80)

    async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Call get_neo4j_schema with default sample size
            response = await session.call_tool("get_neo4j_schema", {"sample_size": 100})

            print("\n✅ Schema Response:")
            for content in response.content:
                if hasattr(content, 'text'):
                    text = content.text
                    if text and text.strip():
                        try:
                            # Try to parse as JSON
                            schema_data = json.loads(text)
                            print(json.dumps(schema_data, indent=2))
                        except json.JSONDecodeError:
                            # If not JSON, print as plain text
                            print(text)
                    else:
                        print("(empty response)")
            print()


async def test_aircraft_query(server_url: str, ws: WorkspaceClient):
    """Test querying aircraft structure for N95040A."""
    print("=" * 80)
    print("TEST 2: Aircraft Structure Query (N95040A)")
    print("=" * 80)

    # Aircraft structure Cypher query from test_mcp_server.py
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

    async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Call read_neo4j_cypher
            response = await session.call_tool("read_neo4j_cypher", {
                "query": aircraft_query,
                "params": {}
            })

            print("\n✅ Aircraft Query Results:")
            for content in response.content:
                if hasattr(content, 'text'):
                    text = content.text
                    if text and text.strip():
                        try:
                            results = json.loads(text)
                            print(json.dumps(results, indent=2))
                        except json.JSONDecodeError:
                            print(text)
                    else:
                        print("(empty response)")
            print()


async def test_simple_count_query(server_url: str, ws: WorkspaceClient):
    """Test a simple count query."""
    print("=" * 80)
    print("TEST 3: Simple Count Query")
    print("=" * 80)

    count_query = "MATCH (n:Aircraft) RETURN count(n) as aircraft_count"

    async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            response = await session.call_tool("read_neo4j_cypher", {
                "query": count_query,
                "params": {}
            })

            print("\n✅ Count Query Results:")
            for content in response.content:
                if hasattr(content, 'text'):
                    text = content.text
                    if text and text.strip():
                        try:
                            results = json.loads(text)
                            print(json.dumps(results, indent=2))
                        except json.JSONDecodeError:
                            print(text)
                    else:
                        print("(empty response)")
            print()


async def main():
    """Main test runner."""
    print("\n" + "=" * 80)
    print("MCP NEO4J CYPHER SERVER - TOOL TESTER")
    print("=" * 80)

    # Initialize Databricks workspace client (uses CLI OAuth)
    ws = WorkspaceClient()

    print(f"\n🔐 Authentication Info:")
    print(f"   Workspace: {ws.config.host}")
    print(f"   Auth Type: {ws.config.auth_type}")
    print(f"   User: {ws.current_user.me().user_name}")
    print(f"   MCP Server: {MCP_SERVER_URL}")
    print()

    try:
        # Test 1: List all available tools
        await list_available_tools(MCP_SERVER_URL, ws)

        # Test 2: Get Neo4j schema
        await test_get_schema(MCP_SERVER_URL, ws)

        # Test 3: Query aircraft structure
        await test_aircraft_query(MCP_SERVER_URL, ws)

        # Test 4: Simple count query
        await test_simple_count_query(MCP_SERVER_URL, ws)

        print("=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print()

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ ERROR OCCURRED")
        print("=" * 80)
        print(f"\nError Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        print("\nFull Traceback:")
        import traceback
        traceback.print_exc()
        print()


if __name__ == "__main__":
    asyncio.run(main())
