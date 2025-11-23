#!/bin/bash
# Populate GCP Secrets with DEV values (for testing)
# ⚠️ IMPORTANT: You should use PROD values for production deployment!

set -e  # Exit on error

echo "Creating secrets in GCP Secret Manager..."

# Create secrets (if they don't exist)
gcloud secrets create telegram-bot-token --replication-policy="automatic" 2>/dev/null || echo "telegram-bot-token already exists"
gcloud secrets create openai-api-key --replication-policy="automatic" 2>/dev/null || echo "openai-api-key already exists"
gcloud secrets create youtube-api-key --replication-policy="automatic" 2>/dev/null || echo "youtube-api-key already exists"
gcloud secrets create google-sheet-id --replication-policy="automatic" 2>/dev/null || echo "google-sheet-id already exists"
gcloud secrets create drive-folder-id --replication-policy="automatic" 2>/dev/null || echo "drive-folder-id already exists"
gcloud secrets create cloud-run-url --replication-policy="automatic" 2>/dev/null || echo "cloud-run-url already exists"

echo ""
echo "Adding secret values..."

# Add DEV values (replace with PROD values for production!)
echo -n "7559131288:AAF2gc-z9G3N1AnIwImcKES07ITBFnMJXqM" | gcloud secrets versions add telegram-bot-token --data-file=-
echo "✅ telegram-bot-token added"

echo -n "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" | gcloud secrets versions add openai-api-key --data-file=-
echo "✅ openai-api-key added"

echo -n "AIzaSyBK3ykljDW67ksOZGX9TSBtW05_ct912Uk" | gcloud secrets versions add youtube-api-key --data-file=-
echo "✅ youtube-api-key added"

echo -n "1-1Y4O4RAa-XgtAcGB_tEzXE3dta8pYxCgzj5o9FRqM0" | gcloud secrets versions add google-sheet-id --data-file=-
echo "✅ google-sheet-id added"

echo -n "1r-9iiDkDLLL6XRy6He55-Af-anLgBDQw" | gcloud secrets versions add drive-folder-id --data-file=-
echo "✅ drive-folder-id added"

echo -n "placeholder" | gcloud secrets versions add cloud-run-url --data-file=-
echo "✅ cloud-run-url added (placeholder)"

echo ""
echo "✅ All secrets populated successfully!"
echo ""
echo "⚠️  WARNING: These are your DEV credentials!"
echo "⚠️  For production, update with PROD bot token:"
echo '    echo -n "PROD_TOKEN" | gcloud secrets versions add telegram-bot-token --data-file=-'
