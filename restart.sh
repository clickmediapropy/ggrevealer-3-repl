#!/bin/bash

echo "🔄 Restarting GGRevealer..."

# Kill any process using port 5000
echo "🛑 Stopping existing server on port 5000..."
lsof -ti:5000 | xargs kill -9 2>/dev/null

# Wait a moment for the port to be released
sleep 1

# Start the application
echo "🚀 Starting server..."
python main.py
