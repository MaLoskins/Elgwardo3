"""
ToDo Manager module for the AI Agent Terminal Interface.
Handles creation and iterative updates of the "ToDo.md" file.
"""

import os
import logging
import time
from typing import Dict, Any, List, Optional, Callable
import asyncio

logger = logging.getLogger(__name__)

class ToDoManager:
    """
    Manages the creation and updates of the ToDo.md file for task tracking.
    
    The ToDo.md file serves as a persistent log of tasks, errors, and progress
    throughout the development process.
    """
    
    def __init__(self, todo_file_path: str = "logs/ToDo.md"):
        """
        Initialize the ToDo Manager.
        
        Args:
            todo_file_path: Path to the ToDo.md file (relative to backend directory)
        """
        self.todo_file_path = todo_file_path
        self.broadcast_message = None
        self.task_counter = 0
        
        # Ensure the logs directory exists
        os.makedirs(os.path.dirname(todo_file_path), exist_ok=True)
        
        logger.info(f"ToDo Manager initialized with file path: {todo_file_path}")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages to WebSocket clients."""
        self.broadcast_message = broadcast_function
    
    def initialize(self):
        """Initialize the ToDo.md file if it doesn't exist."""
        if not os.path.exists(self.todo_file_path):
            with open(self.todo_file_path, 'w') as f:
                f.write("# AI Agent Terminal Interface - ToDo List\n\n")
                f.write("## Active Tasks\n\n")
                f.write("## Completed Tasks\n\n")
                f.write("## Errors and Issues\n\n")
            
            logger.info(f"Created new ToDo.md file at {self.todo_file_path}")
        else:
            logger.info(f"ToDo.md file already exists at {self.todo_file_path}")
            
    def get_todo_content(self) -> str:
        """
        Get the current content of the ToDo.md file.
        
        Returns:
            String containing the current content of the ToDo.md file
        """
        try:
            with open(self.todo_file_path, 'r') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"Error reading ToDo.md file: {str(e)}")
            return "Error reading ToDo.md file"
    
    def add_task(self, task_description: str) -> str:
        """
        Add a new task to the ToDo.md file.
        
        Args:
            task_description: Description of the task
            
        Returns:
            Task ID
        """
        self.task_counter += 1
        task_id = f"task_{self.task_counter}_{int(time.time())}"
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        with open(self.todo_file_path, 'r') as f:
            content = f.read()
        
        # Find the Active Tasks section
        active_tasks_index = content.find("## Active Tasks")
        next_section_index = content.find("##", active_tasks_index + 1)
        
        if active_tasks_index == -1:
            # If Active Tasks section doesn't exist, add it
            content += "\n## Active Tasks\n\n"
            active_tasks_index = content.find("## Active Tasks")
            next_section_index = len(content)
        
        # Insert the new task
        task_entry = f"### [{task_id}] {task_description}\n"
        task_entry += f"- **Status:** In Progress\n"
        task_entry += f"- **Created:** {timestamp}\n"
        task_entry += f"- **Updated:** {timestamp}\n\n"
        
        # Insert at the beginning of the Active Tasks section
        insert_position = content.find("\n", active_tasks_index) + 1
        updated_content = content[:insert_position] + task_entry + content[insert_position:]
        
        with open(self.todo_file_path, 'w') as f:
            f.write(updated_content)
        
        logger.info(f"Added task {task_id}: {task_description}")
        
        # Broadcast update
        asyncio.create_task(self._broadcast_todo_update("task_added", {
            "task_id": task_id,
            "description": task_description
        }))
        
        return task_id
    
    def add_subtask(self, task_id: str, subtask_description: str, completed: bool = False):
        """
        Add a subtask to an existing task.
        
        Args:
            task_id: ID of the parent task
            subtask_description: Description of the subtask
            completed: Whether the subtask is already completed
        """
        with open(self.todo_file_path, 'r') as f:
            content = f.read()
        
        # Find the task
        task_marker = f"### [{task_id}]"
        task_index = content.find(task_marker)
        
        if task_index == -1:
            logger.warning(f"Task {task_id} not found in ToDo.md")
            return
        
        # Find the end of the task section
        next_task_index = content.find("###", task_index + 1)
        if next_task_index == -1:
            next_task_index = len(content)
        
        # Check if there's already a subtasks list
        subtasks_marker = "#### Subtasks:"
        subtasks_index = content.find(subtasks_marker, task_index, next_task_index)
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        if subtasks_index == -1:
            # No subtasks list yet, add one
            subtasks_list = f"\n#### Subtasks:\n"
            subtasks_list += f"- {'[x]' if completed else '[ ]'} {subtask_description} ({timestamp})\n"
            
            # Find where to insert the subtasks list
            updated_marker = "- **Updated:**"
            updated_index = content.find(updated_marker, task_index, next_task_index)
            
            if updated_index != -1:
                # Find the end of the line with the updated timestamp
                line_end = content.find("\n", updated_index)
                if line_end == -1:
                    line_end = len(content)
                
                # Insert after the updated timestamp
                updated_content = content[:line_end + 1] + subtasks_list + content[line_end + 1:]
            else:
                # If no updated timestamp, insert at the end of the task section
                updated_content = content[:next_task_index] + subtasks_list + content[next_task_index:]
        else:
            # Subtasks list exists, add to it
            subtasks_end = content.find("\n\n", subtasks_index)
            if subtasks_end == -1:
                subtasks_end = content.find("####", subtasks_index)
            if subtasks_end == -1:
                subtasks_end = next_task_index
            
            # Add the new subtask
            subtask_entry = f"- {'[x]' if completed else '[ ]'} {subtask_description} ({timestamp})\n"
            updated_content = content[:subtasks_end] + subtask_entry + content[subtasks_end:]
        
        # Update the "Updated" timestamp
        updated_marker = "- **Updated:**"
        updated_index = content.find(updated_marker, task_index, next_task_index)
        
        if updated_index != -1:
            # Find the end of the line with the updated timestamp
            line_end = content.find("\n", updated_index)
            if line_end == -1:
                line_end = len(content)
            
            # Replace the timestamp
            updated_line = f"- **Updated:** {timestamp}"
            updated_content = updated_content[:updated_index] + updated_line + updated_content[line_end:]
        
        with open(self.todo_file_path, 'w') as f:
            f.write(updated_content)
        
        logger.info(f"Added subtask to {task_id}: {subtask_description}")
        
        # Broadcast update
        asyncio.create_task(self._broadcast_todo_update("subtask_added", {
            "task_id": task_id,
            "description": subtask_description,
            "completed": completed
        }))
    
    def mark_subtask_completed(self, task_id: str, subtask_description: str):
        """
        Mark a subtask as completed.
        
        Args:
            task_id: ID of the parent task
            subtask_description: Description of the subtask to mark as completed
        """
        with open(self.todo_file_path, 'r') as f:
            content = f.read()
        
        # Find the task
        task_marker = f"### [{task_id}]"
        task_index = content.find(task_marker)
        
        if task_index == -1:
            logger.warning(f"Task {task_id} not found in ToDo.md")
            return
        
        # Find the end of the task section
        next_task_index = content.find("###", task_index + 1)
        if next_task_index == -1:
            next_task_index = len(content)
        
        # Find the subtasks section
        subtasks_marker = "#### Subtasks:"
        subtasks_index = content.find(subtasks_marker, task_index, next_task_index)
        
        if subtasks_index == -1:
            logger.warning(f"No subtasks found for task {task_id}")
            return
        
        # Find the specific subtask
        subtask_marker = f"- [ ] {subtask_description}"
        subtask_index = content.find(subtask_marker, subtasks_index, next_task_index)
        
        if subtask_index == -1:
            logger.warning(f"Subtask '{subtask_description}' not found for task {task_id}")
            return
        
        # Replace the unchecked box with a checked box
        updated_content = content[:subtask_index] + f"- [x] {subtask_description}" + content[subtask_index + len(subtask_marker):]
        
        # Update the "Updated" timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        updated_marker = "- **Updated:**"
        updated_index = content.find(updated_marker, task_index, next_task_index)
        
        if updated_index != -1:
            # Find the end of the line with the updated timestamp
            line_end = content.find("\n", updated_index)
            if line_end == -1:
                line_end = len(content)
            
            # Replace the timestamp
            updated_line = f"- **Updated:** {timestamp}"
            updated_content = updated_content[:updated_index] + updated_line + updated_content[line_end:]
        
        with open(self.todo_file_path, 'w') as f:
            f.write(updated_content)
        
        logger.info(f"Marked subtask as completed in {task_id}: {subtask_description}")
        
        # Broadcast update
        asyncio.create_task(self._broadcast_todo_update("subtask_completed", {
            "task_id": task_id,
            "description": subtask_description
        }))
    
    def mark_task_completed(self, task_id: str):
        """
        Mark a task as completed and move it to the Completed Tasks section.
        
        Args:
            task_id: ID of the task to mark as completed
        """
        with open(self.todo_file_path, 'r') as f:
            content = f.read()
        
        # Find the task
        task_marker = f"### [{task_id}]"
        task_index = content.find(task_marker)
        
        if task_index == -1:
            logger.warning(f"Task {task_id} not found in ToDo.md")
            return
        
        # Find the end of the task section
        next_task_index = content.find("###", task_index + 1)
        if next_task_index == -1:
            next_task_index = len(content)
        
        # Extract the task section
        task_section = content[task_index:next_task_index]
        
        # Update the status
        status_marker = "- **Status:**"
        status_index = task_section.find(status_marker)
        
        if status_index != -1:
            # Find the end of the status line
            line_end = task_section.find("\n", status_index)
            if line_end == -1:
                line_end = len(task_section)
            
            # Replace the status
            task_section = task_section[:status_index] + "- **Status:** Completed" + task_section[line_end:]
        
        # Update the timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        updated_marker = "- **Updated:**"
        updated_index = task_section.find(updated_marker)
        
        if updated_index != -1:
            # Find the end of the updated line
            line_end = task_section.find("\n", updated_index)
            if line_end == -1:
                line_end = len(task_section)
            
            # Replace the timestamp
            task_section = task_section[:updated_index] + f"- **Updated:** {timestamp}" + task_section[line_end:]
        
        # Add completed timestamp
        completed_marker = "- **Completed:**"
        completed_index = task_section.find(completed_marker)
        
        if completed_index == -1:
            # Add completed timestamp after updated timestamp
            updated_index = task_section.find(updated_marker)
            if updated_index != -1:
                line_end = task_section.find("\n", updated_index)
                if line_end == -1:
                    line_end = len(task_section)
                
                task_section = task_section[:line_end + 1] + f"- **Completed:** {timestamp}\n" + task_section[line_end + 1:]
        
        # Remove the task from the original location
        updated_content = content[:task_index] + content[next_task_index:]
        
        # Find the Completed Tasks section
        completed_tasks_index = updated_content.find("## Completed Tasks")
        
        if completed_tasks_index == -1:
            # If Completed Tasks section doesn't exist, add it
            updated_content += "\n## Completed Tasks\n\n"
            completed_tasks_index = updated_content.find("## Completed Tasks")
        
        # Insert the task in the Completed Tasks section
        insert_position = updated_content.find("\n", completed_tasks_index) + 1
        updated_content = updated_content[:insert_position] + task_section + updated_content[insert_position:]
        
        with open(self.todo_file_path, 'w') as f:
            f.write(updated_content)
        
        logger.info(f"Marked task {task_id} as completed")
        
        # Broadcast update
        asyncio.create_task(self._broadcast_todo_update("task_completed", {
            "task_id": task_id
        }))
    
    def add_error(self, task_id: str, error_message: str):
        """
        Add an error message to the Errors and Issues section.
        
        Args:
            task_id: ID of the related task
            error_message: Error message to add
        """
        with open(self.todo_file_path, 'r') as f:
            content = f.read()
        
        # Find the Errors and Issues section
        errors_index = content.find("## Errors and Issues")
        
        if errors_index == -1:
            # If Errors and Issues section doesn't exist, add it
            content += "\n## Errors and Issues\n\n"
            errors_index = content.find("## Errors and Issues")
        
        # Insert the error
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        error_entry = f"### Error in [{task_id}] - {timestamp}\n"
        error_entry += f"```\n{error_message}\n```\n\n"
        
        # Insert at the beginning of the Errors and Issues section
        insert_position = content.find("\n", errors_index) + 1
        updated_content = content[:insert_position] + error_entry + content[insert_position:]
        
        with open(self.todo_file_path, 'w') as f:
            f.write(updated_content)
        
        logger.info(f"Added error for task {task_id}: {error_message[:50]}...")
        
        # Broadcast update
        asyncio.create_task(self._broadcast_todo_update("error_added", {
            "task_id": task_id,
            "error": error_message
        }))
    
    def get_todo_content(self) -> str:
        """
        Get the current content of the ToDo.md file.
        
        Returns:
            Content of the ToDo.md file
        """
        try:
            with open(self.todo_file_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning(f"ToDo.md file not found at {self.todo_file_path}")
            return ""
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """
        Get a list of active tasks.
        
        Returns:
            List of active task dictionaries
        """
        content = self.get_todo_content()
        
        # Find the Active Tasks section
        active_tasks_index = content.find("## Active Tasks")
        if active_tasks_index == -1:
            return []
        
        # Find the end of the Active Tasks section
        next_section_index = content.find("##", active_tasks_index + 1)
        if next_section_index == -1:
            next_section_index = len(content)
        
        active_tasks_content = content[active_tasks_index:next_section_index]
        
        # Parse tasks
        tasks = []
        task_markers = active_tasks_content.split("### [")
        
        for marker in task_markers[1:]:  # Skip the first split (header)
            task_id = marker[:marker.find("]")]
            description = marker[marker.find("]") + 1:marker.find("\n")].strip()
            
            # Extract status
            status = "In Progress"
            status_marker = "- **Status:**"
            status_index = marker.find(status_marker)
            if status_index != -1:
                status_end = marker.find("\n", status_index)
                if status_end == -1:
                    status_end = len(marker)
                status = marker[status_index + len(status_marker):status_end].strip()
            
            # Extract timestamps
            created = ""
            created_marker = "- **Created:**"
            created_index = marker.find(created_marker)
            if created_index != -1:
                created_end = marker.find("\n", created_index)
                if created_end == -1:
                    created_end = len(marker)
                created = marker[created_index + len(created_marker):created_end].strip()
            
            updated = ""
            updated_marker = "- **Updated:**"
            updated_index = marker.find(updated_marker)
            if updated_index != -1:
                updated_end = marker.find("\n", updated_index)
                if updated_end == -1:
                    updated_end = len(marker)
                updated = marker[updated_index + len(updated_marker):updated_end].strip()
            
            # Extract subtasks
            subtasks = []
            subtasks_marker = "#### Subtasks:"
            subtasks_index = marker.find(subtasks_marker)
            
            if subtasks_index != -1:
                subtasks_end = marker.find("####", subtasks_index + 1)
                if subtasks_end == -1:
                    subtasks_end = len(marker)
                
                subtasks_content = marker[subtasks_index:subtasks_end]
                subtask_lines = subtasks_content.split("\n")
                
                for line in subtask_lines:
                    if line.strip().startswith("- ["):
                        completed = line.strip()[3] == "x"
                        description = line.strip()[5:].strip()
                        if "(" in description:
                            description, timestamp = description.rsplit("(", 1)
                            timestamp = timestamp.rstrip(")").strip()
                            description = description.strip()
                        else:
                            timestamp = ""
                        
                        subtasks.append({
                            "description": description,
                            "completed": completed,
                            "timestamp": timestamp
                        })
            
            tasks.append({
                "id": task_id,
                "description": description,
                "status": status,
                "created": created,
                "updated": updated,
                "subtasks": subtasks
            })
        
        return tasks
    
    async def _broadcast_todo_update(self, update_type: str, data: Dict[str, Any]):
        """
        Broadcast a ToDo update to all connected WebSocket clients.
        
        Args:
            update_type: Type of update (e.g., "task_added", "task_completed")
            data: Update data
        """
        if self.broadcast_message:
            message = {
                "type": f"todo_{update_type}",
                "timestamp": time.time(),
                "data": data
            }
            await self.broadcast_message(message)
