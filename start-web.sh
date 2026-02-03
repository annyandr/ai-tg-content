#!/bin/bash
# Quick start script for Medical SMM Bot with Web Interface

echo "=================================="
echo "Medical SMM Bot - Quick Start"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with required variables:"
    echo "  BOT_TOKEN=..."
    echo "  OPENROUTER_API_KEY=..."
    exit 1
fi

echo "✅ .env file found"
echo ""

# Function to kill background processes on exit
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $API_PID 2>/dev/null
    kill $WEB_PID 2>/dev/null
    echo "Done"
    exit 0
}

trap cleanup INT TERM

# Start API Server
echo "🚀 Starting API Server (port 8000)..."
python main.py api > api.log 2>&1 &
API_PID=$!
sleep 3

# Check if API started successfully
if ! ps -p $API_PID > /dev/null; then
    echo "❌ Failed to start API server"
    echo "Check api.log for errors"
    exit 1
fi

echo "✅ API Server running (PID: $API_PID)"

# Start Web Frontend
echo "🌐 Starting Web Frontend (port 3000)..."
cd web && python main.py > ../web.log 2>&1 &
WEB_PID=$!
cd ..
sleep 2

# Check if Web started successfully
if ! ps -p $WEB_PID > /dev/null; then
    echo "❌ Failed to start Web frontend"
    echo "Check web.log for errors"
    kill $API_PID
    exit 1
fi

echo "✅ Web Frontend running (PID: $WEB_PID)"
echo ""
echo "=================================="
echo "🎉 All services are running!"
echo "=================================="
echo ""
echo "📡 API Server:  http://localhost:8000"
echo "📚 API Docs:    http://localhost:8000/api/docs"
echo "🌐 Web UI:      http://localhost:3000"
echo ""
echo "Logs:"
echo "  API:  tail -f api.log"
echo "  Web:  tail -f web.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for user interrupt
wait
