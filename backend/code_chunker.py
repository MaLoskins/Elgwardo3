"""
Code Chunker module for handling large codebases.
Provides strategies for breaking down large codebases into manageable chunks
for analysis and generation.
"""

import os
import re
import logging
from typing import Dict, Any, List, Tuple, Optional, Set
import ast
import json
import networkx as nx

logger = logging.getLogger(__name__)

class CodeChunker:
    """
    Handles chunking of large codebases into manageable pieces for the LLM.
    
    Strategies include:
    - Semantic chunking based on code structure
    - Import-based dependency tracking
    - Progressive code loading with overlapping content
    - Summary caching for large files
    - Directory-based organization for multi-file projects
    """
    
    def __init__(self, max_chunk_size: int = 8000, overlap_size: int = 500):
        """
        Initialize the Code Chunker.
        
        Args:
            max_chunk_size: Maximum token size for a code chunk
            overlap_size: Size of overlap between chunks
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        
        # Cache for file summaries
        self.file_summaries = {}
        
        # File dependency graph
        self.dependency_graph = nx.DiGraph()
        
        logger.info(f"Code Chunker initialized with max chunk size: {max_chunk_size}, overlap: {overlap_size}")
    
    def chunk_file(self, file_path: str, file_content: str = None) -> List[Dict[str, Any]]:
        """
        Chunk a file into manageable pieces.
        
        Args:
            file_path: Path to the file
            file_content: Content of the file, or None to read from file_path
            
        Returns:
            List of chunk dictionaries with metadata
        """
        # If content is not provided, read it from the file
        if file_content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {str(e)}")
                return []
        
        # Determine the appropriate chunking strategy based on file type
        ext = os.path.splitext(file_path)[1].lower()
        
        # Python files get special treatment with AST parsing
        if ext == '.py':
            return self._chunk_python_file(file_path, file_content)
        
        # JavaScript/TypeScript files get semantic chunking
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            return self._chunk_javascript_file(file_path, file_content)
        
        # Other files get simple line-based chunking
        else:
            return self._chunk_by_lines(file_path, file_content)
    
    def chunk_directory(self, dir_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Chunk all files in a directory.
        
        Args:
            dir_path: Path to the directory
            
        Returns:
            Dictionary mapping file paths to chunk lists
        """
        result = {}
        
        # Walk through the directory
        for root, _, files in os.walk(dir_path):
            for file in files:
                # Skip binary files and hidden files
                if file.startswith('.'):
                    continue
                
                # Skip files with unknown extensions
                ext = os.path.splitext(file)[1].lower()
                if ext not in ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.json', '.md', '.txt']:
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    # Chunk the file
                    chunks = self.chunk_file(file_path, file_content)
                    if chunks:
                        result[file_path] = chunks
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {str(e)}")
        
        # After all files are processed, update the dependency graph
        self._update_dependency_graph(result)
        
        return result
    
    def get_relevant_chunks_for_task(
        self,
        task_description: str,
        chunked_files: Dict[str, List[Dict[str, Any]]],
        max_chunks: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get the most relevant chunks for a specific task.
        
        Args:
            task_description: Description of the task
            chunked_files: Dictionary of chunked files
            max_chunks: Maximum number of chunks to return
            
        Returns:
            List of the most relevant chunks
        """
        all_chunks = []
        for file_path, chunks in chunked_files.items():
            all_chunks.extend(chunks)
        
        # Sort chunks by relevance to the task
        # For now, use a simple keyword-based approach
        keywords = self._extract_keywords(task_description)
        
        # Score chunks based on keyword matches
        scored_chunks = []
        for chunk in all_chunks:
            score = self._compute_relevance_score(chunk, keywords)
            scored_chunks.append((score, chunk))
        
        # Sort by score (highest first)
        scored_chunks.sort(reverse=True, key=lambda x: x[0])
        
        # Take the top N chunks
        top_chunks = [chunk for _, chunk in scored_chunks[:max_chunks]]
        
        return top_chunks
    
    def generate_file_summary(self, file_path: str, file_content: str = None) -> Dict[str, Any]:
        """
        Generate a summary of a file for quick reference.
        
        Args:
            file_path: Path to the file
            file_content: Content of the file, or None to read from file_path
            
        Returns:
            Dictionary with file summary information
        """
        # Check cache first
        if file_path in self.file_summaries:
            return self.file_summaries[file_path]
        
        # If content is not provided, read it from the file
        if file_content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {str(e)}")
                return {}
        
        # Determine file type
        ext = os.path.splitext(file_path)[1].lower()
        
        summary = {
            "file_path": file_path,
            "file_type": ext[1:] if ext else "unknown",
            "line_count": file_content.count('\n') + 1,
            "size_bytes": len(file_content),
            "components": [],
            "imports": [],
            "exports": []
        }
        
        # Extract components based on file type
        if ext == '.py':
            summary.update(self._summarize_python_file(file_content))
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            summary.update(self._summarize_javascript_file(file_content))
        
        # Cache the summary
        self.file_summaries[file_path] = summary
        
        return summary
    
    def get_file_dependencies(self, file_path: str) -> List[str]:
        """
        Get dependencies of a file based on the dependency graph.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of file paths that this file depends on
        """
        # Ensure file exists in the graph
        if file_path not in self.dependency_graph:
            return []
        
        # Get direct dependencies (files this file imports)
        dependencies = []
        for _, dep_file in self.dependency_graph.out_edges(file_path):
            dependencies.append(dep_file)
        
        return dependencies
    
    def get_dependent_files(self, file_path: str) -> List[str]:
        """
        Get files that depend on this file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of file paths that depend on this file
        """
        # Ensure file exists in the graph
        if file_path not in self.dependency_graph:
            return []
        
        # Get files that import this file
        dependents = []
        for dep_file, _ in self.dependency_graph.in_edges(file_path):
            dependents.append(dep_file)
        
        return dependents
    
    def get_import_graph(self) -> nx.DiGraph:
        """
        Get the file dependency graph.
        
        Returns:
            NetworkX DiGraph of file dependencies
        """
        return self.dependency_graph
    
    def _chunk_python_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """
        Chunk a Python file using AST parsing for semantic chunks.
        
        Args:
            file_path: Path to the file
            content: Content of the file
            
        Returns:
            List of chunks with metadata
        """
        try:
            # Parse the Python code
            tree = ast.parse(content)
            
            # Extract imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            
            # Find all classes and functions
            classes = []
            functions = []
            
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": self._find_end_line(node, content),
                        "docstring": ast.get_docstring(node) or ""
                    })
                elif isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": self._find_end_line(node, content),
                        "docstring": ast.get_docstring(node) or ""
                    })
            
            # Create chunks based on semantic structure
            chunks = []
            
            # Always include imports and file-level docstring in the first chunk
            file_docstring = ast.get_docstring(tree) or ""
            header_lines = []
            if file_docstring:
                # Find the end of the docstring
                lines = content.split('\n')
                in_docstring = False
                docstring_end = 0
                
                for i, line in enumerate(lines):
                    if '"""' in line or "'''" in line:
                        if not in_docstring:
                            in_docstring = True
                        else:
                            in_docstring = False
                            docstring_end = i
                            break
                
                header_lines = lines[:docstring_end + 1]
            
            # Get the import lines
            import_lines = []
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if re.match(r'^(import|from)\s+', line):
                    import_lines.append(line)
            
            # Combine header and imports
            header_content = '\n'.join(header_lines + import_lines)
            
            # Create a chunk for the header
            if header_content:
                chunks.append({
                    "file_path": file_path,
                    "chunk_type": "header",
                    "content": header_content,
                    "imports": imports,
                    "line_start": 1,
                    "line_end": len(header_lines) + len(import_lines),
                    "chunk_id": f"{file_path}#header"
                })
            
            # Create chunks for each class
            for cls in classes:
                class_lines = content.split('\n')[cls['line_start'] - 1:cls['line_end']]
                class_content = '\n'.join(class_lines)
                
                chunks.append({
                    "file_path": file_path,
                    "chunk_type": "class",
                    "content": class_content,
                    "name": cls['name'],
                    "docstring": cls['docstring'],
                    "line_start": cls['line_start'],
                    "line_end": cls['line_end'],
                    "chunk_id": f"{file_path}#{cls['name']}"
                })
            
            # Create chunks for top-level functions
            for func in functions:
                func_lines = content.split('\n')[func['line_start'] - 1:func['line_end']]
                func_content = '\n'.join(func_lines)
                
                chunks.append({
                    "file_path": file_path,
                    "chunk_type": "function",
                    "content": func_content,
                    "name": func['name'],
                    "docstring": func['docstring'],
                    "line_start": func['line_start'],
                    "line_end": func['line_end'],
                    "chunk_id": f"{file_path}#{func['name']}"
                })
            
            # Check if we have remaining code not in any chunk
            if chunks:
                covered_lines = set()
                for chunk in chunks:
                    covered_lines.update(range(chunk['line_start'], chunk['line_end'] + 1))
                
                # Find uncovered sections
                lines = content.split('\n')
                uncovered_sections = []
                current_section = []
                current_start = None
                
                for i, line in enumerate(lines, 1):
                    if i not in covered_lines and line.strip():
                        if current_start is None:
                            current_start = i
                        current_section.append(line)
                    elif current_section:
                        uncovered_sections.append({
                            "content": '\n'.join(current_section),
                            "line_start": current_start,
                            "line_end": i - 1
                        })
                        current_section = []
                        current_start = None
                
                # Add any final section
                if current_section:
                    uncovered_sections.append({
                        "content": '\n'.join(current_section),
                        "line_start": current_start,
                        "line_end": len(lines)
                    })
                
                # Add chunks for uncovered sections
                for i, section in enumerate(uncovered_sections):
                    chunks.append({
                        "file_path": file_path,
                        "chunk_type": "other",
                        "content": section['content'],
                        "line_start": section['line_start'],
                        "line_end": section['line_end'],
                        "chunk_id": f"{file_path}#section{i}"
                    })
            
            # If no chunks were created, fall back to line-based chunking
            if not chunks:
                return self._chunk_by_lines(file_path, content)
            
            # Sort chunks by line number
            chunks.sort(key=lambda x: x['line_start'])
            
            return chunks
            
        except SyntaxError:
            # If we can't parse the Python code, fall back to line-based chunking
            logger.warning(f"Syntax error in Python file {file_path}, falling back to line-based chunking")
            return self._chunk_by_lines(file_path, content)
        except Exception as e:
            logger.error(f"Error chunking Python file {file_path}: {str(e)}")
            return self._chunk_by_lines(file_path, content)
    
    def _find_end_line(self, node, content: str) -> int:
        """
        Find the end line of a node in the AST.
        
        Args:
            node: AST node
            content: File content
            
        Returns:
            End line number
        """
        try:
            return node.end_lineno
        except AttributeError:
            # For older Python versions without end_lineno
            try:
                # Count matching indentation to find the end
                lines = content.split('\n')
                start_line = node.lineno - 1  # 0-indexed
                if start_line >= len(lines):
                    return start_line + 1
                
                # Get indentation of the node
                start_line_content = lines[start_line]
                indent = len(start_line_content) - len(start_line_content.lstrip())
                
                # Find the first line with same or less indentation
                for i in range(start_line + 1, len(lines)):
                    line = lines[i]
                    if line.strip() and len(line) - len(line.lstrip()) <= indent:
                        return i
                
                # If we reach the end of the file
                return len(lines)
            except Exception:
                # Fallback: just return the start line
                return node.lineno
    
    def _chunk_javascript_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """
        Chunk a JavaScript/TypeScript file semantically.
        
        Args:
            file_path: Path to the file
            content: Content of the file
            
        Returns:
            List of chunks with metadata
        """
        # Use regex patterns to find semantic structures
        imports = []
        
        # Find import statements
        import_pattern = r'^import\s+.*?[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            imports.append(match.group(1))
        
        # Find require statements
        require_pattern = r'require\([\'"]([^\'"]+)[\'"]\)'
        for match in re.finditer(require_pattern, content):
            imports.append(match.group(1))
        
        # Find class declarations
        classes = []
        class_pattern = r'(class\s+(\w+)(?:\s+extends\s+\w+)?\s*{)'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            
            # Find the closing brace for this class
            open_braces = 0
            end_pos = start_pos
            
            for i in range(start_pos, len(content)):
                if content[i] == '{':
                    open_braces += 1
                elif content[i] == '}':
                    open_braces -= 1
                    if open_braces == 0:
                        end_pos = i
                        break
            
            end_line = content[:end_pos].count('\n') + 1
            
            classes.append({
                "name": match.group(2),
                "line_start": start_line,
                "line_end": end_line
            })
        
        # Find function declarations
        functions = []
        function_patterns = [
            r'(function\s+(\w+)\s*\([^)]*\)\s*{)',  # Regular functions
            r'(const\s+(\w+)\s*=\s*function\s*\([^)]*\)\s*{)',  # Function expressions
            r'(const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{)',  # Arrow functions with block
            r'(export\s+function\s+(\w+)\s*\([^)]*\)\s*{)'  # Exported functions
        ]
        
        for pattern in function_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                start_pos = match.start()
                start_line = content[:start_pos].count('\n') + 1
                
                # Find the closing brace for this function
                if '=>' in match.group(1) and '{' not in match.group(1):
                    # Arrow function without block - find the end of the line
                    end_pos = content.find('\n', start_pos)
                    if end_pos == -1:
                        end_pos = len(content)
                else:
                    # Function with block - find the closing brace
                    open_braces = 0
                    end_pos = start_pos
                    
                    for i in range(start_pos, len(content)):
                        if content[i] == '{':
                            open_braces += 1
                        elif content[i] == '}':
                            open_braces -= 1
                            if open_braces == 0:
                                end_pos = i
                                break
                
                end_line = content[:end_pos].count('\n') + 1
                
                functions.append({
                    "name": match.group(2),
                    "line_start": start_line,
                    "line_end": end_line
                })
        
        # Create chunks based on semantic structure
        chunks = []
        
        # First chunk: imports and top-level variables
        top_level_end = 0
        
        if classes or functions:
            first_declaration = min(
                [c["line_start"] for c in classes] if classes else [float('inf')],
                [f["line_start"] for f in functions] if functions else [float('inf')]
            )
            top_level_end = first_declaration - 1
        else:
            top_level_end = content.count('\n') + 1
        
        if top_level_end > 0:
            top_level_lines = content.split('\n')[:top_level_end]
            top_level_content = '\n'.join(top_level_lines)
            
            chunks.append({
                "file_path": file_path,
                "chunk_type": "imports_and_declarations",
                "content": top_level_content,
                "imports": imports,
                "line_start": 1,
                "line_end": top_level_end,
                "chunk_id": f"{file_path}#top"
            })
        
        # Chunks for classes
        for cls in classes:
            class_lines = content.split('\n')[cls['line_start'] - 1:cls['line_end']]
            class_content = '\n'.join(class_lines)
            
            chunks.append({
                "file_path": file_path,
                "chunk_type": "class",
                "content": class_content,
                "name": cls['name'],
                "line_start": cls['line_start'],
                "line_end": cls['line_end'],
                "chunk_id": f"{file_path}#{cls['name']}"
            })
        
        # Chunks for functions
        for func in functions:
            # Skip functions that are inside classes (to avoid duplication)
            inside_class = False
            for cls in classes:
                if cls['line_start'] <= func['line_start'] and func['line_end'] <= cls['line_end']:
                    inside_class = True
                    break
            
            if inside_class:
                continue
            
            func_lines = content.split('\n')[func['line_start'] - 1:func['line_end']]
            func_content = '\n'.join(func_lines)
            
            chunks.append({
                "file_path": file_path,
                "chunk_type": "function",
                "content": func_content,
                "name": func['name'],
                "line_start": func['line_start'],
                "line_end": func['line_end'],
                "chunk_id": f"{file_path}#{func['name']}"
            })
        
        # Check for remaining code
        if chunks:
            covered_lines = set()
            for chunk in chunks:
                covered_lines.update(range(chunk['line_start'], chunk['line_end'] + 1))
            
            # Find uncovered sections
            lines = content.split('\n')
            uncovered_sections = []
            current_section = []
            current_start = None
            
            for i, line in enumerate(lines, 1):
                if i not in covered_lines and line.strip():
                    if current_start is None:
                        current_start = i
                    current_section.append(line)
                elif current_section:
                    uncovered_sections.append({
                        "content": '\n'.join(current_section),
                        "line_start": current_start,
                        "line_end": i - 1
                    })
                    current_section = []
                    current_start = None
            
            # Add any final section
            if current_section:
                uncovered_sections.append({
                    "content": '\n'.join(current_section),
                    "line_start": current_start,
                    "line_end": len(lines)
                })
            
            # Add chunks for uncovered sections
            for i, section in enumerate(uncovered_sections):
                chunks.append({
                    "file_path": file_path,
                    "chunk_type": "other",
                    "content": section['content'],
                    "line_start": section['line_start'],
                    "line_end": section['line_end'],
                    "chunk_id": f"{file_path}#section{i}"
                })
        
        # If no chunks were created, fall back to line-based chunking
        if not chunks:
            return self._chunk_by_lines(file_path, content)
        
        # Sort chunks by line number
        chunks.sort(key=lambda x: x['line_start'])
        
        return chunks
    
    def _chunk_by_lines(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """
        Chunk a file by lines, respecting logical breaks.
        
        Args:
            file_path: Path to the file
            content: Content of the file
            
        Returns:
            List of chunks with metadata
        """
        # Split content into lines
        lines = content.split('\n')
        
        # Estimate tokens (rough approximation)
        est_tokens = len(content) // 4
        
        # If file is small enough, return as single chunk
        if est_tokens <= self.max_chunk_size:
            return [{
                "file_path": file_path,
                "chunk_type": "full_file",
                "content": content,
                "line_start": 1,
                "line_end": len(lines),
                "chunk_id": f"{file_path}#full"
            }]
        
        # Otherwise, chunk by logical breaks
        chunks = []
        current_chunk_lines = []
        current_chunk_start = 1
        current_chunk_tokens = 0
        
        for i, line in enumerate(lines, 1):
            # Estimate tokens in this line
            line_tokens = len(line) // 4
            
            # If adding this line would exceed the limit, create a chunk
            if current_chunk_lines and current_chunk_tokens + line_tokens > self.max_chunk_size:
                chunk_content = '\n'.join(current_chunk_lines)
                chunks.append({
                    "file_path": file_path,
                    "chunk_type": "partial",
                    "content": chunk_content,
                    "line_start": current_chunk_start,
                    "line_end": i - 1,
                    "chunk_id": f"{file_path}#lines{current_chunk_start}-{i-1}"
                })
                
                # Start a new chunk with overlap
                overlap_start = max(1, i - self.overlap_size // (len(lines[i-1]) // 4 + 1))
                current_chunk_lines = lines[overlap_start-1:i-1]
                current_chunk_start = overlap_start
                current_chunk_tokens = sum(len(l) // 4 for l in current_chunk_lines)
            
            # Add the current line to the chunk
            current_chunk_lines.append(line)
            current_chunk_tokens += line_tokens
        
        # Add the final chunk if not empty
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines)
            chunks.append({
                "file_path": file_path,
                "chunk_type": "partial",
                "content": chunk_content,
                "line_start": current_chunk_start,
                "line_end": len(lines),
                "chunk_id": f"{file_path}#lines{current_chunk_start}-{len(lines)}"
            })
        
        return chunks
    
    def _summarize_python_file(self, content: str) -> Dict[str, Any]:
        """
        Summarize a Python file.
        
        Args:
            content: Content of the file
            
        Returns:
            Dictionary with summary information
        """
        summary = {
            "imports": [],
            "classes": [],
            "functions": [],
            "global_variables": []
        }
        
        try:
            # Parse the Python code
            tree = ast.parse(content)
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        summary["imports"].append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        summary["imports"].append(f"{node.module}.{node.names[0].name}")
            
            # Extract classes and functions
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    
                    summary["classes"].append({
                        "name": node.name,
                        "methods": methods,
                        "docstring": ast.get_docstring(node) or ""
                    })
                elif isinstance(node, ast.FunctionDef):
                    summary["functions"].append({
                        "name": node.name,
                        "docstring": ast.get_docstring(node) or ""
                    })
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            summary["global_variables"].append(target.id)
            
            # Add file-level docstring
            summary["docstring"] = ast.get_docstring(tree) or ""
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing Python file: {str(e)}")
            return summary
    
    def _summarize_javascript_file(self, content: str) -> Dict[str, Any]:
        """
        Summarize a JavaScript/TypeScript file.
        
        Args:
            content: Content of the file
            
        Returns:
            Dictionary with summary information
        """
        summary = {
            "imports": [],
            "exports": [],
            "classes": [],
            "functions": [],
            "components": []
        }
        
        # Find import statements
        import_pattern = r'^import\s+.*?[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            summary["imports"].append(match.group(1))
        
        # Find require statements
        require_pattern = r'require\([\'"]([^\'"]+)[\'"]\)'
        for match in re.finditer(require_pattern, content):
            summary["imports"].append(match.group(1))
        
        # Find export statements
        export_pattern = r'export\s+(default\s+)?(\w+)'
        for match in re.finditer(export_pattern, content, re.MULTILINE):
            summary["exports"].append(match.group(2))
        
        # Find class declarations
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            class_name = match.group(1)
            extends = match.group(2)
            
            class_info = {"name": class_name}
            if extends:
                class_info["extends"] = extends
            
            summary["classes"].append(class_info)
        
        # Find React components
        component_patterns = [
            r'function\s+(\w+)\s*\([^)]*\)\s*{[^}]*return\s*\(',  # Function components
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{[^}]*return\s*\(',  # Arrow function components
            r'class\s+(\w+)\s+extends\s+(React\.Component|Component)'  # Class components
        ]
        
        for pattern in component_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                summary["components"].append(match.group(1))
        
        # Find function declarations
        function_patterns = [
            r'function\s+(\w+)\s*\([^)]*\)',
            r'const\s+(\w+)\s*=\s*function\s*\([^)]*\)',
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>'
        ]
        
        for pattern in function_patterns:
            for match in re.finditer(pattern, content, re.MULTILINE):
                function_name = match.group(1)
                
                # Skip if already identified as a component
                if function_name not in summary["components"]:
                    summary["functions"].append(function_name)
        
        return summary
    
    def _update_dependency_graph(self, chunked_files: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Update the dependency graph based on imports in chunked files.
        
        Args:
            chunked_files: Dictionary of chunked files
        """
        # Clear existing graph
        self.dependency_graph = nx.DiGraph()
        
        # Create a mapping of module names to file paths
        module_to_file = {}
        
        # First, add all files to the graph and map modules to files
        for file_path, chunks in chunked_files.items():
            self.dependency_graph.add_node(file_path)
            
            # Get the summary of the file
            summary = self.generate_file_summary(file_path)
            
            # Map module names based on file type
            filename = os.path.basename(file_path)
            module_name = os.path.splitext(filename)[0]
            
            module_to_file[module_name] = file_path
            
            # For Python files, also map the directory structure
            if file_path.endswith('.py'):
                # Get the full module path for Python files
                dir_path = os.path.dirname(file_path)
                parts = []
                
                while dir_path:
                    dirname = os.path.basename(dir_path)
                    if dirname and dirname not in ['.', '..']:
                        parts.insert(0, dirname)
                    dir_path = os.path.dirname(dir_path)
                
                if parts:
                    full_module = '.'.join(parts + [module_name])
                    module_to_file[full_module] = file_path
        
        # Then, process imports to add edges
        for file_path, chunks in chunked_files.items():
            # Get all imports from the chunks
            imports = set()
            for chunk in chunks:
                if 'imports' in chunk:
                    imports.update(chunk['imports'])
            
            # Add edges for each import
            for imp in imports:
                # Handle relative imports
                if imp.startswith('.'):
                    dir_path = os.path.dirname(file_path)
                    rel_path = imp.lstrip('.')
                    if rel_path:
                        rel_parts = rel_path.split('.')
                    else:
                        rel_parts = []
                    
                    # For each level of '.', go up one directory
                    dots = len(imp) - len(rel_path)
                    for _ in range(dots - 1):
                        dir_path = os.path.dirname(dir_path)
                    
                    # Combine directory path with relative path
                    target_path = dir_path
                    for part in rel_parts:
                        target_path = os.path.join(target_path, part)
                    
                    # Look for files with this path
                    potential_targets = [
                        f for f in chunked_files.keys()
                        if f.startswith(target_path)
                    ]
                    
                    for target in potential_targets:
                        self.dependency_graph.add_edge(file_path, target)
                
                # Handle absolute imports
                elif imp in module_to_file:
                    target_file = module_to_file[imp]
                    self.dependency_graph.add_edge(file_path, target_file)
                
                # Handle package imports (only first component)
                else:
                    package = imp.split('.')[0]
                    if package in module_to_file:
                        target_file = module_to_file[package]
                        self.dependency_graph.add_edge(file_path, target_file)
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from text.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            Set of keywords
        """
        # Convert to lowercase and split by non-alphanumeric characters
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Remove stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'if', 'because', 'as', 'what',
            'when', 'where', 'how', 'which', 'who', 'whom', 'this', 'that', 'these',
            'those', 'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about',
            'for', 'is', 'of', 'while', 'during', 'to', 'from'
        }
        
        return {word for word in words if word not in stopwords and len(word) > 2}
    
    def _compute_relevance_score(self, chunk: Dict[str, Any], keywords: Set[str]) -> float:
        """
        Compute the relevance score of a chunk for a set of keywords.
        
        Args:
            chunk: Chunk to score
            keywords: Keywords to match
            
        Returns:
            Relevance score
        """
        # Convert chunk content to lowercase
        content = chunk.get('content', '').lower()
        
        # Count keyword occurrences
        keyword_count = sum(1 for keyword in keywords if keyword in content)
        
        # Basic TF-IDF-like scoring
        score = keyword_count / (len(content.split()) + 1)
        
        # Bonus for chunks with important types
        if chunk.get('chunk_type') == 'header':
            score *= 1.5
        elif chunk.get('chunk_type') in ['class', 'function']:
            score *= 1.2
        
        return score
