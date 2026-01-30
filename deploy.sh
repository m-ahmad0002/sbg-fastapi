

# Variables - CHANGE THESE
RESOURCE_GROUP="sbg-rag-rg"
LOCATION="eastus"  # CHANGED TO MATCH EXISTING
APP_NAME="sbg-rag-api"
ACR_NAME="sbgragregistry"
IMAGE_NAME="rag-api"
TAG="v1"

# Your Azure credentials - set these or export before running (do not commit real keys)
AZURE_SEARCH_ENDPOINT="${AZURE_SEARCH_ENDPOINT:-https://mysearch-service.search.windows.net}"
AZURE_SEARCH_API_KEY="${AZURE_SEARCH_API_KEY:-YOUR_AZURE_SEARCH_API_KEY}"
AZURE_SEARCH_INDEX_NAME="${AZURE_SEARCH_INDEX_NAME:-rag-documents}"

AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-https://YOUR-RESOURCE.openai.azure.com}"
AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-YOUR_AZURE_OPENAI_API_KEY}"
AZURE_OPENAI_EMBED_DEPLOYMENT="${AZURE_OPENAI_EMBED_DEPLOYMENT:-text-embedding-3-large}"
AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION:-2024-08-01-preview}"
AZURE_OPENAI_CHAT_DEPLOYMENT="${AZURE_OPENAI_CHAT_DEPLOYMENT:-gpt-4o-mini}"

PROJECT_ENDPOINT="${PROJECT_ENDPOINT:-https://YOUR-RESOURCE.services.ai.azure.com/api/projects/YOUR-PROJECT}"
SEARCH_CONNECTION_NAME="${SEARCH_CONNECTION_NAME:-mysearchservice}"
PROJECT_API_KEY="${PROJECT_API_KEY:-YOUR_PROJECT_API_KEY}"

echo "=================================="
echo "Starting Deployment Process"
echo "=================================="

# Step 1: Login to Azure
echo "Step 1: Checking Azure login..."
az account show > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Not logged in. Logging in..."
    az login
else
    echo "Already logged in ✓"
fi

# Step 1.5: Register required providers
echo "Step 1.5: Registering Azure providers..."
az provider register --namespace Microsoft.ContainerRegistry
az provider register --namespace Microsoft.Web
echo "Waiting for registration to complete..."
sleep 10

# Step 2: Create or Use Existing Resource Group
echo "Step 2: Setting up resource group..."
if az group exists --name $RESOURCE_GROUP | grep -q "true"; then
    echo "Resource group '$RESOURCE_GROUP' already exists. Using it."
    # Get existing location
    EXISTING_LOCATION=$(az group show --name $RESOURCE_GROUP --query location -o tsv)
    echo "Existing location: $EXISTING_LOCATION"
    LOCATION=$EXISTING_LOCATION
else
    echo "Creating new resource group..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
fi

# Step 3: Create Azure Container Registry
echo "Step 3: Creating Azure Container Registry..."
if az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP > /dev/null 2>&1; then
    echo "Container Registry '$ACR_NAME' already exists. Skipping creation."
else
    az acr create \
      --resource-group $RESOURCE_GROUP \
      --name $ACR_NAME \
      --sku Basic \
      --admin-enabled true
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create Container Registry. Try a different name."
        echo "Current name: $ACR_NAME"
        echo "Try: ${ACR_NAME}$(date +%s)"
        exit 1
    fi
fi

# Step 4: Build and Push Docker Image
echo "Step 4: Building and pushing Docker image..."
echo "This may take 3-5 minutes..."
az acr build \
  --registry $ACR_NAME \
  --image $IMAGE_NAME:$TAG \
  --file Dockerfile \
  .

if [ $? -ne 0 ]; then
    echo "❌ Failed to build image. Check Dockerfile and code."
    exit 1
fi

# Step 5: Get ACR credentials
echo "Step 5: Getting ACR credentials..."
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)

echo "ACR Login Server: $ACR_LOGIN_SERVER"

# Step 6: Create App Service Plan
echo "Step 6: Creating App Service Plan..."
if az appservice plan show --name ${APP_NAME}-plan --resource-group $RESOURCE_GROUP > /dev/null 2>&1; then
    echo "App Service Plan already exists. Skipping."
else
    az appservice plan create \
      --name ${APP_NAME}-plan \
      --resource-group $RESOURCE_GROUP \
      --sku B1 \
      --is-linux
fi

# Step 7: Create Web App
echo "Step 7: Creating Web App..."
if az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP > /dev/null 2>&1; then
    echo "Web App already exists. Updating configuration..."
else
    az webapp create \
      --resource-group $RESOURCE_GROUP \
      --plan ${APP_NAME}-plan \
      --name $APP_NAME \
      --deployment-container-image-name ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${TAG}
fi

# Step 8: Configure Container Registry credentials
echo "Step 8: Configuring container registry credentials..."
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name ${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${TAG} \
  --docker-registry-server-url https://${ACR_LOGIN_SERVER} \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD

# Step 9: Configure App Settings
echo "Step 9: Configuring environment variables..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings \
    AZURE_SEARCH_ENDPOINT=$AZURE_SEARCH_ENDPOINT \
    AZURE_SEARCH_API_KEY=$AZURE_SEARCH_API_KEY \
    AZURE_SEARCH_INDEX_NAME=$AZURE_SEARCH_INDEX_NAME \
    AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT \
    AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY \
    AZURE_OPENAI_EMBED_DEPLOYMENT=$AZURE_OPENAI_EMBED_DEPLOYMENT \
    AZURE_OPENAI_CHAT_DEPLOYMENT=$AZURE_OPENAI_CHAT_DEPLOYMENT \
    AZURE_OPENAI_API_VERSION=2024-02-01 \
    WEBSITES_PORT=8000

# Step 10: Enable continuous deployment
echo "Step 10: Enabling continuous deployment..."
az webapp deployment container config \
  --enable-cd true \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP

# Step 11: Restart the app
echo "Step 11: Restarting web app..."
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

# Get the URL
APP_URL=$(az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query defaultHostName -o tsv)

echo ""
echo "=================================="
echo "✓ Deployment Complete!"
echo "=================================="
echo "Your API is available at: https://${APP_URL}"
echo "Health check: https://${APP_URL}/health"
echo "API endpoint: https://${APP_URL}/rag/query"
echo ""
echo "⚠️  Note: First startup may take 2-3 minutes"
echo "=================================="
echo ""
echo "Test with:"
echo "curl https://${APP_URL}/health"