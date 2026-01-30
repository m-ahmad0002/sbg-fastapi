#!/bin/bash

# ========================================
# Complete Update Script for Live RAG API
# Updates Code + Environment Variables
# ========================================
#
# 404 on server? Ensure Azure Web App uses the CLASSIC Azure OpenAI endpoint:
#   https://<your-resource-name>.openai.azure.com
# (not the Foundry URL .../api/projects/...). Deployment names must match exactly (no extra spaces).
#

# Variables - CHANGE THESE TO MATCH YOUR DEPLOYMENT
RESOURCE_GROUP="sbg-rag-rg"
APP_NAME="sbg-rag-api"
ACR_NAME="sbgragregistry"
IMAGE_NAME="rag-api"
NEW_TAG="v$(date +%Y%m%d-%H%M%S)"  # Auto-generate version with timestamp

# Git Configuration
GIT_BRANCH="main"  # Change to your branch name (main/master/dev)

# Environment Variables - UPDATE WITH YOUR ACTUAL VALUE
# Use classic endpoint for Azure OpenAI to avoid 404: https://<resource>.openai.azure.com

AZURE_SEARCH_ENDPOINT="https://sbgsearchservice.search.windows.net"
AZURE_SEARCH_API_KEY=""
AZURE_SEARCH_INDEX_NAME="rag-documents"

# Classic Azure OpenAI endpoint (required for SDK - do not use Foundry /api/projects/ URL here)
AZURE_OPENAI_ENDPOINT="https://openai-sbg-azure.openai.azure.com"
AZURE_OPENAI_API_KEY=""
AZURE_OPENAI_EMBED_DEPLOYMENT="text-embedding-3-large"
AZURE_OPENAI_API_VERSION="2024-08-01-preview"
AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4.1-mini"

echo "=========================================="
echo "Complete API Update Process"
echo "=========================================="
echo "App Name: $APP_NAME"
echo "New Version: $NEW_TAG"
echo "Git Branch: $GIT_BRANCH"
echo ""

# Step 0: Check if we're in the right directory
echo "Step 0: Checking project directory..."
if [ ! -f "Dockerfile" ]; then
    echo "❌ Error: Dockerfile not found!"
    echo "Make sure you're in the project directory (cd ~/sbg-fastapi)"
    exit 1
fi

if [ ! -d "app" ]; then
    echo "❌ Error: app/ directory not found!"
    exit 1
fi

echo "✓ Project directory verified"
echo ""

# Step 1: Pull latest code from Git
echo "=========================================="
echo "Step 1: Pulling Latest Code from Git"
echo "=========================================="

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "⚠️  Warning: Not a git repository"
    echo "Skipping git pull..."
else
    echo "Fetching from remote..."
    git fetch origin

    echo "Pulling latest changes from $GIT_BRANCH..."
    git pull origin $GIT_BRANCH

    if [ $? -ne 0 ]; then
        echo "❌ Git pull failed!"
        echo "Options:"
        echo "1. Resolve conflicts and try again"
        echo "2. Skip git pull (use current local code)"
        read -p "Continue without git pull? (y/n): " continue_choice
        if [ "$continue_choice" != "y" ]; then
            exit 1
        fi
    else
        echo "✓ Code updated from Git"
    fi
fi

echo ""

# Step 2: Build new Docker image
echo "=========================================="
echo "Step 2: Building New Docker Image"
echo "=========================================="
echo "Image: $IMAGE_NAME:$NEW_TAG"
echo "This may take 3-5 minutes..."
echo ""

az acr build \
  --registry $ACR_NAME \
  --image $IMAGE_NAME:$NEW_TAG \
  --file Dockerfile \
  .

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    echo "Check your Dockerfile and code for errors."
    echo ""
    echo "Common issues:"
    echo "- Missing files in app/ directory"
    echo "- Syntax errors in Python code"
    echo "- Missing dependencies in requirements.txt"
    exit 1
fi

echo ""
echo "✓ New image built successfully: $IMAGE_NAME:$NEW_TAG"
echo ""

# Step 3: Get ACR credentials
echo "=========================================="
echo "Step 3: Getting ACR Details"
echo "=========================================="

ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

echo "ACR Server: $ACR_LOGIN_SERVER"
echo "✓ Credentials retrieved"
echo ""

