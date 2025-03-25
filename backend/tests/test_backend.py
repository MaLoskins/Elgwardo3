import pytest
import asyncio
import json
import time
from unittest.mock import MagicMock, patch

# Import the modules to test
from utils import get_status, _get_system_status
from knowledge_graph import KnowledgeGraph
from todo_manager import ToDoManager
from terminal_manager import TerminalManager

@pytest.fixture
def mock_agent_coordinator():
    """Create a mock agent coordinator for testing."""
    mock = MagicMock()
    mock.task_status = "idle"
    mock.current_task = None
    mock.model = "gpt-4o"
    
    # Mock knowledge graph
    mock.knowledge_graph = MagicMock()
    mock.knowledge_graph.get_graph_visualization_data.return_value = {
        "nodes": [],
        "edges": []
    }
    mock.knowledge_graph.get_project_structure.return_value = {
        "root": "/workspace",
        "directories": {},
        "files": {}
    }
    
    # Mock agents
    mock.coder_agent = MagicMock()
    mock.coder_agent.model = "gpt-4o"
    mock.coder_agent.status = "idle"
    
    mock.researcher_agent = MagicMock()
    mock.researcher_agent.model = "gpt-4o"
    mock.researcher_agent.status = "idle"
    
    mock.formatter_agent = MagicMock()
    mock.formatter_agent.model = "gpt-4o"
    mock.formatter_agent.status = "idle"
    
    # Mock current execution
    mock.current_execution = {"progress": 0}
    
    return mock

@pytest.fixture
def mock_terminal_manager():
    """Create a mock terminal manager for testing."""
    mock = MagicMock()
    mock.terminal_container_name = "ai_agent_terminal"
    mock.get_command_history.return_value = ["ls", "echo 'test'"]
    mock.get_output_history.return_value = ["file1 file2", "test"]
    mock.check_container_running.return_value = True
    
    return mock

@pytest.fixture
def mock_todo_manager():
    """Create a mock todo manager for testing."""
    mock = MagicMock()
    mock.get_active_tasks.return_value = [
        {
            "id": "task1",
            "description": "Test task",
            "status": "In Progress",
            "created": "2025-03-20",
            "updated": "2025-03-20",
            "subtasks": [
                {"description": "Subtask 1", "completed": False},
                {"description": "Subtask 2", "completed": True}
            ]
        }
    ]
    
    return mock

def test_get_status(mock_agent_coordinator, mock_terminal_manager, mock_todo_manager):
    """Test the get_status function."""
    # Call the function
    status = get_status(mock_agent_coordinator, mock_terminal_manager, mock_todo_manager)
    
    # Verify the result
    assert status["agent"]["status"] == "idle"
    assert status["agent"]["model"] == "gpt-4o"
    assert status["agent"]["progress"] == 0
    
    assert "terminal" in status
    assert "todo" in status
    assert "knowledgeGraph" in status
    assert "system" in status
    assert "version" in status
    assert "timestamp" in status
    
    # Verify terminal history
    assert len(status["terminal"]["history"]) == 2
    assert status["terminal"]["history"][0]["command"] == "ls"
    assert status["terminal"]["history"][0]["output"] == "file1 file2"
    
    # Verify todo tasks
    assert len(status["todo"]["active_tasks"]) == 1
    assert status["todo"]["active_tasks"][0]["id"] == "task1"
    
    # Verify system status
    assert "backend" in status["system"]
    assert "terminal" in status["system"]
    assert "memory" in status["system"]
    assert "cpu" in status["system"]

@patch('psutil.virtual_memory')
@patch('psutil.cpu_percent')
@patch('psutil.disk_usage')
@patch('psutil.boot_time')
def test_get_system_status(mock_boot_time, mock_disk_usage, mock_cpu_percent, mock_virtual_memory, mock_terminal_manager):
    """Test the _get_system_status function."""
    # Mock the psutil functions
    mock_boot_time.return_value = time.time() - 3600  # 1 hour uptime
    
    mock_memory = MagicMock()
    mock_memory.percent = 50
    mock_memory.total = 16000000000
    mock_memory.available = 8000000000
    mock_virtual_memory.return_value = mock_memory
    
    mock_cpu_percent.return_value = 25
    
    mock_disk = MagicMock()
    mock_disk.percent = 70
    mock_disk.total = 500000000000
    mock_disk.free = 150000000000
    mock_disk_usage.return_value = mock_disk
    
    # Call the function
    system_status = _get_system_status(mock_terminal_manager)
    
    # Verify the result
    assert system_status["backend"]["status"] == "healthy"
    assert system_status["terminal"]["status"] == "healthy"
    assert system_status["memory"]["usage"] == 50
    assert system_status["cpu"]["usage"] == 25
    assert system_status["disk"]["usage"] == 70
    assert "platform" in system_status

