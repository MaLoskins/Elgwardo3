import React from 'react';
import styled from 'styled-components';

const ProgressBarContainer = styled.div`
  width: 100%;
  margin: 0.5rem 0;
`;

const ProgressBarTrack = styled.div`
  width: 100%;
  height: 8px;
  background-color: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
`;

const ProgressBarFill = styled.div`
  height: 100%;
  background-color: ${props => {
    if (props.progress >= 100) return '#4caf50';
    if (props.progress >= 75) return '#8bc34a';
    if (props.progress >= 50) return '#ffc107';
    if (props.progress >= 25) return '#ff9800';
    return '#f44336';
  }};
  width: ${props => `${Math.min(Math.max(props.progress, 0), 100)}%`};
  transition: width 0.3s ease-in-out;
`;

const ProgressLabel = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #666;
  margin-top: 0.25rem;
`;

const ProgressBar = ({ progress = 0, showLabel = true }) => {
  // Ensure progress is between 0 and 100
  const normalizedProgress = Math.min(Math.max(progress, 0), 100);
  
  return (
    <ProgressBarContainer>
      <ProgressBarTrack>
        <ProgressBarFill progress={normalizedProgress} />
      </ProgressBarTrack>
      
      {showLabel && (
        <ProgressLabel>
          <span>Progress</span>
          <span>{normalizedProgress}%</span>
        </ProgressLabel>
      )}
    </ProgressBarContainer>
  );
};

export default React.memo(ProgressBar);
