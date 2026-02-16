.PHONY: help build up down restart logs logs-app logs-db shell shell-db clean backup restore health

# Default target
help:
	@echo "CodeAssist Docker Commands:"
	@echo ""
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make logs-app    - View application logs"
	@echo "  make logs-db     - View database logs"
	@echo "  make shell       - Access application shell"
	@echo "  make shell-db    - Access database shell"
	@echo "  make health      - Check service health"
	@echo "  make backup      - Backup database"
	@echo "  make restore     - Restore database from backup"
	@echo "  make clean       - Remove containers and volumes"
	@echo ""

# Build images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build

# Start services
up:
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo "✅ Services started!"
	@echo "Frontend: http://localhost:8001"
	@echo "Backend: http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

# Stop services
down:
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✅ Services stopped"

# Restart services
restart:
	@echo "🔄 Restarting services..."
	docker-compose restart
	@echo "✅ Services restarted"

# View all logs
logs:
	docker-compose logs -f

# View application logs
logs-app:
	docker-compose logs -f app

# View database logs
logs-db:
	docker-compose logs -f postgres

# Access application shell
shell:
	@echo "🐚 Accessing application shell..."
	docker-compose exec app /bin/bash

# Access database shell
shell-db:
	@echo "🗄️ Accessing database shell..."
	docker-compose exec postgres psql -U postgres -d codeassist

# Health check
health:
	@echo "🏥 Checking service health..."
	@docker-compose ps
	@echo ""
	@echo "Backend API:"
	@curl -s http://localhost:8000/health | python -m json.tool || echo "❌ Backend not responding"

# Backup database
backup:
	@echo "💾 Creating database backup..."
	@mkdir -p backups
	@docker-compose exec -T postgres pg_dump -U postgres codeassist > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in backups/"

# Restore database (usage: make restore FILE=backup.sql)
restore:
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Error: Please specify backup file"; \
		echo "Usage: make restore FILE=backups/backup_20240101_120000.sql"; \
		exit 1; \
	fi
	@echo "📥 Restoring database from $(FILE)..."
	@docker-compose exec -T postgres psql -U postgres codeassist < $(FILE)
	@echo "✅ Database restored"

# Clean everything
clean:
	@echo "🧹 Cleaning up Docker resources..."
	@read -p "This will remove all containers and volumes. Continue? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker-compose down -v; \
		echo "✅ Cleanup complete"; \
	else \
		echo "❌ Cleanup cancelled"; \
	fi

# Development mode with auto-reload
dev:
	@echo "🔧 Starting in development mode with auto-reload..."
	RELOAD=1 docker-compose up

# Rebuild and start
rebuild:
	@echo "🔨 Rebuilding and starting..."
	docker-compose up -d --build
	@echo "✅ Rebuild complete"
