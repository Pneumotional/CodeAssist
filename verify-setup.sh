#!/bin/bash

echo "🔍 CodeAssist Docker Setup Verification"
echo "========================================"
echo ""

# Check if Docker is installed
echo "1. Checking Docker installation..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "   ✅ Docker installed: $DOCKER_VERSION"
else
    echo "   ❌ Docker is not installed"
    echo "   Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
echo ""
echo "2. Checking Docker Compose installation..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    echo "   ✅ Docker Compose installed: $COMPOSE_VERSION"
else
    echo "   ❌ Docker Compose is not installed"
    echo "   Install from: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if Docker daemon is running
echo ""
echo "3. Checking Docker daemon..."
if docker info &> /dev/null; then
    echo "   ✅ Docker daemon is running"
else
    echo "   ❌ Docker daemon is not running"
    echo "   Start Docker daemon and try again"
    exit 1
fi

# Check if .env file exists
echo ""
echo "4. Checking environment configuration..."
if [ -f .env ]; then
    echo "   ✅ .env file found"
    
    # Check for important variables
    if grep -q "DB_PASSWORD" .env; then
        echo "   ✅ Database password configured"
    else
        echo "   ⚠️  DB_PASSWORD not set in .env"
    fi
    
    if grep -q "OLLAMA_BASE_URL" .env; then
        echo "   ✅ Ollama URL configured"
    else
        echo "   ⚠️  OLLAMA_BASE_URL not set in .env"
    fi
else
    echo "   ⚠️  .env file not found"
    echo "   Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "   ✅ Created .env from .env.example"
        echo "   Please review and update .env with your settings"
    else
        echo "   ❌ .env.example not found"
        exit 1
    fi
fi

# Check if Ollama is running
echo ""
echo "5. Checking Ollama availability..."
if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "   ✅ Ollama is running on localhost:11434"
    
    # Check if the model is available
    MODEL=$(grep OLLAMA_MODEL .env | cut -d '=' -f2)
    if [ -n "$MODEL" ]; then
        if curl -s http://localhost:11434/api/tags | grep -q "$MODEL"; then
            echo "   ✅ Model $MODEL is available"
        else
            echo "   ⚠️  Model $MODEL not found"
            echo "   Pull it with: ollama pull $MODEL"
        fi
    fi
else
    echo "   ❌ Ollama is not running on localhost:11434"
    echo "   Install and start Ollama: https://ollama.com"
    echo "   Then pull the model: ollama pull qwen2.5-coder:1.5b"
fi

# Check required directories
echo ""
echo "6. Checking project structure..."
REQUIRED_DIRS=("backend" "frontend" "uploads")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "   ✅ Directory exists: $dir/"
    else
        echo "   ⚠️  Directory missing: $dir/"
        if [ "$dir" = "uploads" ]; then
            mkdir -p "$dir"
            echo "      Created: $dir/"
        fi
    fi
done

# Check required files
echo ""
echo "7. Checking required files..."
REQUIRED_FILES=("requirements.txt" "Dockerfile" "docker-compose.yml" "backend/main.py" "backend/agent.py" "backend/database.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ File exists: $file"
    else
        echo "   ❌ File missing: $file"
    fi
done

# Check ports availability
echo ""
echo "8. Checking port availability..."
PORTS=(8000 8001 5432)
for port in "${PORTS[@]}"; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "   ⚠️  Port $port is already in use"
    else
        echo "   ✅ Port $port is available"
    fi
done

echo ""
echo "========================================"
echo "✨ Verification complete!"
echo ""
echo "Next steps:"
echo "1. Review and update .env file with your settings"
echo "2. Ensure Ollama is running: ollama serve"
echo "3. Build and start containers: make up"
echo "   Or: docker-compose up -d"
echo ""
