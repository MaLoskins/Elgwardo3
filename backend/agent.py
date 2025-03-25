"""
Agent module for the AI Agent Terminal Interface.
Contains core logic for autonomous code generation and refinement.
"""

import os
import asyncio
import logging
import json
import time
from typing import Dict, Any, Callable, Optional, List

import openai
import httpx

from knowledge_graph import KnowledgeGraph
from todo_manager import ToDoManager
from terminal_manager import TerminalManager
from assessment import AssessmentSystem

logger = logging.getLogger(__name__)


class FormatGuardianAgent:
    """
    A "guardian" or "pre-flight" agent that checks commands and code
    before we finalize them, ensuring we don't mix shell commands inside
    code files, or embed code in a command that should remain separate.
    
    This helps avoid situations where a user ends up with lines like:
    
        npm start
        import React from 'react';
    
    all in the same file.
    """
    
    def validate_command(self, command: str) -> str:
        """
        Called right before a command is executed.
        If we detect that the command string includes lines that look like code
        (e.g., `import`, `class`, etc.), we attempt to remove or comment them.
        
        You can customize this logic as needed.
        """
        # Simple heuristic: If a line starts with 'import ', or 'function ', etc., remove it
        suspicious_keywords = ["import ", "const ", "class ", "ReactDOM.render"]
        
        cleaned_lines = []
        for line in command.split("\n"):
            # If it starts with suspicious code keywords, skip or comment it out
            if any(k in line for k in suspicious_keywords):
                logger.warning(f"GuardianAgent: Removing potential code snippet from command line: {line}")
                continue
            cleaned_lines.append(line)
        
        cleaned_command = "\n".join(cleaned_lines).strip()
        
        # In case there's leftover trailing code references
        # Additional checks here if needed.
        
        return cleaned_command

    def validate_code(self, code: str) -> str:
        """
        Called right before writing a code file.
        If we detect lines that look like shell commands (e.g., `npm install`,
        `pip install`, etc.), we'll either comment them out or remove them.
        
        This avoids the scenario where a user’s code accidentally includes:
            npm start
            cd graph-parameters-form
            ...
        which belongs in a shell script, not in the .js or .py file.
        """
        suspicious_shell_keywords = [
            "npm install", "npm start", "npm run", "npx create-react-app", 
            "cd ", "pip install", "apt-get", "chmod ", "git clone"
        ]
        
        cleaned_lines = []
        for line in code.split("\n"):
            if any(kw in line for kw in suspicious_shell_keywords):
                logger.warning(f"GuardianAgent: Found suspicious shell command in code. Commenting out: {line}")
                # Instead of removing, let's comment it out to preserve readability
                line = f"// RemovedShellCmd: {line}"
            
            cleaned_lines.append(line)
        
        cleaned_code = "\n".join(cleaned_lines)
        return cleaned_code


