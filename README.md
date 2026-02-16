# CodeAssist - AI Coding Agent

A production-ready AI coding assistant powered by Ollama, LlamaIndex, and FastAPI. CodeAssist provides an intelligent chat interface for code generation, debugging, explanation, and review with persistent sessions and file upload capabilities.

## Features

- **AI-Powered Code Assistance**: Leverages Ollama with code-specific models (qwen2.5-coder:1.5b by default)
- **Multi-User Support**: User authentication with API key-based access
- **Persistent Sessions**: Save and manage multiple chat sessions per user
- **File Upload**: Upload code files for context-aware assistance
- **Streaming Responses**: Real-time token streaming with markdown formatting
- **Syntax Highlighting**: Beautiful code rendering with language detection
- **Dockerized Deployment**: Easy setup with PostgreSQL database
- **Modern UI**: Clean, dark-themed interface optimized for code

## Architecture

- **Backend**: FastAPI + LlamaIndex + Ollama
- **Database**: PostgreSQL with asyncpg
- **Frontend**: Vue.js with TailwindCSS (static files)
- **AI Engine**: Ollama with configurable code models
- **Deployment**: Docker Compose with multi-container orchestration

## Prerequisites

- Docker and Docker Compose
- Ollama (installed and running on host machine)
- Git (optional)

## Quick Start

### 1. Install Ollama and Pull a Model

```bash
# Install Ollama (if not already installed)
# Visit https://ollama.com for installation instructions

# Start Ollama service
ollama serve

# In another terminal, pull a coding model (example with qwen2.5-coder)
ollama pull qwen2.5-coder:1.5b
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Database Configuration
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=codeassist
DB_MIN_POOL_SIZE=2
DB_MAX_POOL_SIZE=10

# Ollama Configuration
OLLAMA_MODEL=qwen2.5-coder:1.5b
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Application Ports
APP_PORT=8000
FRONTEND_PORT=8001
```

**Note**: For Linux hosts, you may need to use `http://172.17.0.1:11434` instead of `host.docker.internal` for Ollama.

### 3. Build and Run with Docker Compose

```bash
# Build and start all services
docker-compose up -d --build

# Check logs
docker-compose logs -f

# Verify services are running
docker-compose ps
```

### 4. Access the Application

- Frontend UI: http://localhost:8001
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Manual Setup (Without Docker)

If you prefer to run without Docker:

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure PostgreSQL
# Create database and update .env file

# Run database migrations (tables are created automatically on first run)

# Start backend server
python run.py --host 0.0.0.0 --port 8000
```

### Frontend Setup

The frontend is served separately:

```bash
# Install Python dependencies for frontend server
pip install aiofiles jinja2

# Start frontend server
python frontend.py
```

## Project Structure

```
codeassist/
├── backend/
│   ├── agent.py          # Ollama agent with streaming
│   ├── database.py       # PostgreSQL database manager
│   ├── main.py          # FastAPI application
│   └── __init__.py
├── frontend/
│   ├── index.html       # Main UI
│   ├── app.js           # Vue.js application
│   ├── styles.css       # Custom styles
│   └── assets/          # Static assets
├── uploads/             # Uploaded files (created on first run)
├── postgres_data/       # PostgreSQL data (created by Docker)
├── docker-compose.yml   # Docker Compose configuration
├── Dockerfile           # Docker build instructions
├── frontend.py         # Static file server for development
├── run.py              # Backend server runner
├── requirements.txt    # Python dependencies
├── .env.example        # Example environment variables
└── README.md          # This file
```

## API Endpoints

### Authentication

- `POST /auth/register` - Create new user account
- `POST /auth/login` - Authenticate with username + API key

### Sessions

- `GET /sessions?api_key={key}` - List user sessions
- `POST /sessions?api_key={key}` - Create new session
- `DELETE /sessions/{session_id}?api_key={key}` - Delete session
- `GET /sessions/{session_id}/messages?api_key={key}` - Get session messages

### File Management

- `POST /sessions/{session_id}/upload?api_key={key}` - Upload file
- `GET /sessions/{session_id}/files?api_key={key}` - List session files
- `DELETE /sessions/{session_id}/files/{filename}?api_key={key}` - Delete file

### Chat

- `POST /chat/stream` - Stream AI responses (JSON body with session_id, message, api_key)

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DB_HOST | PostgreSQL host | postgres |
| DB_PORT | PostgreSQL port | 5432 |
| DB_USER | Database user | postgres |
| DB_PASSWORD | Database password | (required) |
| DB_NAME | Database name | postgres |
| DB_MIN_POOL_SIZE | Minimum connection pool size | 2 |
| DB_MAX_POOL_SIZE | Maximum connection pool size | 10 |
| OLLAMA_MODEL | Ollama model to use | qwen2.5-coder:1.5b |
| OLLAMA_BASE_URL | Ollama API URL | http://host.docker.internal:11434 |
| APP_PORT | Backend port | 8000 |
| FRONTEND_PORT | Frontend port | 8001 |

### Supported Models

Any Ollama code model should work. Recommended models:
- `qwen2.5-coder:1.5b` (default)
- `codellama:latest`
- `deepseek-coder:latest`
- `starcoder2:latest`
- `mistral:latest` (general purpose)

## Troubleshooting

### Common Issues

**Ollama Connection Refused**
- Ensure Ollama is running: `ollama serve`
- Check OLLAMA_BASE_URL in .env (use `host.docker.internal` for Docker Desktop, or host IP for Linux)
- Test connection: `curl http://localhost:11434/api/tags`

**Database Connection Issues**
- Verify PostgreSQL container is running: `docker-compose ps`
- Check database logs: `docker-compose logs postgres`
- Ensure database credentials in .env match

**Port Conflicts**
- Change ports in .env file
- Check for existing services: `lsof -i :8000`

**Model Not Found**
- Pull the model: `ollama pull qwen2.5-coder:1.5b`
- Verify model name in .env matches exactly

### Verification Script

Run the verification script to check your setup:

```bash
chmod +x verify-setup.sh
./verify-setup.sh
```

## Development

### Building Frontend

The frontend uses Vue.js loaded via CDN. For development:

```bash
# Frontend files are in frontend/
# Edit index.html, app.js, and styles.css directly
# Changes are reflected immediately (no build step required)
```

### Database Migrations

Database tables are created automatically on first run. To reset:

```bash
# With Docker
docker-compose down -v  # WARNING: Deletes all data!

# Manual
# Drop and recreate database
```

### Adding New Features

1. Backend: Add endpoints in `backend/main.py`
2. Database: Add models in `backend/database.py`
3. Frontend: Add Vue components in `frontend/app.js`

## Security Considerations

- API keys are generated using UUID v4 and stored securely
- Passwords are not used - authentication is API key based
- File uploads are limited to 500KB and sanitized
- Database credentials are stored in .env (not committed)
- CORS is configured to allow specific origins in production

## Production Deployment

For production use:

1. Set secure database password
2. Configure CORS with specific origins
3. Use reverse proxy (nginx) for SSL termination
4. Set up database backups
5. Monitor Ollama resource usage
6. Consider using a process manager for Ollama

Example nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://localhost:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Performance Tuning

- Adjust DB_POOL_SIZE based on concurrent users
- Monitor Ollama memory usage (models typically use 1-8GB RAM)
- Consider using GPU acceleration for Ollama
- Increase context_window in agent.py for larger conversations

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- Email: bryteh123@gmail.com

