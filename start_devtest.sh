#!/bin/bash

# Telegram Bot Development Starter Script
# This script starts the server, ngrok, and sets up the webhook automatically

set -e  # Exit on error

echo "🚀 Starting Telegram Bot Development Environment..."

# Load bot token from .env
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with your TELEGRAM_BOT_TOKEN"
    exit 1
fi

# Extract bot token from .env
BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN .env | cut -d '=' -f2 | tr -d ' "'"'"'')

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN not found in .env"
    exit 1
fi

# Clean up function to kill processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    if [ ! -z "$SERVER_PID" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Stop a previous dev server started by this script. Do not kill other
# listeners (Docker publishes Odysseus SearXNG on 127.0.0.1:8080).
echo "🧹 Stopping any previous dev server..."
pkill -f "uvicorn main:app --host 0.0.0.0 --port" 2>/dev/null || true
sleep 1

port_in_use() {
    ss -tlnH "sport = :$1" | grep -q .
}

DEV_PORT="${DEV_PORT:-8080}"
if port_in_use "$DEV_PORT"; then
    echo "⚠️  Port ${DEV_PORT} is already in use (Odysseus SearXNG listens on 127.0.0.1:8080)."
    for candidate in 8081 8082 8888 8090; do
        if ! port_in_use "$candidate"; then
            DEV_PORT="$candidate"
            break
        fi
    done
    if port_in_use "$DEV_PORT"; then
        echo "❌ Error: No free dev port found (tried 8080, 8081, 8082, 8888, 8090)."
        exit 1
    fi
    echo "   Using port ${DEV_PORT} instead."
fi

# Start uvicorn server in background
echo "📦 Starting server..."
pipenv run uvicorn main:app --host 0.0.0.0 --port "$DEV_PORT" > /tmp/telegram-bot-server.log 2>&1 &
SERVER_PID=$!
echo "   Server PID: $SERVER_PID"
sleep 3  # Wait for server to start

if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "❌ Error: Server exited during startup. Last log lines:"
    tail -n 30 /tmp/telegram-bot-server.log
    exit 1
fi

# Start ngrok in background
echo "🌐 Starting ngrok..."
ngrok http "$DEV_PORT" > /tmp/telegram-bot-ngrok.log 2>&1 &
NGROK_PID=$!
echo "   Ngrok PID: $NGROK_PID"
sleep 4  # Wait for ngrok to start

# Get ngrok URL from API
echo "🔍 Getting ngrok URL..."
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[a-zA-Z0-9.-]*\.ngrok-free\.[a-zA-Z]*' | head -n 1)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Error: Could not get ngrok URL"
    echo "Check if ngrok is running: http://localhost:4040"
    cleanup
fi

echo "   Ngrok URL: $NGROK_URL"

# Set Telegram webhook
echo "🔗 Setting Telegram webhook..."
WEBHOOK_RESPONSE=$(curl -s -X POST \
  "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"${NGROK_URL}/webhook\"}")

if echo "$WEBHOOK_RESPONSE" | grep -q '"ok":true'; then
    echo "   ✅ Webhook set successfully!"
else
    echo "   ❌ Webhook setup failed:"
    echo "   $WEBHOOK_RESPONSE"
    cleanup
fi

echo ""
echo "✨ Development environment is ready!"
echo ""
echo "📊 Status:"
echo "   Server:  http://localhost:${DEV_PORT}"
echo "   Ngrok:   $NGROK_URL"
echo "   Ngrok UI: http://localhost:4040"
echo ""
echo "📝 Logs:"
echo "   Server: tail -f /tmp/telegram-bot-server.log"
echo "   Ngrok:  tail -f /tmp/telegram-bot-ngrok.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep script running and show server logs
tail -f /tmp/telegram-bot-server.log
