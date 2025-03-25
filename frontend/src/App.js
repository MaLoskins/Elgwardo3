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
  
  // Execute task
  const executeTask = useCallback(async (taskInput) => {
    try {
      await apiService.executeTask(taskInput);
      // Refresh data after task execution
      fetchStatus(true);
      fetchTodoTasks(true);
    } catch (error) {
      console.error('Error executing task:', error);
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
    console.log('Received WebSocket message:', data);
    
    if (!data || !data.type) return;
    
    // Reset reconnect attempt counter on successful message
    if (reconnectAttempt > 0) {
      setReconnectAttempt(0);
    }
    
    // Update last ping time for ping/pong messages
    if (data.type === 'pong') {
      lastPingTimeRef.current = Date.now();
      return;
    }
    
    switch (data.type) {
      case 'terminal_update':
        setTerminalOutput(prev => [...prev, data.data]);
        break;
      case 'todo_update':
        fetchTodoTasks(true);
        break;
      case 'graph_update':
        fetchKnowledgeGraph(true);
        break;
      case 'status_update':
        fetchStatus(true);
        break;
      case 'task_update':
        fetchTodoTasks(true);
        break;
      case 'agent_status_change':
        setStatus(prev => ({
          ...prev,
          agentStatus: data.data.status,
          lastUpdated: new Date().toISOString()
        }));
        break;
      default:
        console.log('Unknown message type:', data.type);
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
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    console.log('Connecting to WebSocket at:', wsUrl);
    
    wsRef.current = createWebSocketConnection(
      wsUrl,
      handleWebSocketMessage,
      () => {
        setWsConnected(true);
        setReconnectAttempt(0);
        setIsReconnecting(false);
        console.log('WebSocket connected successfully');
        
        // Set up ping interval to keep connection alive
        lastPingTimeRef.current = Date.now();
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send('ping');
          }
        }, 30000); // Send ping every 30 seconds (increased from 15s)
      },
      () => {
        setWsConnected(false);
        setIsReconnecting(false);
        
        // Clear ping interval on close
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        scheduleReconnect();
      },
      (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
        setIsReconnecting(false);
        
        // Clear ping interval on error
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        scheduleReconnect();
      }
    );
    
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
  }, [handleWebSocketMessage, scheduleReconnect]);
  
  // Manual reconnect handler
  const handleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    setReconnectAttempt(0);
    initializeWebSocket();
  }, [initializeWebSocket]);
  
  // Initialize data and WebSocket connection
  useEffect(() => {
    // Initial data fetch - do this only once
    const initialFetchData = async () => {
      await fetchStatus();
      await fetchTodoTasks();
      await fetchKnowledgeGraph();
    };
    
    initialFetchData();
    
    // Initialize WebSocket
    const cleanup = initializeWebSocket();
    
    // Set up polling intervals with much longer durations for development
    statusPollingIntervalRef.current = setInterval(() => {
      fetchStatus();
    }, 60000); // Poll status every 60 seconds (increased from 30s)
    
    graphUpdateIntervalRef.current = setInterval(() => {
      fetchKnowledgeGraph();
      fetchTodoTasks();
    }, 120000); // Poll graph and todos every 120 seconds (increased from 60s)
    
    // Cleanup function
    return () => {
      cleanup();
      
      if (statusPollingIntervalRef.current) {
        clearInterval(statusPollingIntervalRef.current);
      }
      
      if (graphUpdateIntervalRef.current) {
        clearInterval(graphUpdateIntervalRef.current);
      }
    };
  }, [fetchStatus, fetchTodoTasks, fetchKnowledgeGraph, initializeWebSocket]);
  
  // Monitor WebSocket connection health - with reduced frequency
  useEffect(() => {
    const checkConnectionHealth = () => {
      // If we're connected but haven't received a pong in 90 seconds, reconnect
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
              <div className={`status-indicator ${wsConnected ? 'connected' : 'disconnected'}`}></div>
              <span>{wsConnected ? 'Connected' : 'Disconnected'}</span>
              {!wsConnected && !isReconnecting && (
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
              connected={wsConnected}
            />
          </GraphContainer>
          
          <TerminalContainer>
            <TerminalView 
              output={terminalOutput} 
              onExecute={executeTask} 
              onClear={() => setTerminalOutput([])}
              connected={wsConnected}
            />
          </TerminalContainer>
        </RightPanel>
      </MainContent>
      
      <Footer />
    </AppContainer>
  );
}

export default App;