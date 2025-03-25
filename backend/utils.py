import os
import logging
import time
import re
import traceback
import json
import psutil
import platform
from typing import Dict, Any, List, Optional, Tuple

def setup_logging(log_dir: str = "logs", level: int = logging.INFO):
    """
    Set up enhanced logging configuration with rotating file handler.
    
    Args:
        log_dir: Directory for log files
        level: Logging level
        
    Returns:
        Logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up rotating file handler
    from logging.handlers import RotatingFileHandler
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            RotatingFileHandler(
                os.path.join(log_dir, "ai_agent.log"),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5
            ),
            logging.StreamHandler()
        ]
    )
    
    # Create agent-specific loggers
    loggers = {
        "agent": logging.getLogger("ai_agent"),
        "coder": logging.getLogger("ai_agent.coder"),
        "researcher": logging.getLogger("ai_agent.researcher"),
        "formatter": logging.getLogger("ai_agent.formatter"),
    }
    
    # Set up exception logging
    def exception_handler(exc_type, exc_value, exc_traceback):
        loggers["agent"].error("Uncaught exception", 
                      exc_info=(exc_type, exc_value, exc_traceback))
    
    import sys
    sys.excepthook = exception_handler
    
    # Log startup
    loggers["agent"].info("Enhanced logging initialized")
    
    return loggers["agent"]

def get_status(agent_coordinator, terminal_manager, todo_manager):
    """
    Get the current status of the agent and terminal with enhanced details.
    
    Args:
        agent_coordinator: AgentCoordinator instance
        terminal_manager: TerminalManager instance
        todo_manager: ToDoManager instance
        
    Returns:
        Dictionary with detailed status information
    """
    # Get active tasks
    active_tasks = todo_manager.get_active_tasks()
    
    # Get command history (last 10 commands)
    command_history = terminal_manager.get_command_history()[-10:] if terminal_manager.get_command_history() else []
    
    # Get output history (last 10 outputs)
    output_history = terminal_manager.get_output_history()[-10:] if terminal_manager.get_output_history() else []
    
    # Combine command and output history
    terminal_history = []
    for i in range(min(len(command_history), len(output_history))):
        terminal_history.append({
            "command": command_history[i],
            "output": output_history[i]
        })
    
    # Get knowledge graph data
    knowledge_graph_data = agent_coordinator.knowledge_graph.get_graph_visualization_data()
    
    # Get project structure
    project_structure = agent_coordinator.knowledge_graph.get_project_structure()
    
    # Get agent-specific statuses
    agent_statuses = {
        "coder": _get_agent_status(agent_coordinator.coder_agent),
        "researcher": _get_agent_status(agent_coordinator.researcher_agent),
        "formatter": _get_agent_status(agent_coordinator.formatter_agent)
    }
    
    # Get system status information
    system_status = _get_system_status(terminal_manager)
    
    return {
        "agent": {
            "status": agent_coordinator.task_status,
            "current_task": agent_coordinator.current_task,
            "model": agent_coordinator.model,
            "specialized_agents": agent_statuses,
            "activities": agent_statuses,  # Duplicate for frontend compatibility
            "progress": agent_coordinator.current_execution.get("progress", 0) if hasattr(agent_coordinator, "current_execution") else 0
        },
        "terminal": {
            "container_name": terminal_manager.terminal_container_name,
            "history": terminal_history
        },
        "todo": {
            "active_tasks": active_tasks
        },
        "knowledgeGraph": knowledge_graph_data,
        "projectStructure": project_structure,
        "system": system_status,
        "version": "2.1.0",
        "timestamp": time.time()
    }

def _get_system_status(terminal_manager):
    """
    Get system status information.
    
    Args:
        terminal_manager: TerminalManager instance
        
    Returns:
        Dictionary with system status information
    """
    # Get memory usage
    memory = psutil.virtual_memory()
    memory_usage = memory.percent
    
    # Get CPU usage
    cpu_usage = psutil.cpu_percent(interval=0.1)
    
    # Get disk usage
    disk = psutil.disk_usage('/')
    disk_usage = disk.percent
    
    # Check backend status
    backend_status = "healthy"  # Assume healthy by default
    
    # Check terminal status
    terminal_status = "unknown"
    try:
        # Check if terminal container is running
        if terminal_manager and hasattr(terminal_manager, "check_container_running"):
            terminal_running = terminal_manager.check_container_running()
            terminal_status = "healthy" if terminal_running else "error"
        else:
            terminal_status = "unknown"
    except Exception:
        terminal_status = "error"
    
    # Check Redis status
    redis_status = "unknown"
    try:
        import redis
        r = redis.Redis(host='redis', port=6379, db=0)
        r.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "error"
    
    return {
        "backend": {
            "status": backend_status,
            "uptime": time.time() - psutil.boot_time()
        },
        "terminal": {
            "status": terminal_status
        },
        "redis": {
            "status": redis_status
        },
        "memory": {
            "usage": memory_usage,
            "total": memory.total,
            "available": memory.available
        },
        "cpu": {
            "usage": cpu_usage,
            "cores": psutil.cpu_count()
        },
        "disk": {
            "usage": disk_usage,
            "total": disk.total,
            "free": disk.free
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version()
        }
    }

def _get_agent_status(agent):
    """
    Get status information for a specialized agent.
    
    Args:
        agent: Specialized agent instance
        
    Returns:
        Dictionary with agent status information
    """
    # Extract basic information available in all agent types
    status = {
        "model": agent.model,
        "status": "idle"  # Default status
    }
    
    # Add any agent-specific status if available
    if hasattr(agent, "status"):
        status["status"] = agent.status
    
    if hasattr(agent, "current_task"):
        status["current_task"] = agent.current_task
        
    if hasattr(agent, "last_activity"):
        status["lastActivity"] = agent.last_activity
        
    if hasattr(agent, "current_action"):
        status["currentAction"] = agent.current_action
    
    return status

def parse_error_output(output: str) -> Dict[str, Any]:
    """
    Enhanced error output parsing with improved detection capabilities.
    
    Args:
        output: Terminal output string
        
    Returns:
        Dictionary with parsed error information
    """
    error_info = {
        "error_type": "Unknown",
        "error_message": "",
        "line_number": None,
        "file_name": None,
        "error_context": [],
        "suggestions": []
    }
    
    # Use regex to find patterns with improved accuracy
    
    # Check for Python traceback
    if "Traceback (most recent call last)" in output:
        error_info["error_type"] = "Python Exception"
        
        # Extract the full traceback
        traceback_match = re.search(r"Traceback \(most recent call last\):(.+?)(?:\n\n|\Z)", 
                                   output, re.DOTALL)
        if traceback_match:
            traceback_text = traceback_match.group(1).strip()
            error_info["error_context"].append(traceback_text)
        
        # Extract the exception type and message
        exception_match = re.search(r"([A-Za-z]+Error|Exception): (.+?)(?:\n|$)", output)
        if exception_match:
            error_info["error_type"] = exception_match.group(1)
            error_info["error_message"] = exception_match.group(2)
            
            # Suggest fixes based on the error type
            if "ImportError" in error_info["error_type"] or "ModuleNotFoundError" in error_info["error_type"]:
                # Extract module name
                module_match = re.search(r"No module named '([^']+)'", error_info["error_message"])
                if module_match:
                    module_name = module_match.group(1)
                    error_info["suggestions"].append(f"Install the missing module: pip install {module_name}")
            
            elif "SyntaxError" in error_info["error_type"]:
                error_info["suggestions"].append("Check for missing brackets, parentheses, or quotes")
            
            elif "TypeError" in error_info["error_type"]:
                error_info["suggestions"].append("Check the types of the arguments passed to functions")
            
            elif "IndexError" in error_info["error_type"] or "KeyError" in error_info["error_type"]:
                error_info["suggestions"].append("Verify the index or key exists before accessing it")
            
            elif "AttributeError" in error_info["error_type"]:
                error_info["suggestions"].append("Ensure the object has the attribute you're trying to access")
        
        # Extract file name and line number
        file_line_match = re.findall(r'File "([^"]+)", line (\d+)', output)
        if file_line_match:
            last_match = file_line_match[-1]  # Get the last (most relevant) match
            error_info["file_name"] = last_match[0]
            error_info["line_number"] = int(last_match[1])
    
    # Check for JavaScript/Node.js errors
    elif any(js_error in output for js_error in ["ReferenceError", "TypeError", "SyntaxError", "Error:"]):
        error_info["error_type"] = "JavaScript Error"
        
        # Extract the error message
        js_error_match = re.search(r"(ReferenceError|TypeError|SyntaxError|Error): (.+?)(?:\n|$)", output)
        if js_error_match:
            error_info["error_type"] = js_error_match.group(1)
            error_info["error_message"] = js_error_match.group(2)
            
            # Get file and line info
            js_file_line_match = re.search(r"at .+ \(([^:]+):(\d+):(\d+)\)", output)
            if js_file_line_match:
                error_info["file_name"] = js_file_line_match.group(1)
                error_info["line_number"] = int(js_file_line_match.group(2))
            
            # Add suggestions based on error type
            if "ReferenceError" in error_info["error_type"]:
                error_info["suggestions"].append("Check if all variables are properly defined before use")
            elif "TypeError" in error_info["error_type"]:
                error_info["suggestions"].append("Verify you're using the correct data types")
            elif "SyntaxError" in error_info["error_type"]:
                error_info["suggestions"].append("Check for syntax errors like missing brackets or semicolons")
    
    # Check for npm/yarn errors
    elif "npm ERR!" in output or "yarn error" in output:
        error_info["error_type"] = "Package Manager Error"
        
        # Extract error message
        npm_error_match = re.search(r"npm ERR! (.+?)(?:\n|$)", output)
        yarn_error_match = re.search(r"yarn error (.+?)(?:\n|$)", output)
        
        if npm_error_match:
            error_info["error_message"] = npm_error_match.group(1)
        elif yarn_error_match:
            error_info["error_message"] = yarn_error_match.group(1)
            
        # Add suggestions
        error_info["suggestions"].append("Check package.json for dependency issues")
        error_info["suggestions"].append("Try clearing node_modules and reinstalling dependencies")
    
    # Check for Docker errors
    elif "docker:" in output.lower() and ("error" in output.lower() or "failed" in output.lower()):
        error_info["error_type"] = "Docker Error"
        
        # Extract error message
        docker_error_match = re.search(r"(?:docker:|error:) (.+?)(?:\n|$)", output, re.IGNORECASE)
        if docker_error_match:
            error_info["error_message"] = docker_error_match.group(1)
            
        # Add suggestions
        error_info["suggestions"].append("Check Docker daemon status")
        error_info["suggestions"].append("Verify Docker container configuration")
    
    # If we couldn't identify a specific error type but found an error message
    elif "error" in output.lower() or "exception" in output.lower():
        # Extract the line with the error
        error_line_match = re.search(r"(?:error|exception):? (.+?)(?:\n|$)", output, re.IGNORECASE)
        if error_line_match:
            error_info["error_message"] = error_line_match.group(1)
    
    return error_info
