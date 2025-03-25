"""
Enhanced Knowledge Graph module for the AI Agent Terminal Interface.
Manages the dynamic knowledge graph tracking code context, dependencies, and errors
with support for complex projects and larger codebases.
"""

import logging
import time
import json
import os
from typing import Dict, Any, List, Optional, Set, Tuple, Union
import networkx as nx
from collections import defaultdict

logger = logging.getLogger(__name__)

class KnowledgeGraph:
    """
    Manages a dynamic knowledge graph to track code modules, functions, errors,
    and their interrelationships.
    
    The graph structure maps code components, their dependencies, errors encountered,
    and contextual information to provide a comprehensive view of the codebase
    and development history.
    
    Enhancements:
    - Improved project structure tracking
    - Better dependency management
    - Code history versioning
    - Module relationship analysis
    - Enhanced error pattern recognition
    """
    
    def __init__(self):
        """Initialize the enhanced knowledge graph."""
        # Initialize directed graph
        self.graph = nx.DiGraph()
        
        # Track task IDs for organization
        self.tasks = set()
        
        # Cache for quick lookups
        self.context_cache = {}
        self.search_results_cache = {}
        
        # File tracking
        self.files = {}  # Map of filename to file info
        
        # Component and module relationships
        self.component_relationships = defaultdict(set)
        
        # Project structure tracking
        self.project_structure = {
            "root": "/workspace",
            "directories": {},
            "files": {}
        }
        
        # Error patterns for recognition
        self.error_patterns = defaultdict(int)
        
        logger.info("Enhanced knowledge graph initialized")
    
    def add_task_context(self, task_id: str, context: Dict[str, Any]):
        """
        Add task context to the knowledge graph.
        
        Args:
            task_id: Unique identifier for the task
            context: Dictionary containing task analysis information
        """
        if task_id not in self.tasks:
            self.tasks.add(task_id)
            self.graph.add_node(task_id, type="task", timestamp=time.time())
        
        # Add context node
        context_id = f"{task_id}_context_{int(time.time())}"
        self.graph.add_node(context_id, type="context", data=context, timestamp=time.time())
        
        # Connect task to context
        self.graph.add_edge(task_id, context_id, type="has_context")
        
        # Extract components and dependencies
        components = context.get("components", [])
        dependencies = context.get("dependencies", [])
        
        # Add components to graph
        for component in components:
            component_id = f"component_{component}_{int(time.time())}"
            self.graph.add_node(component_id, type="component", name=component, timestamp=time.time())
            self.graph.add_edge(context_id, component_id, type="requires")
        
        # Add dependencies to graph
        for dependency in dependencies:
            dependency_id = f"dependency_{dependency}_{int(time.time())}"
            self.graph.add_node(dependency_id, type="dependency", name=dependency, timestamp=time.time())
            self.graph.add_edge(context_id, dependency_id, type="uses")
        
        # Update context cache
        self.context_cache[task_id] = context
        
        # Update project structure based on context
        self._update_project_structure_from_context(context)
        
        logger.info(f"Added task context for task {task_id}")
    
    def _update_project_structure_from_context(self, context: Dict[str, Any]):
        """
        Update project structure based on task context.
        
        Args:
            context: Task context dictionary
        """
        if "architecture" in context:
            # Extract directory structure from architecture description
            architecture = context.get("architecture", "")
            if isinstance(architecture, str):
                # Simple heuristic to extract directory paths
                lines = architecture.split("\n")
                for line in lines:
                    if "/" in line:
                        # Extract potential directory paths
                        parts = line.replace(",", " ").replace(".", " ").split()
                        for part in parts:
                            if part.startswith("/") or part.startswith("./"):
                                self._add_to_project_structure(part)
        
        # Extract potential file paths from other fields
        for path in self._extract_paths_from_context(context):
            self._add_to_project_structure(path)
    
    def _extract_paths_from_context(self, context: Dict[str, Any]) -> List[str]:
        """
        Extract potential file and directory paths from context.
        
        Args:
            context: Task context dictionary
            
        Returns:
            List of potential paths
        """
        paths = []
        
        # Function to recursively extract paths from strings in a dictionary
        def extract_from_dict(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, str):
                        self._extract_paths_from_string(v, paths)
                    elif isinstance(v, (dict, list)):
                        extract_from_dict(v)
            elif isinstance(d, list):
                for item in d:
                    extract_from_dict(item)
        
        extract_from_dict(context)
        return paths
    
    def _extract_paths_from_string(self, text: str, paths: List[str]):
        """
        Extract file and directory paths from a string.
        
        Args:
            text: String to extract paths from
            paths: List to append found paths to
        """
        if not text:
            return
            
        words = text.replace(",", " ").replace(";", " ").split()
        for word in words:
            # Check if it looks like a file path
            if (
                "/" in word 
                and not word.startswith("http") 
                and not word.startswith("www.")
            ):
                # Ignore URLs
                if not any(domain in word for domain in [".com", ".org", ".net", ".io"]):
                    paths.append(word)
            # Check for file extensions
            elif "." in word:
                ext = word.split(".")[-1].lower()
                if ext in ["py", "js", "html", "css", "json", "txt", "md", "jsx", "tsx"]:
                    paths.append(word)
    
    def _add_to_project_structure(self, path: str):
        """
        Add a path to the project structure.
        
        Args:
            path: File or directory path
        """
        if not path:
            return
            
        # Normalize path
        path = path.strip()
        if path.startswith("./"):
            path = path[2:]
        if not path.startswith("/"):
            path = "/" + path
        
        # Determine if it's a file or directory
        is_file = "." in path.split("/")[-1]
        
        if is_file:
            # It's a file
            directory = os.path.dirname(path)
            filename = os.path.basename(path)
            
            # Add directories
            current_dir = ""
            for part in directory.split("/"):
                if not part:
                    continue
                current_dir = os.path.join(current_dir, part)
                self.project_structure["directories"][current_dir] = {
                    "name": part,
                    "path": current_dir,
                    "files": []
                }
            
            # Add file
            if directory not in self.project_structure["directories"]:
                self.project_structure["directories"][directory] = {
                    "name": os.path.basename(directory),
                    "path": directory,
                    "files": []
                }
            
            self.project_structure["files"][path] = {
                "name": filename,
                "path": path,
                "directory": directory
            }
            
            if path not in self.project_structure["directories"][directory]["files"]:
                self.project_structure["directories"][directory]["files"].append(path)
        else:
            # It's a directory
            current_dir = ""
            for part in path.split("/"):
                if not part:
                    continue
                current_dir = os.path.join(current_dir, part)
                self.project_structure["directories"][current_dir] = {
                    "name": part,
                    "path": current_dir,
                    "files": []
                }
    
    def add_error_context(self, task_id: str, error_analysis: Dict[str, Any]):
        """
        Add error analysis to the knowledge graph.
        
        Args:
            task_id: Unique identifier for the task
            error_analysis: Dictionary containing error analysis information
        """
        if task_id not in self.tasks:
            self.tasks.add(task_id)
            self.graph.add_node(task_id, type="task", timestamp=time.time())
        
        # Add error node
        error_id = f"{task_id}_error_{int(time.time())}"
        self.graph.add_node(error_id, type="error", data=error_analysis, timestamp=time.time())
        
        # Connect task to error
        self.graph.add_edge(task_id, error_id, type="encountered_error")
        
        # Extract error type and fixes
        error_type = error_analysis.get("error_type", "Unknown")
        fixes = error_analysis.get("fixes", [])
        
        # Add error type to graph
        error_type_id = f"error_type_{error_type}_{int(time.time())}"
        self.graph.add_node(error_type_id, type="error_type", name=error_type, timestamp=time.time())
        self.graph.add_edge(error_id, error_type_id, type="is_type")
        
        # Add fixes to graph
        for i, fix in enumerate(fixes):
            fix_id = f"{error_id}_fix_{i}_{int(time.time())}"
            self.graph.add_node(fix_id, type="fix", description=fix, timestamp=time.time())
            self.graph.add_edge(error_id, fix_id, type="has_fix")
        
        # Track error patterns for recognition
        self.error_patterns[error_type] += 1
        
        logger.info(f"Added error context for task {task_id}")
    
    def add_search_results(self, task_id: str, search_results: str):
        """
        Add search results to the knowledge graph.
        
        Args:
            task_id: Unique identifier for the task
            search_results: String containing search results
        """
        if task_id not in self.tasks:
            self.tasks.add(task_id)
            self.graph.add_node(task_id, type="task", timestamp=time.time())
        
        # Add search results node
        search_id = f"{task_id}_search_{int(time.time())}"
        self.graph.add_node(search_id, type="search", data=search_results, timestamp=time.time())
        
        # Connect task to search results
        self.graph.add_edge(task_id, search_id, type="has_search_results")
        
        # Update search results cache
        self.search_results_cache[task_id] = search_results
        
        logger.info(f"Added search results for task {task_id}")
    
    def add_code_file(self, task_id: str, filename: str, code: str):
        """
        Add a code file to the knowledge graph with enhanced relationship tracking.
        
        Args:
            task_id: Unique identifier for the task
            filename: Name of the code file
            code: Content of the code file
        """
        if task_id not in self.tasks:
            self.tasks.add(task_id)
            self.graph.add_node(task_id, type="task", timestamp=time.time())
        
        # Add code file node
        file_id = f"{task_id}_file_{filename}_{int(time.time())}"
        self.graph.add_node(file_id, type="file", filename=filename, code=code, timestamp=time.time())
        
        # Connect task to code file
        self.graph.add_edge(task_id, file_id, type="produced")
        
        # Add to files dictionary
        self.files[filename] = {
            "id": file_id,
            "task_id": task_id,
            "code": code,
            "timestamp": time.time(),
            "components": self._extract_components_from_code(code, filename),
            "dependencies": self._extract_dependencies_from_code(code, filename)
        }
        
        # Add file to project structure
        self._add_to_project_structure(filename)
        
        # Update component relationships
        self._update_component_relationships(filename, code)
        
        logger.info(f"Added code file {filename} for task {task_id}")
    
    def _extract_components_from_code(self, code: str, filename: str) -> List[str]:
        """
        Extract components from code.
        
        Args:
            code: Code content
            filename: Name of the file
            
        Returns:
            List of component names
        """
        components = []
        
        # Determine the file type
        ext = os.path.splitext(filename)[1].lower()
        
        # Python files
        if ext == ".py":
            # Extract classes and functions
            lines = code.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("class "):
                    # Extract class name
                    parts = line.split("class ")[1].split("(")[0].split(":")[0].strip()
                    components.append(f"class:{parts}")
                elif line.startswith("def "):
                    # Extract function name
                    parts = line.split("def ")[1].split("(")[0].strip()
                    components.append(f"function:{parts}")
        
        # JavaScript/TypeScript files
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            # Extract classes, functions, and components
            lines = code.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("class "):
                    # Extract class name
                    parts = line.split("class ")[1].split("{")[0].split("extends")[0].strip()
                    components.append(f"class:{parts}")
                elif line.startswith("function "):
                    # Extract function name
                    parts = line.split("function ")[1].split("(")[0].strip()
                    components.append(f"function:{parts}")
                elif "= () =>" in line or "=> {" in line:
                    # Extract arrow function or component
                    if "=" in line:
                        parts = line.split("=")[0].strip()
                        components.append(f"component:{parts}")
        
        return components
    
    def _extract_dependencies_from_code(self, code: str, filename: str) -> List[str]:
        """
        Extract dependencies from code.
        
        Args:
            code: Code content
            filename: Name of the file
            
        Returns:
            List of dependency paths
        """
        dependencies = []
        
        # Determine the file type
        ext = os.path.splitext(filename)[1].lower()
        
        # Python files
        if ext == ".py":
            # Extract imports
            lines = code.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    # Extract import path
                    if line.startswith("import "):
                        parts = line.split("import ")[1].split("#")[0].strip()
                        for part in parts.split(","):
                            dependencies.append(f"import:{part.strip()}")
                    elif line.startswith("from "):
                        module = line.split("from ")[1].split("import")[0].strip()
                        dependencies.append(f"import:{module}")
        
        # JavaScript/TypeScript files
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            # Extract imports
            lines = code.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("import "):
                    # Extract import path
                    if "from " in line:
                        parts = line.split("from ")[1].split(";")[0].strip()
                        # Fix the f-string with backslash issue by using a temporary variable
                        cleaned_parts = parts.replace("'", "").replace('"', "")
                        dependencies.append(f"import:{cleaned_parts}")

        return dependencies
    
    def _update_component_relationships(self, filename: str, code: str):
        """
        Update component relationships based on code.
        
        Args:
            filename: Name of the file
            code: Code content
        """
        components = self._extract_components_from_code(code, filename)
        dependencies = self._extract_dependencies_from_code(code, filename)
        
        # Add file as a component
        file_component = f"file:{filename}"
        
        # Connect file to its components
        for component in components:
            self.component_relationships[file_component].add(component)
            
            # Connect component to its dependencies
            for dependency in dependencies:
                self.component_relationships[component].add(dependency)
    
    def get_context_for_task(self, task: str) -> str:
        """
        Get context information for a task.
        
        Args:
            task: Task description or ID
            
        Returns:
            Formatted context string
        """
        # Try to find task ID from description
        task_id = None
        for t_id in self.tasks:
            if task in t_id or task == t_id:
                task_id = t_id
                break
        
        if not task_id:
            return ""
        
        # Check cache first
        if task_id in self.context_cache:
            context = self.context_cache[task_id]
            return json.dumps(context, indent=2)
        
        # Otherwise, build context from graph
        context_nodes = []
        for _, node_id in self.graph.out_edges(task_id):
            node_data = self.graph.nodes[node_id]
            if node_data.get("type") == "context":
                context_nodes.append(node_data)
        
        if not context_nodes:
            return ""
        
        # Sort by timestamp (newest first)
        context_nodes.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        # Return the newest context
        return json.dumps(context_nodes[0].get("data", {}), indent=2)
    
    def get_search_results(self, task: str) -> str:
        """
        Get search results for a task.
        
        Args:
            task: Task description or ID
            
        Returns:
            Search results string
        """
        # Try to find task ID from description
        task_id = None
        for t_id in self.tasks:
            if task in t_id or task == t_id:
                task_id = t_id
                break
        
        if not task_id:
            return ""
        
        # Check cache first
        if task_id in self.search_results_cache:
            return self.search_results_cache[task_id]
        
        # Otherwise, build from graph
        search_nodes = []
        for _, node_id in self.graph.out_edges(task_id):
            node_data = self.graph.nodes[node_id]
            if node_data.get("type") == "search":
                search_nodes.append(node_data)
        
        if not search_nodes:
            return ""
        
        # Sort by timestamp (newest first)
        search_nodes.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        # Return the newest search results
        return search_nodes[0].get("data", "")
    
    def get_error_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get error history for a task.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            List of error analysis dictionaries
        """
        if task_id not in self.tasks:
            return []
        
        error_nodes = []
        for _, node_id in self.graph.out_edges(task_id):
            node_data = self.graph.nodes[node_id]
            if node_data.get("type") == "error":
                error_nodes.append(node_data)
        
        # Sort by timestamp
        error_nodes.sort(key=lambda x: x.get("timestamp", 0))
        
        # Extract error data
        return [node.get("data", {}) for node in error_nodes]
    
    def get_code_files(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get code files for a task.
        
        Args:
            task_id: Unique identifier for the task
            
        Returns:
            List of code file dictionaries
        """
        if task_id not in self.tasks:
            return []
        
        file_nodes = []
        for _, node_id in self.graph.out_edges(task_id):
            node_data = self.graph.nodes[node_id]
            if node_data.get("type") == "file":
                file_nodes.append(node_data)
        
        # Sort by timestamp (newest first)
        file_nodes.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        # Extract file data
        return [
            {
                "filename": node.get("filename", ""),
                "code": node.get("code", ""),
                "timestamp": node.get("timestamp", 0)
            }
            for node in file_nodes
        ]
    
    def get_component_dependencies(self, component: str) -> List[str]:
        """
        Get dependencies for a component.
        
        Args:
            component: Component identifier
            
        Returns:
            List of dependency identifiers
        """
        return list(self.component_relationships.get(component, set()))
    
    def get_project_structure(self) -> Dict[str, Any]:
        """
        Get the project structure.
        
        Returns:
            Dictionary with project structure
        """
        return self.project_structure
    
    def get_common_error_patterns(self) -> Dict[str, int]:
        """
        Get common error patterns.
        
        Returns:
            Dictionary mapping error types to occurrence counts
        """
        return dict(self.error_patterns)
    
    def get_graph_visualization_data(self) -> Dict[str, Any]:
        """
        Get data for visualizing the knowledge graph.
        
        Returns:
            Dictionary with nodes and edges for visualization
        """
        nodes = []
        for node_id in self.graph.nodes:
            node_data = self.graph.nodes[node_id]
            node_type = node_data.get("type", "unknown")
            
            # Customize label and color based on node type
            if node_type == "task":
                label = f"Task: {node_id}"
                color = "#4caf50"  # Green
            elif node_type == "context":
                label = "Context"
                color = "#2196f3"  # Blue
            elif node_type == "error":
                label = f"Error: {node_data.get('data', {}).get('error_type', 'Unknown')}"
                color = "#f44336"  # Red
            elif node_type == "file":
                label = f"File: {node_data.get('filename', '')}"
                color = "#ff9800"  # Orange
            else:
                label = node_data.get("name", node_id)
                color = "#9c27b0"  # Purple
            
            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": label,
                "timestamp": node_data.get("timestamp", 0),
                "color": color
            })
        
        edges = []
        for source, target in self.graph.edges:
            edge_data = self.graph.edges[source, target]
            edges.append({
                "source": source,
                "target": target,
                "type": edge_data.get("type", "unknown")
            })
        
        # Add component relationships
        for source, targets in self.component_relationships.items():
            for target in targets:
                edges.append({
                    "source": source,
                    "target": target,
                    "type": "depends_on"
                })
                
                # Add nodes if they don't exist yet
                if source not in [node["id"] for node in nodes]:
                    nodes.append({
                        "id": source,
                        "type": "component",
                        "label": source,
                        "timestamp": time.time(),
                        "color": "#673ab7"  # Deep Purple
                    })
                
                if target not in [node["id"] for node in nodes]:
                    nodes.append({
                        "id": target,
                        "type": "dependency",
                        "label": target,
                        "timestamp": time.time(),
                        "color": "#3f51b5"  # Indigo
                    })
        
        return {
            "nodes": nodes,
            "edges": edges
        }
    
    def clear(self):
        """Clear the knowledge graph."""
        self.graph = nx.DiGraph()
        self.tasks = set()
        self.context_cache = {}
        self.search_results_cache = {}
        self.files = {}
        self.component_relationships = defaultdict(set)
        self.project_structure = {
            "root": "/workspace",
            "directories": {},
            "files": {}
        }
        self.error_patterns = defaultdict(int)
        logger.info("Knowledge graph cleared")