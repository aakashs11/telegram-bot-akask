#!/bin/bash

# Define your project ID
PROJECT_ID="telegram-bot-akask"

# Check if you have the necessary permissions
echo "Checking IAM permissions..."
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --filter="bindings.role:roles/owner OR bindings.role:roles/editor OR bindings.role:roles/serviceusage.serviceUsageAdmin" --format="table(bindings.role)"

# Check if the billing account is active
echo "Checking billing account..."
BILLING_ACCOUNT=$(gcloud beta billing projects describe $PROJECT_ID --format="value(billingAccountName)")
if [[ -z "$BILLING_ACCOUNT" ]]; then
  echo "No active billing account associated with this project."
  exit 1
else
  echo "Billing account active: $BILLING_ACCOUNT"
fi

# Enable required services
echo "Attempting to enable required services..."
SERVICES=("run.googleapis.com" "cloudbuild.googleapis.com")
for SERVICE in "${SERVICES[@]}"; do
  echo "Enabling $SERVICE..."
  gcloud services enable $SERVICE --project=$PROJECT_ID
  if [[ $? -ne 0 ]]; then
    echo "Failed to enable $SERVICE. Check permissions or organizational policies."
    exit 1
  else
    echo "$SERVICE enabled successfully."
  fi
done

echo "All services enabled successfully!"
