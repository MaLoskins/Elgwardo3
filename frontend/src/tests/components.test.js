import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from 'styled-components';
import Header from '../components/Header';
import Footer from '../components/Footer';
import ToDoList from '../components/ToDoList';
import TerminalView from '../components/TerminalView';
import AgentActivityMonitor from '../components/AgentActivityMonitor';
import StatusDisplay from '../components/StatusDisplay';
import ProgressBar from '../components/ProgressBar';

// Mock theme for styled-components
const mockTheme = {
  background: '#f5f7fa',
  cardBackground: '#ffffff',
  text: '#333333',
  textSecondary: '#666666',
  primary: '#007bff',
  secondary: '#6c757d',
  success: '#28a745',
  error: '#dc3545',
  warning: '#ffc107',
  info: '#17a2b8',
  border: '#dee2e6',
  borderLight: '#e9ecef',
  shadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
  terminalBackground: '#1e1e1e',
  terminalText: '#f0f0f0',
  statusBackground: {
    default: 'rgba(108, 117, 125, 0.1)',
    status: 'rgba(23, 162, 184, 0.1)',
    task_start: 'rgba(0, 123, 255, 0.1)',
    task_complete: 'rgba(40, 167, 69, 0.1)',
    error: 'rgba(220, 53, 69, 0.1)'
  }
};

// Wrap component with ThemeProvider for testing
const renderWithTheme = (ui) => {
  return render(
    <ThemeProvider theme={mockTheme}>
      {ui}
    </ThemeProvider>
  );
};

describe('Header Component', () => {
  test('renders header with title', () => {
    renderWithTheme(
      <Header 
        model="gpt-4o"
        onModelChange={() => {}}
        darkMode={false}
        onToggleTheme={() => {}}
        isConnected={true}
        onReconnect={() => {}}
        isExecuting={false}
      />
    );
    
    expect(screen.getByText('Dynamic AI Agent')).toBeInTheDocument();
  });
  
  test('shows reconnect button when disconnected', () => {
    renderWithTheme(
      <Header 
        model="gpt-4o"
        onModelChange={() => {}}
        darkMode={false}
        onToggleTheme={() => {}}
        isConnected={false}
        onReconnect={() => {}}
        isExecuting={false}
      />
    );
    
    expect(screen.getByText('Reconnect')).toBeInTheDocument();
  });
});

describe('Footer Component', () => {
  test('renders footer with version info', () => {
    renderWithTheme(
      <Footer 
        systemStatus={{}}
        version="2.1.0"
      />
    );
    
    expect(screen.getByText(/Dynamic AI Agent v2.1.0/)).toBeInTheDocument();
  });
});

describe('ToDoList Component', () => {
  test('renders empty state when no tasks', () => {
    renderWithTheme(<ToDoList todoContent={[]} />);
    
    expect(screen.getByText('No tasks available. Start a task to see it here.')).toBeInTheDocument();
  });
  
  test('renders tasks when provided', () => {
    const mockTasks = [
      {
        id: '1',
        description: 'Test Task',
        status: 'In Progress',
        created: '2025-03-20',
        updated: '2025-03-20',
        subtasks: [
          { description: 'Subtask 1', completed: false },
          { description: 'Subtask 2', completed: true }
        ]
      }
    ];
    
    renderWithTheme(<ToDoList todoContent={mockTasks} />);
    
    expect(screen.getByText('Test Task')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Subtask 1')).toBeInTheDocument();
    expect(screen.getByText('Subtask 2')).toBeInTheDocument();
  });
});

describe('TerminalView Component', () => {
  test('renders empty terminal state', () => {
    renderWithTheme(<TerminalView terminalOutput={[]} />);
    
    expect(screen.getByText('Terminal ready. Execute a task to see output here.')).toBeInTheDocument();
  });
  
  test('renders terminal output', () => {
    const mockOutput = [
      { type: 'command', content: 'echo "Hello World"' },
      { type: 'output', content: 'Hello World', success: true }
    ];
    
    renderWithTheme(<TerminalView terminalOutput={mockOutput} />);
    
    expect(screen.getByText('echo "Hello World"')).toBeInTheDocument();
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });
});

describe('AgentActivityMonitor Component', () => {
  test('renders empty state when no activities', () => {
    renderWithTheme(<AgentActivityMonitor activities={{}} />);
    
    expect(screen.getByText('No agent activity at the moment')).toBeInTheDocument();
  });
  
  test('renders agent activities', () => {
    const mockActivities = {
      coder: {
        status: 'active',
        currentAction: 'generating_code',
        lastActivity: Date.now() / 1000
      },
      researcher: {
        status: 'idle',
        lastActivity: Date.now() / 1000
      }
    };
    
    renderWithTheme(<AgentActivityMonitor activities={mockActivities} />);
    
    expect(screen.getByText('Code Generator')).toBeInTheDocument();
    expect(screen.getByText('Research & Context')).toBeInTheDocument();
    expect(screen.getByText('Generating Code')).toBeInTheDocument();
  });
});

describe('StatusDisplay Component', () => {
  test('renders empty state when no messages', () => {
    renderWithTheme(<StatusDisplay status={{}} messages={[]} />);
    
    expect(screen.getByText('No status messages yet. Execute a task to see updates here.')).toBeInTheDocument();
  });
  
  test('renders status messages', () => {
    const mockMessages = [
      { type: 'status', content: 'Task started', timestamp: Date.now() },
      { type: 'error', content: 'Error occurred', timestamp: Date.now() }
    ];
    
    renderWithTheme(<StatusDisplay status={{}} messages={mockMessages} />);
    
    expect(screen.getByText('Task started')).toBeInTheDocument();
    expect(screen.getByText('Error occurred')).toBeInTheDocument();
  });
});

describe('ProgressBar Component', () => {
  test('renders progress bar with correct percentage', () => {
    renderWithTheme(<ProgressBar progress={50} showText={true} />);
    
    expect(screen.getByText('50%')).toBeInTheDocument();
  });
});
