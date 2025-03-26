import React, { useState, useCallback, useEffect, useRef } from 'react';
import styled from 'styled-components';


const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
`;

const Title = styled.h3`
  margin: 0;
  padding: 10px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const OutputContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  background-color: #1e1e1e;
  color: #f0f0f0;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.5;
`;

const CommandLine = styled.div`
  display: flex;
  padding: 5px 10px;
  background-color: #2d2d2d;
  border-top: 1px solid #444;
`;

const Prompt = styled.span`
  color: #4caf50;
  margin-right: 5px;
`;

const Input = styled.input`
  flex: 1;
  background-color: transparent;
  border: none;
  color: #f0f0f0;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  
  &:focus {
    outline: none;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const Button = styled.button`
  padding: 5px 10px;
  background-color: #4a90e2;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  
  &:hover {
    background-color: #3a80d2;
  }
  
  &:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }
`;

const FilterContainer = styled.div`
  display: flex;
  gap: 5px;
`;

const FilterButton = styled.button`
  padding: 2px 8px;
  background-color: ${props => props.active ? '#4a90e2' : '#ddd'};
  color: ${props => props.active ? 'white' : '#333'};
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  
  &:hover {
    background-color: ${props => props.active ? '#3a80d2' : '#ccc'};
  }
`;

const CommandOutput = styled.div`
  margin-bottom: 8px;
  white-space: pre-wrap;
  word-break: break-word;
`;

const Command = styled.div`
  color: #4caf50;
  font-weight: bold;
`;

const Output = styled.div`
  color: #f0f0f0;
`;

const Error = styled.div`
  color: #f44336;
`;

const Info = styled.div`
  color: #2196f3;
`;

const EmptyState = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #666;
  font-style: italic;
`;

const ConnectionStatus = styled.div`
  display: flex;
  align-items: center;
  margin-right: 10px;
  
  .status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 5px;
  }
  
  .connected {
    background-color: #4caf50;
  }
  
  .disconnected {
    background-color: #f44336;
  }
  
  .status-text {
    font-size: 12px;
    font-weight: normal;
  }
`;

const ErrorMessage = styled.div`
  background-color: #ffebee;
  color: #b71c1c;
  padding: 8px;
  margin-bottom: 8px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  color: #b71c1c;
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  
  &:hover {
    color: #d32f2f;
  }
`;

const DebugInfo = styled.div`
  position: absolute;
  bottom: 10px;
  right: 10px;
  background-color: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 5px;
  border-radius: 4px;
  font-size: 10px;
  z-index: 100;
