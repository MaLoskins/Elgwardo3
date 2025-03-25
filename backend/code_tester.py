"""
Code Testing module for the AI Agent Terminal Interface.
Provides functionality for generating and running tests for different code types.
"""

import os
import logging
import asyncio
import time
import re
import importlib.util
import sys
import json
from typing import Dict, Any, List, Optional, Tuple, Union, Set
import tempfile

logger = logging.getLogger(__name__)

class CodeTester:
    """
    Testing module for validating generated code.
    
    Supports:
    - Python unit tests generation
    - JavaScript/React component testing
    - Integration tests for multi-file projects
    - End-to-end functionality validation
    """
    
    def __init__(self, terminal_manager):
        """
        Initialize the Code Tester.
        
        Args:
            terminal_manager: Reference to the TerminalManager instance
        """
        self.terminal_manager = terminal_manager
        
        # Testing frameworks by language
        self.test_frameworks = {
            'python': {
                'framework': 'pytest',
                'file_pattern': 'test_*.py',
                'command': 'python -m pytest'
            },
            'javascript': {
                'framework': 'jest',
                'file_pattern': '*.test.js',
                'command': 'npx jest'
            },
            'typescript': {
                'framework': 'jest',
                'file_pattern': '*.test.ts',
                'command': 'npx jest'
            }
        }
        
        logger.info("Code Tester initialized")
    
    async def generate_tests(
        self, 
        file_path: str, 
        code_content: str = None,
        language: str = None,
        test_description: str = None,
        openai_client = None,
        model: str = "gpt-4o"
    ) -> Tuple[str, str]:
        """
        Generate tests for a code file.
        
        Args:
            file_path: Path to the code file
            code_content: Content of the code file (if None, read from file_path)
            language: Programming language (if None, detect from file extension)
            test_description: Description of the tests to generate
            openai_client: OpenAI client for generating tests
            model: Model to use for test generation
            
        Returns:
            Tuple of (test file path, test content)
        """
        # If code content is not provided, read it from the file
        if code_content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code_content = f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {str(e)}")
                return None, f"Error reading file: {str(e)}"
        
        # If language is not provided, detect from file extension
        if language is None:
            language = self._detect_language(file_path)
        
        # Get test file path
        test_file_path = self._get_test_file_path(file_path, language)
        
        # Check if OpenAI client is available
        if openai_client is None:
            logger.error("OpenAI client not provided for test generation")
            return test_file_path, self._generate_basic_tests(file_path, code_content, language)
        
        # Generate tests using LLM
        logger.info(f"Generating tests for {file_path} using {model}")
        
        prompt = self._create_test_generation_prompt(file_path, code_content, language, test_description)
        
        try:
            # Call OpenAI API to generate tests
            response = openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert test engineer who specializes in writing thorough, "
                            "effective tests for software applications. You write tests that check "
                            "both typical usage patterns and edge cases."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            test_content = response.choices[0].message.content
            
            # Extract code from markdown if present
            test_content = self._extract_code_blocks(test_content)
            
            # Write tests to file
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            logger.info(f"Tests written to {test_file_path}")
            return test_file_path, test_content
            
        except Exception as e:
            logger.error(f"Error generating tests: {str(e)}")
            return test_file_path, self._generate_basic_tests(file_path, code_content, language)
    
    async def run_tests(
        self, 
        test_dir: str, 
        language: str = 'python', 
        specific_file: str = None,
        working_dir: str = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Run tests for a specific language.
        
        Args:
            test_dir: Directory containing the tests
            language: Programming language
            specific_file: Specific test file to run (if None, run all tests)
            working_dir: Working directory for test execution
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with test results
        """
        # Get the appropriate test command
        framework_info = self.test_frameworks.get(language, self.test_frameworks['python'])
        test_command = framework_info['command']
        
        # If a specific file is provided, modify the command
        if specific_file:
            if language == 'python':
                test_command += f" {specific_file}"
            elif language in ['javascript', 'typescript']:
                test_command += f" -- {specific_file}"
        
        # Run the tests
        logger.info(f"Running {language} tests in {test_dir} with command: {test_command}")
        
        try:
            working_directory = working_dir or test_dir
            
            # Run any setup commands needed
            await self._run_test_setup(language, working_directory)
            
            # Run the tests
            success, output = await self.terminal_manager.execute_command(
                test_command,
                timeout=timeout,
                working_dir=working_directory
            )
            
            # Parse the test results
            test_results = self._parse_test_results(output, language)
            test_results['success'] = success
            test_results['raw_output'] = output
            
            return test_results
            
        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'tests_run': 0,
                'tests_passed': 0,
                'tests_failed': 0,
                'raw_output': str(e)
            }
    
    async def run_python_tests_in_memory(self, test_content: str, code_content: str, module_name: str) -> Dict[str, Any]:
        """
        Run Python tests in memory without writing to files.
        
        Args:
            test_content: Test code content
            code_content: Source code content
            module_name: Name of the module being tested
            
        Returns:
            Dictionary with test results
        """
        try:
            # Create temporary directory for testing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write code and test files to temporary directory
                code_path = os.path.join(temp_dir, f"{module_name}.py")
                test_path = os.path.join(temp_dir, f"test_{module_name}.py")
                
                with open(code_path, 'w', encoding='utf-8') as f:
                    f.write(code_content)
                
                with open(test_path, 'w', encoding='utf-8') as f:
                    f.write(test_content)
                
                # Run tests in the temporary directory
                return await self.run_tests(temp_dir, 'python', specific_file=test_path)
                
        except Exception as e:
            logger.error(f"Error running Python tests in memory: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'tests_run': 0,
                'tests_passed': 0,
                'tests_failed': 0,
                'raw_output': str(e)
            }
    
    async def validate_project(self, project_dir: str) -> Dict[str, Any]:
        """
        Validate a project by running all tests.
        
        Args:
            project_dir: Path to the project directory
            
        Returns:
            Dictionary with validation results
        """
        results = {
            'success': True,
            'errors': [],
            'test_results': {},
            'files_tested': 0,
            'total_tests': 0,
            'passing_tests': 0,
            'failing_tests': 0
        }
        
        try:
            # Detect project type and languages
            project_info = self._analyze_project(project_dir)
            
            # Run tests for each language detected
            for language, files in project_info['files_by_language'].items():
                if language in self.test_frameworks:
                    # Generate tests for all implementation files if needed
                    implementation_files = [f for f in files if not self._is_test_file(f, language)]
                    
                    for impl_file in implementation_files:
                        test_file = self._get_test_file_path(impl_file, language)
                        
                        # Check if test file exists, generate if not
                        if not os.path.exists(test_file):
                            await self.generate_tests(impl_file, language=language)
                            results['files_tested'] += 1
                    
                    # Run all tests for this language
                    test_results = await self.run_tests(project_dir, language)
                    results['test_results'][language] = test_results
                    
                    # Aggregate results
                    results['total_tests'] += test_results.get('tests_run', 0)
                    results['passing_tests'] += test_results.get('tests_passed', 0)
                    results['failing_tests'] += test_results.get('tests_failed', 0)
                    
                    if not test_results.get('success', False):
                        results['success'] = False
                        results['errors'].append(f"Tests for {language} failed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating project: {str(e)}")
            return {
                'success': False,
                'errors': [str(e)],
                'test_results': {},
                'files_tested': 0,
                'total_tests': 0,
                'passing_tests': 0,
                'failing_tests': 0
            }
    
    def _detect_language(self, file_path: str) -> str:
        """
        Detect the programming language of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Detected language
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.py':
            return 'python'
        elif ext in ['.js', '.jsx']:
            return 'javascript'
        elif ext in ['.ts', '.tsx']:
            return 'typescript'
        else:
            return 'unknown'
    
    def _get_test_file_path(self, file_path: str, language: str) -> str:
        """
        Get the path for the test file.
        
        Args:
            file_path: Path to the implementation file
            language: Programming language
            
        Returns:
            Path for the test file
        """
        directory = os.path.dirname(file_path)
        filename = os.path.basename(file_path)
        name, ext = os.path.splitext(filename)
        
        if language == 'python':
            return os.path.join(directory, f"test_{name}.py")
        elif language in ['javascript', 'typescript']:
            return os.path.join(directory, f"{name}.test{ext}")
        else:
            return os.path.join(directory, f"test_{filename}")
    
    def _is_test_file(self, file_path: str, language: str) -> bool:
        """
        Check if a file is a test file.
        
        Args:
            file_path: Path to the file
            language: Programming language
            
        Returns:
            True if the file is a test file, False otherwise
        """
        filename = os.path.basename(file_path)
        
        if language == 'python':
            return filename.startswith('test_')
        elif language in ['javascript', 'typescript']:
            return '.test.' in filename or '.spec.' in filename
        else:
            return False
    
    def _create_test_generation_prompt(
        self, 
        file_path: str, 
        code_content: str, 
        language: str, 
        test_description: str = None
    ) -> str:
        """
        Create a prompt for test generation.
        
        Args:
            file_path: Path to the implementation file
            code_content: Content of the implementation file
            language: Programming language
            test_description: Description of the tests to generate
            
        Returns:
            Prompt for test generation
        """
        prompt = f"""
        I need you to generate comprehensive tests for this {language} code:
        
        ```{language}
        {code_content}
        ```
        
        File name: {os.path.basename(file_path)}
        """
        
        if test_description:
            prompt += f"\nTest requirements: {test_description}\n"
        
        # Language-specific instructions
        if language == 'python':
            prompt += """
            Write comprehensive pytest tests that:
            1. Test both normal operations and edge cases
            2. Include appropriate fixtures
            3. Use pytest asserts (not unittest)
            4. Have descriptive test names and docstrings
            5. Include test coverage for all functions/methods
            
            Return only the test code without explanations.
            """
        elif language == 'javascript':
            prompt += """
            Write comprehensive Jest tests that:
            1. Test both normal operations and edge cases
            2. Use appropriate Jest matchers
            3. Include proper mocking where needed
            4. Have descriptive test names
            5. Include test coverage for all functions/components
            
            Return only the test code without explanations.
            """
        elif language == 'typescript':
            prompt += """
            Write comprehensive TypeScript Jest tests that:
            1. Test both normal operations and edge cases
            2. Use appropriate Jest matchers
            3. Include proper type definitions and mocking
            4. Have descriptive test names
            5. Include test coverage for all functions/components
            
            Return only the test code without explanations.
            """
        
        return prompt
    
    def _generate_basic_tests(self, file_path: str, code_content: str, language: str) -> str:
        """
        Generate basic tests for a file when LLM generation fails.
        
        Args:
            file_path: Path to the implementation file
            code_content: Content of the implementation file
            language: Programming language
            
        Returns:
            Test code content
        """
        filename = os.path.basename(file_path)
        name, _ = os.path.splitext(filename)
        
        if language == 'python':
            return self._generate_basic_python_tests(name, code_content)
        elif language == 'javascript':
            return self._generate_basic_javascript_tests(name, code_content)
        elif language == 'typescript':
            return self._generate_basic_typescript_tests(name, code_content)
        else:
            return f"# No basic test template available for {language}\n"
    
    def _generate_basic_python_tests(self, module_name: str, code_content: str) -> str:
        """
        Generate basic Python tests.
        
        Args:
            module_name: Name of the module
            code_content: Content of the implementation file
            
        Returns:
            Test code content
        """
        # Try to extract function and class names
        function_pattern = r'def\s+(\w+)\s*\('
        class_pattern = r'class\s+(\w+)\s*[:\(]'
        
        functions = re.findall(function_pattern, code_content)
        classes = re.findall(class_pattern, code_content)
        
        # Filter out private functions
        functions = [f for f in functions if not f.startswith('_')]
        
        # Create basic tests
        test_code = f"""import pytest
import {module_name}

# Basic test to verify the module can be imported
def test_module_import():
    assert {module_name} is not None

"""
        
        # Add tests for functions
        for func in functions:
            test_code += f"""
def test_{func}_basic():
    # TODO: Add actual test logic
    try:
        # Assuming the function exists and can be called without arguments
        # Modify as needed for actual function signature
        {module_name}.{func}
        assert True  # Replace with actual assertions
    except Exception as e:
        pytest.fail(f"Function {func} raised exception: {{e}}")
"""
        
        # Add tests for classes
        for cls in classes:
            test_code += f"""
class Test{cls}:
    def test_init(self):
        # TODO: Add actual test logic
        try:
            # Assuming the class can be instantiated without arguments
            # Modify as needed for actual class constructor
            instance = {module_name}.{cls}
            assert isinstance(instance, {module_name}.{cls})
        except Exception as e:
            pytest.fail(f"Class {cls} instantiation raised exception: {{e}}")
"""
        
        return test_code
    
    def _generate_basic_javascript_tests(self, module_name: str, code_content: str) -> str:
        """
        Generate basic JavaScript tests.
        
        Args:
            module_name: Name of the module
            code_content: Content of the implementation file
            
        Returns:
            Test code content
        """
        # Try to extract function and class names
        function_pattern = r'function\s+(\w+)\s*\('
        const_function_pattern = r'const\s+(\w+)\s*=\s*(?:function|\([^\)]*\)\s*=>)'
        class_pattern = r'class\s+(\w+)\s*(?:extends|\{)'
        component_pattern = r'(?:function|const)\s+(\w+)\s*(?:=\s*)?(?:\([^\)]*\))?\s*(?:=>)?\s*\{[^}]*return\s*\('
        
        functions = re.findall(function_pattern, code_content)
        functions.extend(re.findall(const_function_pattern, code_content))
        classes = re.findall(class_pattern, code_content)
        components = re.findall(component_pattern, code_content)
        
        # Create basic tests
        test_code = f"""
// Import the module to test
const {module_name} = require('./{module_name}');

// Basic test to verify the module can be imported
test('Module can be imported', () => {{
  expect({module_name}).toBeDefined();
}});

"""
        
        # Add tests for functions
        for func in functions:
            test_code += f"""
test('{func} function exists', () => {{
  // TODO: Add actual test logic
  expect(typeof {module_name}.{func}).toBe('function');
}});
"""
        
        # Add tests for classes
        for cls in classes:
            test_code += f"""
describe('{cls} class', () => {{
  test('can be instantiated', () => {{
    // TODO: Add actual test logic
    // Assuming the class can be instantiated without arguments
    // Modify as needed for actual class constructor
    const instance = new {module_name}.{cls}();
    expect(instance).toBeInstanceOf({module_name}.{cls});
  }});
}});
"""
        
        # Add tests for React components
        for component in components:
            if component not in functions:  # Avoid duplicates
                test_code += f"""
describe('{component} component', () => {{
  test('renders without crashing', () => {{
    // TODO: Add actual test logic for React component
    // This is just a placeholder, actual test would use React Testing Library or similar
    expect({module_name}.{component}).toBeDefined();
  }});
}});
"""
        
        return test_code
    
    def _generate_basic_typescript_tests(self, module_name: str, code_content: str) -> str:
        """
        Generate basic TypeScript tests.
        
        Args:
            module_name: Name of the module
            code_content: Content of the implementation file
            
        Returns:
            Test code content
        """
        # Start with import statement that includes types
        test_code = f"""
import {{ {module_name} }} from './{module_name}';

// Basic test to verify the module can be imported
test('Module can be imported', () => {{
  expect({module_name}).toBeDefined();
}});

"""
        
        # The rest is similar to JavaScript tests, but we need to handle TypeScript-specific patterns
        # Type signatures, interfaces, etc.
        
        # Try to extract function and class names
        function_pattern = r'function\s+(\w+)\s*\<?\w*\>?\s*\('
        const_function_pattern = r'const\s+(\w+)\s*:\s*(?:any|\w+|\([^\)]*\)\s*=>|\([^\)]*\)\s*:\s*\w+)'
        class_pattern = r'class\s+(\w+)(?:\<\w+\>)?\s*(?:implements|\{|extends)'
        interface_pattern = r'interface\s+(\w+)(?:\<\w+\>)?\s*(?:extends|\{)'
        
        functions = re.findall(function_pattern, code_content)
        functions.extend(re.findall(const_function_pattern, code_content))
        classes = re.findall(class_pattern, code_content)
        interfaces = re.findall(interface_pattern, code_content)
        
        # Add tests for functions
        for func in functions:
            test_code += f"""
test('{func} function exists', () => {{
  // TODO: Add actual test logic
  expect(typeof {module_name}.{func}).toBe('function');
}});
"""
        
        # Add tests for classes
        for cls in classes:
            test_code += f"""
describe('{cls} class', () => {{
  test('can be instantiated', () => {{
    // TODO: Add actual test logic
    // Assuming the class can be instantiated without arguments
    // Modify as needed for actual class constructor
    const instance = new {module_name}.{cls}();
    expect(instance).toBeInstanceOf({module_name}.{cls});
  }});
}});
"""
        
        return test_code
    
    async def _run_test_setup(self, language: str, directory: str):
        """
        Run setup commands for tests.
        
        Args:
            language: Programming language
            directory: Working directory
        """
        try:
            if language == 'python':
                # Check if pytest is installed
                _, output = await self.terminal_manager.execute_command(
                    "pip list | grep pytest",
                    working_dir=directory
                )
                
                if 'pytest' not in output:
                    # Install pytest
                    await self.terminal_manager.execute_command(
                        "pip install pytest",
                        working_dir=directory
                    )
            
            elif language in ['javascript', 'typescript']:
                # Check if package.json exists
                package_json_exists = await self.terminal_manager.check_file_exists(
                    os.path.join(directory, 'package.json')
                )
                
                if not package_json_exists:
                    # Create basic package.json
                    await self.terminal_manager.execute_command(
                        "npm init -y",
                        working_dir=directory
                    )
                
                # Check if Jest is installed
                node_modules_exists = await self.terminal_manager.check_directory_exists(
                    os.path.join(directory, 'node_modules')
                )
                
                if not node_modules_exists:
                    # Install Jest
                    if language == 'typescript':
                        await self.terminal_manager.execute_command(
                            "npm install --save-dev jest ts-jest @types/jest typescript",
                            working_dir=directory
                        )
                    else:
                        await self.terminal_manager.execute_command(
                            "npm install --save-dev jest",
                            working_dir=directory
                        )
        
        except Exception as e:
            logger.error(f"Error running test setup: {str(e)}")
    
    def _parse_test_results(self, output: str, language: str) -> Dict[str, Any]:
        """
        Parse test results from output.
        
        Args:
            output: Test command output
            language: Programming language
            
        Returns:
            Dictionary with parsed test results
        """
        results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'tests': []
        }
        
        if language == 'python':
            # Parse pytest output
            # Look for patterns like "4 passed, 1 failed in 0.12s"
            summary_pattern = r'(\d+)\s+passed(?:,\s+(\d+)\s+failed)?'
            summary_match = re.search(summary_pattern, output)
            
            if summary_match:
                results['tests_passed'] = int(summary_match.group(1) or 0)
                results['tests_failed'] = int(summary_match.group(2) or 0)
                results['tests_run'] = results['tests_passed'] + results['tests_failed']
            
            # Extract individual test results
            test_pattern = r'(\w+)\s+PASSED|FAILED\s+\[([^\]]+)\]\s+(\w+)'
            for match in re.finditer(test_pattern, output):
                results['tests'].append({
                    'name': match.group(3) if match.group(3) else 'unknown',
                    'status': 'passed' if 'PASSED' in match.group(0) else 'failed'
                })
        
        elif language in ['javascript', 'typescript']:
            # Parse Jest output
            # Look for patterns like "Tests: 4 passed, 1 failed, 5 total"
            summary_pattern = r'Tests:\s+(\d+)\s+passed,\s+(\d+)\s+failed,\s+(\d+)\s+total'
            summary_match = re.search(summary_pattern, output)
            
            if summary_match:
                results['tests_passed'] = int(summary_match.group(1) or 0)
                results['tests_failed'] = int(summary_match.group(2) or 0)
                results['tests_run'] = int(summary_match.group(3) or 0)
            
            # Extract individual test results
            test_pattern = r'(✓|✕)\s+([^\(]+)'
            for match in re.finditer(test_pattern, output):
                results['tests'].append({
                    'name': match.group(2).strip(),
                    'status': 'passed' if match.group(1) == '✓' else 'failed'
                })
        
        return results
    
    def _analyze_project(self, project_dir: str) -> Dict[str, Any]:
        """
        Analyze a project directory.
        
        Args:
            project_dir: Path to the project directory
            
        Returns:
            Dictionary with project information
        """
        result = {
            'languages': set(),
            'files_by_language': {},
            'test_files': [],
            'implementation_files': []
        }
        
        # Walk through the directory
        for root, _, files in os.walk(project_dir):
            for file in files:
                file_path = os.path.join(root, file)
                language = self._detect_language(file_path)
                
                if language != 'unknown':
                    result['languages'].add(language)
                    
                    if language not in result['files_by_language']:
                        result['files_by_language'][language] = []
                    
                    result['files_by_language'][language].append(file_path)
                    
                    if self._is_test_file(file_path, language):
                        result['test_files'].append(file_path)
                    else:
                        result['implementation_files'].append(file_path)
        
        # Convert set to list for JSON serialization
        result['languages'] = list(result['languages'])
        
        return result
    
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
