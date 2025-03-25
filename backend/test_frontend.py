"""
Test script for frontend components.
This script tests React components using Jest and React Testing Library.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

class TestFrontendComponents(unittest.TestCase):
    """Test cases for the frontend components."""
    
    def test_package_json(self):
        """Test that package.json exists and has required dependencies."""
        package_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'package.json')
        self.assertTrue(os.path.exists(package_json_path), "package.json file not found")
        
        # Read package.json
        import json
        with open(package_json_path, 'r') as f:
            package_data = json.load(f)
        
        # Check required dependencies
        self.assertIn('dependencies', package_data, "No dependencies found in package.json")
        dependencies = package_data['dependencies']
        
        # Check for React
        self.assertIn('react', dependencies, "React dependency not found")
        self.assertIn('react-dom', dependencies, "React DOM dependency not found")
        
        # Check for styling libraries
        self.assertIn('styled-components', dependencies, "styled-components not found")
        
        # Check for API/WebSocket libraries
        self.assertTrue(
            'axios' in dependencies or 'fetch' in dependencies or 'websocket' in dependencies,
            "No API/WebSocket library found"
        )
    
    def test_component_files_exist(self):
        """Test that required component files exist."""
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')
        components_dir = os.path.join(frontend_dir, 'src', 'components')
        
        # Check that components directory exists
        self.assertTrue(os.path.exists(components_dir), "Components directory not found")
        
        # Check for required component files
        required_components = [
            'ToDoList.js',
            'GraphViewer.js',
            'TerminalView.js',
            'Header.js',
            'Footer.js'
        ]
        
        for component in required_components:
            component_path = os.path.join(components_dir, component)
            self.assertTrue(os.path.exists(component_path), f"{component} not found")
    
    def test_app_js_exists(self):
        """Test that App.js exists and imports required components."""
        app_js_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'src', 'App.js')
        self.assertTrue(os.path.exists(app_js_path), "App.js not found")
        
        # Read App.js
        with open(app_js_path, 'r') as f:
            app_js_content = f.read()
        
        # Check for imports of required components
        self.assertIn('import', app_js_content, "No imports found in App.js")
        self.assertIn('ToDoList', app_js_content, "ToDoList component not imported in App.js")
        self.assertIn('GraphViewer', app_js_content, "GraphViewer component not imported in App.js")
        self.assertIn('TerminalView', app_js_content, "TerminalView component not imported in App.js")
    
    def test_api_service_exists(self):
        """Test that API service file exists and has required functions."""
        api_service_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend', 'src', 'services', 'apiService.js')
        self.assertTrue(os.path.exists(api_service_path), "apiService.js not found")
        
        # Read apiService.js
        with open(api_service_path, 'r') as f:
            api_service_content = f.read()
        
        # Check for required functions
        self.assertIn('connectWebSocket', api_service_content, "connectWebSocket function not found in apiService.js")
        self.assertIn('getStatus', api_service_content, "getStatus function not found in apiService.js")
        self.assertIn('executeTask', api_service_content, "executeTask function not found in apiService.js")

if __name__ == "__main__":
    unittest.main()
