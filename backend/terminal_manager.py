"""
Enhanced Terminal Manager module for the AI Agent Terminal Interface.
Interfaces with the containerized terminal environment with improved streaming
and timeout handling capabilities.
"""

import os
import logging
import asyncio
import time
import re
from typing import Dict, Any, Tuple, List, Optional, Callable, Union
import json
import shlex

logger = logging.getLogger(__name__)

class TerminalManager:
    """
    Manages interactions with the containerized terminal environment.
    
    This enhanced version provides:
    - Improved streaming of command output in real-time
    - Handling of long-running processes without timeouts
    - Better error detection and recovery
    - Command chunking for large operations
    - Automatic dependency installation
    - Background task execution
    """
    
    def __init__(
        self, 
        terminal_container_name: str = "ai_agent_terminal",
        command_timeout: int = 300,  # 5 minutes default timeout
        streaming_interval: float = 0.5  # Stream updates every 0.5 seconds
    ):
        """
        Initialize the Terminal Manager.
        
        Args:
            terminal_container_name: Name of the Docker container running the terminal
            command_timeout: Default timeout for commands in seconds
            streaming_interval: Interval for streaming command output in seconds
        """
        self.terminal_container_name = terminal_container_name
        self.command_timeout = command_timeout
        self.streaming_interval = streaming_interval
        self.broadcast_message = None
        self.command_history = []
        self.output_history = []
        
        # Track running commands
        self.running_processes = {}
        
        # Track installed packages to avoid redundant installations
        self.installed_packages = {
            "pip": set(),
            "npm": set()
        }
        
        # Keep track of the working directory
        self.working_directory = "/workspace"
        
        logger.info(f"Enhanced Terminal Manager initialized with container: {terminal_container_name}")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages to WebSocket clients."""
        self.broadcast_message = broadcast_function
    
    async def initialize(self):
        """Initialize the terminal environment."""
        try:
            # Check if the terminal container is running
            result = await self._run_local_command(f"docker ps --filter name={self.terminal_container_name} --format '{{{{.Names}}}}'")
            
            if self.terminal_container_name not in result:
                logger.warning(f"Terminal container '{self.terminal_container_name}' not found running")
                logger.info("Terminal container will be started by Docker Compose")
            else:
                logger.info(f"Terminal container '{self.terminal_container_name}' is running")
            
            # Create workspace directory in the container
            await self.execute_command("mkdir -p /workspace")
            
            # Change to the workspace directory
            await self.execute_command("cd /workspace")
            
            # Install basic development tools
            await self._broadcast_terminal_update("status", {
                "message": "Installing basic development tools..."
            })
            
            # Run apt-get update first
            await self.execute_command("apt-get update")
            
            # Install basic tools
            basic_tools = [
                "python3-pip",
                "git",
                "curl",
                "wget",
                "build-essential",
                "nodejs",
                "npm"
            ]
            
            # Install tools in the background to avoid blocking initialization
            asyncio.create_task(self._install_basic_tools(basic_tools))
            
            # Set up Python virtual environment
            asyncio.create_task(self._setup_python_environment())
            
            logger.info("Terminal environment initialized")
            
        except Exception as e:
            logger.error(f"Error initializing terminal environment: {str(e)}")
            raise
    
    async def _install_basic_tools(self, tools: List[str]):
        """
        Install basic development tools in the background.
        
        Args:
            tools: List of packages to install
        """
        for tool in tools:
            try:
                await self.execute_command(f"apt-get install -y {tool}")
            except Exception as e:
                logger.error(f"Error installing {tool}: {str(e)}")
    
    async def _setup_python_environment(self):
        """Set up a Python virtual environment for isolation."""
        try:
            # Install virtualenv
            await self.execute_command("pip3 install virtualenv")
            
            # Create virtual environment if it doesn't exist
            await self.execute_command("if [ ! -d /workspace/venv ]; then virtualenv /workspace/venv; fi")
            
            # Create a .bashrc with automatic virtual environment activation
            bashrc_content = """
            if [ -d "/workspace/venv" ]; then
                source /workspace/venv/bin/activate
            fi
            """
            
            # Write to .bashrc
            await self.execute_command(f"echo '{bashrc_content}' > ~/.bashrc")
            
            logger.info("Python virtual environment setup complete")
        except Exception as e:
            logger.error(f"Error setting up Python environment: {str(e)}")
    
    async def shutdown(self):
        """Clean up resources on shutdown."""
        logger.info("Terminal Manager shutting down")
        
        # Stop any running background processes
        for process_id, process_info in list(self.running_processes.items()):
            if process_info.get("process"):
                try:
                    process_info["process"].terminate()
                    await process_info["process"].wait()
                except Exception as e:
                    logger.error(f"Error terminating process {process_id}: {str(e)}")
        
        self.running_processes.clear()
    
    async def execute_command(
        self, 
        command: str, 
        timeout: Optional[int] = None,
        stream_output: bool = True,
        background: bool = False,
        working_dir: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Execute a command in the terminal container with enhanced streaming and timeout handling.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds, or None to use default
            stream_output: Whether to stream output in real-time
            background: Whether to run the command in the background
            working_dir: Working directory to use, or None to use current
            
        Returns:
            Tuple of (success, output)
        """
        try:
            # Store the working directory if provided
            if working_dir:
                self.working_directory = working_dir
            
            # Add command to history
            self.command_history.append(command)
            
            # Broadcast command execution
            await self._broadcast_terminal_update("command", {"command": command})
            
            # Clean up the command
            cleaned_command = self._clean_command(command)
            
            # Check for cd command to update working directory
            if cleaned_command.startswith("cd "):
                return await self._handle_cd_command(cleaned_command)
            
            # Check for special commands
            if cleaned_command.startswith("pip install ") or cleaned_command.startswith("pip3 install "):
                return await self._handle_pip_install(cleaned_command)
            
            if cleaned_command.startswith("npm install ") or cleaned_command.startswith("yarn add "):
                return await self._handle_npm_install(cleaned_command)
            
            # Prepare the docker command with current working directory
            docker_command = self._prepare_docker_command(cleaned_command, working_dir)
            
            # For streaming output, we need to use a different approach
            if stream_output:
                return await self._execute_with_streaming(docker_command, timeout or self.command_timeout, background)
            else:
                # For non-streaming output, use the direct approach
                output = await self._run_local_command(docker_command, timeout or self.command_timeout)
                
                # Add output to history
                self.output_history.append(output)
                
                # Determine success based on exit code and output content
                success = not self._detect_error_in_output(output)
                
                # Broadcast command output
                await self._broadcast_terminal_update("output", {
                    "command": command,
                    "output": output,
                    "success": success
                })
                
                logger.info(f"Executed command: {command}")
                if not success:
                    logger.warning(f"Command execution failed: {command}")
                    logger.debug(f"Output: {output}")
                
                return success, output
                
        except asyncio.TimeoutError:
            error_message = f"Command '{command}' timed out after {timeout or self.command_timeout} seconds"
            logger.error(error_message)
            
            # Broadcast timeout error
            await self._broadcast_terminal_update("error", {
                "command": command,
                "error": error_message,
                "type": "timeout"
            })
            
            return False, error_message
        
        except Exception as e:
            error_message = f"Error executing command '{command}': {str(e)}"
            logger.error(error_message)
            
            # Broadcast error
            await self._broadcast_terminal_update("error", {
                "command": command,
                "error": error_message,
                "type": "exception"
            })
            
            return False, error_message
    
    def _clean_command(self, command: str) -> str:
        """
        Clean up a command for execution.
        
        Args:
            command: Command to clean up
            
        Returns:
            Cleaned command
        """
        # Remove any leading/trailing whitespace
        command = command.strip()
        
        # Remove any line continuations
        command = command.replace("\\\n", " ")
        
        # Replace multiple spaces with a single space
        command = re.sub(r'\s+', ' ', command)
        
        return command
    
    def _prepare_docker_command(self, command: str, working_dir: Optional[str] = None) -> str:
        """
        Prepare a docker command with the proper working directory.
        
        Args:
            command: Command to execute
            working_dir: Working directory to use, or None to use the current one
            
        Returns:
            Docker command string
        """
        # Use the specified working directory or the current one
        cwd = working_dir or self.working_directory
        
        # Escape single quotes in the command for bash
        escaped_command = command.replace("'", "'\\''")
        
        # Construct the docker command with working directory
        return f"docker exec -w {cwd} {self.terminal_container_name} bash -c '{escaped_command}'"
    
    async def _handle_cd_command(self, command: str) -> Tuple[bool, str]:
        """
        Handle the cd command by updating the working directory.
        
        Args:
            command: cd command
            
        Returns:
            Tuple of (success, output)
        """
        # Extract the target directory
        target_dir = command[3:].strip()
        
        # Handle special cases
        if target_dir == "..":
            # Go up one directory
            self.working_directory = os.path.dirname(self.working_directory)
            output = f"Changed directory to {self.working_directory}"
            await self._broadcast_terminal_update("output", {
                "command": command,
                "output": output,
                "success": True
            })
            return True, output
        
        elif target_dir.startswith("/"):
            # Absolute path
            self.working_directory = target_dir
            output = f"Changed directory to {self.working_directory}"
            await self._broadcast_terminal_update("output", {
                "command": command,
                "output": output,
                "success": True
            })
            return True, output
        
        else:
            # Relative path
            new_dir = os.path.join(self.working_directory, target_dir)
            
            # Check if the directory exists
            check_cmd = f"docker exec {self.terminal_container_name} bash -c '[ -d {new_dir} ] && echo exists'"
            result = await self._run_local_command(check_cmd)
            
            if "exists" in result:
                self.working_directory = new_dir
                output = f"Changed directory to {self.working_directory}"
                await self._broadcast_terminal_update("output", {
                    "command": command,
                    "output": output,
                    "success": True
                })
                return True, output
            else:
                output = f"Directory not found: {new_dir}"
                await self._broadcast_terminal_update("output", {
                    "command": command,
                    "output": output,
                    "success": False
                })
                return False, output
    
    async def _handle_pip_install(self, command: str) -> Tuple[bool, str]:
        """
        Handle pip install commands with package tracking.
        
        Args:
            command: pip install command
            
        Returns:
            Tuple of (success, output)
        """
        # Extract the package names
        parts = command.split()
        if "-r" in parts:
            # Requirements file, just execute normally
            return await self._execute_with_streaming(
                self._prepare_docker_command(command),
                self.command_timeout,
                False
            )
        
        # Extract packages, handling options
        packages = []
        i = 0
        while i < len(parts):
            if parts[i] in ["pip", "pip3", "install"]:
                i += 1
                continue
            if parts[i].startswith("-"):
                # Skip option and its value if it has one
                if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    i += 2
                else:
                    i += 1
                continue
            packages.append(parts[i])
            i += 1
        
        # Check which packages are already installed
        new_packages = [pkg for pkg in packages if pkg not in self.installed_packages["pip"]]
        
        if not new_packages:
            # All packages already installed
            output = f"All packages already installed: {', '.join(packages)}"
            await self._broadcast_terminal_update("output", {
                "command": command,
                "output": output,
                "success": True
            })
            return True, output
        
        # Install only the new packages
        install_cmd = f"pip install {' '.join(new_packages)}"
        docker_cmd = self._prepare_docker_command(install_cmd)
        
        success, output = await self._execute_with_streaming(docker_cmd, self.command_timeout, False)
        
        if success:
            # Add packages to installed set
            self.installed_packages["pip"].update(new_packages)
        
        return success, output
    
    async def _handle_npm_install(self, command: str) -> Tuple[bool, str]:
        """
        Handle npm install commands with package tracking.
        
        Args:
            command: npm install command
            
        Returns:
            Tuple of (success, output)
        """
        # Extract the package names
        parts = command.split()
        is_yarn = "yarn" in parts[0]
        
        # Handle different package manager syntax
        if is_yarn:
            install_cmd = "add"
            save_dev_flag = "--dev"
        else:
            install_cmd = "install"
            save_dev_flag = "--save-dev"
        
        # Check for global flag or save-dev
        is_global = "-g" in parts or "--global" in parts
        is_dev = "--save-dev" in parts or "-D" in parts or save_dev_flag in parts
        
        if is_global:
            # Global installs, just execute normally
            return await self._execute_with_streaming(
                self._prepare_docker_command(command),
                self.command_timeout,
                False
            )
        
        # Extract packages, handling options
        packages = []
        i = 0
        while i < len(parts):
            if parts[i] in ["npm", "yarn", install_cmd, "add"]:
                i += 1
                continue
            if parts[i].startswith("-"):
                # Skip option and its value if it has one
                if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                    i += 2
                else:
                    i += 1
                continue
            packages.append(parts[i])
            i += 1
        
        # Check which packages are already installed
        new_packages = [pkg for pkg in packages if pkg not in self.installed_packages["npm"]]
        
        if not new_packages:
            # All packages already installed
            output = f"All packages already installed: {', '.join(packages)}"
            await self._broadcast_terminal_update("output", {
                "command": command,
                "output": output,
                "success": True
            })
            return True, output
        
        # Install only the new packages
        if is_yarn:
            install_cmd = f"yarn add {' '.join(new_packages)}"
            if is_dev:
                install_cmd += " --dev"
        else:
            install_cmd = f"npm install {' '.join(new_packages)}"
            if is_dev:
                install_cmd += " --save-dev"
        
        docker_cmd = self._prepare_docker_command(install_cmd)
        
        success, output = await self._execute_with_streaming(docker_cmd, self.command_timeout, False)
        
        if success:
            # Add packages to installed set
            self.installed_packages["npm"].update(new_packages)
        
        return success, output
    
    async def _execute_with_streaming(
        self, 
        docker_command: str, 
        timeout: int,
        background: bool
    ) -> Tuple[bool, str]:
        """
        Execute a command with real-time output streaming.
        
        Args:
            docker_command: Docker command to execute
            timeout: Timeout in seconds
            background: Whether to run in the background
            
        Returns:
            Tuple of (success, output)
        """
        # Generate a unique ID for this process
        process_id = f"process_{int(time.time())}_{hash(docker_command) % 10000}"
        
        # Start the process
        process = await asyncio.create_subprocess_shell(
            docker_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Store the process info
        self.running_processes[process_id] = {
            "process": process,
            "command": docker_command,
            "start_time": time.time(),
            "background": background,
            "timeout": timeout,
            "output": []
        }
        
        # If background, start a task to monitor and return immediately
        if background:
            asyncio.create_task(self._monitor_background_process(process_id))
            return True, f"Started background process {process_id}"
        
        # Handle foreground process with timeout
        try:
            full_output = await asyncio.wait_for(
                self._stream_process_output(process_id),
                timeout=timeout
            )
            
            # Remove from running processes
            if process_id in self.running_processes:
                del self.running_processes[process_id]
            
            # Add output to history
            self.output_history.append(full_output)
            
            # Determine success based on exit code and output content
            success = process.returncode == 0 and not self._detect_error_in_output(full_output)
            
            # Broadcast final output
            await self._broadcast_terminal_update("output", {
                "command": docker_command,
                "output": full_output,
                "success": success
            })
            
            return success, full_output
            
        except asyncio.TimeoutError:
            # Kill the process
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
            
            # Remove from running processes
            if process_id in self.running_processes:
                output_so_far = "".join(self.running_processes[process_id]["output"])
                del self.running_processes[process_id]
            else:
                output_so_far = ""
            
            # Create timeout message
            timeout_message = f"Command timed out after {timeout} seconds\n{output_so_far}"
            
            # Add to output history
            self.output_history.append(timeout_message)
            
            # Broadcast timeout
            await self._broadcast_terminal_update("error", {
                "command": docker_command,
                "error": timeout_message,
                "type": "timeout"
            })
            
            return False, timeout_message
    
    async def _stream_process_output(self, process_id: str) -> str:
        """
        Stream output from a process in real-time.
        
        Args:
            process_id: ID of the process to monitor
            
        Returns:
            Complete output as a string
        """
        if process_id not in self.running_processes:
            return ""
        
        process_info = self.running_processes[process_id]
        process = process_info["process"]
        
        # Track accumulated output
        accumulated_output = []
        last_update_time = time.time()
        
        # Stream output using a loop
        while True:
            # Check for new stdout and stderr data
            stdout_chunk = await process.stdout.read(1024)
            stderr_chunk = await process.stderr.read(1024)
            
            if stdout_chunk:
                # Decode and add to output
                stdout_text = stdout_chunk.decode('utf-8', errors='replace')
                accumulated_output.append(stdout_text)
                process_info["output"].append(stdout_text)
                
                # Check if it's time to send an update
                current_time = time.time()
                if current_time - last_update_time >= self.streaming_interval:
                    # Broadcast streaming update
                    await self._broadcast_terminal_update("streaming", {
                        "command": process_info["command"],
                        "output": stdout_text,
                        "process_id": process_id
                    })
                    last_update_time = current_time
            
            if stderr_chunk:
                # Decode and add to output
                stderr_text = stderr_chunk.decode('utf-8', errors='replace')
                accumulated_output.append(stderr_text)
                process_info["output"].append(stderr_text)
                
                # Check if it's time to send an update
                current_time = time.time()
                if current_time - last_update_time >= self.streaming_interval:
                    # Broadcast streaming update
                    await self._broadcast_terminal_update("streaming", {
                        "command": process_info["command"],
                        "error": stderr_text,
                        "process_id": process_id
                    })
                    last_update_time = current_time
            
            # Check if process has finished
            if stdout_chunk == b'' and stderr_chunk == b'' and process.returncode is not None:
                break
            
            # If no output, sleep briefly to avoid busy waiting
            if not stdout_chunk and not stderr_chunk:
                await asyncio.sleep(0.1)
        
        # Return full output
        return "".join(accumulated_output)
    
    async def _monitor_background_process(self, process_id: str):
        """
        Monitor a background process until completion.
        
        Args:
            process_id: ID of the process to monitor
        """
        if process_id not in self.running_processes:
            return
        
        process_info = self.running_processes[process_id]
        process = process_info["process"]
        timeout = process_info["timeout"]
        
        # Start time
        start_time = time.time()
        
        # Monitor the process with a timeout
        try:
            # Stream the output
            full_output = await asyncio.wait_for(
                self._stream_process_output(process_id),
                timeout=timeout
            )
            
            # Process completed successfully
            success = process.returncode == 0 and not self._detect_error_in_output(full_output)
            
            # Broadcast completion
            await self._broadcast_terminal_update("background_complete", {
                "command": process_info["command"],
                "output": full_output,
                "success": success,
                "process_id": process_id,
                "duration": time.time() - start_time
            })
            
        except asyncio.TimeoutError:
            # Kill the process
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
            
            # Create timeout message
            timeout_message = f"Background process timed out after {timeout} seconds"
            
            # Broadcast timeout
            await self._broadcast_terminal_update("background_timeout", {
                "command": process_info["command"],
                "error": timeout_message,
                "process_id": process_id,
                "duration": time.time() - start_time
            })
        
        except Exception as e:
            # Handle any other exceptions
            error_message = f"Error monitoring background process: {str(e)}"
            logger.error(error_message)
            
            # Broadcast error
            await self._broadcast_terminal_update("background_error", {
                "command": process_info["command"],
                "error": error_message,
                "process_id": process_id,
                "duration": time.time() - start_time
            })
        
        finally:
            # Remove from running processes
            if process_id in self.running_processes:
                del self.running_processes[process_id]
    
    def _detect_error_in_output(self, output: str) -> bool:
        """
        Detect if an output contains error indicators.
        
        Args:
            output: Command output
            
        Returns:
            True if errors detected, False otherwise
        """
        # Check for common error indicators
        error_keywords = [
            "error:", "Error:", "ERROR:",
            "exception:", "Exception:", "EXCEPTION:",
            "failed:", "Failed:", "FAILED:",
            "command not found",
            "No such file or directory",
            "Permission denied",
            "fatal:",
            "Traceback (most recent call last)"
        ]
        
        # Check if any error keyword is in the output
        return any(keyword in output for keyword in error_keywords)
    
    async def execute_interactive_command(
        self, 
        command: str, 
        inputs: List[str] = None,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Execute an interactive command with predefined inputs.
        
        Args:
            command: Command to execute
            inputs: List of inputs to provide to the command
            timeout: Timeout in seconds, or None to use default
            working_dir: Working directory to use, or None to use current
            
        Returns:
            Tuple of (success, output)
        """
        if inputs is None:
            inputs = []
        
        try:
            # Store the working directory if provided
            if working_dir:
                self.working_directory = working_dir
            
            # Add command to history
            self.command_history.append(command)
            
            # Broadcast command execution
            await self._broadcast_terminal_update("command", {"command": command})
            
            # Prepare the input string
            input_string = "\\n".join(inputs) + "\\n" if inputs else ""
            
            # Prepare the docker command with current working directory
            cwd = working_dir or self.working_directory
            docker_command = f"echo -e '{input_string}' | docker exec -i -w {cwd} {self.terminal_container_name} bash -c '{command}'"
            
            # Execute the command with a timeout
            output = await self._run_local_command(docker_command, timeout or self.command_timeout)
            
            # Add output to history
            self.output_history.append(output)
            
            # Determine success based on exit code and output content
            success = not self._detect_error_in_output(output)
            
            # Broadcast command output
            await self._broadcast_terminal_update("output", {
                "command": command,
                "output": output,
                "success": success
            })
            
            logger.info(f"Executed interactive command: {command}")
            if not success:
                logger.warning(f"Interactive command execution failed: {command}")
                logger.debug(f"Output: {output}")
            
            return success, output
            
        except asyncio.TimeoutError:
            error_message = f"Interactive command '{command}' timed out after {timeout or self.command_timeout} seconds"
            logger.error(error_message)
            
            # Broadcast timeout error
            await self._broadcast_terminal_update("error", {
                "command": command,
                "error": error_message,
                "type": "timeout"
            })
            
            return False, error_message
        
        except Exception as e:
            error_message = f"Error executing interactive command '{command}': {str(e)}"
            logger.error(error_message)
            
            # Broadcast error
            await self._broadcast_terminal_update("error", {
                "command": command,
                "error": error_message,
                "type": "exception"
            })
            
            return False, error_message
    
    async def copy_file_to_container(self, local_path: str, container_path: str) -> bool:
        """
        Copy a file from the local filesystem to the terminal container.
        
        Args:
            local_path: Path to the file on the local filesystem
            container_path: Path where the file should be copied in the container
            
        Returns:
            True if successful, False otherwise
        """
        try:
            command = f"docker cp {local_path} {self.terminal_container_name}:{container_path}"
            output = await self._run_local_command(command)
            
            logger.info(f"Copied file from {local_path} to {container_path} in container")
            return True
            
        except Exception as e:
            logger.error(f"Error copying file to container: {str(e)}")
            return False
    
    async def copy_file_from_container(self, container_path: str, local_path: str) -> bool:
        """
        Copy a file from the terminal container to the local filesystem.
        
        Args:
            container_path: Path to the file in the container
            local_path: Path where the file should be copied on the local filesystem
            
        Returns:
            True if successful, False otherwise
        """
        try:
            command = f"docker cp {self.terminal_container_name}:{container_path} {local_path}"
            output = await self._run_local_command(command)
            
            logger.info(f"Copied file from {container_path} in container to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying file from container: {str(e)}")
            return False
    
    async def check_file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in the container.
        
        Args:
            file_path: Path to the file in the container
            
        Returns:
            True if the file exists, False otherwise
        """
        try:
            command = f"docker exec {self.terminal_container_name} bash -c '[ -f {file_path} ] && echo exists'"
            result = await self._run_local_command(command)
            
            return "exists" in result
            
        except Exception as e:
            logger.error(f"Error checking if file exists: {str(e)}")
            return False
    
    async def check_directory_exists(self, dir_path: str) -> bool:
        """
        Check if a directory exists in the container.
        
        Args:
            dir_path: Path to the directory in the container
            
        Returns:
            True if the directory exists, False otherwise
        """
        try:
            command = f"docker exec {self.terminal_container_name} bash -c '[ -d {dir_path} ] && echo exists'"
            result = await self._run_local_command(command)
            
            return "exists" in result
            
        except Exception as e:
            logger.error(f"Error checking if directory exists: {str(e)}")
            return False
    
    async def list_directory(self, dir_path: str) -> List[str]:
        """
        List the contents of a directory in the container.
        
        Args:
            dir_path: Path to the directory in the container
            
        Returns:
            List of filenames in the directory
        """
        try:
            command = f"docker exec {self.terminal_container_name} bash -c 'ls -1a {dir_path}'"
            result = await self._run_local_command(command)
            
            # Split by newlines and filter out empty lines
            files = [line.strip() for line in result.split('\n') if line.strip()]
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing directory: {str(e)}")
            return []
    
    async def read_file(self, file_path: str) -> Optional[str]:
        """
        Read the contents of a file in the container.
        
        Args:
            file_path: Path to the file in the container
            
        Returns:
            File contents as a string, or None if an error occurred
        """
        try:
            command = f"docker exec {self.terminal_container_name} bash -c 'cat {file_path}'"
            result = await self._run_local_command(command)
            
            return result
            
        except Exception as e:
            logger.error(f"Error reading file: {str(e)}")
            return None
    
    async def write_file(self, file_path: str, content: str) -> bool:
        """
        Write content to a file in the container.
        
        Args:
            file_path: Path to the file in the container
            content: Content to write to the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            dir_path = os.path.dirname(file_path)
            if dir_path:
                await self.execute_command(f"mkdir -p {dir_path}")
            
            # Write content to file
            # Escape single quotes in the content
            escaped_content = content.replace("'", "'\\''")
            
            command = f"docker exec {self.terminal_container_name} bash -c 'echo -e '\\''{escaped_content}\\'' > {file_path}'"
            await self._run_local_command(command)
            
            # Verify that the file was created
            return await self.check_file_exists(file_path)
            
        except Exception as e:
            logger.error(f"Error writing to file: {str(e)}")
            return False
    
    def get_command_history(self) -> List[str]:
        """
        Get the command execution history.
        
        Returns:
            List of executed commands
        """
        return self.command_history
    
    def get_output_history(self) -> List[str]:
        """
        Get the command output history.
        
        Returns:
            List of command outputs
        """
        return self.output_history
    
    def get_running_processes(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently running processes.
        
        Returns:
            Dictionary mapping process IDs to process information
        """
        # Return a copy without the actual process objects
        return {
            pid: {
                k: v for k, v in info.items() if k != "process"
            }
            for pid, info in self.running_processes.items()
        }
    
    async def _run_local_command(self, command: str, timeout: Optional[int] = None) -> str:
        """
        Run a command on the local system with timeout.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds, or None for no timeout
            
        Returns:
            Command output
        """
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            if timeout is not None:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            else:
                stdout, stderr = await process.communicate()
            
            if process.returncode != 0 and stderr:
                logger.warning(f"Command '{command}' returned non-zero exit code {process.returncode}")
                logger.debug(f"stderr: {stderr.decode()}")
            
            # Combine stdout and stderr for complete output
            output = stdout.decode('utf-8', errors='replace')
            if stderr:
                error_output = stderr.decode('utf-8', errors='replace')
                if error_output:
                    output += f"\n{error_output}"
            
            return output
            
        except asyncio.TimeoutError:
            try:
                # Kill the process on timeout
                process.terminate()
                await process.wait()
            except Exception:
                pass
            
            raise
    
    async def _broadcast_terminal_update(self, update_type: str, data: Dict[str, Any]):
        """
        Broadcast a terminal update to all connected WebSocket clients.
        
        Args:
            update_type: Type of update (e.g., "command", "output", "error")
            data: Update data
        """
        if self.broadcast_message:
            message = {
                "type": f"terminal_{update_type}",
                "timestamp": time.time(),
                "data": data
            }
            await self.broadcast_message(message)