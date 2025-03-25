"""
Coder Agent module for the AI Agent Terminal Interface.
Specializes in generating and refining code based on requirements.
"""

import logging
import asyncio
import json
import os
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

import openai

from knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class CoderAgent:
    """
    Specialized agent focused on code generation and implementation.
    
    This agent is responsible for:
    - Understanding coding requirements
    - Generating code across multiple files and languages
    - Refining and fixing code when issues arise
    - Ensuring code meets functional requirements
    """
    
    def __init__(
        self,
        openai_api_key: str,
        model: str,
        knowledge_graph: KnowledgeGraph
    ):
        """
        Initialize the Coder Agent.
        
        Args:
            openai_api_key: API key for OpenAI
            model: OpenAI model to use
            knowledge_graph: Reference to the KnowledgeGraph instance
        """
        self.openai_api_key = openai_api_key
        self.model = model
        self.knowledge_graph = knowledge_graph
        self.broadcast_function = None
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Language-specific settings for code generation
        self.language_extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "html": ".html",
            "css": ".css",
            "react": ".jsx",
            "react-typescript": ".tsx",
            "json": ".json"
        }
        
        logger.info("Coder Agent initialized")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages."""
        self.broadcast_function = broadcast_function
    
    def set_model(self, model: str):
        """Update the OpenAI model selection."""
        self.model = model
        logger.info(f"Coder Agent model updated to {model}")
    
    async def determine_filename(self, description: str, module_type: str = "") -> str:
        """
        Determine an appropriate filename based on the description and module type.
        
        Args:
            description: Description of the code to be generated
            module_type: Type of module (e.g., "component", "utility", "api")
            
        Returns:
            Appropriate filename with extension
        """
        prompt = f"""
        Determine an appropriate filename for the following code description:
        
        Description: {description}
        Module Type: {module_type}
        
        Return ONLY the filename with appropriate extension. No explanation.
        Choose the extension based on the likely language (e.g., .py for Python, .js for JavaScript).
        Use snake_case for Python files and camelCase for JavaScript/TypeScript files.
        Make the filename descriptive of the functionality.
        """
        
        filename = await self._call_openai_api(prompt)
        
        # Clean up response to ensure it's just a filename
        filename = filename.strip().replace('`', '').replace('\n', '')
        
        # Ensure it has an extension
        if not any(filename.endswith(ext) for ext in self.language_extensions.values()):
            if "react" in module_type.lower():
                filename += ".jsx"
            else:
                filename += ".py"  # Default to Python
        
        logger.info(f"Determined filename: {filename} for {description}")
        return filename
    
    async def generate_plan(self, task: str, research_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate a detailed development plan for the task.
        
        Args:
            task: Task description
            research_result: Research information from the researcher agent
            
        Returns:
            Dictionary containing the development plan with sub-steps
        """
        context = ""
        if research_result:
            context = f"""
            RESEARCH CONTEXT:
            {json.dumps(research_result, indent=2)}
            """
        
        prompt = f"""
        You are an expert software architect. Create a detailed development plan for this task:
        
        TASK: {task}
        
        {context}
        
        Include a step-by-step plan with:
        1. A list of files to create with appropriate filenames and extensions
        2. Dependencies between files
        3. Order of implementation
        4. Any commands that need to be run (like installations)
        
        Structure your plan in JSON format with these keys:
        - description: Overall task description
        - architecture: Brief description of the system architecture
        - sub_steps: Array of steps, each with:
          - description: What this step accomplishes
          - type: "research" | "command" | "code" | "module" 
          - [For "command" type]: "commands" array with shell commands to run
          - [For "code"/"module" type]: "filename" and "module_type" fields
          - dependencies: Array of step indexes that must be completed first
        
        Return ONLY valid JSON. No markdown, no code fences, no explanations.
        """
        
        # Request JSON with retries
        plan = await self._request_json_from_llm(prompt)
        
        # Ensure the plan has valid sub-steps
        if "sub_steps" not in plan:
            logger.warning("No sub_steps found in plan. Creating default.")
            plan["sub_steps"] = [{"description": task, "type": "code"}]
        
        # Add dependencies for data flow
        self._add_dependencies_to_plan(plan)
        
        # Log the plan
        await self._broadcast("plan_created", {"plan": plan})
        logger.info(f"Generated development plan with {len(plan.get('sub_steps', []))} steps")
        
        return plan
    
    def _add_dependencies_to_plan(self, plan: Dict[str, Any]):
        """
        Add implicit dependencies to the plan based on file relationships.
        
        Args:
            plan: The development plan to enhance
        """
        sub_steps = plan.get("sub_steps", [])
        
        # Track files and their step indices
        file_steps = {}
        for i, step in enumerate(sub_steps):
            if step.get("type") in ["code", "module"] and "filename" in step:
                file_steps[step["filename"]] = i
        
        # Add dependencies based on import patterns
        for i, step in enumerate(sub_steps):
            if step.get("type") in ["code", "module"] and "filename" in step:
                filename = step["filename"]
                # Python files might depend on other modules
                if filename.endswith(".py"):
                    # Add dependencies on utility files
                    for other_file, other_index in file_steps.items():
                        if other_file != filename and "util" in other_file and other_file.endswith(".py"):
                            if "dependencies" not in step:
                                step["dependencies"] = []
                            if other_index not in step["dependencies"]:
                                step["dependencies"].append(other_index)
                
                # Frontend components might depend on utility functions
                if filename.endswith((".jsx", ".tsx", ".js", ".ts")):
                    for other_file, other_index in file_steps.items():
                        if other_file != filename and "util" in other_file and other_file.endswith((".js", ".ts")):
                            if "dependencies" not in step:
                                step["dependencies"] = []
                            if other_index not in step["dependencies"]:
                                step["dependencies"].append(other_index)
    
    async def generate_code(
        self,
        description: str,
        module_type: str,
        research_result: Dict[str, Any] = None,
        existing_code: str = ""
    ) -> str:
        """
        Generate code based on the description and context.
        
        Args:
            description: Description of the code to generate
            module_type: Type of module (e.g., "component", "utility", "api")
            research_result: Research information from the researcher agent
            existing_code: Existing code if this is an update
            
        Returns:
            Generated code as string
        """
        # Determine programming language based on module type
        language = "python"
        if module_type.lower() in ["component", "react", "frontend", "ui", "view"]:
            language = "javascript"
        
        context = ""
        if research_result:
            context = f"""
            RESEARCH CONTEXT:
            {json.dumps(research_result, indent=2)}
            """
        
        existing_context = ""
        if existing_code:
            existing_context = f"""
            EXISTING CODE TO EXTEND/MODIFY:
            <code>
            {existing_code}
            </code>
            
            Maintain the same code structure and style. Preserve existing imports and functions.
            Make surgical modifications and additions as needed.
            """
        
        # Different prompts based on whether this is new code or an update
        if existing_code:
            prompt = f"""
            Update or enhance the provided code based on this description:
            
            DESCRIPTION: {description}
            MODULE TYPE: {module_type}
            LANGUAGE: {language}
            
            {context}
            
            {existing_context}
            
            Write the COMPLETE updated code.
            Ensure code is well-documented with docstrings/comments.
            Include robust error handling.
            Handle edge cases.
            """
        else:
            prompt = f"""
            Generate complete code based on this description:
            
            DESCRIPTION: {description}
            MODULE TYPE: {module_type}
            LANGUAGE: {language}
            
            {context}
            
            Requirements:
            1. Include appropriate imports at the top
            2. Use best practices for {language}
            3. Add comprehensive docstrings and comments
            4. Include error handling for robustness
            5. Make the code modular and maintainable
            6. Include sample usage if appropriate
            
            Write the COMPLETE functioning code. Don't abbreviate or skip sections.
            """
        
        # Split into chunks if the task is complex
        if len(description) > 500 or (existing_code and len(existing_code) > 1000):
            return await self._generate_large_code_file(
                prompt, description, language, module_type, existing_code
            )
        
        # For simpler cases, generate directly
        code = await self._call_openai_api(prompt)
        
        # Extract code if it's wrapped in markdown code blocks
        code = self._extract_code_blocks(code)
        
        await self._broadcast("code_generated", {
            "description": description,
            "language": language,
            "length": len(code)
        })
        
        return code
    
    async def _generate_large_code_file(
        self,
        base_prompt: str,
        description: str,
        language: str,
        module_type: str,
        existing_code: str = ""
    ) -> str:
        """
        Generate code for complex tasks by breaking it into smaller components.
        
        Args:
            base_prompt: Base prompt for code generation
            description: Description of the code to generate
            language: Programming language
            module_type: Type of module
            existing_code: Existing code if this is an update
            
        Returns:
            Complete generated code
        """
        await self._broadcast("status_update", {
            "message": "Breaking down complex code generation into components..."
        })
        
        # First, generate a high-level design
        design_prompt = f"""
        Create a detailed design for this code task:
        
        DESCRIPTION: {description}
        LANGUAGE: {language}
        MODULE TYPE: {module_type}
        
        Break this down into logical components or sections, including:
        1. Overall structure and architecture
        2. Required imports and dependencies
        3. Key functions/classes and their responsibilities
        4. How the components interact
        
        Return your answer as a JSON object with these keys:
        - imports: Array of import statements
        - components: Array of objects, each with:
          - name: Component name (class/function/section)
          - description: What it does
          - dependencies: Other components it depends on
        - implementation_order: Suggested order to implement components
        
        ONLY return the JSON, no markdown or explanations.
        """
        
        design = await self._request_json_from_llm(design_prompt)
        
        # Generate each component
        components = design.get("components", [])
        if not components:
            # Fallback if design doesn't have components
            logger.warning("No components in design. Falling back to direct code generation.")
            code = await self._call_openai_api(base_prompt)
            return self._extract_code_blocks(code)
        
        implementation_order = design.get("implementation_order", list(range(len(components))))
        imports = design.get("imports", [])
        
        # Generate code for each component
        component_code_segments = []
        
        # Start with imports
        if imports:
            import_code = "\n".join(imports)
            component_code_segments.append(import_code)
        
        # Generate each component
        for idx in implementation_order:
            if idx >= len(components):
                continue
                
            component = components[idx]
            component_name = component.get("name", f"Component_{idx}")
            component_desc = component.get("description", "")
            
            await self._broadcast("status_update", {
                "message": f"Generating component: {component_name}..."
            })
            
            # Find existing code for this component if updating
            existing_component_code = ""
            if existing_code and component_name in existing_code:
                # Simple extraction - can be enhanced with regex for better precision
                try:
                    # For classes
                    if f"class {component_name}" in existing_code:
                        parts = existing_code.split(f"class {component_name}")
                        if len(parts) > 1:
                            class_part = parts[1]
                            # Find the end of the class
                            next_class_idx = class_part.find("class ")
                            if next_class_idx == -1:
                                next_class_idx = len(class_part)
                            existing_component_code = f"class {component_name}" + class_part[:next_class_idx]
                    
                    # For functions
                    elif f"def {component_name}" in existing_code:
                        parts = existing_code.split(f"def {component_name}")
                        if len(parts) > 1:
                            func_part = parts[1]
                            # Find the end of the function
                            next_func_idx = func_part.find("def ")
                            if next_func_idx == -1:
                                next_func_idx = len(func_part)
                            existing_component_code = f"def {component_name}" + func_part[:next_func_idx]
                except Exception as e:
                    logger.error(f"Error extracting existing component code: {str(e)}")
            
            # Create the prompt with conditional part handled separately
            base_prompt = f"""
            Generate code for the following component:
            
            COMPONENT: {component_name}
            DESCRIPTION: {component_desc}
            LANGUAGE: {language}
            
            This component is part of a larger program with this overall purpose:
            {description}
            """
            
            # Add existing code section if available
            if existing_component_code:
                base_prompt += f"""
            
            EXISTING CODE TO ADAPT/IMPROVE:
            <code>
            {existing_component_code}
            </code>
            
            Write complete, well-documented code for just this component.
            Include comprehensive error handling and comments.
            """
            
            component_prompt = base_prompt

            
            component_code = await self._call_openai_api(component_prompt)
            component_code = self._extract_code_blocks(component_code)
            
            component_code_segments.append(component_code)
        
        # Combine all components
        final_code = "\n\n".join(component_code_segments)
        
        # Verify combined code
        await self._broadcast("status_update", {
            "message": "Verifying combined code..."
        })
        
        verification_prompt = f"""
        Review this generated code for completeness and correctness:
        
        ```
        {final_code}
        ```
        
        Does it fully implement the requirements:
        {description}
        
        If there are any issues, provide the corrected code.
        If the code is good, just respond with "CODE VERIFIED".
        """
        
        verification = await self._call_openai_api(verification_prompt)
        
        if "CODE VERIFIED" not in verification:
            # The LLM found issues and provided fixes
            fixed_code = self._extract_code_blocks(verification)
            if fixed_code and len(fixed_code) > 200:  # Avoid empty or tiny "fixes"
                final_code = fixed_code
        
        return final_code
    
    async def fix_code_errors(self, code: str, error_output: str) -> str:
        """
        Fix errors in code based on error messages.
        
        Args:
            code: Original code with errors
            error_output: Error messages from execution
            
        Returns:
            Fixed code
        """
        prompt = f"""
        Fix the errors in this code based on the error output:
        
        CODE WITH ERRORS:
        ```
        {code}
        ```
        
        ERROR OUTPUT:
        ```
        {error_output}
        ```
        
        Provide the complete fixed code with corrections for all errors.
        Include clear comments explaining what was fixed.
        """
        
        fixed_code = await self._call_openai_api(prompt)
        fixed_code = self._extract_code_blocks(fixed_code)
        
        await self._broadcast("code_fixed", {
            "original_length": len(code),
            "fixed_length": len(fixed_code)
        })
        
        return fixed_code
    
    async def fix_code_issues(self, code: str, issues: List[str]) -> str:
        """
        Fix code issues identified during verification.
        
        Args:
            code: Original code
            issues: List of issues to fix
            
        Returns:
            Fixed code
        """
        issues_text = "\n".join([f"- {issue}" for issue in issues])
        
        prompt = f"""
        Fix the following issues in this code:
        
        CODE TO FIX:
        ```
        {code}
        ```
        
        ISSUES TO RESOLVE:
        {issues_text}
        
        Provide the complete fixed code with corrections for all issues.
        Include clear comments explaining what was fixed.
        """
        
        fixed_code = await self._call_openai_api(prompt)
        fixed_code = self._extract_code_blocks(fixed_code)
        
        await self._broadcast("code_issues_fixed", {
            "issues_count": len(issues),
            "original_length": len(code),
            "fixed_length": len(fixed_code)
        })
        
        return fixed_code
    
    async def refine_command(self, command: str, error_analysis: Dict[str, Any]) -> str:
        """
        Refine a shell command based on error analysis.
        
        Args:
            command: Original command
            error_analysis: Error analysis dictionary
            
        Returns:
            Refined command
        """
        prompt = f"""
        Refine this shell command to fix the error:
        
        ORIGINAL COMMAND:
        {command}
        
        ERROR ANALYSIS:
        {json.dumps(error_analysis, indent=2)}
        
        Provide ONLY the corrected command. No explanation.
        """
        
        refined_command = await self._call_openai_api(prompt)
        
        # Clean up any backticks or extra whitespace
        refined_command = refined_command.strip()
        refined_command = refined_command.replace('`', '').replace('\n', ' ')
        
        await self._broadcast("command_refined", {
            "original": command,
            "refined": refined_command
        })
        
        return refined_command
    
    async def verify_implementation(self, task: str, workspace_dir: str) -> Dict[str, Any]:
        """
        Verify that the implementation meets the task requirements.
        
        Args:
            task: Original task description
            workspace_dir: Directory containing the implementation
            
        Returns:
            Dictionary with verification results
        """
        # Collect all code files in the workspace
        code_files = []
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                if file.endswith(tuple(self.language_extensions.values())):
                    file_path = os.path.join(root, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            content = f.read()
                            code_files.append({
                                "path": file_path,
                                "name": file,
                                "content": content
                            })
                        except Exception as e:
                            logger.error(f"Error reading {file_path}: {str(e)}")
        
        if not code_files:
            return {
                "verified": False,
                "issues": ["No code files found in workspace"],
                "files_to_fix": []
            }
        
        # Combine code files for verification, but limit total size
        combined_code = ""
        files_too_large = []
        
        for code_file in code_files:
            if len(combined_code) + len(code_file["content"]) < 100000:
                combined_code += f"\n\n# FILE: {code_file['name']}\n"
                combined_code += code_file["content"]
            else:
                files_too_large.append(code_file["name"])
        
        prompt = f"""
        Verify that this code implementation meets the requirements for the task:
        
        TASK: {task}
        
        CODE IMPLEMENTATION:
        ```
        {combined_code}
        ```
        

        Note: Some files were too large to include: {', '.join(files_too_large)}" if files_too_large else "" 
        Check for:
        1. Completeness - Does the code implement all required functionality?
        2. Correctness - Is the implementation likely to work as expected?
        3. Edge cases - Are potential issues and edge cases handled?
        
        Return a JSON object with:
        - verified: boolean (true if implementation meets requirements)
        - issues: array of strings describing any issues found
        - files_to_fix: array of file paths that need fixes
        
        ONLY return the JSON. No markdown or explanations.
        """
        
        result = await self._request_json_from_llm(prompt)
        
        await self._broadcast("implementation_verified", {
            "verified": result.get("verified", False),
            "issues_count": len(result.get("issues", []))
        })
        
        return result
    
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
                            "You are an expert software engineer with deep knowledge across "
                            "multiple programming languages and frameworks. You write clean, "
                            "efficient, well-documented code that follows best practices."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Lower temperature for more deterministic code
                max_tokens=4000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise
    
    async def _request_json_from_llm(self, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Request JSON data from the LLM with retries for valid JSON.
        
        Args:
            prompt: Prompt to send
            max_retries: Maximum number of retries
            
        Returns:
            Parsed JSON data
        """
        system_instruction = (
            "You are an AI assistant that outputs ONLY valid JSON with no markdown, "
            "no code blocks, and no extra text. If your response is not valid JSON, "
            "you will be asked to fix it."
        )
        
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                
                # Try to parse JSON
                result = json.loads(content)
                return result
                
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Invalid JSON (attempt {attempt + 1}): {str(e)}")
                    # Update prompt to request valid JSON
                    prompt = f"You provided invalid JSON. The error was: {str(e)}. Please fix it and return ONLY valid JSON."
                else:
                    logger.error(f"Failed to get valid JSON after {max_retries} attempts")
                    # Return empty dict as fallback
                    return {}
            except Exception as e:
                logger.error(f"Error in request_json_from_llm: {str(e)}")
                # Return empty dict as fallback
                return {}
    
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
