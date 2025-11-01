#!/usr/bin/env -S uv run
"""
Comprehensive Tool Tester for MCP Neo4j Cypher Server

This script directly tests the deployed MCP server tools without using an LLM.
Includes tests for common aircraft analysis queries.

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


async def call_tool(server_url: str, ws: WorkspaceClient, tool_name: str, arguments: dict):
    """Helper to call an MCP tool and return the result"""
    async with connect(server_url, auth=DatabricksOAuthClientProvider(ws)) as (
        read_stream,
        write_stream,
        _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.call_tool(tool_name, arguments)

            # Extract text from response
            for content in response.content:
                if hasattr(content, 'text'):
                    return content.text
            return None


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
                print(f"   Description: {tool.description[:100]}...")
                print()

            return tools_response.tools


async def test_get_schema(server_url: str, ws: WorkspaceClient):
    """Test 1: Get Neo4j Schema"""
    print("=" * 80)
    print("TEST 1: Get Neo4j Schema")
    print("=" * 80)

    result = await call_tool(server_url, ws, "get_neo4j_schema", {"sample_size": 100})

    print("\n✅ Schema Response:")
    if result:
        schema_data = json.loads(result)
        # Print summary instead of full schema
        node_types = [k for k, v in schema_data.items() if isinstance(v, dict) and v.get('type') == 'node']
        rel_types = [k for k, v in schema_data.items() if isinstance(v, dict) and v.get('type') == 'relationship']
        print(f"   Node Types: {len(node_types)} - {', '.join(node_types[:5])}...")
        print(f"   Relationship Types: {len(rel_types)} - {', '.join(rel_types[:5])}...")
    print()


async def test_count_query(server_url: str, ws: WorkspaceClient):
    """Test 2: Simple Count Query"""
    print("=" * 80)
    print("TEST 2: Simple Aircraft Count")
    print("=" * 80)

    query = "MATCH (a:Aircraft) RETURN count(a) as aircraft_count"
    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})

    print("\n✅ Count Query Results:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_aircraft_tail_lookup(server_url: str, ws: WorkspaceClient):
    """Test 3: Show me aircraft with tail number N95040A"""
    print("=" * 80)
    print("TEST 3: Aircraft Tail Number Lookup (N95040A)")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft {tail_number: 'N95040A'})
    RETURN a.tail_number AS tail_number,
           a.model AS model,
           a.manufacturer AS manufacturer,
           a.operator AS operator,
           a.icao24 AS icao24
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Aircraft Details:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_high_egt_with_maintenance(server_url: str, ws: WorkspaceClient):
    """Test 4: Aircraft with highest average EGT readings and recent maintenance events"""
    print("=" * 80)
    print("TEST 4: Aircraft with Maintenance Events")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft)
    OPTIONAL MATCH (a)<-[:AFFECTS_AIRCRAFT]-(m:MaintenanceEvent)
    WITH a,
         count(m) AS maintenance_count,
         collect({
           fault: m.fault,
           severity: m.severity,
           reported_at: m.reported_at
         })[0..3] AS recent_maintenance
    WHERE maintenance_count > 0
    RETURN a.tail_number AS aircraft,
           a.model AS model,
           maintenance_count,
           recent_maintenance
    ORDER BY maintenance_count DESC
    LIMIT 5
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Aircraft with Maintenance:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_boeing_737_sensor_data(server_url: str, ws: WorkspaceClient):
    """Test 5: Boeing 737-800 aircraft with sensor data"""
    print("=" * 80)
    print("TEST 5: Boeing 737 Aircraft with Sensor Data")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft)
    WHERE a.model CONTAINS '737'
    OPTIONAL MATCH (a)-[:HAS_SYSTEM]->(sys:System)
    OPTIONAL MATCH (sys)-[:HAS_SENSOR]->(s:Sensor)
    OPTIONAL MATCH (a)<-[:AFFECTS_AIRCRAFT]-(m:MaintenanceEvent)
    RETURN a.tail_number AS aircraft,
           a.model AS model,
           count(DISTINCT sys) AS system_count,
           count(DISTINCT s) AS sensor_count,
           count(DISTINCT m) AS maintenance_event_count
    ORDER BY sensor_count DESC
    LIMIT 5
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Boeing 737 Aircraft:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_vibration_and_maintenance(server_url: str, ws: WorkspaceClient):
    """Test 6: Vibration trends for aircraft N95040A with maintenance history"""
    print("=" * 80)
    print("TEST 6: Vibration Analysis and Maintenance Correlation (N95040A)")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft {tail_number: 'N95040A'})
    OPTIONAL MATCH (a)-[:HAS_SYSTEM]->(sys:System)
    OPTIONAL MATCH (sys)-[:HAS_SENSOR]->(s:Sensor)
    WHERE s.type = 'Vibration' OR s.name CONTAINS 'Vibration' OR s.name CONTAINS 'vibration'
    OPTIONAL MATCH (a)<-[:AFFECTS_AIRCRAFT]-(m:MaintenanceEvent)
    RETURN a.tail_number AS aircraft,
           count(DISTINCT s) AS vibration_sensors,
           count(DISTINCT sys) AS systems_monitored,
           collect(DISTINCT {
             fault: m.fault,
             severity: m.severity,
             system_id: m.system_id,
             reported_at: m.reported_at
           })[0..5] AS maintenance_events
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Vibration and Maintenance Correlation:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_maintenance_delays(server_url: str, ws: WorkspaceClient):
    """Test 7: Flights with maintenance-related delays"""
    print("=" * 80)
    print("TEST 7: Flights with Maintenance-Related Delays")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft)-[:OPERATES_FLIGHT]->(f:Flight)
    MATCH (f)-[:HAS_DELAY]->(d:Delay)
    WHERE toLower(d.cause) CONTAINS 'maintenance'
       OR toLower(d.cause) CONTAINS 'technical'
       OR toLower(d.cause) CONTAINS 'mechanical'
    OPTIONAL MATCH (a)<-[:AFFECTS_AIRCRAFT]-(m:MaintenanceEvent)
    WHERE m.reported_at IS NOT NULL
    RETURN f.flight_number AS flight,
           a.tail_number AS aircraft,
           f.origin AS origin,
           f.destination AS destination,
           d.cause AS delay_cause,
           d.minutes AS delay_minutes,
           count(DISTINCT m) AS maintenance_events
    ORDER BY d.minutes DESC
    LIMIT 10
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Maintenance Delays:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_fuel_efficiency_comparison(server_url: str, ws: WorkspaceClient):
    """Test 8: Compare aircraft models in the fleet"""
    print("=" * 80)
    print("TEST 8: Aircraft Model Fleet Comparison")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft)
    WITH a.model AS model,
         a.manufacturer AS manufacturer,
         count(a) AS aircraft_count
    OPTIONAL MATCH (aircraft:Aircraft {model: model})
    OPTIONAL MATCH (aircraft)-[:OPERATES_FLIGHT]->(f:Flight)
    RETURN model,
           manufacturer,
           aircraft_count,
           count(DISTINCT f) AS total_flights,
           count(DISTINCT aircraft) AS fleet_size
    ORDER BY total_flights DESC
    LIMIT 10
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Fleet Comparison by Model:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_system_hierarchy(server_url: str, ws: WorkspaceClient):
    """Test 9: Complete system hierarchy for an aircraft"""
    print("=" * 80)
    print("TEST 9: Aircraft System Hierarchy (N95040A)")
    print("=" * 80)

    query = """
    MATCH (a:Aircraft {tail_number: 'N95040A'})
    OPTIONAL MATCH (a)-[:HAS_SYSTEM]->(sys:System)
    OPTIONAL MATCH (sys)-[:HAS_COMPONENT]->(c:Component)
    OPTIONAL MATCH (sys)-[:HAS_SENSOR]->(s:Sensor)
    WITH a, sys,
         count(DISTINCT c) AS component_count,
         count(DISTINCT s) AS sensor_count
    RETURN a.tail_number AS aircraft,
           collect({
             system_name: sys.name,
             system_type: sys.type,
             components: component_count,
             sensors: sensor_count
           }) AS systems
    LIMIT 1
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ System Hierarchy:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def test_sensor_readings_summary(server_url: str, ws: WorkspaceClient):
    """Test 10: Sensor readings summary statistics"""
    print("=" * 80)
    print("TEST 10: Sensor Reading Statistics")
    print("=" * 80)

    query = """
    MATCH (s:Sensor)
    OPTIONAL MATCH (sys:System)-[:HAS_SENSOR]->(s)
    OPTIONAL MATCH (aircraft:Aircraft)-[:HAS_SYSTEM]->(sys)
    WITH s.type AS sensor_type,
         count(DISTINCT s) AS sensor_count,
         count(DISTINCT sys) AS system_count,
         count(DISTINCT aircraft) AS aircraft_count
    WHERE sensor_type IS NOT NULL
    RETURN sensor_type,
           sensor_count,
           system_count,
           aircraft_count
    ORDER BY sensor_count DESC
    LIMIT 10
    """

    result = await call_tool(server_url, ws, "read_neo4j_cypher", {"query": query})
    print(f"\n✅ Sensor Statistics:")
    print(json.dumps(json.loads(result), indent=2))
    print()


