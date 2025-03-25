#!/usr/bin/env python3
"""
Unit test script for the AI Agent application.
Tests individual components to ensure they work correctly.
"""

import os
import sys
import unittest
import json
from unittest.mock import MagicMock, patch

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modules to test
try:
    from backend.main import app, get_cache, set_cache, invalidate_cache
    from fastapi.testclient import TestClient
except ImportError:
    print("Error: Could not import required modules.")
    print("Make sure you have installed the required dependencies:")
    print("  pip install fastapi pytest requests websocket-client")
    sys.exit(1)

class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoints."""
    
    def setUp(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test the root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("status", data)
        self.assertIn("version", data)
    
    def test_status_endpoint(self):
        """Test the /status endpoint."""
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("agentStatus", data)
        self.assertIn("systemStatus", data)
    
    def test_health_endpoint(self):
        """Test the /health endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("components", data)
    
    @patch('backend.knowledge_graph.KnowledgeGraph.get_graph_visualization_data')
    def test_graph_endpoint(self, mock_get_graph):
        """Test the /graph endpoint."""
        # Mock the graph data
        mock_get_graph.return_value = {"nodes": [], "links": []}
        
        response = self.client.get("/graph")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("nodes", data)
        self.assertIn("links", data)
    
    @patch('backend.todo_manager.ToDoManager.get_todo_content')
    def test_todos_endpoint(self, mock_get_todos):
        """Test the /todos endpoint."""
        # Mock the todo data
        mock_get_todos.return_value = "# Test ToDo"
        
        response = self.client.get("/todos")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("content", data)
        self.assertIn("timestamp", data)
    
    def test_error_handling(self):
        """Test error handling for invalid requests."""
        # Test invalid endpoint
        response = self.client.get("/invalid_endpoint")
        self.assertEqual(response.status_code, 404)
        
        # Test invalid request body
        response = self.client.post("/execute", json={"invalid": "data"})
        self.assertIn(response.status_code, (400, 422))

class TestCaching(unittest.TestCase):
    """Test caching functionality."""
    
    @patch('backend.main.redis_client')
    async def test_get_cache(self, mock_redis):
        """Test get_cache function."""
        # Mock Redis get
        mock_redis.get.return_value = json.dumps({"test": "data"})
        
        # Test with Redis available
        result = await get_cache("test_key")
        self.assertEqual(result, {"test": "data"})
        mock_redis.get.assert_called_once_with("test_key")
        
        # Test with Redis unavailable
        mock_redis.get.side_effect = Exception("Redis error")
        result = await get_cache("test_key")
        self.assertIsNone(result)
    
    @patch('backend.main.redis_client')
    async def test_set_cache(self, mock_redis):
        """Test set_cache function."""
        # Test with Redis available
        result = await set_cache("test_key", {"test": "data"}, 60)
        self.assertTrue(result)
        mock_redis.setex.assert_called_once()
        
        # Test with Redis unavailable
        mock_redis.setex.side_effect = Exception("Redis error")
        result = await set_cache("test_key", {"test": "data"}, 60)
        self.assertFalse(result)
    
    @patch('backend.main.redis_client')
    async def test_invalidate_cache(self, mock_redis):
        """Test invalidate_cache function."""
        # Test with Redis available
        result = await invalidate_cache("test_key")
        self.assertTrue(result)
        mock_redis.delete.assert_called_once_with("test_key")
        
        # Test with Redis unavailable
        mock_redis.delete.side_effect = Exception("Redis error")
        result = await invalidate_cache("test_key")
        self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