# Step 4: Update Environment Variables
echo "=========================================="
echo "Step 4: Updating Environment Variables"
echo "=========================================="

az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings \
    AZURE_SEARCH_ENDPOINT="$AZURE_SEARCH_ENDPOINT" \
    AZURE_SEARCH_API_KEY="$AZURE_SEARCH_API_KEY" \
    AZURE_SEARCH_INDEX_NAME="$AZURE_SEARCH_INDEX_NAME" \
    AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
    AZURE_OPENAI_EMBED_DEPLOYMENT="$AZURE_OPENAI_EMBED_DEPLOYMENT" \
    AZURE_OPENAI_CHAT_DEPLOYMENT="$AZURE_OPENAI_CHAT_DEPLOYMENT" \
    AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
    WEBSITES_PORT=8000 \
    > /dev/null

if [ $? -ne 0 ]; then
    echo "❌ Failed to update environment variables"
    exit 1
fi

echo "✓ Environment variables updated"
echo ""

# Step 5: Update Container Image
echo "=========================================="
echo "Step 5: Updating Web App Container"
echo "=========================================="

az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:$NEW_TAG \
  --docker-registry-server-url https://${ACR_LOGIN_SERVER} \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD

if [ $? -ne 0 ]; then
    echo "❌ Failed to update container configuration"
    exit 1
fi

echo "✓ Container updated to: ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:$NEW_TAG"
echo ""

# Step 6: Restart Web App
echo "=========================================="
echo "Step 6: Restarting Web App"
echo "=========================================="

az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

if [ $? -ne 0 ]; then
    echo "❌ Restart failed"
    exit 1
fi

echo "✓ Web App restarted"
echo ""

# Step 7: Wait for startup
echo "=========================================="
echo "Step 7: Waiting for Application Startup"
echo "=========================================="
echo "Waiting 30 seconds for initial startup..."

for i in {30..1}; do
    echo -ne "\rTime remaining: $i seconds..."
    sleep 1
done
echo -e "\n"

# Get app URL
APP_URL=$(az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query defaultHostName -o tsv)

echo "=========================================="
echo "Step 8: Testing Deployment"
echo "=========================================="
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "URL: https://${APP_URL}/health"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" https://${APP_URL}/health 2>&1)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n 1)
BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Health check PASSED"
    echo "Response: $BODY"
else
    echo "⚠️  Health check returned code: $HTTP_CODE"
    echo "Response: $BODY"
    echo "Note: App may still be starting up..."
fi

echo ""

# Test 2: Root Endpoint
echo "Test 2: Root Endpoint"
echo "URL: https://${APP_URL}/"
ROOT_RESPONSE=$(curl -s -w "\n%{http_code}" https://${APP_URL}/ 2>&1)
HTTP_CODE=$(echo "$ROOT_RESPONSE" | tail -n 1)
BODY=$(echo "$ROOT_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Root endpoint PASSED"
    echo "Response: $BODY"
else
    echo "⚠️  Root endpoint returned code: $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""
echo "=========================================="
echo "✓ UPDATE COMPLETE!"
echo "=========================================="
echo ""
echo "Deployment Summary:"
echo "-------------------"
echo "App Name: $APP_NAME"
echo "Version: $NEW_TAG"
echo "API URL: https://${APP_URL}"
echo ""
echo "Available Endpoints:"
echo "-------------------"
echo "Health: https://${APP_URL}/health"
echo "Root: https://${APP_URL}/"
echo "RAG Query: https://${APP_URL}/rag/query"
echo "API Docs: https://${APP_URL}/docs"
echo "ReDoc: https://${APP_URL}/redoc"
echo ""
echo "Test RAG Query:"
echo "-------------------"
echo "curl -X POST https://${APP_URL}/rag/query \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"query\":\"What information is available?\",\"session_id\":\"test\"}'"
echo ""
echo "View Live Logs:"
echo "-------------------"
echo "az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "Rollback to Previous Version (if needed):"
echo "-------------------"
echo "# List all tags:"
echo "az acr repository show-tags --name $ACR_NAME --repository $IMAGE_NAME --orderby time_desc"
echo ""
echo "# Rollback command:"
echo "az webapp config container set \\"
echo "  --name $APP_NAME --resource-group $RESOURCE_GROUP \\"
echo "  --docker-custom-image-name ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:PREVIOUS_TAG"
echo ""
echo "=========================================="
