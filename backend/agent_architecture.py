"""
Enhanced Multi-Agent Architecture for AI Agent Terminal Interface.
Implements a coordinating system of specialized agents to handle different aspects
of code generation, research, and formatting.
"""

import logging
import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Callable, Tuple, Union
import os

# Local imports
from agents.coder_agent import CoderAgent
from agents.researcher_agent import ResearcherAgent
from agents.formatter_agent import FormatterAgent
from knowledge_graph import KnowledgeGraph
from todo_manager import ToDoManager
from terminal_manager import TerminalManager

logger = logging.getLogger(__name__)

class AgentCoordinator:
    """
    Coordinates the activities of specialized agents:
    - CoderAgent: Handles code generation and implementation
    - ResearcherAgent: Gathers information and context for tasks
    - FormatterAgent: Ensures code is properly formatted and structured
    
    This coordinator manages the workflow between agents and ensures they
    collaborate effectively on complex tasks.
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
        Initialize the Agent Coordinator with API keys and component references.
        
        Args:
            openai_api_key: API key for OpenAI
            brave_search_api_key: API key for Brave Search
            model: OpenAI model to use (e.g., gpt-4o)
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
        
        # Heartbeat controls
        self.heartbeat_interval = 5  # seconds
        self.heartbeat_task = None
        
        # Initialize specialized agents
        self.coder_agent = CoderAgent(
            openai_api_key=openai_api_key,
            model=model,
            knowledge_graph=knowledge_graph
        )
        
        self.researcher_agent = ResearcherAgent(
            openai_api_key=openai_api_key,
            brave_search_api_key=brave_search_api_key,
            model=model,
            knowledge_graph=knowledge_graph
        )
        
        self.formatter_agent = FormatterAgent(
            openai_api_key=openai_api_key,
            model=model
        )
        
        # Project management
        self.workspace_dir = os.path.join(os.getcwd(), "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        logger.info("Agent Coordinator initialized with specialized agents")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages to WebSocket clients."""
        self.broadcast_message = broadcast_function
        # Pass the broadcast function to specialized agents as needed
        # This allows agents to send detailed updates during their operations
        self.coder_agent.set_broadcast_function(self._create_agent_broadcaster("coder"))
        self.researcher_agent.set_broadcast_function(self._create_agent_broadcaster("researcher"))
        self.formatter_agent.set_broadcast_function(self._create_agent_broadcaster("formatter"))
    
    def _create_agent_broadcaster(self, agent_type: str) -> Callable:
        """
        Create a broadcaster function for a specific agent type.
        This wraps the main broadcast function with agent-specific context.
        
        Args:
            agent_type: Type of agent (coder, researcher, formatter)
            
        Returns:
            Callable that broadcasts agent-specific messages
        """
        async def agent_broadcaster(update_type: str, data: Dict[str, Any]):
            if self.broadcast_message:
                message = {
                    "type": f"{agent_type}_{update_type}",
                    "timestamp": time.time(),
                    "data": data
                }
                await self.broadcast_message(message)
        
        return agent_broadcaster
    
    def set_model(self, model: str):
        """
        Update the OpenAI model selection for all agents.
        
        Args:
            model: New model to use
            
        Raises:
            ValueError: If the model is not supported
        """
        supported_models = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        if model not in supported_models:
            raise ValueError(f"Unsupported model: {model}. Supported models: {supported_models}")
        
        self.model = model
        self.coder_agent.set_model(model)
        self.researcher_agent.set_model(model)
        self.formatter_agent.set_model(model)
        logger.info(f"Model updated to {model} for all agents")
    
    async def _start_heartbeat(self):
        """Start sending heartbeat messages to keep the WebSocket connection alive."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        async def heartbeat_loop():
            while True:
                await self._broadcast_update("heartbeat", {
                    "task": self.current_task,
                    "status": self.task_status,
                    "timestamp": time.time()
                })
                await asyncio.sleep(self.heartbeat_interval)
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info(f"Heartbeat started with interval of {self.heartbeat_interval} seconds")
    
    async def _stop_heartbeat(self):
        """Stop the heartbeat loop."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
            logger.info("Heartbeat stopped")
    
    async def execute_task(self, task: str):
        """
        Execute a coding task using the coordinated multi-agent approach.
        
        This orchestrates the workflow between specialized agents:
        1. Researcher agent gathers context and information
        2. Coder agent generates code based on requirements and research
        3. Formatter agent ensures code quality and organization
        
        Args:
            task: The task description to execute
        """
        try:
            self.current_task = task
            self.task_status = "running"
            
            # Start heartbeat to keep connection alive
            await self._start_heartbeat()
            
            # Log task start
            logger.info(f"Starting task execution: {task}")
            await self._broadcast_update("task_start", {"task": task})
            
            # Add task to ToDo.md
            task_id = self.todo_manager.add_task(task)
            
            # Step 1: Initial research and context gathering
            await self._broadcast_update("status_update", {
                "message": "Researching context and gathering information...",
                "progress": 10
            })
            
            research_result = await self.researcher_agent.research_task(task)
            self.knowledge_graph.add_task_context(task_id, research_result)
            
            # Step 2: Generate a task plan with the coder agent
            await self._broadcast_update("status_update", {
                "message": "Analyzing task requirements and creating a development plan...",
                "progress": 20
            })
            
            plan = await self.coder_agent.generate_plan(task, research_result)
            
            # Step 3: Execute the plan using all agents in coordination
            total_steps = len(plan.get("sub_steps", []))
            if total_steps == 0:
                total_steps = 1
                plan["sub_steps"] = [{"description": "Complete the task", "type": "code"}]
            
            for step_index, step in enumerate(plan["sub_steps"]):
                step_num = step_index + 1
                step_desc = step.get("description", f"Step {step_num}")
                step_type = step.get("type", "code")
                
                progress = 20 + (60 * step_index // total_steps)
                await self._broadcast_update("status_update", {
                    "message": f"Executing step {step_num}/{total_steps}: {step_desc}",
                    "progress": progress
                })
                
                # Add step as subtask
                self.todo_manager.add_subtask(task_id, step_desc)
                
                # Execute appropriate actions based on step type
                if step_type == "research":
                    # Additional research for this specific step
                    search_query = step.get("search_query", step_desc)
                    step_research = await self.researcher_agent.search_information(search_query)
                    self.knowledge_graph.add_search_results(task_id, step_research)
                    
                elif step_type == "command":
                    # Execute shell commands
                    commands = step.get("commands", [])
                    for cmd_index, cmd in enumerate(commands):
                        cmd_desc = f"{step_desc} - Command {cmd_index + 1}/{len(commands)}"
                        await self._broadcast_update("status_update", {
                            "message": f"Executing command: {cmd}",
                            "progress": progress + (5 * cmd_index // len(commands))
                        })
                        
                        # Format the command before execution
                        formatted_cmd = self.formatter_agent.format_command(cmd)
                        
                        # Execute with refinement if necessary
                        success, output = await self._execute_with_refinement(
                            formatted_cmd, step_desc, task_id
                        )
                        
                        if not success:
                            # Handle failure with the researcher agent
                            solution = await self.researcher_agent.find_solution_for_error(
                                cmd, output
                            )
                            
                            if solution:
                                fixed_cmd = solution.get("fixed_command", "")
                                if fixed_cmd:
                                    success, _ = await self._execute_with_refinement(
                                        fixed_cmd, step_desc, task_id
                                    )
                
                elif step_type == "code" or step_type == "module":
                    # Generate code using the coder agent
                    filename = step.get("filename", "")
                    module_type = step.get("module_type", "")
                    
                    # If filename wasn't specified, determine it based on step description
                    if not filename:
                        filename = await self.coder_agent.determine_filename(step_desc, module_type)
                    
                    await self._broadcast_update("status_update", {
                        "message": f"Generating code for {filename}...",
                        "progress": progress + 2
                    })
                    
                    # Get any existing code from the file if it exists
                    existing_code = ""
                    file_path = os.path.join(self.workspace_dir, filename)
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            existing_code = f.read()
                    
                    # Generate code
                    code_content = await self.coder_agent.generate_code(
                        step_desc, 
                        module_type,
                        research_result,
                        existing_code
                    )
                    
                    # Format the code
                    await self._broadcast_update("status_update", {
                        "message": f"Formatting code for {filename}...",
                        "progress": progress + 4
                    })
                    formatted_code = await self.formatter_agent.format_code(
                        code_content, 
                        filename
                    )
                    
                    # Save the code
                    file_path = await self._save_code_to_file(formatted_code, filename)
                    self.knowledge_graph.add_code_file(task_id, filename, formatted_code)
                    
                    # Execute if needed (Python files)
                    if filename.endswith(".py") and step.get("execute", True):
                        run_command = f"python {file_path}"
                        success, output = await self._execute_with_refinement(
                            run_command, step_desc, task_id
                        )
                        
                        if not success:
                            # Try to fix code errors
                            fixed_code = await self.coder_agent.fix_code_errors(
                                formatted_code, output
                            )
                            formatted_fixed_code = await self.formatter_agent.format_code(
                                fixed_code, filename
                            )
                            file_path = await self._save_code_to_file(formatted_fixed_code, filename)
                            
                            # Try running again
                            success, _ = await self._execute_with_refinement(
                                run_command, step_desc, task_id
                            )
                
                # Mark step as completed
                self.todo_manager.mark_subtask_completed(task_id, step_desc)
            
            # Final verification
            await self._broadcast_update("status_update", {
                "message": "Performing final verification...",
                "progress": 90
            })
            
            # Use all three agents for verification
            verification_results = await asyncio.gather(
                self.coder_agent.verify_implementation(task, self.workspace_dir),
                self.formatter_agent.verify_formatting(self.workspace_dir),
                self.researcher_agent.verify_completeness(task, self.workspace_dir)
            )
            
            coder_verification, formatter_verification, researcher_verification = verification_results
            
            all_verified = all([
                coder_verification.get("verified", False),
                formatter_verification.get("verified", False),
                researcher_verification.get("verified", False)
            ])
            
            if all_verified:
                # Complete the task
                self.todo_manager.mark_task_completed(task_id)
                await self._broadcast_update("status_update", {
                    "message": "Task completed successfully!",
                    "progress": 100
                })
                self.task_status = "completed"
                logger.info(f"Task execution completed successfully: {task}")
                await self._broadcast_update("task_complete", {"task": task})
            else:
                # Perform refinements as needed
                await self._perform_final_refinements(
                    task, 
                    task_id, 
                    coder_verification, 
                    formatter_verification, 
                    researcher_verification
                )
            
        except Exception as e:
            self.task_status = "failed"
            error_message = f"Error executing task: {str(e)}"
            logger.error(error_message)
            await self._broadcast_update("error", {"message": error_message})
            self.todo_manager.add_error(self.current_task or "unknown", error_message)
        
        finally:
            # Stop heartbeat when task completes (whether success or failure)
            await self._stop_heartbeat()
    
    async def _perform_final_refinements(
        self, 
        task: str, 
        task_id: str,
        coder_verification: Dict[str, Any],
        formatter_verification: Dict[str, Any],
        researcher_verification: Dict[str, Any]
    ):
        """
        Perform final refinements based on verification results.
        
        Args:
            task: Original task
            task_id: Task ID
            coder_verification: Results from coder verification
            formatter_verification: Results from formatter verification
            researcher_verification: Results from researcher verification
        """
        max_refinement_iterations = 3
        for iteration in range(max_refinement_iterations):
            await self._broadcast_update("status_update", {
                "message": f"Performing refinement iteration {iteration + 1}/{max_refinement_iterations}...",
                "progress": 90 + ((iteration + 1) * 3)
            })
            
            # Collect issues
            issues = []
            issues.extend(coder_verification.get("issues", []))
            issues.extend(formatter_verification.get("issues", []))
            issues.extend(researcher_verification.get("issues", []))
            
            if not issues:
                break
                
            # Add issues as subtasks
            for issue in issues:
                self.todo_manager.add_subtask(task_id, f"Refinement: {issue}")
            
            # Fix issues
            fixed_any = False
            
            # Fix code issues
            if not coder_verification.get("verified", False):
                for file_path in coder_verification.get("files_to_fix", []):
                    filename = os.path.basename(file_path)
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    fixed_code = await self.coder_agent.fix_code_issues(
                        content, 
                        coder_verification.get("issues", [])
                    )
                    
                    formatted_code = await self.formatter_agent.format_code(fixed_code, filename)
                    await self._save_code_to_file(formatted_code, filename)
                    fixed_any = True
            
            # Fix formatting issues
            if not formatter_verification.get("verified", False):
                for file_path in formatter_verification.get("files_to_fix", []):
                    filename = os.path.basename(file_path)
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    formatted_code = await self.formatter_agent.format_code(content, filename)
                    await self._save_code_to_file(formatted_code, filename)
                    fixed_any = True
            
            # If we couldn't fix anything, break the loop
            if not fixed_any:
                break
            
            # Re-verify
            verification_results = await asyncio.gather(
                self.coder_agent.verify_implementation(task, self.workspace_dir),
                self.formatter_agent.verify_formatting(self.workspace_dir),
                self.researcher_agent.verify_completeness(task, self.workspace_dir)
            )
            
            coder_verification, formatter_verification, researcher_verification = verification_results
            
            all_verified = all([
                coder_verification.get("verified", False),
                formatter_verification.get("verified", False),
                researcher_verification.get("verified", False)
            ])
            
            if all_verified:
                # Complete the task
                self.todo_manager.mark_task_completed(task_id)
                await self._broadcast_update("status_update", {
                    "message": "Task completed successfully after refinements!",
                    "progress": 100
                })
                self.task_status = "completed"
                logger.info(f"Task execution completed after refinements: {task}")
                await self._broadcast_update("task_complete", {"task": task})
                return
        
        # If we get here, we've tried refinements but still have issues
        self.task_status = "partial"
        await self._broadcast_update("status_update", {
            "message": "Task partially completed with some unresolved issues.",
            "progress": 100
        })
        logger.warning(f"Task execution partially completed with unresolved issues: {task}")
        await self._broadcast_update("task_partial", {"task": task})
    
    async def _execute_with_refinement(self, command: str, step_description: str, task_id: str) -> Tuple[bool, str]:
        """
        Execute a shell command with repeated refinement if it fails.
        
        Args:
            command: Command to execute
            step_description: Description of the step
            task_id: Task ID
            
        Returns:
            Tuple of (success, output)
        """
        max_iterations = 3
        
        for iteration in range(max_iterations):
            iteration_msg = f"Executing command (attempt {iteration + 1}/{max_iterations}): {command}"
            logger.info(iteration_msg)
            await self._broadcast_update("status_update", {"message": iteration_msg})
            
            success, output = await self.terminal_manager.execute_command(command)
            
            if success:
                return True, output
            
            if iteration < max_iterations - 1:
                # Analyze error and refine command
                error_analysis = await self.researcher_agent.analyze_error(output)
                refined_command = await self.coder_agent.refine_command(command, error_analysis)
                command = refined_command
            else:
                # Failed after max attempts
                err_msg = f"Command failed after {max_iterations} attempts: {command}"
                logger.error(err_msg)
                self.todo_manager.add_error(task_id, err_msg)
                return False, output
        
        return False, "Maximum refinement iterations reached"
    
    async def _save_code_to_file(self, code: str, filename: str) -> str:
        """
        Save code to a file.
        
        Args:
            code: Code content
            filename: Filename
            
        Returns:
            Full path to the saved file
        """
        # Ensure the file has an appropriate extension
        if not any(filename.endswith(ext) for ext in ['.py', '.js', '.html', '.css', '.json', '.jsx', '.ts', '.tsx']):
            filename += '.py'  # Default to Python
        
        file_path = os.path.join(self.workspace_dir, filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        logger.info(f"Code saved to {file_path}")
        return file_path
    
    async def _broadcast_update(self, update_type: str, data: Dict[str, Any]):
        """
        Broadcast an update to all connected WebSocket clients.
        
        Args:
            update_type: Type of update
            data: Update data
        """
        if self.broadcast_message:
            message = {
                "type": update_type,
                "timestamp": time.time(),
                "data": data
            }
            await self.broadcast_message(message)
