#!/bin/bash
# Test script for the AI Agent application
# This script runs both unit and integration tests

set -e  # Exit on error

echo "========================================"
echo "Running tests for AI Agent application"
echo "========================================"

# Check if the application is running
echo "Checking if the application is running..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "Error: Application is not running or not accessible."
    echo "Please start the application with 'docker compose up --build' before running tests."
    exit 1
fi

# Install test dependencies if needed
echo "Installing test dependencies..."
pip install pytest requests websocket-client pytest-asyncio > /dev/null

# Make scripts executable
chmod +x tests/integration_test.py
chmod +x tests/unit_test.py

# Run unit tests
echo -e "\n========================================"
echo "Running unit tests..."
echo "========================================"
python -m pytest tests/unit_test.py -v

# Run integration tests
echo -e "\n========================================"
echo "Running integration tests..."
echo "========================================"
python tests/integration_test.py

echo -e "\n========================================"
echo "All tests completed!"
echo "========================================"
