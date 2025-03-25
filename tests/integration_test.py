#!/usr/bin/env python3
"""
Integration test script for the AI Agent application.
Tests all components to ensure they work correctly together.
"""

import os
import sys
import requests
import json
import time
import websocket
import threading
import argparse
from typing import Dict, Any, List, Optional

# Configuration
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_WS_URL = "ws://localhost:8000/ws"
TEST_TIMEOUT = 30  # seconds

class TestResult:
    """Class to track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []
    
    def add_pass(self, test_name: str):
        """Record a passed test."""
        self.passed += 1
        print(f"✅ PASS: {test_name}")
    
    def add_fail(self, test_name: str, error: str):
        """Record a failed test."""
        self.failed += 1
        self.failures.append((test_name, error))
        print(f"❌ FAIL: {test_name} - {error}")
    
    def add_skip(self, test_name: str, reason: str):
        """Record a skipped test."""
        self.skipped += 1
        print(f"⚠️ SKIP: {test_name} - {reason}")
    
    def summary(self):
        """Print test summary."""
        print("\n" + "="*50)
        print(f"TEST SUMMARY: {self.passed} passed, {self.failed} failed, {self.skipped} skipped")
        
        if self.failures:
            print("\nFAILURES:")
            for name, error in self.failures:
                print(f"  - {name}: {error}")
        
        print("="*50)
        return self.failed == 0

class WebSocketClient:
    """WebSocket client for testing WebSocket connections."""
    def __init__(self, url: str):
        self.url = url
        self.connected = False
        self.messages = []
        self.error = None
        self.ws = None
        self.thread = None
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            self.messages.append(data)
        except Exception as e:
            self.error = f"Failed to parse message: {str(e)}"
    
    def on_error(self, ws, error):
        """Handle WebSocket errors."""
        self.error = str(error)
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        self.connected = False
    
    def on_open(self, ws):
        """Handle WebSocket connection open."""
        self.connected = True
    
    def connect(self, timeout: int = 10) -> bool:
        """Connect to WebSocket server."""
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.thread = threading.Thread(target=self.ws.run_forever)
        self.thread.daemon = True
        self.thread.start()
        
        # Wait for connection
        start_time = time.time()
        while not self.connected and not self.error and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        return self.connected
    
    def send(self, message: str) -> bool:
        """Send message to WebSocket server."""
        if not self.connected:
            return False
        
        try:
            self.ws.send(message)
            return True
        except Exception as e:
            self.error = str(e)
            return False
    
    def close(self):
        """Close WebSocket connection."""
        if self.ws:
            self.ws.close()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)

class AIAgentTester:
    """Test runner for AI Agent application."""
    def __init__(self, base_url: str, ws_url: str):
        self.base_url = base_url
        self.ws_url = ws_url
        self.results = TestResult()
        self.session = requests.Session()
    
    def run_tests(self) -> bool:
        """Run all tests and return True if all passed."""
        try:
            # Test basic connectivity
            self.test_status_endpoint()
            
            # Test API endpoints
            self.test_graph_endpoint()
            self.test_todos_endpoint()
            self.test_health_endpoint()
            
            # Test WebSocket
            self.test_websocket_connection()
            
            # Test error handling
            self.test_error_handling()
            
            # Test rate limiting
            self.test_rate_limiting()
            
            # Print summary
            return self.results.summary()
        except Exception as e:
            print(f"Error running tests: {str(e)}")
            return False
    
    def test_status_endpoint(self):
        """Test the /status endpoint."""
        test_name = "Status Endpoint"
        try:
            response = self.session.get(f"{self.base_url}/status", timeout=TEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if "agentStatus" in data and "systemStatus" in data:
                    self.results.add_pass(test_name)
                else:
                    self.results.add_fail(test_name, "Response missing required fields")
            else:
                self.results.add_fail(test_name, f"Unexpected status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.results.add_fail(test_name, f"Request failed: {str(e)}")
    
    def test_graph_endpoint(self):
        """Test the /graph endpoint."""
        test_name = "Graph Endpoint"
        try:
            response = self.session.get(f"{self.base_url}/graph", timeout=TEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if "nodes" in data and "links" in data:
                    self.results.add_pass(test_name)
                else:
                    self.results.add_fail(test_name, "Response missing required fields")
            else:
                self.results.add_fail(test_name, f"Unexpected status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.results.add_fail(test_name, f"Request failed: {str(e)}")
    
    def test_todos_endpoint(self):
        """Test the /todos endpoint."""
        test_name = "Todos Endpoint"
        try:
            response = self.session.get(f"{self.base_url}/todos", timeout=TEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if "content" in data and "timestamp" in data:
                    self.results.add_pass(test_name)
                else:
                    self.results.add_fail(test_name, "Response missing required fields")
            else:
                self.results.add_fail(test_name, f"Unexpected status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.results.add_fail(test_name, f"Request failed: {str(e)}")
    
    def test_health_endpoint(self):
        """Test the /health endpoint."""
        test_name = "Health Endpoint"
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=TEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if "status" in data and "components" in data:
                    self.results.add_pass(test_name)
                else:
                    self.results.add_fail(test_name, "Response missing required fields")
            else:
                self.results.add_fail(test_name, f"Unexpected status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.results.add_fail(test_name, f"Request failed: {str(e)}")
    
    def test_websocket_connection(self):
        """Test WebSocket connection."""
        test_name = "WebSocket Connection"
        client = WebSocketClient(self.ws_url)
        
        try:
            # Connect to WebSocket
            if not client.connect(timeout=5):
                self.results.add_fail(test_name, f"Failed to connect: {client.error or 'Connection timeout'}")
                return
            
            # Send ping message
            if not client.send("ping"):
                self.results.add_fail(test_name, f"Failed to send message: {client.error}")
                return
            
            # Wait for pong response
            start_time = time.time()
            while time.time() - start_time < 5:
                for message in client.messages:
                    if message.get("type") == "pong":
                        self.results.add_pass(test_name)
                        return
                time.sleep(0.1)
            
            self.results.add_fail(test_name, "No pong response received")
        except Exception as e:
            self.results.add_fail(test_name, f"Unexpected error: {str(e)}")
        finally:
            client.close()
    
    def test_error_handling(self):
        """Test error handling for invalid requests."""
        test_name = "Error Handling"
        try:
            # Test invalid endpoint
            response = self.session.get(f"{self.base_url}/invalid_endpoint", timeout=TEST_TIMEOUT)
            
            if response.status_code == 404:
                # Test invalid request body
                response = self.session.post(
                    f"{self.base_url}/execute", 
                    json={"invalid": "data"},
                    timeout=TEST_TIMEOUT
                )
                
                if response.status_code in (400, 422):
                    self.results.add_pass(test_name)
                else:
                    self.results.add_fail(test_name, f"Expected 400/422 for invalid request body, got {response.status_code}")
            else:
                self.results.add_fail(test_name, f"Expected 404 for invalid endpoint, got {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.results.add_fail(test_name, f"Request failed: {str(e)}")
    
    def test_rate_limiting(self):
        """Test rate limiting."""
        test_name = "Rate Limiting"
        
        # This test is optional as it might disrupt other tests
        self.results.add_skip(test_name, "Skipping to avoid disrupting other tests")
        return
        
        try:
            # Make many requests in quick succession
            for i in range(70):  # More than the default limit
                self.session.get(f"{self.base_url}/status", timeout=1)
            
            # This request should be rate limited
            response = self.session.get(f"{self.base_url}/status", timeout=TEST_TIMEOUT)
            
            if response.status_code == 429:
                self.results.add_pass(test_name)
            else:
                self.results.add_fail(test_name, f"Expected 429 for rate limited request, got {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.results.add_fail(test_name, f"Request failed: {str(e)}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test AI Agent application")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for API endpoints")
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL, help="WebSocket URL")
    args = parser.parse_args()
    
    print(f"Testing AI Agent application at {args.base_url}")
    print(f"WebSocket URL: {args.ws_url}")
    print("="*50)
    
    tester = AIAgentTester(args.base_url, args.ws_url)
    success = tester.run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
