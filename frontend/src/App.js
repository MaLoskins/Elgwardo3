import React, { useState, useEffect, useRef, useCallback } from 'react';
import styled from 'styled-components';
import ToDoList from './components/ToDoList';
import GraphViewer from './components/GraphViewer';
import TerminalView from './components/TerminalView';
import Header from './components/Header';
import Footer from './components/Footer';
import StatusDisplay from './components/StatusDisplay';
import ProgressBar from './components/ProgressBar';
import apiService from './services/apiService';
import { useStableConnectionStatus } from './utils/connection-handler';

// Improved WebSocket connection with automatic reconnection and better error handling
const createWebSocketConnection = (url, onMessage, onOpen, onClose, onError) => {
  let ws = null;
  
  try {
    ws = new WebSocket(url);
    
    ws.onopen = (event) => {
      console.log('WebSocket connection established');
      if (onOpen) onOpen(event);
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    
    ws.onclose = (event) => {
      console.log('WebSocket connection closed', event.code, event.reason);
      if (onClose) onClose(event);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (onError) onError(error);
    };
  } catch (error) {
    console.error('Error creating WebSocket connection:', error);
    if (onError) onError(error);
  }
  
  return ws;
};

const AppContainer = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
  color: #333;
  font-family: 'Roboto', sans-serif;
  
  @media (max-width: 768px) {
    height: auto;
    min-height: 100vh;
  }
`;

const MainContent = styled.main`
  display: flex;
  flex: 1;
  overflow: hidden;
  
  @media (max-width: 768px) {
    flex-direction: column;
    overflow: visible;
  }
`;

const LeftPanel = styled.div`
  display: flex;
  flex-direction: column;
  width: 30%;
  padding: 1rem;
  background-color: #fff;
  box-shadow: 2px 0 5px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  
  @media (max-width: 768px) {
    width: 100%;
    box-shadow: none;
    border-bottom: 1px solid #ddd;
  }
`;

const RightPanel = styled.div`
  display: flex;
  flex-direction: column;
  width: 70%;
  padding: 1rem;
  overflow: hidden;
  
  @media (max-width: 768px) {
    width: 100%;
  }
`;

const GraphContainer = styled.div`
  flex: 1;
  margin-bottom: 1rem;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
`;

const TerminalContainer = styled.div`
  flex: 1;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
`;

const StatusContainer = styled.div`
  margin-bottom: 1rem;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 1rem;
`;

const ToDoContainer = styled.div`
  flex: 1;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
`;

const ConnectionStatus = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 0.5rem;
  
  .status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 0.5rem;
  }
  
  .connected {
    background-color: #4caf50;
  }
  
  .disconnected {
    background-color: #f44336;
  }
`;

const ReconnectButton = styled.button`
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  
  &:hover {
    background-color: #45a049;
  }
  
  &:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }
`;

function App() {
  // State for WebSocket connection
  const [wsConnected, setWsConnected] = useState(false);
  // Use the stable connection status hook to prevent flashing "disconnected" status
  const stableConnectionStatus = useStableConnectionStatus(wsConnected, 2000);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const lastPingTimeRef = useRef(Date.now());
  const maxReconnectAttempts = 10;
  
  // State for application data
  const [todoTasks, setTodoTasks] = useState([]);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [terminalOutput, setTerminalOutput] = useState([]);
  const [status, setStatus] = useState({
    agentStatus: 'idle',
    systemStatus: 'online',
    lastUpdated: new Date().toISOString(),
    version: '1.0.0'
  });
  
  // Polling intervals
  const graphUpdateIntervalRef = useRef(null);
  const statusPollingIntervalRef = useRef(null);
  
  // Fetch todo tasks
  const fetchTodoTasks = useCallback(async (forceRefresh = false) => {
    try {
      const data = await apiService.getTodoTasks(forceRefresh);
      setTodoTasks(data);
    } catch (error) {
      console.error('Error fetching todo tasks:', error);
    }
  }, []);
  
  // Fetch knowledge graph
  const fetchKnowledgeGraph = useCallback(async (forceRefresh = false) => {
    try {
      const data = await apiService.getKnowledgeGraph(forceRefresh);
      setGraphData(data);
    } catch (error) {
      console.error('Error fetching knowledge graph:', error);
    }
  }, []);
  
  // Fetch status
  const fetchStatus = useCallback(async (forceRefresh = false) => {
    try {
      const data = await apiService.getStatus(forceRefresh);
      setStatus(data);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  }, []);

  const injectLogToTerminal = useCallback((message, type = 'info') => {
    setTerminalOutput(prev => [
      ...prev,
      {
        type: type,
        content: message,
        timestamp: new Date().toISOString()
      }
    ]);
  }, []);

  // Execute task
  const executeTask = useCallback(async (taskInput) => {
    // Add command to terminal immediately
    setTerminalOutput(prev => [
      ...prev,
      {
        type: 'command',
        content: typeof taskInput === 'string' ? taskInput : JSON.stringify(taskInput),
        timestamp: new Date().toISOString()
      }
    ]);
    
    try {
      // Special case for terminal test command
      if (taskInput === "_test_terminal_connection") {
        setTerminalOutput(prev => [
          ...prev,
          {
            type: 'info',
            content: 'Terminal connection test successful!',
            timestamp: new Date().toISOString()
          }
        ]);
        return;
      }
      
      // Format task input if needed
      const formattedTaskInput = typeof taskInput === 'string' 
        ? { task: taskInput }
        : taskInput;
      
      // Execute the task through the API
      const result = await apiService.executeTask(formattedTaskInput);
      
      // Add result to terminal
      setTerminalOutput(prev => [
        ...prev,
        {
          type: 'output',
          content: typeof result === 'string' ? result : 'Task submitted successfully',
          timestamp: new Date().toISOString()
        }
      ]);
      
      // Refresh data after task execution
      fetchStatus(true);
      fetchTodoTasks(true);
      
      return result;
    } catch (error) {
      console.error('Error executing task:', error);
      
      // Add error to terminal
      setTerminalOutput(prev => [
        ...prev,
        {
          type: 'error',
          content: `Error executing task: ${error.message || 'Unknown error'}`,
          timestamp: new Date().toISOString()
        }
      ]);
      
      throw error;
    }
  }, [fetchStatus, fetchTodoTasks]);
  
  // Schedule WebSocket reconnection with exponential backoff
  const scheduleReconnect = useCallback(() => {
    // Don't schedule reconnect if already reconnecting
    if (isReconnecting) {
      return;
    }
    
    // Clear any existing reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    // Check if we've exceeded max reconnect attempts
    if (reconnectAttempt >= maxReconnectAttempts) {
      console.log(`Maximum reconnect attempts (${maxReconnectAttempts}) reached. Stopping automatic reconnection.`);
      return;
    }
    
    const delay = Math.min(1000 * (2 ** reconnectAttempt), 30000); // Max 30 seconds
    console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttempt + 1})`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      setReconnectAttempt(prev => prev + 1);
      initializeWebSocket();
    }, delay);
  }, [reconnectAttempt, isReconnecting, maxReconnectAttempts]);
  
  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((data) => {
    console.log('Processing WebSocket message:', data);
    
    if (!data) {
      console.warn('Empty WebSocket message received');
      return;
    }
    
    // Reset reconnect attempt counter on successful message
    if (reconnectAttempt > 0) {
      setReconnectAttempt(0);
    }
    
    // Handle ping/pong messages
    if (data.type === 'ping' || data.type === 'pong') {
      lastPingTimeRef.current = Date.now();
      return;
    }
    
    // Special handling for log messages that should appear in the terminal
    if (data.type === 'log' || data.message || data.content || data.output || 
        (data.data && (typeof data.data === 'string' || data.data.message || data.data.content))) {
      
      let messageContent = '';
      let messageType = 'info';
      
      // Extract content from various formats
      if (data.message) {
        messageContent = data.message;
      } else if (data.content) {
        messageContent = data.content;
      } else if (data.output) {
        messageContent = data.output;
      } else if (typeof data.data === 'string') {
        messageContent = data.data;
      } else if (data.data && (data.data.message || data.data.content || data.data.output)) {
        messageContent = data.data.message || data.data.content || data.data.output;
        if (data.data.type) {
          messageType = data.data.type;
        }
      }
      
      // Default to showing the raw data if we couldn't extract meaningful content
      if (!messageContent && data) {
        try {
          messageContent = JSON.stringify(data);
        } catch (e) {
          messageContent = 'Unparseable message received';
        }
      }
      
      // Add to terminal output
      if (messageContent) {
        setTerminalOutput(prev => [...prev, {
          type: messageType,
          content: messageContent,
          timestamp: new Date().toISOString()
        }]);
      }
    }
    
    // Process specific message types
    switch (data.type) {
      case 'terminal_update':
        if (data.data) {
          let newTerminalItem;
          
          if (typeof data.data === 'string') {
            newTerminalItem = {
              type: 'output',
              content: data.data,
              timestamp: new Date().toISOString()
            };
          } else {
            newTerminalItem = {
              type: data.data.type || 'output',
              content: data.data.content || data.data.message || JSON.stringify(data.data),
              timestamp: data.data.timestamp || new Date().toISOString()
            };
          }
          
          setTerminalOutput(prev => [...prev, newTerminalItem]);
        }
        break;
        
      case 'command_executed':
        if (data.data && data.data.command) {
          setTerminalOutput(prev => [
            ...prev, 
            {
              type: 'command',
              content: data.data.command,
              timestamp: data.data.timestamp || new Date().toISOString()
            }
          ]);
        }
        break;
        
      case 'command_result':
        if (data.data) {
          setTerminalOutput(prev => [
            ...prev, 
            {
              type: data.data.success ? 'output' : 'error',
              content: data.data.output || data.data.message || JSON.stringify(data.data),
              timestamp: data.data.timestamp || new Date().toISOString()
            }
          ]);
        }
        break;
        
      case 'todo_update':
        fetchTodoTasks(true);
        
        // Add log to terminal about todo update
        if (data.data && (typeof data.data === 'string' || data.data.message)) {
          const todoMsg = typeof data.data === 'string' ? 
            data.data : data.data.message;
            
          setTerminalOutput(prev => [
            ...prev, 
            {
              type: 'info',
              content: `ToDo updated: ${todoMsg}`,
              timestamp: new Date().toISOString()
            }
          ]);
        }
        break;
        
      case 'graph_update':
        fetchKnowledgeGraph(true);
        break;
        
      case 'status_update':
        fetchStatus(true);
        break;
        
      case 'task_update':
        fetchTodoTasks(true);
        
        // Add task updates to terminal
        if (data.data) {
          const taskMsg = typeof data.data === 'string' ? 
            data.data : 
            `Task ${data.data.action || 'updated'}: ${data.data.task || data.data.description || JSON.stringify(data.data)}`;
            
          setTerminalOutput(prev => [
            ...prev, 
            {
              type: 'info',
              content: taskMsg,
              timestamp: new Date().toISOString()
            }
          ]);
        }
        break;
        
      case 'agent_status_change':
        setStatus(prev => ({
          ...prev,
          agentStatus: data.data.status,
          lastUpdated: new Date().toISOString()
        }));
        
        // Add status change to terminal
        setTerminalOutput(prev => [
          ...prev, 
          {
            type: 'info',
            content: `Agent status changed to: ${data.data.status}`,
            timestamp: new Date().toISOString()
          }
        ]);
        break;
        
      default:
        console.log('Unknown message type:', data.type);
        
        // Try to extract any potentially useful information
        let messageContent = '';
        if (data.data) {
          messageContent = typeof data.data === 'string' ? 
            data.data : 
            data.data.message || data.data.content || data.data.output || JSON.stringify(data.data);
            
          if (messageContent) {
            setTerminalOutput(prev => [
              ...prev, 
              {
                type: 'output',
                content: messageContent,
                timestamp: new Date().toISOString()
              }
            ]);
          }
        }
    }
  }, [fetchTodoTasks, fetchKnowledgeGraph, fetchStatus, reconnectAttempt]);
  
  // Initialize WebSocket connection
  const initializeWebSocket = useCallback(() => {
    // Clear any existing connection and intervals
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    
    setIsReconnecting(true);
    
    // Use window.location to dynamically determine the WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    console.log('Connecting to WebSocket at:', wsUrl);
    
    // Create WebSocket connection
    try {
      const ws = new WebSocket(wsUrl);
      
      ws.onopen = (event) => {
        console.log('WebSocket connection established');
        setWsConnected(true);
        setReconnectAttempt(0);
        setIsReconnecting(false);
        
        // Add initial terminal message to show connection is working
        setTerminalOutput(prev => [
          ...prev,
          {
            type: 'info',
            content: 'WebSocket connection established',
            timestamp: new Date().toISOString()
          }
        ]);
        
        // Set up ping interval to keep connection alive
        lastPingTimeRef.current = Date.now();
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000); // Send ping every 30 seconds
      };
      
      ws.onmessage = (event) => {
        try {
          // Try to parse as JSON first
          let data;
          try {
            data = JSON.parse(event.data);
          } catch (e) {
            // If not JSON, use as plain text
            data = { type: 'output', data: event.data };
          }
          
          console.log('WebSocket message received:', data);
          
          // Always add raw messages to terminal for debugging
          if (typeof data === 'object' && data !== null) {
            // Process the message
            handleWebSocketMessage(data);
          } else {
            // Handle plain text message
            setTerminalOutput(prev => [
              ...prev,
              {
                type: 'output',
                content: String(event.data),
                timestamp: new Date().toISOString()
              }
            ]);
          }
        } catch (error) {
          console.error('Error handling WebSocket message:', error);
          setTerminalOutput(prev => [
            ...prev,
            {
              type: 'error',
              content: `Error processing message: ${error.message}`,
              timestamp: new Date().toISOString()
            }
          ]);
        }
      };
      
      ws.onclose = (event) => {
        console.log('WebSocket connection closed', event.code, event.reason);
        setWsConnected(false);
        setIsReconnecting(false);
        
        setTerminalOutput(prev => [
          ...prev,
          {
            type: 'error',
            content: `WebSocket connection closed: ${event.reason || 'Unknown reason'}`,
            timestamp: new Date().toISOString()
          }
        ]);
        
        // Clear ping interval on close
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        scheduleReconnect();
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
        setIsReconnecting(false);
        
        setTerminalOutput(prev => [
          ...prev,
          {
            type: 'error',
            content: 'WebSocket connection error',
            timestamp: new Date().toISOString()
          }
        ]);
        
        // Clear ping interval on error
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        scheduleReconnect();
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('Error creating WebSocket:', error);
      setWsConnected(false);
      setIsReconnecting(false);
      scheduleReconnect();
    }
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
      }
    };
  }, []);
  
  // Manual reconnect handler
const handleReconnect = useCallback(() => {
  if (reconnectTimeoutRef.current) {
    clearTimeout(reconnectTimeoutRef.current);
  }
  setReconnectAttempt(0);
  initializeWebSocket();
}, [initializeWebSocket]);

  // Monitor WebSocket connection health - with reduced frequency
  useEffect(() => {
    const checkConnectionHealth = () => {
      // If we're connected but haven't received a pong in 90 seconds, reconnect
      // Note: We use actual wsConnected here, not stableConnectionStatus, for internal health checks
      if (wsConnected && Date.now() - lastPingTimeRef.current > 90000) {
        console.log('WebSocket connection appears stale. Reconnecting...');
        handleReconnect();
      }
    };
    
    const healthCheckInterval = setInterval(checkConnectionHealth, 30000); // Check every 30s instead of 15s
    
    return () => {
      clearInterval(healthCheckInterval);
    };
  }, [wsConnected, handleReconnect]);
  
  return (
    <AppContainer>
      <Header />
      
      <MainContent>
        <LeftPanel>
          <StatusContainer>
            <ConnectionStatus>
              <div className={`status-indicator ${stableConnectionStatus ? 'connected' : 'disconnected'}`}></div>
              <span>{stableConnectionStatus ? 'Connected' : 'Disconnected'}</span>
              {!stableConnectionStatus && !isReconnecting && (
                <button 
                  onClick={handleReconnect}
                  style={{
                    marginLeft: '10px',
                    padding: '3px 8px',
                    background: '#4caf50',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  Reconnect
                </button>
              )}
            </ConnectionStatus>
            <StatusDisplay status={status} />
            <ProgressBar progress={75} /> {/* Fixed value for now to avoid excessive renders */}
          </StatusContainer>
          
          <ToDoContainer>
            <ToDoList tasks={todoTasks} />
          </ToDoContainer>
        </LeftPanel>
        
        <RightPanel>
          <GraphContainer>
            <GraphViewer 
              data={graphData} 
              onRefresh={() => fetchKnowledgeGraph(true)}
              connected={stableConnectionStatus}
            />
          </GraphContainer>
          
          <TerminalContainer>
            <TerminalView 
              output={terminalOutput} 
              onExecute={executeTask} 
              onClear={() => setTerminalOutput([])}
              connected={stableConnectionStatus}
            />
          </TerminalContainer>
        </RightPanel>
      </MainContent>
      
      <Footer />
    </AppContainer>
  );
}

export default App;