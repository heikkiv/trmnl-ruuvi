#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="trmnl-ruuvi"
REGION="eu-west-1"
RUNTIME="python3.12"
ARCH="arm64"
MEMORY=256
TIMEOUT=30
ZIP_FILE="lambda.zip"
PACKAGE_DIR=".lambda_package"

# --- Validate required environment variables ---

if [ -z "${LAMBDA_ROLE_ARN:-}" ]; then
  echo "Error: LAMBDA_ROLE_ARN environment variable is required"
  echo "  export LAMBDA_ROLE_ARN=arn:aws:iam::123456789012:role/your-lambda-role"
  exit 1
fi

if [ -z "${RUUVI_TOKEN:-}" ]; then
  echo "Error: RUUVI_TOKEN environment variable is required"
  echo "  export RUUVI_TOKEN=your-ruuvi-bearer-token"
  exit 1
fi

# Build the Lambda environment variable string
ENV_VARS="Variables={RUUVI_TOKEN=${RUUVI_TOKEN},PLUGIN_NAME=${PLUGIN_NAME:-Ruuvi}}"
if [ -n "${RUUVI_API_URL:-}" ]; then
  ENV_VARS="Variables={RUUVI_TOKEN=${RUUVI_TOKEN},PLUGIN_NAME=${PLUGIN_NAME:-Ruuvi},RUUVI_API_URL=${RUUVI_API_URL}}"
fi

# --- Package ---

echo "Packaging Lambda function..."
rm -rf "$PACKAGE_DIR" "$ZIP_FILE"
mkdir -p "$PACKAGE_DIR"
pip3 install -r requirements.txt -t "$PACKAGE_DIR" --quiet
cp lambda_function.py "$PACKAGE_DIR/"
cd "$PACKAGE_DIR"
zip -r "../$ZIP_FILE" . -x "*.pyc" -x "*/__pycache__/*" > /dev/null
cd ..
rm -rf "$PACKAGE_DIR"
echo "Package size: $(du -sh $ZIP_FILE | cut -f1)"

# --- Deploy ---

if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
  echo "Updating existing function..."
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --zip-file "fileb://$ZIP_FILE" \
    --output text --query 'FunctionArn'

  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --runtime "$RUNTIME" \
    --memory-size "$MEMORY" \
    --timeout "$TIMEOUT" \
    --environment "$ENV_VARS" \
    --output text --query 'FunctionArn' > /dev/null

  # Ensure Function URL exists with NONE auth
  if ! aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --region "$REGION" > /dev/null 2>&1; then
    echo "Creating Function URL..."
    aws lambda create-function-url-config \
      --function-name "$FUNCTION_NAME" \
      --region "$REGION" \
      --auth-type NONE \
      --output text --query 'FunctionUrl' > /dev/null
  fi

  # Ensure public invoke permissions exist
  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --statement-id "AllowPublicAccess" \
    --action "lambda:InvokeFunctionUrl" \
    --principal "*" \
    --function-url-auth-type NONE \
    --output text > /dev/null 2>&1 || true

  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --statement-id "AllowPublicInvoke" \
    --action "lambda:InvokeFunction" \
    --principal "*" \
    --output text > /dev/null 2>&1 || true
else
  echo "Creating new function..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --runtime "$RUNTIME" \
    --architectures "$ARCH" \
    --handler "lambda_function.handler" \
    --role "$LAMBDA_ROLE_ARN" \
    --zip-file "fileb://$ZIP_FILE" \
    --memory-size "$MEMORY" \
    --timeout "$TIMEOUT" \
    --environment "$ENV_VARS" \
    --output text --query 'FunctionArn'

  echo "Waiting for function to become active..."
  aws lambda wait function-active-v2 --function-name "$FUNCTION_NAME" --region "$REGION"

  echo "Creating Function URL..."
  aws lambda create-function-url-config \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --auth-type NONE \
    --output text --query 'FunctionUrl' > /dev/null

  echo "Adding public invoke permissions..."
  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --statement-id "AllowPublicAccess" \
    --action "lambda:InvokeFunctionUrl" \
    --principal "*" \
    --function-url-auth-type NONE \
    --output text > /dev/null

  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --statement-id "AllowPublicInvoke" \
    --action "lambda:InvokeFunction" \
    --principal "*" \
    --output text > /dev/null
fi

rm -f "$ZIP_FILE"

FUNCTION_URL=$(aws lambda get-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --output text --query 'FunctionUrl' 2>/dev/null || echo "")

echo ""
echo "Deployed successfully!"
echo "  Function: $FUNCTION_NAME ($REGION)"
if [ -n "$FUNCTION_URL" ]; then
  echo "  Polling URL: $FUNCTION_URL"
  echo "  Configure this URL as the polling endpoint in the TRMNL dashboard"
fi