class Agent:
    """
    AI Agent responsible for autonomous code generation, testing, and refinement.
    
    This agent interfaces with the OpenAI API and Brave Search API to generate
    code, analyze errors, and iteratively refine solutions. The improvements here
    ensure that the agent will keep attempting to complete tasks, executing
    multiple commands if needed, and performing repeated refinements until
    the objectives in the ToDo list have been satisfied (or until the same
    error repeats too many times).
    """
    
    def __init__(
        self,
        openai_api_key: str,
        brave_search_api_key: str,
        model: str,
        knowledge_graph: KnowledgeGraph,
        todo_manager: ToDoManager,
        terminal_manager: TerminalManager
    ):
        """
        Initialize the Agent with API keys and component references.
        
        Args:
            openai_api_key: API key for OpenAI
            brave_search_api_key: API key for Brave Search
            model: OpenAI model to use (e.g., gpt-4, gpt-4o, gpt-3.5-turbo)
            knowledge_graph: Reference to the KnowledgeGraph instance
            todo_manager: Reference to the ToDoManager instance
            terminal_manager: Reference to the TerminalManager instance
        """
        self.openai_api_key = openai_api_key
        self.brave_search_api_key = brave_search_api_key
        self.model = model
        self.knowledge_graph = knowledge_graph
        self.todo_manager = todo_manager
        self.terminal_manager = terminal_manager
        self.broadcast_message = None
        self.current_task = None
        self.task_status = "idle"
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Initialize HTTP client for Brave Search API
        self.http_client = httpx.AsyncClient(
            headers={"X-Subscription-Token": brave_search_api_key}
        )
        
        # Initialize Assessment System
        self.assessment_system = AssessmentSystem(self.openai_client, model)
        
        # NEW: Initialize our Guardian agent
        self.format_guardian_agent = FormatGuardianAgent()
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """
        Set the function used to broadcast messages to WebSocket clients.
        """
        self.broadcast_message = broadcast_function
    
    def set_model(self, model: str):
        """
        Update the OpenAI model selection.
        
        Args:
            model: New model to use
            
        Raises:
            ValueError: If the model is not supported
        """
        supported_models = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]  # Example set
        if model not in supported_models:
            raise ValueError(f"Unsupported model: {model}. Supported models: {supported_models}")
        
        self.model = model
        logger.info(f"Model updated to {model}")
    
    async def execute_task(self, task: str):
        """
        Execute a coding (or multi-step) task autonomously.
        
        This method implements a multi-step task execution flow:
        
        1. Generate a plan (list of sub-steps).
        2. For each sub-step, either run shell commands or generate code (and execute it).
        3. If any step fails, refine the command until success or repeated errors.
        4. After completing all sub-steps, run a final assessment. 
        5. If final assessment indicates incomplete tasks, do a high-level refinement loop
           until tasks are completed or repeated identical failures appear.
        """
        try:
            self.current_task = task
            self.task_status = "running"
            
            # Log task start
            logger.info(f"Starting task execution: {task}")
            await self._broadcast_update("task_start", {"task": task})
            
            # Add task to ToDo.md
            task_id = self.todo_manager.add_task(task)
            
            # Step 1: Generate an overall plan
            await self._broadcast_update("status_update", {"message": "Analyzing task requirements to create a plan..."})
            plan_info = await self._generate_plan(task)
            self.knowledge_graph.add_task_context(task_id, plan_info)
            
            # Step 2: Execute each sub-step from the plan in order
            sub_steps = plan_info.get("sub_steps", [])
            if not sub_steps:
                # If no sub-steps found, treat the entire task as one sub-step
                sub_steps = [{"description": "Complete the entire task", "type": "code"}]
            
            for index, sub_step in enumerate(sub_steps, 1):
                step_description = sub_step.get("description", f"Sub-step {index}")
                step_type = sub_step.get("type", "code")  # e.g., "code", "command"
                
                await self._broadcast_update(
                    "status_update", 
                    {"message": f"Executing sub-step {index}/{len(sub_steps)}: {step_description}"}
                )
                logger.info(f"Executing sub-step {index}/{len(sub_steps)}: {step_description}")
                
                if step_type == "command":
                    # Possibly the sub-step is a direct command we need to run
                    command_list = sub_step.get("commands", [])
                    for cmd in command_list:
                        success, output = await self._execute_with_refinement(cmd, step_description, task_id)
                        if not success:
                            # If repeated failures occur, mark failed
                            self.task_status = "failed"
                            return
                else:
                    # Default: code generation sub-step
                    task_analysis = await self._analyze_task(step_description)
                    
                    code_content = await self._generate_code(step_description, task_analysis)
                    
                    # <--- Guardian agent check BEFORE writing the file. --->
                    code_content = self.format_guardian_agent.validate_code(code_content)
                    
                    filename = task_analysis.get("filename", f"sub_step_{index}.py")
                    code_file_path = await self._save_code_to_file(code_content, filename)
                    
                    # Then run that code
                    run_command = f"python {code_file_path}"
                    success, output = await self._execute_with_refinement(run_command, step_description, task_id)
                    
                    if not success:
                        # If repeated identical errors block further progress, mark failure
                        self.task_status = "failed"
                        return
            
            # Step 3: After all sub-steps, do a final assessment
            await self._broadcast_update("status_update", {"message": "Verifying overall task completion..."})
            todo_content = self.todo_manager.get_todo_content()
            
            assessment_result = await self.assessment_system.verify_task_completion(
                task,
                "N/A",  # Not referencing a single file
                "All sub-steps completed",
                todo_content
            )
            
            if assessment_result["is_completed"] and assessment_result["confidence"] > 70:
                # Mark the entire task completed
                self.todo_manager.mark_task_completed(task_id)
                await self._broadcast_update("status_update", {"message": "Task completed successfully!"})
                self.task_status = "completed"
                logger.info(f"Task execution completed successfully: {task}")
                await self._broadcast_update("task_complete", {"task": task})
            else:
                # If final assessment indicates incomplete, refine at the task level
                for recommendation in assessment_result.get("recommendations", []):
                    self.todo_manager.add_subtask(task_id, recommendation, False)
                
                logger.warning(f"Final assessment indicates incomplete or low confidence for: {task}")
                await self._broadcast_update("status_update", {"message": "Task requires further refinement."})
                
                # Attempt additional refinements at high level
                refinement_success = await self._high_level_refinement_loop(task, assessment_result, task_id)
                if refinement_success:
                    self.task_status = "completed"
                    logger.info(f"Task execution completed after high-level refinements: {task}")
                    await self._broadcast_update("task_complete", {"task": task})
                else:
                    self.task_status = "failed"
                    logger.error(f"Task execution failed after high-level refinement attempts: {task}")
                    await self._broadcast_update("error", {"message": "Failed to complete task after multiple refinement attempts"})

        except Exception as e:
            self.task_status = "failed"
            error_message = f"Error executing task: {str(e)}"
            logger.error(error_message)
            await self._broadcast_update("error", {"message": error_message})
            self.todo_manager.add_error(self.current_task or "unknown", error_message)

    async def _high_level_refinement_loop(self, task: str, assessment_result: Dict[str, Any], task_id: str) -> bool:
        """
        Perform additional refinements if final assessment indicates incomplete or low confidence.
        Tries to generate new steps or commands, repeating until success or repeated identical errors.
        """
        repeated_error_count = 0
        last_error_msg = None
        
        while True:
            logger.info("Starting high-level refinement iteration.")
            await self._broadcast_update("status_update", {"message": "High-level refinement iteration."})
            
            # Use knowledge graph + assessment to generate next steps
            prompt = f"""
            The final assessment indicates the task isn't fully complete or confidence is low.
            Below is the relevant final assessment result:

            {json.dumps(assessment_result, indent=2)}

            Additionally, the knowledge graph context is:
            {self.knowledge_graph.get_context_for_task(task)}

            Please suggest one or more commands or code blocks that should be executed 
            or created to finalize the task. Provide a JSON array of sub-steps, 
            each containing:
              - "description"
              - "type": "command" or "code"
              - if "type"="command", "commands": [list of commands]
              - if "type"="code", "filename" and "code_content"

            Return ONLY valid JSON (no markdown, no code fences).
            """
            # Use our JSON request method here
            new_sub_steps = await self._request_json_from_llm(prompt)
            if not isinstance(new_sub_steps, list):
                # If the user gave us a single dict, wrap it in a list
                new_sub_steps = [new_sub_steps]
            
            if not new_sub_steps:
                logger.warning("No new high-level refinement steps suggested. Stopping.")
                return False
            
            # Execute each sub-step
            for sub_step in new_sub_steps:
                step_desc = sub_step.get("description", "Refinement step")
                step_type = sub_step.get("type", "command")
                
                if step_type == "command":
                    cmd_list = sub_step.get("commands", [])
                    for cmd in cmd_list:
                        success, output = await self._execute_with_refinement(cmd, step_desc, task_id)
                        if not success:
                            # Possibly repeated error
                            if output == last_error_msg:
                                repeated_error_count += 1
                            else:
                                last_error_msg = output
                                repeated_error_count = 0
                            
                            if repeated_error_count >= 3:
                                logger.error("Encountered the same error 3 times in a row. Aborting.")
                                return False
                else:
                    # sub_step is for code
                    filename = sub_step.get("filename", "refinement_step.py")
                    code_content = sub_step.get("code_content", "# No code provided")
                    
                    # <--- Guardian check before saving code. --->
                    code_content = self.format_guardian_agent.validate_code(code_content)
                    
                    file_path = await self._save_code_to_file(code_content, filename)
                    run_command = f"python {file_path}"
                    
                    success, output = await self._execute_with_refinement(run_command, step_desc, task_id)
                    if not success:
                        if output == last_error_msg:
                            repeated_error_count += 1
                        else:
                            last_error_msg = output
                            repeated_error_count = 0
                        
                        if repeated_error_count >= 3:
                            logger.error("Encountered the same error 3 times in a row. Aborting.")
                            return False
            
            # Re-check after these new steps
            todo_content = self.todo_manager.get_todo_content()
            assessment_result = await self.assessment_system.verify_task_completion(
                task,
                "N/A",
                "Refinement iteration attempt completed.",
                todo_content
            )
            if assessment_result["is_completed"] and assessment_result["confidence"] > 70:
                self.todo_manager.mark_task_completed(task_id)
                return True
            # otherwise, keep refining

    async def _execute_with_refinement(self, command: str, step_description: str, task_id: str) -> (bool, str):
        """
        Execute a shell command with repeated refinement if it fails.
        Returns (success, final_output).
        Terminates if the same error repeats 3 times in a row.
        """
        iteration = 0
        repeated_error_count = 0
        last_error_msg = None
        
        while True:
            iteration += 1
            
            # <--- Guardian agent check BEFORE running the command. --->
            command = self.format_guardian_agent.validate_command(command)
            
            iteration_msg = f"Executing command (attempt {iteration}): {command}"
            logger.info(iteration_msg)
            await self._broadcast_update("status_update", {"message": iteration_msg})
            
            success, output = await self.terminal_manager.execute_command(command)
            
            if success:
                self.todo_manager.mark_subtask_completed(task_id, f"{step_description} - iteration {iteration}")
                return True, output
            
            # If fails, check if error is repeated
            if output == last_error_msg:
                repeated_error_count += 1
            else:
                last_error_msg = output
                repeated_error_count = 0
            
            if repeated_error_count >= 3:
                err_msg = (
                    f"Repeated identical error encountered 3 times for command: {command}.\n"
                    f"Error output:\n{output}"
                )
                logger.error(err_msg)
                self.todo_manager.add_error(task_id, err_msg)
                return False, output
            
            logger.info(f"Command failed. Attempting refinement iteration {iteration} for step: {step_description}")
            await self._broadcast_update("status_update", {"message": f"Refinement iteration {iteration} for: {step_description}"})
            
            # Analyze error + refine command
            error_analysis = await self._analyze_errors(output)
            self.knowledge_graph.add_error_context(task_id, error_analysis)
            
            if error_analysis.get("needs_search", False):
                query = error_analysis.get("search_query", "generic error debugging query")
                search_results = await self._search_brave(query)
                self.knowledge_graph.add_search_results(task_id, search_results)
            
            # Create refined command
            command = await self._refine_command(step_description, command, error_analysis)

    async def _generate_plan(self, task: str) -> Dict[str, Any]:
        """
        Generate a plan in JSON with sub-steps (each step either 'command' or 'code').
        """
        prompt = f"""
        You are an AI coding assistant. The user wants to perform the following task:

        {task}

        Break it down into a list of sub-steps, each having:
          - description (short text)
          - type: "command" or "code"
          - if type="command", include a "commands" list
          - if type="code", just leave it so we know we must generate code later
        Return a JSON object with "sub_steps" (array). 

        IMPORTANT: Return ONLY valid JSON. Do not include markdown or code fences.
        Example:
        {{
          "sub_steps": [
            {{
              "description": "Install nano and dependencies",
              "type": "command",
              "commands": ["apt-get update", "apt-get install -y nano"]
            }},
            {{
              "description": "Create the main code file for 3D Pong",
              "type": "code"
            }}
          ]
        }}
        """
        # Use our JSON request method
        plan = await self._request_json_from_llm(prompt)
        
        if "sub_steps" not in plan:
            logger.warning("No 'sub_steps' found in plan. Using fallback single step.")
            plan["sub_steps"] = [{"description": task, "type": "code"}]
        
        return plan
    
    async def _analyze_task(self, task_description: str) -> Dict[str, Any]:
        """
        Analyze a sub-task to determine code details (language, filename, approach, etc.).
        Return a dict with 'language', 'filename', 'components', 'dependencies', 'approach'.
        """
        prompt = f"""
        Analyze the following coding sub-step:

        {task_description}

        Provide strictly valid JSON with the fields:
        {{
          "description": "...",
          "language": "...",
          "filename": "...",
          "components": [...],
          "dependencies": [...],
          "approach": [...]
        }}

        IMPORTANT: Do NOT use markdown or code fences, return ONLY valid JSON.
        """
        analysis = await self._request_json_from_llm(prompt)
        
        # Ensure we have minimal fields
        if "language" not in analysis:
            analysis["language"] = "python"
        if "filename" not in analysis:
            analysis["filename"] = "script.py"
        if "components" not in analysis:
            analysis["components"] = []
        if "dependencies" not in analysis:
            analysis["dependencies"] = []
        if "approach" not in analysis:
            analysis["approach"] = []
        
        return analysis
    
    async def _generate_code(self, task_description: str, task_analysis: Dict[str, Any]) -> str:
        """
        Generate code for a sub-step. Return the code as a string.
        """
        language = task_analysis.get("language", "python")
        components = task_analysis.get("components", [])
        dependencies = task_analysis.get("dependencies", [])
        approach = task_analysis.get("approach", [])
        
        prompt = f"""
        Generate code for the following sub-step:
        
        SUB-STEP: {task_description}
        LANGUAGE: {language}

        KEY COMPONENTS TO IMPLEMENT:
        {json.dumps(components, indent=2)}

        DEPENDENCIES:
        {json.dumps(dependencies, indent=2)}

        APPROACH:
        {json.dumps(approach, indent=2)}

        Provide the complete, working code.
        You MAY use a code block if you want, but the agent will extract it automatically.
        """
        
        # Add knowledge graph context if any
        context = self.knowledge_graph.get_context_for_task(task_description)
        if context:
            prompt += f"\n\nADDITIONAL CONTEXT:\n{context}"
        
        code = await self._call_openai_api(prompt)
        return self._extract_code_blocks(code)

    async def _refine_command(self, step_description: str, original_command: str, error_analysis: Dict[str, Any]) -> str:
        """
        Use the LLM to suggest an improved shell command, given the original command + error analysis.
        """
        context = self.knowledge_graph.get_context_for_task(step_description)
        search_results = self.knowledge_graph.get_search_results(step_description)
        
        prompt = f"""
        The following command failed:
        {original_command}

        Error analysis:
        {json.dumps(error_analysis, indent=2)}

        Knowledge graph context:
        {context}

        Web search results:
        {search_results}

        Suggest a single refined shell command that attempts to fix the problem.
        Output ONLY the command as plain text (no code fences, no JSON).
        """
        refined_cmd = await self._call_openai_api(prompt)
        
        # Clean up any backticks or multi-line issues
        refined_cmd = refined_cmd.strip().replace("`", "").replace("\n", " ").replace("\r", "")
        if not refined_cmd:
            logger.warning("Refined command is empty, falling back to original command.")
            return original_command
        
        return refined_cmd
    
    async def _save_code_to_file(self, code: str, filename: str) -> str:
        """
        Save generated code to a file. Default extension .py if missing.
        """
        valid_exts = ['.py', '.js', '.html', '.css', '.json', '.cpp', '.cs']
        if not any(filename.endswith(ext) for ext in valid_exts):
            filename += '.py'
        
        workspace_dir = os.path.join(os.getcwd(), "workspace")
        os.makedirs(workspace_dir, exist_ok=True)
        
        file_path = os.path.join(workspace_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        logger.info(f"Code saved to {file_path}")
        return file_path
    
    async def _analyze_errors(self, error_output: str) -> Dict[str, Any]:
        """
        Analyze terminal output for error details, returning JSON with
        fields: error_type, error_message, cause, fixes, needs_search, search_query
        """
        prompt = f"""
        Analyze this terminal output for errors:

        {error_output}

        Return JSON with:
          "error_type"
          "error_message"
          "cause"
          "fixes" (array of suggestions)
          "needs_search" (boolean)
          "search_query" (if needs_search = true)

        IMPORTANT: Return ONLY valid JSON, no code fences or markdown.
        """
        
        # We'll try once normally:
        analysis = await self._request_json_from_llm(prompt)
        
        # Ensure minimal fields
        if "error_type" not in analysis:
            analysis["error_type"] = "Unknown"
        if "error_message" not in analysis:
            analysis["error_message"] = error_output
        if "cause" not in analysis:
            analysis["cause"] = "Unknown cause"
        if "fixes" not in analysis:
            analysis["fixes"] = []
        if "needs_search" not in analysis:
            analysis["needs_search"] = True
        if analysis["needs_search"] and "search_query" not in analysis:
            analysis["search_query"] = "python error debugging"
        
        return analysis
    
    async def _search_brave(self, query: str) -> str:
        """
        Search the web using Brave Search API for additional context.
        """
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            params = {"q": query, "count": 5}
            
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return "No search results found."
            
            out_lines = []
            for i, res in enumerate(results, start=1):
                title = res.get("title", "No title")
                link = res.get("url", "No URL")
                desc = res.get("description", "No description")
                out_lines.append(f"{i}. {title}\nURL: {link}\nDescription: {desc}\n")
            
            return "\n".join(out_lines)
        except Exception as e:
            logger.error(f"Error searching Brave: {str(e)}")
            return f"Error performing search: {str(e)}"
    
    async def _call_openai_api(self, prompt: str) -> str:
        """
        Call the OpenAI API with the given prompt, returning response text.
        """
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "You are an AI assistant that helps with coding tasks. "
                            "Provide clear, thorough, step-by-step responses.\n\n"
                            + prompt
                        )
                    }
                ],
                temperature=0.2,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise

    async def _request_json_from_llm(self, prompt: str, max_retries: int = 3) -> Any:
        """
        Force the LLM to return valid JSON by:
        1) Sending a system instruction to respond ONLY in JSON.
        2) Trying to parse it.
        3) If parse fails, we tell the LLM precisely that it returned invalid JSON, ask it to correct it.
        4) Repeat up to max_retries times.
        """
        system_instructions = (
            "You are an AI assistant that outputs ONLY valid JSON with no markdown, no code blocks, "
            "and no extra keys. If your response is not valid JSON, you will be asked to fix it.\n"
        )
        attempt = 0
        last_error = None

        while attempt < max_retries:
            attempt += 1
            # Combine system instructions with the user prompt
            messages = [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": prompt}
            ]
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1000
                )
                content = response.choices[0].message.content.strip()
                # Attempt to parse JSON
                return json.loads(content)
            except Exception as e:
                # Possibly a parse error or API error
                last_error = str(e)
                logger.warning(f"[JSON Parse Attempt {attempt}] Could not parse LLM response as JSON. Error: {last_error}")

                # Retry by telling the LLM to fix its JSON
                prompt = (
                    f"You returned invalid JSON. The error was: {last_error}.\n"
                    f"Please ONLY output valid JSON. No explanation. Just the corrected JSON."
                )
        
        # If we fail all attempts, log a warning and return empty dict
        logger.error(f"Failed to get valid JSON after {max_retries} attempts. Returning empty object.")
        return {}

    def _extract_code_blocks(self, text: str) -> str:
        """
        Extract code from Markdown code fences. If multiple fences, combine them.
        """
        if "```" not in text:
            return text.strip()
        
        code_blocks = []
        lines = text.split("\n")
        in_block = False
        current_block = []
        
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    code_blocks.append("\n".join(current_block))
                    current_block = []
                in_block = not in_block
                continue
            if in_block:
                current_block.append(line)
        
        # If we have a trailing block
        if current_block:
            code_blocks.append("\n".join(current_block))
        
        return "\n\n".join(code_blocks).strip()

    async def _broadcast_update(self, update_type: str, data: Dict[str, Any]):
        """
        Broadcast an update to all connected WebSocket clients.
        """
        if self.broadcast_message:
            message = {
                "type": update_type,
                "timestamp": time.time(),
                "data": data
            }
            await self.broadcast_message(message)
