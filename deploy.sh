#!/bin/bash
# Automated Deployment Script for Telegram Bot
# Deploys to Google Cloud Run and configures webhook

set -e  # Exit on error

PROJECT_ID="telegram-bot-akask"
SERVICE_NAME="telegram-bot"
REGION="asia-south1"
SERVICE_ACCOUNT="telegram-bot-user@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🚀 Starting deployment to Cloud Run..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 1: Deploy to Cloud Run
echo ""
echo "📦 Step 1: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 10 \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
  --quiet

echo "✅ Deployment successful!"

# Step 2: Get Cloud Run URL and update secret
echo ""
echo "🔗 Step 2: Updating Cloud Run URL in Secret Manager..."
CLOUD_RUN_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project $PROJECT_ID \
  --format='value(status.url)')

echo "Cloud Run URL: $CLOUD_RUN_URL"

echo -n "${CLOUD_RUN_URL}" | gcloud secrets versions add cloud-run-url \
  --project $PROJECT_ID \
  --data-file=-

echo "✅ Secret updated!"

# Step 3: Configure Telegram webhook
echo ""
echo "🤖 Step 3: Configuring Telegram webhook..."
BOT_TOKEN=$(gcloud secrets versions access latest \
  --project $PROJECT_ID \
  --secret=telegram-bot-token)

WEBHOOK_SECRET=$(gcloud secrets versions access latest \
  --project $PROJECT_ID \
  --secret=telegram-webhook-secret 2>/dev/null || true)

if [ -n "$WEBHOOK_SECRET" ]; then
  WEBHOOK_RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -d "url=${CLOUD_RUN_URL}/webhook" \
    -d "secret_token=${WEBHOOK_SECRET}")
else
  echo "⚠️ telegram-webhook-secret not found; configuring webhook without request authentication."
  WEBHOOK_RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    -d "url=${CLOUD_RUN_URL}/webhook")
fi

echo "Webhook response: $WEBHOOK_RESPONSE"

# Verify webhook
echo ""
echo "🔍 Verifying webhook..."
WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")
echo "$WEBHOOK_INFO" | jq '.'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Deployment Complete!"
echo ""
echo "📊 Summary:"
echo "  Service: $SERVICE_NAME"
echo "  Region: $REGION"
echo "  URL: $CLOUD_RUN_URL"
echo ""
echo "✅ Bot is now live and should respond to messages!"
echo ""
echo "📝 Next steps:"
echo "  1. Test by messaging your bot"
echo "  2. Monitor logs: gcloud run services logs read $SERVICE_NAME --region $REGION"
echo "  3. View service: gcloud run services describe $SERVICE_NAME --region $REGION"
