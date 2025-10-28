#!/bin/bash

echo "🔄 Restarting GGRevealer..."

# Kill any process using port 8000
echo "🛑 Stopping existing server on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Wait a moment for the port to be released
sleep 1

# Start the application on port 8000
echo "🚀 Starting server on port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
