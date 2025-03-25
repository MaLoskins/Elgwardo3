"""
Agent Coordinator module for the AI Agent Terminal Interface.
Orchestrates the collaboration between specialized agents and handles task distribution.
"""

import os
import logging
import asyncio
import time
import json
from typing import Dict, Any, List, Set, Optional, Callable, Tuple, Union
import traceback
import random

from agent_factory import AgentFactory
from knowledge_graph import KnowledgeGraph
from code_chunker import CodeChunker
from todo_manager import ToDoManager
from terminal_manager import TerminalManager

logger = logging.getLogger(__name__)

class AgentCoordinator:
    """
    Coordinates the activities of specialized agents and manages their collaboration.
    
    Key responsibilities:
    1. Task decomposition and distribution
    2. Inter-agent communication
    3. Progress tracking and status updates
    4. Error handling and recovery
    5. Resource management for large codebases
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
        Initialize the Agent Coordinator.
        
        Args:
            openai_api_key: API key for OpenAI
            brave_search_api_key: API key for Brave Search
            model: OpenAI model to use
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
        
        # Create agent factory
        self.agent_factory = AgentFactory(
            openai_api_key=openai_api_key,
            brave_search_api_key=brave_search_api_key
        )
        
        # Initialize specialized agents
        self.coder_agent = self.agent_factory.create_agent(
            agent_type="coder",
            model=model,
            knowledge_graph=knowledge_graph
        )
        
        self.researcher_agent = self.agent_factory.create_agent(
            agent_type="researcher",
            model=model,
            knowledge_graph=knowledge_graph
        )
        
        self.formatter_agent = self.agent_factory.create_agent(
            agent_type="formatter",
            model=model
        )
        
        # Create code chunker for handling large codebases
        self.code_chunker = CodeChunker()
        
        # Project management
        self.workspace_dir = os.path.join(os.getcwd(), "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Task execution tracking
        self.current_execution = {
            "task_id": None,
            "start_time": None,
            "steps": [],
            "current_step": None,
            "progress": 0,
            "errors": [],
            "warnings": []
        }
        
        # Agent activity logging
        self.agent_activities = {
            "coder": [],
            "researcher": [],
            "formatter": []
        }
        
        # Maximum number of retries for failed steps
        self.max_retries = 3
        
        logger.info("Agent Coordinator initialized")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages to WebSocket clients."""
        self.broadcast_message = broadcast_function
        
        # Pass the broadcast function to specialized agents
        self.coder_agent.set_broadcast_function(self._create_agent_broadcaster("coder"))
        self.researcher_agent.set_broadcast_function(self._create_agent_broadcaster("researcher"))
        self.formatter_agent.set_broadcast_function(self._create_agent_broadcaster("formatter"))
    
    def _create_agent_broadcaster(self, agent_type: str) -> Callable:
        """
        Create a broadcaster function for a specific agent type.
        
        Args:
            agent_type: Type of agent (coder, researcher, formatter)
            
        Returns:
            Function that broadcasts agent-specific messages
        """
        async def agent_broadcaster(update_type: str, data: Dict[str, Any]):
            # Log the agent activity
            self.agent_activities[agent_type].append({
                "type": update_type,
                "timestamp": time.time(),
                "data": data
            })
            
            # Broadcast the message
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
                    "progress": self.current_execution["progress"],
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
        Execute a task using the coordinated multi-agent approach.
        
        Args:
            task: The task description to execute
        """
        try:
            self.current_task = task
            self.task_status = "running"
            
            # Reset current execution tracking
            self.current_execution = {
                "task_id": None,
                "start_time": time.time(),
                "steps": [],
                "current_step": None,
                "progress": 0,
                "errors": [],
                "warnings": []
            }
            
            # Start heartbeat to keep connection alive
            await self._start_heartbeat()
            
            # Log task start
            logger.info(f"Starting task execution: {task}")
            await self._broadcast_update("task_start", {"task": task})
            
            # Add task to ToDo.md
            task_id = self.todo_manager.add_task(task)
            self.current_execution["task_id"] = task_id
            
            # Step 1: Initial research and context gathering
            await self._update_progress(10, "Researching context and gathering information...")
            
            research_result = await self.researcher_agent.research_task(task)
            self.knowledge_graph.add_task_context(task_id, research_result)
            
            # Step 2: Generate a task plan with the coder agent
            await self._update_progress(20, "Analyzing task requirements and creating a development plan...")
            
            plan = await self.coder_agent.generate_plan(task, research_result)
            
            # Step 3: Execute the plan using all agents in coordination
            total_steps = len(plan.get("sub_steps", []))
            if total_steps == 0:
                total_steps = 1
                plan["sub_steps"] = [{"description": "Complete the task", "type": "code"}]
            
            # Save plan to current execution
            self.current_execution["steps"] = plan.get("sub_steps", [])
            
            # Track dependencies between steps
            dependency_graph = self._build_dependency_graph(plan.get("sub_steps", []))
            
            # Progress tracking variables
            progress_step = 60 / total_steps  # 60% of progress bar for steps execution
            
            # Execute steps in dependency order
            ready_steps = self._get_ready_steps(dependency_graph, [])
            completed_steps = set()
            
            while ready_steps:
                # Execute steps that can be executed in parallel
                await self._execute_parallel_steps(ready_steps, task_id, progress_step)
                
                # Update completed steps
                completed_steps.update(ready_steps)
                
                # Get next ready steps
                ready_steps = self._get_ready_steps(dependency_graph, list(completed_steps))
            
            # Final verification
            await self._update_progress(90, "Performing final verification...")
            
            # Use all three agents for verification
            verification_results = await asyncio.gather(
                self._verify_with_coder(task),
                self._verify_with_formatter(),
                self._verify_with_researcher(task)
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
                await self._update_progress(100, "Task completed successfully!")
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
            logger.error(traceback.format_exc())
            await self._broadcast_update("error", {"message": error_message})
            
            if self.current_execution["task_id"]:
                self.todo_manager.add_error(self.current_execution["task_id"], error_message)
        
        finally:
            # Stop heartbeat when task completes (whether success or failure)
            await self._stop_heartbeat()
    
    def _build_dependency_graph(self, steps: List[Dict[str, Any]]) -> Dict[int, List[int]]:
        """
        Build a dependency graph from steps.
        
        Args:
            steps: List of steps
            
        Returns:
            Dictionary mapping step indices to lists of dependent step indices
        """
        dependency_graph = {}
        
        for i in range(len(steps)):
            dependencies = steps[i].get("dependencies", [])
            dependency_graph[i] = dependencies
        
        return dependency_graph
    
    def _get_ready_steps(self, dependency_graph: Dict[int, List[int]], completed_steps: List[int]) -> List[int]:
        """
        Get steps that are ready to be executed.
        
        Args:
            dependency_graph: Dependency graph
            completed_steps: List of completed step indices
            
        Returns:
            List of step indices that are ready to be executed
        """
        ready_steps = []
        
        for step_idx, dependencies in dependency_graph.items():
            if step_idx not in completed_steps and all(dep in completed_steps for dep in dependencies):
                ready_steps.append(step_idx)
        
        return ready_steps
    
    async def _execute_parallel_steps(self, step_indices: List[int], task_id: str, progress_increment: float):
        """
        Execute multiple steps in parallel.
        
        Args:
            step_indices: List of step indices to execute
            task_id: Task ID
            progress_increment: Progress increment per step
        """
        # For now, just execute steps sequentially
        # This could be enhanced to use proper parallelization in the future
        for step_idx in step_indices:
            step = self.current_execution["steps"][step_idx]
            step_desc = step.get("description", f"Step {step_idx + 1}")
            
            self.current_execution["current_step"] = step_idx
            
            # Calculate progress for this step
            step_progress = 20 + (progress_increment * step_idx)
            await self._update_progress(step_progress, f"Executing step {step_idx + 1}: {step_desc}")
            
            # Add step as subtask
            self.todo_manager.add_subtask(task_id, step_desc)
            
            # Execute the step
            success = await self._execute_step(step, task_id, step_idx)
            
            if success:
                # Mark step as completed
                self.todo_manager.mark_subtask_completed(task_id, step_desc)
            else:
                # Log step failure
                logger.error(f"Step {step_idx + 1} failed: {step_desc}")
                self.current_execution["errors"].append({
                    "step_idx": step_idx,
                    "step_desc": step_desc,
                    "timestamp": time.time()
                })
    
    async def _execute_step(self, step: Dict[str, Any], task_id: str, step_idx: int) -> bool:
        """
        Execute a single step of the task.
        
        Args:
            step: Step definition
            task_id: Task ID
            step_idx: Step index
            
        Returns:
            True if the step was executed successfully, False otherwise
        """
        step_type = step.get("type", "code")
        step_desc = step.get("description", f"Step {step_idx + 1}")
        
        try:
            if step_type == "research":
                # Additional research for this specific step
                search_query = step.get("search_query", step_desc)
                step_research = await self.researcher_agent.search_information(search_query)
                self.knowledge_graph.add_search_results(task_id, step_research)
                return True
                
            elif step_type == "command":
                # Execute shell commands
                commands = step.get("commands", [])
                for cmd_index, cmd in enumerate(commands):
                    cmd_desc = f"{step_desc} - Command {cmd_index + 1}/{len(commands)}"
                    await self._broadcast_update("status_update", {
                        "message": f"Executing command: {cmd}",
                        "progress": self.current_execution["progress"]
                    })
                    
                    # Format the command before execution
                    formatted_cmd = self.formatter_agent.format_command(cmd)
                    
                    # Execute with refinement if necessary
                    success, output = await self._execute_with_refinement(
                        formatted_cmd, step_desc, task_id
                    )
                    
                    if not success:
                        return False
                
                return True
            
            elif step_type == "code" or step_type == "module":
                # Generate code using the coder agent
                filename = step.get("filename", "")
                module_type = step.get("module_type", "")
                
                # If filename wasn't specified, determine it based on step description
                if not filename:
                    filename = await self.coder_agent.determine_filename(step_desc, module_type)
                
                await self._broadcast_update("status_update", {
                    "message": f"Generating code for {filename}...",
                    "progress": self.current_execution["progress"]
                })
                
                # Get any existing code from the file if it exists
                existing_code = ""
                file_path = os.path.join(self.workspace_dir, filename)
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        existing_code = f.read()
                
                # Gather research context
                research_context = self.knowledge_graph.get_context_for_task(task_id)
                if not research_context:
                    # If no specific research context, get general research info
                    research_context = "{}"
                
                # Generate code
                code_content = await self.coder_agent.generate_code(
                    step_desc, 
                    module_type,
                    json.loads(research_context) if research_context else {},
                    existing_code
                )
                
                # Format the code
                await self._broadcast_update("status_update", {
                    "message": f"Formatting code for {filename}...",
                    "progress": self.current_execution["progress"]
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
                    run_command = f"cd {self.workspace_dir} && python {filename}"
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
                        return success
                
                return True
            
            else:
                # Unknown step type
                logger.warning(f"Unknown step type: {step_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing step {step_idx + 1}: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
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
        for attempt in range(self.max_retries):
            try:
                # Execute the command
                logger.info(f"Executing command (attempt {attempt + 1}/{self.max_retries}): {command}")
                await self._broadcast_update("status_update", {
                    "message": f"Executing command (attempt {attempt + 1}/{self.max_retries}): {command}",
                    "progress": self.current_execution["progress"]
                })
                
                success, output = await self.terminal_manager.execute_command(command)
                
                if success:
                    return True, output
                
                # Command failed, try to refine it
                if attempt < self.max_retries - 1:
                    # Analyze error with researcher agent
                    error_analysis = await self.researcher_agent.analyze_error(output)
                    
                    # Refine command with coder agent
                    refined_command = await self.coder_agent.refine_command(command, error_analysis)
                    
                    # Update command for next attempt
                    command = refined_command
                else:
                    # Failed after max attempts
                    logger.error(f"Command failed after {self.max_retries} attempts: {command}")
                    self.todo_manager.add_error(task_id, f"Command failed after {self.max_retries} attempts: {command}\n\nOutput: {output}")
                    return False, output
                    
            except Exception as e:
                logger.error(f"Error executing command: {str(e)}")
                if attempt == self.max_retries - 1:
                    return False, str(e)
        
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
    
    async def _verify_with_coder(self, task: str) -> Dict[str, Any]:
        """
        Verify the implementation with the coder agent.
        
        Args:
            task: Original task
            
        Returns:
            Verification results
        """
        try:
            verification = await self.coder_agent.verify_implementation(task, self.workspace_dir)
            return verification
        except Exception as e:
            logger.error(f"Error verifying with coder agent: {str(e)}")
            return {"verified": False, "issues": [str(e)]}
    
    async def _verify_with_formatter(self) -> Dict[str, Any]:
        """
        Verify the formatting with the formatter agent.
        
        Returns:
            Verification results
        """
        try:
            verification = await self.formatter_agent.verify_formatting(self.workspace_dir)
            return verification
        except Exception as e:
            logger.error(f"Error verifying with formatter agent: {str(e)}")
            return {"verified": False, "issues": [str(e)]}
    
    async def _verify_with_researcher(self, task: str) -> Dict[str, Any]:
        """
        Verify the completeness with the researcher agent.
        
        Args:
            task: Original task
            
        Returns:
            Verification results
        """
        try:
            verification = await self.researcher_agent.verify_completeness(task, self.workspace_dir)
            return verification
        except Exception as e:
            logger.error(f"Error verifying with researcher agent: {str(e)}")
            return {"verified": False, "issues": [str(e)]}
    
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
            coder_verification: Coder verification results
            formatter_verification: Formatter verification results
            researcher_verification: Researcher verification results
        """
        max_refinement_iterations = 3
        
        for iteration in range(max_refinement_iterations):
            # Update progress and status
            refinement_progress = 90 + ((iteration + 1) * 3)
            await self._update_progress(
                refinement_progress,
                f"Performing refinement iteration {iteration + 1}/{max_refinement_iterations}..."
            )
            
            # Collect all issues
            issues = []
            issues.extend(coder_verification.get("issues", []))
            issues.extend(formatter_verification.get("issues", []))
            issues.extend(researcher_verification.get("issues", []))
            
            if not issues:
                # No issues to fix, we're done
                self.todo_manager.mark_task_completed(task_id)
                await self._update_progress(100, "Task completed after refinements!")
                self.task_status = "completed"
                logger.info(f"Task execution completed after refinements: {task}")
                await self._broadcast_update("task_complete", {"task": task})
                return
            
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
                    
                    try:
                        # Fix code issues
                        fixed_code = await self.coder_agent.fix_code_issues(
                            content, 
                            coder_verification.get("issues", [])
                        )
                        
                        # Format the fixed code
                        formatted_code = await self.formatter_agent.format_code(
                            fixed_code, filename
                        )
                        
                        # Save the fixed code
                        await self._save_code_to_file(formatted_code, filename)
                        fixed_any = True
                    except Exception as e:
                        logger.error(f"Error fixing code issues in {filename}: {str(e)}")
            
            # Fix formatting issues
            if not formatter_verification.get("verified", False):
                for file_path in formatter_verification.get("files_to_fix", []):
                    filename = os.path.basename(file_path)
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    try:
                        # Format the code
                        formatted_code = await self.formatter_agent.format_code(
                            content, filename
                        )
                        
                        # Save the formatted code
                        await self._save_code_to_file(formatted_code, filename)
                        fixed_any = True
                    except Exception as e:
                        logger.error(f"Error formatting code in {filename}: {str(e)}")
            
            # If we couldn't fix anything, break the loop
            if not fixed_any:
                break
            
            # Re-verify
            if iteration < max_refinement_iterations - 1:  # Skip final verification on last iteration
                verification_results = await asyncio.gather(
                    self._verify_with_coder(task),
                    self._verify_with_formatter(),
                    self._verify_with_researcher(task)
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
                    await self._update_progress(100, "Task completed successfully after refinements!")
                    self.task_status = "completed"
                    logger.info(f"Task execution completed after refinements: {task}")
                    await self._broadcast_update("task_complete", {"task": task})
                    return
        
        # If we get here, we've tried refinements but still have issues
        self.task_status = "partial"
        await self._update_progress(100, "Task partially completed with some unresolved issues.")
        logger.warning(f"Task execution partially completed with unresolved issues: {task}")
        await self._broadcast_update("task_partial", {"task": task})
    
    async def _update_progress(self, progress: float, message: str):
        """
        Update the progress of the current task.
        
        Args:
            progress: Progress percentage (0-100)
            message: Status message
        """
        # Update progress tracking
        self.current_execution["progress"] = progress
        
        # Broadcast status update
        await self._broadcast_update("status_update", {
            "message": message,
            "progress": progress
        })
        
        # Add random jitter to progress updates for better user experience
        jitter = random.uniform(0.5, 1.5)
        await asyncio.sleep(jitter)
    
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
