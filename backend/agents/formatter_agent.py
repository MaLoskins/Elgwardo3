"""
Formatter Agent module for the AI Agent Terminal Interface.
Specializes in code formatting, style, and quality assurance.
"""

import logging
import asyncio
import json
import os
import re
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

import openai

logger = logging.getLogger(__name__)

class FormatterAgent:
    """
    Specialized agent focused on code formatting and style consistency.
    
    This agent is responsible for:
    - Ensuring consistent code formatting across files
    - Applying language-specific style guides
    - Adding proper documentation and comments
    - Validating file structure and organization
    """
    
    def __init__(
        self,
        openai_api_key: str,
        model: str
    ):
        """
        Initialize the Formatter Agent.
        
        Args:
            openai_api_key: API key for OpenAI
            model: OpenAI model to use
        """
        self.openai_api_key = openai_api_key
        self.model = model
        self.broadcast_function = None
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Style guides for different languages
        self.style_guides = {
            "python": {
                "indentation": 4,
                "max_line_length": 88,
                "quote_type": "double",
                "naming_conventions": {
                    "classes": "PascalCase",
                    "functions": "snake_case",
                    "variables": "snake_case",
                    "constants": "UPPER_SNAKE_CASE"
                }
            },
            "javascript": {
                "indentation": 2,
                "max_line_length": 80,
                "quote_type": "single",
                "naming_conventions": {
                    "classes": "PascalCase",
                    "functions": "camelCase",
                    "variables": "camelCase",
                    "constants": "UPPER_SNAKE_CASE"
                }
            }
        }
        
        logger.info("Formatter Agent initialized")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages."""
        self.broadcast_function = broadcast_function
    
    def set_model(self, model: str):
        """Update the OpenAI model selection."""
        self.model = model
        logger.info(f"Formatter Agent model updated to {model}")
    
    def detect_language(self, filename: str) -> str:
        """
        Detect the programming language based on the file extension.
        
        Args:
            filename: Name of the file
            
        Returns:
            Programming language name
        """
        ext = os.path.splitext(filename)[1].lower()
        
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown"
        }
        
        return language_map.get(ext, "unknown")
    
    def format_command(self, command: str) -> str:
        """
        Format and validate a shell command.
        
        Args:
            command: Shell command to format
            
        Returns:
            Formatted command
        """
        # Remove any code snippets that might be mixed in
        command = self._remove_code_snippets(command)
        
        # Cleanup whitespace and quotes
        command = command.strip()
        
        # Fix common command issues
        if "|" in command:
            # Ensure spaces around pipe
            command = re.sub(r'\|', ' | ', command)
        
        # Ensure && has spaces
        command = re.sub(r'&&', ' && ', command)
        
        # Clean up multiple spaces
        command = re.sub(r'\s+', ' ', command)
        
        return command
    
    def _remove_code_snippets(self, command: str) -> str:
        """
        Remove code snippets that might be mixed in with shell commands.
        
        Args:
            command: Command that might contain code snippets
            
        Returns:
            Cleaned command
        """
        # Common code patterns to filter out
        code_patterns = [
            r'import\s+[\w\s,]+\s+from\s+[\'"][\w\.\/]+[\'"]',  # import statements
            r'const\s+\w+\s*=',  # const declarations
            r'let\s+\w+\s*=',   # let declarations
            r'var\s+\w+\s*=',   # var declarations
            r'function\s+\w+\s*\(',  # function declarations
            r'class\s+\w+',    # class declarations
            r'def\s+\w+\s*\(',  # Python function declarations
        ]
        
        lines = command.split('\n')
        filtered_lines = []
        
        for line in lines:
            is_code = False
            for pattern in code_patterns:
                if re.search(pattern, line):
                    is_code = True
                    break
            
            if not is_code:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    async def format_code(self, code: str, filename: str) -> str:
        """
        Format code according to language-specific style guidelines.
        
        Args:
            code: Code to format
            filename: Name of the file containing the code
            
        Returns:
            Formatted code
        """
        language = self.detect_language(filename)
        style_guide = self.style_guides.get(language, {})
        
        # For very small code snippets, return as is
        if len(code) < 100:
            return code
        
        # For larger code, use LLM to format
        prompt = f"""
        Format this {language} code according to best practices:
        
        ```
        {code}
        ```
        
        Apply these formatting guidelines:
        1. Consistent indentation ({style_guide.get("indentation", 4)} spaces)
        2. Maximum line length of {style_guide.get("max_line_length", 80)} characters
        3. {style_guide.get("quote_type", "double")} quotes for strings
        4. Proper spacing around operators
        5. Consistent naming conventions
        6. Complete and consistent docstrings/comments
        7. Remove unused imports and variables
        8. Organize imports (standard library first, then third-party, then local)
        
        Return ONLY the formatted code, no explanations.
        """
        
        formatted_code = await self._call_openai_api(prompt)
        
        # Extract code if it's in a code block
        formatted_code = self._extract_code_blocks(formatted_code)
        
        await self._broadcast("code_formatted", {
            "filename": filename,
            "language": language,
            "original_length": len(code),
            "formatted_length": len(formatted_code)
        })
        
        return formatted_code
    
    async def verify_formatting(self, workspace_dir: str) -> Dict[str, Any]:
        """
        Verify that all code files in the workspace are properly formatted.
        
        Args:
            workspace_dir: Directory containing code files
            
        Returns:
            Dictionary with verification results
        """
        # Map of file extensions to check
        extensions_to_check = [
            ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json"
        ]
        
        files_to_check = []
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                if any(file.endswith(ext) for ext in extensions_to_check):
                    files_to_check.append(os.path.join(root, file))
        
        if not files_to_check:
            return {
                "verified": True,
                "issues": [],
                "files_to_fix": []
            }
        
        # Check each file
        issues = []
        files_to_fix = []
        
        for file_path in files_to_check:
            filename = os.path.basename(file_path)
            language = self.detect_language(filename)
            
            # Skip unknown languages
            if language == "unknown":
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Very basic formatting checks
                file_issues = []
                
                # Line length check
                max_line_length = self.style_guides.get(language, {}).get("max_line_length", 80)
                long_lines = []
                
                for i, line in enumerate(content.split('\n')):
                    if len(line) > max_line_length:
                        long_lines.append(i + 1)
                
                if long_lines:
                    # Only report up to 5 line numbers
                    reported_lines = long_lines[:5]
                    if len(long_lines) > 5:
                        reported_lines.append(f"... and {len(long_lines) - 5} more")
                    
                    file_issues.append(
                        f"Lines exceeding maximum length ({max_line_length}): {', '.join(map(str, reported_lines))}"
                    )
                
                # Inconsistent indentation check (very basic)
                indentation_sizes = set()
                for line in content.split('\n'):
                    if line.strip() and line.startswith(' '):
                        # Count leading spaces
                        leading_spaces = len(line) - len(line.lstrip(' '))
                        if leading_spaces > 0:
                            indentation_sizes.add(leading_spaces)
                
                if len(indentation_sizes) > 1:
                    file_issues.append(
                        f"Inconsistent indentation: found sizes {', '.join(map(str, indentation_sizes))}"
                    )
                
                # Basic docstring/comment check for Python
                if language == "python" and len(content) > 200:  # Only check substantial files
                    if not content.strip().startswith('"""') and not content.strip().startswith('#'):
                        file_issues.append("Missing module docstring or header comment")
                    
                    # Check functions/classes for docstrings (very basic)
                    function_pattern = r'def\s+\w+\s*\('
                    class_pattern = r'class\s+\w+'
                    
                    for pattern, kind in [(function_pattern, "function"), (class_pattern, "class")]:
                        for match in re.finditer(pattern, content):
                            pos = match.end()
                            next_100_chars = content[pos:pos+100]
                            if '"""' not in next_100_chars and "'''" not in next_100_chars:
                                file_issues.append(f"Missing docstring in a {kind}")
                                break
                
                if file_issues:
                    issues.extend([f"{filename}: {issue}" for issue in file_issues])
                    files_to_fix.append(file_path)
            
            except Exception as e:
                logger.error(f"Error checking formatting for {file_path}: {str(e)}")
        
        return {
            "verified": len(issues) == 0,
            "issues": issues,
            "files_to_fix": files_to_fix
        }
    
    async def _call_openai_api(self, prompt: str) -> str:
        """
        Call the OpenAI API with the given prompt.
        
        Args:
            prompt: Prompt to send to the API
            
        Returns:
            API response text
        """
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert code formatter and style guide specialist. "
                            "You follow language-specific best practices and conventions "
                            "to ensure code is clean, readable, and maintainable."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Very low temperature for consistent formatting
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise
    
    def _extract_code_blocks(self, text: str) -> str:
        """
        Extract code from markdown code blocks.
        
        Args:
            text: Text that may contain code blocks
            
        Returns:
            Extracted code
        """
        if "```" not in text:
            return text.strip()
        
        code_blocks = []
        in_block = False
        current_block = []
        lines = text.split("\n")
        
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    # End of block
                    code_blocks.append("\n".join(current_block))
                    current_block = []
                else:
                    # Start of block, skip the line with ```
                    pass
                in_block = not in_block
                continue
            
            if in_block:
                current_block.append(line)
        
        # Handle case where there's an unclosed code block
        if current_block:
            code_blocks.append("\n".join(current_block))
        
        # If we extracted multiple blocks, join them
        if code_blocks:
            return "\n\n".join(code_blocks)
        
        # If no blocks were found, return the original text
        return text.strip()
    
    async def _broadcast(self, update_type: str, data: Dict[str, Any]):
        """
        Broadcast an update using the broadcast function.
        
        Args:
            update_type: Type of update
            data: Update data
        """
        if self.broadcast_function:
            await self.broadcast_function(update_type, data)
