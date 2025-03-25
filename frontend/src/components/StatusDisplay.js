import React from 'react';
import styled from 'styled-components';

const StatusContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
`;

const StatusRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const StatusLabel = styled.span`
  font-weight: bold;
  color: #555;
`;

const StatusValue = styled.span`
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.9rem;
  font-weight: bold;
  background-color: ${props => {
    switch (props.value.toLowerCase()) {
      case 'idle': return '#9e9e9e';
      case 'working': return '#2196f3';
      case 'thinking': return '#ff9800';
      case 'error': return '#f44336';
      case 'online': return '#4caf50';
      case 'offline': return '#f44336';
      case 'degraded': return '#ff9800';
      default: return '#9e9e9e';
    }
  }};
  color: white;
`;

const LastUpdated = styled.div`
  font-size: 0.8rem;
  color: #888;
  text-align: right;
  margin-top: 0.5rem;
`;

const StatusDisplay = ({ status }) => {
  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
  };
  
  // Default status if not provided
  const defaultStatus = {
    agentStatus: 'idle',
    systemStatus: 'online',
    lastUpdated: new Date().toISOString(),
    version: '1.0.0'
  };
  
  // Merge with defaults
  const currentStatus = { ...defaultStatus, ...status };
  
  // Format last updated time
  const lastUpdated = formatDate(currentStatus.lastUpdated);
  
  // Get version
  const version = currentStatus.version || '1.0.0';
  
  return (
    <StatusContainer>
      <StatusRow>
        <StatusLabel>Agent Status:</StatusLabel>
        <StatusValue value={currentStatus.agentStatus}>
          {currentStatus.agentStatus}
        </StatusValue>
      </StatusRow>
      
      <StatusRow>
        <StatusLabel>System Status:</StatusLabel>
        <StatusValue value={currentStatus.systemStatus}>
          {currentStatus.systemStatus}
        </StatusValue>
      </StatusRow>
      
      <LastUpdated>
        Last updated: {lastUpdated}
      </LastUpdated>
    </StatusContainer>
  );
};

export default React.memo(StatusDisplay);
