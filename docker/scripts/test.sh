#!/bin/bash

# Test script for Dynamic AI Agent application
# This script will run tests to verify the functionality of the application

echo "Starting tests for Dynamic AI Agent application..."

# Check if backend dependencies are installed
echo "Checking backend dependencies..."
cd /app
pip install -r requirements.txt

# Check if Redis is running
echo "Checking Redis connection..."
python -c "
import redis
try:
    r = redis.Redis(host='redis', port=6379, db=0)
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
"

# Check if backend API is accessible
echo "Checking backend API..."
curl -s http://localhost:8000/ | grep "running" || echo "Backend API not accessible"

# Check WebSocket connection
echo "Checking WebSocket connection..."
python -c "
import asyncio
import websockets
import json
import time

async def test_websocket():
    try:
        uri = 'ws://localhost:8000/ws'
        async with websockets.connect(uri, timeout=5) as websocket:
            # Send ping message
            await websocket.send(json.dumps({
                'type': 'ping',
                'timestamp': time.time()
            }))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get('type') == 'pong':
                print('WebSocket connection successful')
            else:
                print(f'Unexpected response: {data}')
    except Exception as e:
        print(f'WebSocket connection failed: {e}')

asyncio.run(test_websocket())
"

# Check if terminal container is running
echo "Checking terminal container..."
docker ps | grep ai_agent_terminal || echo "Terminal container not running"

# Check if frontend is accessible
echo "Checking frontend..."
curl -s http://localhost:3000/ | grep "Dynamic AI Agent" || echo "Frontend not accessible"

echo "Tests completed."
