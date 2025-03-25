"""
Test script for backend API endpoints.
This script tests the FastAPI endpoints without requiring Docker.
"""

import asyncio
import sys
import os
import json
import unittest
from fastapi.testclient import TestClient

# Add the current directory to the path so we can import the main module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app
from main import app

class TestBackendAPI(unittest.TestCase):
    """Test cases for the backend API endpoints."""
    
    def setUp(self):
        """Set up the test client."""
        self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test the root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Enhanced AI Agent Terminal Interface API")
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["version"], "2.0.0")
    
    def test_status_endpoint(self):
        """Test the status endpoint."""
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Check that the response contains expected keys
        self.assertIn("agent_status", data)
        self.assertIn("terminal_status", data)
        self.assertIn("todo_status", data)
        self.assertIn("timestamp", data)
    
    def test_model_endpoint(self):
        """Test the model selection endpoint."""
        # Test setting a valid model
        response = self.client.post("/model", json={"model": "gpt-4o"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Model updated to gpt-4o")
        
        # Test setting an invalid model
        response = self.client.post("/model", json={"model": "invalid-model"})
        self.assertEqual(response.status_code, 400)
    
    def test_execute_endpoint(self):
        """Test the execute endpoint."""
        # This is a simple test that just checks if the endpoint accepts requests
        # We don't actually execute tasks as that would require OpenAI API calls
        response = self.client.post("/execute", json={"task": "Test task", "model": "gpt-4o"})
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["message"], "Task execution started")
        self.assertEqual(data["task"], "Test task")
        self.assertEqual(data["model"], "gpt-4o")

if __name__ == "__main__":
    unittest.main()
