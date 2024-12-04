#!/bin/bash

# Define variables
PROJECT_ID="your-google-cloud-project-id"
SERVICE_NAME="telegram-bot"
REGION="asia-south1"
TELEGRAM_BOT_TOKEN="your-telegram-bot-token"

# Deploy the Cloud Run service
gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN

# Fetch the deployed Cloud Run URL
CLOUD_RUN_URL=$(gcloud run services describe $SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --format "value(status.url)")

# Set the webhook using the fetched URL
WEBHOOK_URL="${CLOUD_RUN_URL}/webhook"
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}"

echo "Webhook set to: ${WEBHOOK_URL}"