class TestKnowledgeGraph:
    """Test the KnowledgeGraph class."""
    
    def test_initialization(self):
        """Test that the knowledge graph initializes correctly."""
        kg = KnowledgeGraph()
        assert kg.graph is not None
        assert kg.tasks == set()
        
    def test_add_task(self):
        """Test adding a task to the knowledge graph."""
        kg = KnowledgeGraph()
        kg.add_task("test_task", "Test task description")
        
        assert "test_task" in kg.tasks
        assert kg.graph.has_node("test_task")
        assert kg.graph.nodes["test_task"]["type"] == "task"
        
    def test_get_graph_visualization_data(self):
        """Test getting visualization data from the knowledge graph."""
        kg = KnowledgeGraph()
        kg.add_task("test_task", "Test task description")
        
        data = kg.get_graph_visualization_data()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["id"] == "test_task"

class TestToDoManager:
    """Test the ToDoManager class."""
    
    @pytest.fixture
    def todo_manager(self, tmp_path):
        """Create a ToDoManager instance with a temporary file."""
        todo_file = tmp_path / "ToDo.md"
        todo_file.write_text("""# ToDo List

## Active Tasks

### [task1] Test Task 1
- **Status:** In Progress
- **Created:** 2025-03-20
- **Updated:** 2025-03-20

#### Subtasks:
- [ ] Subtask 1
- [x] Subtask 2 (2025-03-20)

### [task2] Test Task 2
- **Status:** Completed
- **Created:** 2025-03-19
- **Updated:** 2025-03-20

#### Subtasks:
- [x] Subtask 1 (2025-03-19)
- [x] Subtask 2 (2025-03-20)

## Completed Tasks

### [task3] Test Task 3
- **Status:** Completed
- **Created:** 2025-03-18
- **Completed:** 2025-03-19
""")
        
        return ToDoManager(str(todo_file))
    
    def test_get_active_tasks(self, todo_manager):
        """Test getting active tasks from the ToDo file."""
        tasks = todo_manager.get_active_tasks()
        
        assert len(tasks) == 2
        assert tasks[0]["id"] == "task1"
        assert tasks[0]["status"] == "In Progress"
        assert len(tasks[0]["subtasks"]) == 2
        assert tasks[0]["subtasks"][0]["completed"] == False
        assert tasks[0]["subtasks"][1]["completed"] == True
        
        assert tasks[1]["id"] == "task2"
        assert tasks[1]["status"] == "Completed"

class TestTerminalManager:
    """Test the TerminalManager class."""
    
    @pytest.fixture
    def terminal_manager(self):
        """Create a TerminalManager instance."""
        with patch('terminal_manager.TerminalManager._run_local_command') as mock_run:
            mock_run.return_value = "test output"
            manager = TerminalManager("ai_agent_terminal")
            return manager
    
    @patch('terminal_manager.TerminalManager._run_local_command')
    def test_execute_command(self, mock_run, terminal_manager):
        """Test executing a command."""
        mock_run.return_value = "command output"
        
        # Execute a command
        asyncio.run(terminal_manager.execute_command("echo 'test'"))
        
        # Verify the command was executed
        mock_run.assert_called()
        assert "echo 'test'" in terminal_manager.command_history
        assert "command output" in terminal_manager.output_history
    
    def test_get_command_history(self, terminal_manager):
        """Test getting command history."""
        # Add some commands to history
        terminal_manager.command_history = ["ls", "echo 'test'", "pwd"]
        
        # Get the history
        history = terminal_manager.get_command_history()
        
        # Verify the result
        assert len(history) == 3
        assert history[0] == "ls"
        assert history[1] == "echo 'test'"
        assert history[2] == "pwd"
    
    def test_get_output_history(self, terminal_manager):
        """Test getting output history."""
        # Add some outputs to history
        terminal_manager.output_history = ["file1 file2", "test", "/home/user"]
        
        # Get the history
        history = terminal_manager.get_output_history()
        
        # Verify the result
        assert len(history) == 3
        assert history[0] == "file1 file2"
        assert history[1] == "test"
        assert history[2] == "/home/user"
