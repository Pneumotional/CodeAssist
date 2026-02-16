#!/bin/bash
set -e

echo "🚀 Starting CodeAssist Application..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until pg_isready -h ${DB_HOST:-postgres} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres}; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "✅ PostgreSQL is ready!"

# Start backend server in background
echo "🔧 Starting backend server on port ${PORT:-8000}..."
python run.py --host ${HOST:-0.0.0.0} --port ${PORT:-8000} &
BACKEND_PID=$!

# Wait a bit for backend to initialize
sleep 3

# Start frontend server
echo "🎨 Starting frontend server on port 8001..."
python frontend.py &
FRONTEND_PID=$!

# Function to handle shutdown
shutdown() {
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "✅ Servers stopped"
    exit 0
}

# Trap SIGTERM and SIGINT
trap shutdown SIGTERM SIGINT

echo "✅ All services started!"
echo "📡 Backend API: http://localhost:${PORT:-8000}"
echo "🌐 Frontend UI: http://localhost:8001"

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