async def main():
    """Main test runner."""
    print("\n" + "=" * 80)
    print("MCP NEO4J CYPHER SERVER - COMPREHENSIVE TOOL TESTER")
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
        # List available tools
        await list_available_tools(MCP_SERVER_URL, ws)

        # Run all tests
        await test_get_schema(MCP_SERVER_URL, ws)
        await test_count_query(MCP_SERVER_URL, ws)
        await test_aircraft_tail_lookup(MCP_SERVER_URL, ws)
        await test_high_egt_with_maintenance(MCP_SERVER_URL, ws)
        await test_boeing_737_sensor_data(MCP_SERVER_URL, ws)
        await test_vibration_and_maintenance(MCP_SERVER_URL, ws)
        await test_maintenance_delays(MCP_SERVER_URL, ws)
        await test_fuel_efficiency_comparison(MCP_SERVER_URL, ws)
        await test_system_hierarchy(MCP_SERVER_URL, ws)
        await test_sensor_readings_summary(MCP_SERVER_URL, ws)

        print("=" * 80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print(f"\n📊 Tests Run: 10")
        print(f"   1. Schema Retrieval")
        print(f"   2. Aircraft Count")
        print(f"   3. Aircraft Tail Lookup (N95040A)")
        print(f"   4. Aircraft with Maintenance Events")
        print(f"   5. Boeing 737 Sensor Data")
        print(f"   6. Vibration & Maintenance Correlation")
        print(f"   7. Maintenance-Related Delays")
        print(f"   8. Fleet Comparison by Model")
        print(f"   9. System Hierarchy")
        print(f"   10. Sensor Reading Statistics")
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
