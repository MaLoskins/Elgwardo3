# AI Agent Application - README

## Overview

This is a microservices-based AI agent application that uses Docker to orchestrate multiple components:
- React frontend
- FastAPI backend
- Terminal service
- Redis for caching

The application provides an interface for interacting with AI agents, managing tasks, and visualizing knowledge graphs.

## Components

1. **Frontend**: React-based user interface
2. **Backend**: FastAPI application that manages AI agents and coordinates tasks
3. **Terminal**: Containerized terminal service for executing commands
4. **Redis**: Caching layer for improved performance

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 16+ (for development only)
- Python 3.10+ (for development only)

### Running the Application

1. Clone the repository
2. Navigate to the project directory
3. Start the application with Docker Compose:

```bash
docker compose up --build
```

4. Access the application at http://localhost:3000

## Architecture

The application follows a microservices architecture:

- **Frontend Container**: Serves the React application
- **Backend Container**: Runs the FastAPI application
- **Terminal Container**: Provides a containerized terminal environment
- **Redis Container**: Handles caching and pub/sub messaging

## API Endpoints

- `/status`: Get the current status of the agent and terminal
- `/execute`: Execute a coding task autonomously
- `/graph`: Get the knowledge graph visualization data
- `/todos`: Get the current ToDo list content
- `/health`: Health check endpoint for monitoring
- `/ws`: WebSocket endpoint for real-time updates

## Features

- **AI Agent Coordination**: Manages multiple specialized AI agents
- **Knowledge Graph**: Visualizes relationships between concepts and code
- **Task Management**: Tracks and manages tasks in a ToDo list
- **Terminal Interface**: Provides a terminal for executing commands
- **Real-time Updates**: Uses WebSockets for real-time communication

## Development

### Frontend Development

```bash
cd frontend
npm install
npm start
```

### Backend Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Testing

Run the test suite with:

```bash
cd tests
./run_tests.sh
```

This will run both unit and integration tests.

## Recent Changes

See [CHANGES.md](CHANGES.md) for a detailed list of recent changes and fixes.

## Troubleshooting

### Common Issues

1. **404 Errors for API Endpoints**: Make sure the backend is running and all services are properly connected.
2. **WebSocket Connection Issues**: Check network connectivity and firewall settings.
3. **Docker Compose Errors**: Ensure all ports are available and not in use by other applications.

### Logs

- Frontend logs: `docker logs ai_agent_frontend`
- Backend logs: `docker logs ai_agent_backend`
- Terminal logs: `docker logs ai_agent_terminal`
- Redis logs: `docker logs ai_agent_redis`

## License

This project is licensed under the MIT License - see the LICENSE file for details.
