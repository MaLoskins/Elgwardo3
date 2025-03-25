"""
Main entry point for the FastAPI application.
Handles routing and initialization of the enhanced AI agent terminal interface.
"""

import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from typing import List, Dict, Any, Optional, Set
import time
import logging
import json
from functools import lru_cache
import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool

# Import local modules
from agent_coordinator import AgentCoordinator
from knowledge_graph import KnowledgeGraph
from todo_manager import ToDoManager
from terminal_manager import TerminalManager
from utils import setup_logging, get_status

# Create agents directory if it doesn't exist
os.makedirs('agents', exist_ok=True)

# Ensure the agents directory has an __init__.py file
init_path = os.path.join('agents', '__init__.py')
if not os.path.exists(init_path):
    with open(init_path, 'w') as f:
        f.write('"""Agent modules package."""\n')

# Setup logging
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced AI Agent Terminal Interface",
    description="Local AI agent capable of end-to-end coding operations with a containerized WSL-like terminal.",
    version="2.0.0"
)

# Add CORS middleware to allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "BSA7pk2iup6t2Em3vA9VrbH0GU27th4")
MODEL_SELECTION = os.getenv("MODEL_SELECTION", "gpt-4o")

# Initialize Redis client for caching
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5
    )
    logger.info("Redis client initialized")
except Exception as e:
    logger.warning(f"Failed to initialize Redis client: {str(e)}. Using in-memory cache.")
    redis_client = None

# Cache configuration
CACHE_TTL = 60  # 60 seconds default TTL
CACHE_ENABLED = True

# Rate limiting configuration
RATE_LIMIT_ENABLED = True
RATE_LIMIT_REQUESTS = 60  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# Initialize components
knowledge_graph = KnowledgeGraph()
todo_manager = ToDoManager()
terminal_manager = TerminalManager()

# Initialize the Agent Coordinator with specialized agents
agent_coordinator = AgentCoordinator(
    openai_api_key=OPENAI_API_KEY,
    brave_search_api_key=BRAVE_SEARCH_API_KEY,
    model=MODEL_SELECTION,
    knowledge_graph=knowledge_graph,
    todo_manager=todo_manager,
    terminal_manager=terminal_manager
)

# WebSocket connections and their active status
class WebSocketConnection:
    def __init__(self, socket: WebSocket):
        self.socket = socket
        self.last_activity = time.time()
        self.is_active = True

# Store for active WebSocket connections
active_connections: List[WebSocketConnection] = []

# Request models
class ExecuteRequest(BaseModel):
    task: str
    model: Optional[str] = "gpt-4o"

class ModelSelectionRequest(BaseModel):
    model: str

# In-memory cache for when Redis is unavailable
in_memory_cache = {}

# Cache helper functions
async def get_cache(key: str) -> Optional[Any]:
    """Get data from cache."""
    if not CACHE_ENABLED:
        return None
        
    try:
        if redis_client:
            # Try Redis first
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        else:
            # Fall back to in-memory cache
            if key in in_memory_cache:
                cache_item = in_memory_cache[key]
                if time.time() < cache_item["expires"]:
                    return cache_item["data"]
                else:
                    # Clean up expired item
                    del in_memory_cache[key]
    except Exception as e:
        logger.warning(f"Cache get error for key {key}: {str(e)}")
    
    return None

async def set_cache(key: str, data: Any, ttl: int = CACHE_TTL) -> bool:
    """Set data in cache with TTL."""
    if not CACHE_ENABLED:
        return False
        
    try:
        json_data = json.dumps(data)
        if redis_client:
            # Try Redis first
            await redis_client.setex(key, ttl, json_data)
        else:
            # Fall back to in-memory cache
            in_memory_cache[key] = {
                "data": data,
                "expires": time.time() + ttl
            }
        return True
    except Exception as e:
        logger.warning(f"Cache set error for key {key}: {str(e)}")
        return False

async def invalidate_cache(key: str = None) -> bool:
    """Invalidate specific cache key or all keys with prefix."""
    try:
        if key:
            if redis_client:
                await redis_client.delete(key)
            else:
                if key in in_memory_cache:
                    del in_memory_cache[key]
        else:
            # Invalidate all keys
            if redis_client:
                # Get all keys with our prefix and delete them
                keys = await redis_client.keys("ai_agent:*")
                if keys:
                    await redis_client.delete(*keys)
            else:
                in_memory_cache.clear()
        return True
    except Exception as e:
        logger.warning(f"Cache invalidation error: {str(e)}")
        return False

# Rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)
            
        # Skip rate limiting for WebSocket connections
        if request.url.path == "/ws":
            return await call_next(request)
            
        client_ip = request.client.host
        rate_key = f"ai_agent:rate_limit:{client_ip}"
        
        try:
            if redis_client:
                # Get current count
                count = await redis_client.get(rate_key)
                count = int(count) if count else 0
                
                if count >= RATE_LIMIT_REQUESTS:
                    # Rate limit exceeded
                    return Response(
                        content=json.dumps({"detail": "Rate limit exceeded. Please try again later."}),
                        status_code=429,
                        media_type="application/json"
                    )
                
                # Increment count and set expiry if not exists
                pipe = redis_client.pipeline()
                pipe.incr(rate_key)
                pipe.expire(rate_key, RATE_LIMIT_WINDOW)
                await pipe.execute()
            else:
                # Simple in-memory rate limiting
                current_time = time.time()
                rate_key_memory = f"rate_limit:{client_ip}"
                
                if rate_key_memory in in_memory_cache:
                    rate_data = in_memory_cache[rate_key_memory]
                    # Clean up old requests
                    rate_data["requests"] = [ts for ts in rate_data["requests"] if current_time - ts < RATE_LIMIT_WINDOW]
                    
                    if len(rate_data["requests"]) >= RATE_LIMIT_REQUESTS:
                        # Rate limit exceeded
                        return Response(
                            content=json.dumps({"detail": "Rate limit exceeded. Please try again later."}),
                            status_code=429,
                            media_type="application/json"
                        )
                    
                    # Add current request
                    rate_data["requests"].append(current_time)
                else:
                    # First request from this IP
                    in_memory_cache[rate_key_memory] = {
                        "requests": [current_time]
                    }
        except Exception as e:
            logger.warning(f"Rate limiting error: {str(e)}")
            # Continue on error, don't block the request
            
        # Process the request
        return await call_next(request)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Error handling middleware
class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An unexpected error occurred",
                    "error_type": type(e).__name__,
                    "timestamp": time.time()
                }
            )

# Add error handling middleware
app.add_middleware(ErrorHandlingMiddleware)

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    logger.info("Starting Enhanced AI Agent Terminal Interface")
    # Ensure ToDo.md exists
    todo_manager.initialize()
    # Initialize terminal
    await terminal_manager.initialize()
    # Start the WebSocket connection monitor
    asyncio.create_task(monitor_websocket_connections())
    # Check Redis connection
    if redis_client:
        try:
            await redis_client.ping()
            logger.info("Redis connection verified")
        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}")
    logger.info("Initialization complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Enhanced AI Agent Terminal Interface")
    await terminal_manager.shutdown()
    # Close Redis connection
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

async def monitor_websocket_connections():
    """
    Monitor WebSocket connections and remove inactive ones.
    This helps with resource management.
    """
    INACTIVE_TIMEOUT = 30  # seconds
    PING_INTERVAL = 15     # seconds
    
    while True:
        try:
            current_time = time.time()
            connections_to_remove = []
            
            # Check for inactive connections
            for conn in active_connections:
                if current_time - conn.last_activity > INACTIVE_TIMEOUT:
                    conn.is_active = False
                    connections_to_remove.append(conn)
                elif current_time - conn.last_activity > PING_INTERVAL:
                    # Send ping to keep connection alive
                    try:
                        await conn.socket.send_json({"type": "ping", "timestamp": current_time})
                        conn.last_activity = current_time
                    except Exception:
                        conn.is_active = False
                        connections_to_remove.append(conn)
            
            # Remove inactive connections
            for conn in connections_to_remove:
                if conn in active_connections:
                    active_connections.remove(conn)
                    logger.info("Removed inactive WebSocket connection")
            
            await asyncio.sleep(5)  # Check every 5 seconds
        except Exception as e:
            logger.error(f"Error in WebSocket monitor: {str(e)}")
            await asyncio.sleep(10)  # Longer delay on error

@app.get("/")
async def root():
    """Root endpoint that returns basic information about the API."""
    return {
        "message": "Enhanced AI Agent Terminal Interface API",
        "status": "running",
        "version": "2.0.0"
    }

@app.get("/status")
async def status():
    """Get the current status of the agent and terminal."""
    cache_key = "ai_agent:status"
    
    # Try to get from cache first
    cached_data = await get_cache(cache_key)
    if cached_data:
        return cached_data
    
    # Get fresh data
    status_data = get_status(agent_coordinator, terminal_manager, todo_manager)
    
    # Cache the result (short TTL for status)
    await set_cache(cache_key, status_data, ttl=15)
    
    return status_data

@app.post("/execute")
async def execute(request: ExecuteRequest, background_tasks: BackgroundTasks):
    """
    Execute a coding task autonomously.
    
    The task is processed in the background to allow for long-running operations.
    """
    try:
        # Update model if different from current
        if request.model != agent_coordinator.model:
            agent_coordinator.set_model(request.model)
        
        # Start task execution in background
        background_tasks.add_task(agent_coordinator.execute_task, request.task)
        
        # Invalidate caches since we're starting a new task
        background_tasks.add_task(invalidate_cache)
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Task execution started",
                "task": request.task,
                "model": agent_coordinator.model
            }
        )
    except Exception as e:
        logger.error(f"Error executing task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/model")
