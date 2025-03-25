import React from 'react';
import styled from 'styled-components';

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  margin-bottom: 1rem;
`;

const Title = styled.h3`
  margin: 0;
  padding: 10px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
`;

const ActivityList = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 0;
`;

const ActivityItem = styled.div`
  padding: 10px 15px;
  border-bottom: 1px solid #eee;
  
  &:last-child {
    border-bottom: none;
  }
`;

const ActivityHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
`;

const ActivityDescription = styled.div`
  font-weight: bold;
  color: #333;
`;

const ActivityType = styled.span`
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  background-color: ${props => {
    switch (props.type.toLowerCase()) {
      case 'research': return '#2196f3';
      case 'coding': return '#4caf50';
      case 'analysis': return '#ff9800';
      case 'error': return '#f44336';
      default: return '#9e9e9e';
    }
  }};
  color: white;
`;

const ActivityMeta = styled.div`
  font-size: 12px;
  color: #888;
`;

const ActivityDetails = styled.div`
  margin-top: 5px;
  font-size: 14px;
  color: #555;
  white-space: pre-wrap;
  word-break: break-word;
`;

const EmptyState = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: #888;
  font-style: italic;
`;

const AgentActivityMonitor = ({ activities = [] }) => {
  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
  };
  
  return (
    <Container>
      <Title>Agent Activity Monitor</Title>
      
      <ActivityList>
        {activities.length > 0 ? (
          activities.map((activity, index) => (
            <ActivityItem key={index}>
              <ActivityHeader>
                <ActivityDescription>
                  {activity.title || 'Agent Activity'}
                </ActivityDescription>
                <ActivityType type={activity.type || 'info'}>
                  {activity.type || 'Info'}
                </ActivityType>
              </ActivityHeader>
              
              <ActivityMeta>
                {formatDate(activity.timestamp)}
              </ActivityMeta>
              
              {activity.details && (
                <ActivityDetails>
                  {activity.details}
                </ActivityDetails>
              )}
            </ActivityItem>
          ))
        ) : (
          <EmptyState>
            No agent activities to display
          </EmptyState>
        )}
      </ActivityList>
    </Container>
  );
};

export default React.memo(AgentActivityMonitor);
