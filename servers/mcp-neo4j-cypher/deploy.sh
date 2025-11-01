#!/bin/bash
# Deployment script for MCP Neo4j Cypher Server to Databricks Apps
#
# This script:
# 1. Reads Neo4j credentials from neo4j_auth.txt
# 2. Creates Databricks secret scope and stores credentials securely
# 3. Syncs application files to Databricks workspace
# 4. Deploys the MCP server as a Databricks App

set -e  # Exit on error

# Configuration
APP_NAME="mcp-neo4j-cypher"
SECRET_SCOPE="mcp-neo4j-cypher"
AUTH_FILE="neo4j_auth.txt"

echo "=========================================="
echo "  Deploying MCP Neo4j Cypher Server"
echo "=========================================="
echo ""

# ============================================================================
# Step 1: Validate Prerequisites
# ============================================================================

echo "🔍 Validating prerequisites..."

# Check if databricks CLI is installed
if ! command -v databricks &> /dev/null; then
    echo "❌ Error: databricks CLI not found"
    echo "   Install it with: pip install databricks-cli"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "❌ Error: jq not found"
    echo "   Install it with: brew install jq (macOS) or apt-get install jq (Linux)"
    exit 1
fi

# Check if authenticated
if ! databricks current-user me &> /dev/null; then
    echo "❌ Error: Not authenticated with Databricks"
    echo "   Run: databricks auth login --host https://<your-workspace-hostname>"
    exit 1
fi

# Check if neo4j_auth.txt exists
if [ ! -f "$AUTH_FILE" ]; then
    echo "❌ Error: $AUTH_FILE not found!"
    echo "   Please create $AUTH_FILE with your Neo4j credentials."
    echo "   See sample_auth.txt for the expected format."
    exit 1
fi

echo "✅ Prerequisites validated"
echo ""

# ============================================================================
# Step 2: Read Neo4j Configuration
# ============================================================================

echo "📋 Reading Neo4j configuration from $AUTH_FILE..."

# Function to read value from auth file
read_auth_value() {
    local key=$1
    grep "^${key}=" "$AUTH_FILE" | cut -d'=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

NEO4J_URI=$(read_auth_value "NEO4J_URI")
NEO4J_USERNAME=$(read_auth_value "NEO4J_USERNAME")
NEO4J_PASSWORD=$(read_auth_value "NEO4J_PASSWORD")
NEO4J_DATABASE=$(read_auth_value "NEO4J_DATABASE")

# Validate all required values are present
if [ -z "$NEO4J_URI" ]; then
    echo "❌ Error: NEO4J_URI not found in $AUTH_FILE"
    exit 1
fi

if [ -z "$NEO4J_USERNAME" ]; then
    echo "❌ Error: NEO4J_USERNAME not found in $AUTH_FILE"
    exit 1
fi

if [ -z "$NEO4J_PASSWORD" ]; then
    echo "❌ Error: NEO4J_PASSWORD not found in $AUTH_FILE"
    exit 1
fi

if [ -z "$NEO4J_DATABASE" ]; then
    echo "⚠️  Warning: NEO4J_DATABASE not found, using default: neo4j"
    NEO4J_DATABASE="neo4j"
fi

echo "  ✓ NEO4J_URI: $NEO4J_URI"
echo "  ✓ NEO4J_USERNAME: $NEO4J_USERNAME"
echo "  ✓ NEO4J_PASSWORD: ***"
echo "  ✓ NEO4J_DATABASE: $NEO4J_DATABASE"
echo ""

# ============================================================================
# Step 3: Create Databricks Secret Scope
# ============================================================================

echo "🔐 Setting up Databricks secrets..."

# Check if secret scope exists
if databricks secrets list-scopes 2>/dev/null | grep -q "^${SECRET_SCOPE}"; then
    echo "  ℹ️  Secret scope '$SECRET_SCOPE' already exists"
else
    echo "  Creating secret scope '$SECRET_SCOPE'..."
    databricks secrets create-scope "$SECRET_SCOPE" 2>/dev/null || {
        echo "  ⚠️  Warning: Could not create secret scope (it may already exist or you may lack permissions)"
    }
fi

# Set secrets
echo "  Storing Neo4j credentials as secrets..."
databricks secrets put-secret "$SECRET_SCOPE" neo4j-uri --string-value "$NEO4J_URI"
databricks secrets put-secret "$SECRET_SCOPE" neo4j-username --string-value "$NEO4J_USERNAME"
databricks secrets put-secret "$SECRET_SCOPE" neo4j-password --string-value "$NEO4J_PASSWORD"
databricks secrets put-secret "$SECRET_SCOPE" neo4j-database --string-value "$NEO4J_DATABASE"

echo "  ✅ Secrets stored successfully"
echo ""

# ============================================================================
# Step 4: Create Databricks App
# ============================================================================

echo "📦 Creating Databricks app '$APP_NAME'..."

# Create app (ignore error if it already exists)
databricks apps create "$APP_NAME" 2>/dev/null && echo "  ✅ App created" || echo "  ℹ️  App already exists"
echo ""

# ============================================================================
# Step 5: Sync Files to Databricks Workspace
# ============================================================================

echo "📤 Syncing files to Databricks workspace..."

# Get username for workspace path
USERNAME=$(databricks current-user me | jq -r .userName)

# Sync files (exclude non-critical files)
databricks sync . "/Users/$USERNAME/$APP_NAME" \
    --exclude ".env*" \
    --exclude ".gitignore" \
    --exclude "__pycache__" \
    --exclude ".claude" \
    --exclude ".databricks" \
    --exclude "test_*.py" \
    --exclude "venv" \
    --exclude ".venv" \
    --exclude "uv.lock" \
    --exclude ".DS_Store" \
    --exclude "neo4j_auth.txt" \
    --exclude "sample_auth.txt" \
    --exclude "*.md" \
    --exclude ".python-version" \
    --exclude "docker-compose.yml" \
    --exclude "Dockerfile" \
    --exclude "Makefile" \
    --exclude "*.sh" \
    --exclude "tests" \
    --exclude "assets"

echo "✅ Files synced successfully"
echo ""

# ============================================================================
# Step 6: Deploy the App
# ============================================================================

echo "🚀 Deploying app to Databricks..."

databricks apps deploy "$APP_NAME" --source-code-path "/Workspace/Users/$USERNAME/$APP_NAME"

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "App Name: $APP_NAME"
echo ""
echo "Next steps:"
echo "  1. Check app status:  databricks apps get $APP_NAME"
echo "  2. View logs:         databricks apps logs $APP_NAME"
echo "  3. Test the server:   uv run test_mcp_server.py"
echo ""
echo "Once the app is RUNNING, the MCP server will be available at:"
echo "  https://<app-url>/mcp/"
echo ""