async def set_model(request: ModelSelectionRequest):
    """Update the OpenAI model selection."""
    try:
        agent_coordinator.set_model(request.model)
        return {"message": f"Model updated to {request.model}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/graph")
async def get_graph():
    """
    Get the knowledge graph visualization data.
    
    Returns the nodes and edges of the knowledge graph for visualization.
    """
    cache_key = "ai_agent:graph"
    
    # Try to get from cache first
    cached_data = await get_cache(cache_key)
    if cached_data:
        return cached_data
    
    try:
        # Get fresh data
        graph_data = knowledge_graph.get_graph_visualization_data()
        
        # Cache the result
        await set_cache(cache_key, graph_data, ttl=60)
        
        return JSONResponse(
            status_code=200,
            content=graph_data
        )
    except Exception as e:
        logger.error(f"Error retrieving knowledge graph: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/todos")
async def get_todos():
    """
    Get the current ToDo list content.
    
    Returns the content of the ToDo.md file.
    """
    cache_key = "ai_agent:todos"
    
    # Try to get from cache first
    cached_data = await get_cache(cache_key)
    if cached_data:
        return cached_data
    
    try:
        # Get fresh data
        todo_content = todo_manager.get_todo_content()
        
        response_data = {
            "content": todo_content,
            "timestamp": time.time()
        }
        
        # Cache the result
        await set_cache(cache_key, response_data, ttl=30)
        
        return JSONResponse(
            status_code=200,
            content=response_data
        )
    except Exception as e:
        logger.error(f"Error retrieving todo list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns the health status of various components.
    """
    health_data = {
        "status": "healthy",
        "timestamp": time.time(),
        "components": {
            "api": "healthy",
            "redis": "unknown",
            "terminal": "unknown",
            "agents": "unknown"
        }
    }
    
    # Check Redis health
    if redis_client:
        try:
            await redis_client.ping()
            health_data["components"]["redis"] = "healthy"
        except Exception:
            health_data["components"]["redis"] = "unhealthy"
            health_data["status"] = "degraded"
    else:
        health_data["components"]["redis"] = "disabled"
    
    # Check terminal health
    try:
        terminal_status = await terminal_manager.get_status()
        health_data["components"]["terminal"] = "healthy" if terminal_status.get("running", False) else "unhealthy"
        if health_data["components"]["terminal"] == "unhealthy":
            health_data["status"] = "degraded"
    except Exception:
        health_data["components"]["terminal"] = "unhealthy"
        health_data["status"] = "degraded"
    
    # Check agent health
    try:
        agent_status = agent_coordinator.get_status()
        health_data["components"]["agents"] = "healthy" if agent_status.get("initialized", False) else "unhealthy"
        if health_data["components"]["agents"] == "unhealthy":
            health_data["status"] = "degraded"
    except Exception:
        health_data["components"]["agents"] = "unhealthy"
        health_data["status"] = "degraded"
    
    return health_data

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Clients can connect to this endpoint to receive real-time updates
    about task execution, terminal output, and agent status.
    """
    await websocket.accept()
    connection = WebSocketConnection(websocket)
    active_connections.append(connection)
    
    try:
        while True:
            # Keep connection alive and wait for client messages
            data = await websocket.receive_text()
            connection.last_activity = time.time()
            
            # Handle client messages
            if data.lower() == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
            else:
                # Process other message types if needed
                await websocket.send_json({"type": "message_received", "data": data, "timestamp": time.time()})
    except WebSocketDisconnect:
        connection.is_active = False
        if connection in active_connections:
            active_connections.remove(connection)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        connection.is_active = False
        if connection in active_connections:
            active_connections.remove(connection)

# Function to broadcast messages to all connected clients
async def broadcast_message(message: Dict[str, Any]):
    """Send a message to all connected WebSocket clients."""
    connections_to_remove = []
    
    for connection in active_connections:
        if not connection.is_active:
            connections_to_remove.append(connection)
            continue
            
        try:
            await connection.socket.send_json(message)
            connection.last_activity = time.time()
        except Exception as e:
            logger.error(f"Error broadcasting message: {str(e)}")
            connection.is_active = False
            connections_to_remove.append(connection)
    
    # Remove failed connections
    for conn in connections_to_remove:
        if conn in active_connections:
            active_connections.remove(conn)

# Make broadcast function available to other modules
agent_coordinator.set_broadcast_function(broadcast_message)
terminal_manager.set_broadcast_function(broadcast_message)
todo_manager.set_broadcast_function(broadcast_message)

# Mount static files for the frontend
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")

# Mount static files for the frontend
# Check if frontend/build directory exists before mounting
import os
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "build")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
else:
    logger.warning(f"Frontend build directory not found at {frontend_dir}. Static files will not be served.")

if __name__ == "__main__":
    # Run the FastAPI app with Uvicorn when executed directly
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