`;

const TerminalView = ({ output = [], onExecute, onClear, connected = false }) => {
  const [command, setCommand] = useState('');
  const [filter, setFilter] = useState('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const [error, setError] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastCommand, setLastCommand] = useState('');
  const [commandHistory, setCommandHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [debugInfo, setDebugInfo] = useState({ lastUpdateTime: null, outputCount: 0 });
  const outputContainerRef = useRef(null);
  const inputRef = useRef(null);
  
  // Update debug info whenever output changes
  useEffect(() => {
    setDebugInfo({
      lastUpdateTime: new Date().toISOString(),
      outputCount: output?.length || 0
    });
  }, [output]);
  
  // Ensure output is treated as an array
  const safeOutput = Array.isArray(output) ? output : [];
  
  // Stable filtered output to prevent unnecessary renders
  const filteredOutput = React.useMemo(() => {
    return safeOutput.filter(item => {
      if (!item || !item.type) return false;
      if (filter === 'all') return true;
      return item.type === filter;
    });
  }, [safeOutput, filter]);
  
  // Handle command input
  const handleCommandChange = useCallback((e) => {
    setCommand(e.target.value);
  }, []);
  
  // Handle command submission with debounce to prevent multiple submissions
  const handleCommandSubmit = useCallback(async (e) => {
    e.preventDefault();
    
    // Do nothing if conditions aren't met
    if (!command.trim() || !connected || isExecuting) return;
    
    const trimmedCommand = command.trim();
    setLastCommand(trimmedCommand);
    
    // Add to command history
    setCommandHistory(prev => {
      const newHistory = [...prev];
      if (newHistory.length >= 50) newHistory.shift(); // Limit history size
      newHistory.push(trimmedCommand);
      return newHistory;
    });
    setHistoryIndex(-1);
    
    try {
      setIsExecuting(true);
      setError(null);
      
      // Clear command before execution to prevent re-submission
      setCommand('');
      
      // Execute the command
      if (onExecute) {
        await onExecute(trimmedCommand);
      }
      
    } catch (err) {
      console.error('Error executing command:', err);
      setError(`Failed to execute command: ${err.message || 'Unknown error'}`);
    } finally {
      setIsExecuting(false);
      
      // Focus the input again after execution completes
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }
  }, [command, connected, isExecuting, onExecute]);
  
  // Handle filter change
  const handleFilterChange = useCallback((newFilter) => {
    setFilter(newFilter);
  }, []);
  
  // Handle auto-scroll toggle
  const handleAutoScrollToggle = useCallback(() => {
    setAutoScroll(prev => !prev);
  }, []);
  
  // Handle clear terminal
  const handleClear = useCallback(() => {
    if (onClear) {
      onClear();
    }
    setError(null);
  }, [onClear]);
  
  // Handle error dismissal
  const handleDismissError = useCallback(() => {
    setError(null);
  }, []);
  
  // Handle command history navigation
  const handleKeyDown = useCallback((e) => {
    if (commandHistory.length === 0) return;
    
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      const newIndex = historyIndex < commandHistory.length - 1 ? historyIndex + 1 : historyIndex;
      setHistoryIndex(newIndex);
      if (newIndex >= 0 && newIndex < commandHistory.length) {
        setCommand(commandHistory[commandHistory.length - 1 - newIndex]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      const newIndex = historyIndex > 0 ? historyIndex - 1 : -1;
      setHistoryIndex(newIndex);
      if (newIndex >= 0) {
        setCommand(commandHistory[commandHistory.length - 1 - newIndex]);
      } else {
        setCommand('');
      }
    }
  }, [commandHistory, historyIndex]);
  
  // Auto-scroll to bottom when new output is added
  useEffect(() => {
    if (outputContainerRef.current && autoScroll) {
      outputContainerRef.current.scrollTop = outputContainerRef.current.scrollHeight;
    }
  }, [filteredOutput, autoScroll]);
  
  // Focus input when terminal is first loaded or when connected status changes
  useEffect(() => {
    // Short delay to ensure component is fully rendered
    const timer = setTimeout(() => {
      if (inputRef.current && connected) {
        inputRef.current.focus();
      }
    }, 200);
    
    return () => clearTimeout(timer);
  }, [connected]);
  
  // Retry last command
  const handleRetryLastCommand = useCallback(() => {
    if (lastCommand && connected && !isExecuting) {
      setCommand(lastCommand);
      // Focus after setting the command
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }
  }, [lastCommand, connected, isExecuting]);

  // Manual terminal message test function
  const injectTestMessage = useCallback(() => {
    if (onExecute) {
      // This creates a temporary injection to test if the terminal can receive messages
      const testCommand = "_test_terminal_connection";
      onExecute(testCommand);
    }
  }, [onExecute]);
  
  return (
    <Container>
      <Title>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          Terminal
          <ConnectionStatus>
            <div className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></div>
            <span className="status-text">{connected ? 'Connected' : 'Disconnected'}</span>
          </ConnectionStatus>
        </div>
        <FilterContainer>
          <FilterButton 
            active={filter === 'all'} 
            onClick={() => handleFilterChange('all')}
          >
            All
          </FilterButton>
          <FilterButton 
            active={filter === 'command'} 
            onClick={() => handleFilterChange('command')}
          >
            Commands
          </FilterButton>
          <FilterButton 
            active={filter === 'output'} 
            onClick={() => handleFilterChange('output')}
          >
            Output
          </FilterButton>
          <FilterButton 
            active={filter === 'error'} 
            onClick={() => handleFilterChange('error')}
          >
            Errors
          </FilterButton>
          <Button onClick={handleAutoScrollToggle}>
            {autoScroll ? 'Disable Auto-Scroll' : 'Enable Auto-Scroll'}
          </Button>
          <Button onClick={handleClear}>Clear</Button>
          <Button onClick={injectTestMessage}>Test Terminal</Button>
        </FilterContainer>
      </Title>
      
      <OutputContainer ref={outputContainerRef}>
        {error && (
          <ErrorMessage>
            <span>{error}</span>
            <CloseButton onClick={handleDismissError}>×</CloseButton>
          </ErrorMessage>
        )}
        
        {!connected && (
          <ErrorMessage>
            <span>Terminal disconnected. Commands cannot be executed until connection is restored.</span>
            {lastCommand && (
              <Button 
                onClick={handleRetryLastCommand} 
                disabled={!lastCommand || isExecuting}
              >
                Retry Last Command
              </Button>
            )}
          </ErrorMessage>
        )}
        
        {filteredOutput.length > 0 ? (
          filteredOutput.map((item, index) => (
            <CommandOutput key={index}>
              {item.type === 'command' && (
                <Command>{`$ ${item.content}`}</Command>
              )}
              {item.type === 'output' && (
                <Output>{item.content}</Output>
              )}
              {item.type === 'error' && (
                <Error>{item.content}</Error>
              )}
              {item.type === 'info' && (
                <Info>{item.content}</Info>
              )}
            </CommandOutput>
          ))
        ) : (
          <EmptyState>
            {connected 
              ? 'No terminal output - Type a command to begin'
              : 'Terminal disconnected - Awaiting connection to server'}
          </EmptyState>
        )}

        {/* Debug info panel */}
        <DebugInfo>
          Last update: {debugInfo.lastUpdateTime ? new Date(debugInfo.lastUpdateTime).toLocaleTimeString() : 'Never'}
          <br />
          Messages: {debugInfo.outputCount}
          <br />
          Connection: {connected ? 'Yes' : 'No'}
        </DebugInfo>
      </OutputContainer>
      
      <CommandLine>
        <form onSubmit={handleCommandSubmit} style={{ display: 'flex', width: '100%' }}>
          <Prompt>$</Prompt>
          <Input 
            type="text" 
            value={command} 
            onChange={handleCommandChange}
            onKeyDown={handleKeyDown}
            placeholder={connected ? "Enter command..." : "Terminal disconnected..."}
            disabled={!connected || isExecuting}
            ref={inputRef}
          />
          <Button 
            type="submit" 
            disabled={!connected || !command.trim() || isExecuting}
          >
            {isExecuting ? 'Executing...' : 'Execute'}
          </Button>
        </form>
      </CommandLine>
    </Container>
  );
};

export default React.memo(TerminalView);