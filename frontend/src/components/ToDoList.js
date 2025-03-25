import React, { useState, useCallback } from 'react';
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

const TaskList = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 0;
`;

const TaskItem = styled.div`
  padding: 10px 15px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: #f9f9f9;
  }
  
  &:last-child {
    border-bottom: none;
  }
`;

const TaskHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
`;

const TaskDescription = styled.div`
  font-weight: ${props => props.completed ? 'normal' : 'bold'};
  color: ${props => props.completed ? '#888' : '#333'};
  text-decoration: ${props => props.completed ? 'line-through' : 'none'};
`;

const TaskStatus = styled.span`
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
  background-color: ${props => {
    switch (props.status.toLowerCase()) {
      case 'completed': return '#4caf50';
      case 'in progress': return '#2196f3';
      case 'pending': return '#ff9800';
      case 'failed': return '#f44336';
      default: return '#9e9e9e';
    }
  }};
  color: white;
`;

const TaskMeta = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
`;

const SubtaskList = styled.div`
  margin-top: 5px;
  padding-left: 15px;
`;

const SubtaskItem = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 3px;
  font-size: 13px;
  color: ${props => props.completed ? '#888' : '#555'};
`;

const Checkbox = styled.span`
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 1px solid #aaa;
  border-radius: 2px;
  margin-right: 8px;
  position: relative;
  
  &::after {
    content: '';
    position: absolute;
    display: ${props => props.checked ? 'block' : 'none'};
    top: 1px;
    left: 4px;
    width: 4px;
    height: 8px;
    border: solid #4caf50;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
  }
`;

const FilterBar = styled.div`
  display: flex;
  padding: 10px;
  border-bottom: 1px solid #eee;
  gap: 10px;
`;

const FilterButton = styled.button`
  padding: 5px 10px;
  background-color: ${props => props.active ? '#4a90e2' : '#f5f5f5'};
  color: ${props => props.active ? 'white' : '#333'};
  border: 1px solid ${props => props.active ? '#4a90e2' : '#ddd'};
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  
  &:hover {
    background-color: ${props => props.active ? '#3a80d2' : '#e5e5e5'};
  }
`;

const EmptyState = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
  color: #888;
  font-style: italic;
  padding: 20px;
  text-align: center;
`;

const ErrorState = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
  color: #f44336;
  font-style: italic;
  padding: 10px;
  text-align: center;
`;

const ToDoList = ({ tasks }) => {
  const [filter, setFilter] = useState('all');
  const [expandedTasks, setExpandedTasks] = useState({});
  
  // Ensure tasks is always an array and handle both array and object formats
  const processedTasks = React.useMemo(() => {
    if (!tasks) return [];
    
    // If it's already an array, use it
    if (Array.isArray(tasks)) {
      return tasks;
    }
    
    // If it's string content from the API response
    if (tasks.content && typeof tasks.content === 'string') {
      try {
        // Try to parse it from markdown-like format (simple approach)
        const lines = tasks.content.split('\n');
        const resultTasks = [];
        let currentTask = null;
        let taskId = 1;
        
        for (const line of lines) {
          if (line.startsWith('* ') || line.startsWith('- ')) {
            // This is a main task
            const description = line.substring(2).trim();
            let status = 'pending';
            
            if (description.toLowerCase().includes('[completed]') || 
                description.toLowerCase().includes('✓')) {
              status = 'completed';
            } else if (description.toLowerCase().includes('[in progress]')) {
              status = 'in progress';
            }
            
            currentTask = {
              id: `task_${taskId++}`,
              description: description.replace(/\[.*?\]/g, '').trim(),
              status: status,
              created: new Date().toISOString(),
              updated: new Date().toISOString(),
              subtasks: []
            };
            
            resultTasks.push(currentTask);
          } else if (currentTask && (line.startsWith('  * ') || line.startsWith('  - '))) {
            // This is a subtask
            const subtaskDescription = line.substring(4).trim();
            const completed = subtaskDescription.toLowerCase().includes('[x]') || 
                              subtaskDescription.toLowerCase().includes('✓');
            
            currentTask.subtasks.push({
              id: `subtask_${currentTask.id}_${currentTask.subtasks.length + 1}`,
              description: subtaskDescription.replace(/\[.*?\]/g, '').trim(),
              completed: completed
            });
          }
        }
        
        return resultTasks;
      } catch (error) {
        console.error('Error parsing todo content:', error);
        return [];
      }
    }
    
    // If it's some other format, return empty array
    return [];
  }, [tasks]);
  
  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch (error) {
      return 'Invalid date';
    }
  };
  
  // Toggle task expansion
  const toggleTaskExpansion = useCallback((taskId) => {
    setExpandedTasks(prev => ({
      ...prev,
      [taskId]: !prev[taskId]
    }));
  }, []);
  
  // Handle filter change
  const handleFilterChange = useCallback((newFilter) => {
    setFilter(newFilter);
  }, []);
  
  // Filter tasks based on selected filter
  const filteredTasks = processedTasks.filter(task => {
    if (filter === 'all') return true;
    return task.status.toLowerCase() === filter.toLowerCase();
  });
  
  // Sort tasks by priority: In Progress > Pending > Completed
  const sortedTasks = [...filteredTasks].sort((a, b) => {
    const priorityMap = {
      'in progress': 0,
      'pending': 1,
      'completed': 2,
      'failed': 3
    };
    
    const priorityA = priorityMap[a.status.toLowerCase()] ?? 4;
    const priorityB = priorityMap[b.status.toLowerCase()] ?? 4;
    
    return priorityA - priorityB;
  });
  
  return (
    <Container>
      <Title>To-Do List</Title>
      
      <FilterBar>
        <FilterButton 
          active={filter === 'all'} 
          onClick={() => handleFilterChange('all')}
        >
          All
        </FilterButton>
        <FilterButton 
          active={filter === 'in progress'} 
          onClick={() => handleFilterChange('in progress')}
        >
          In Progress
        </FilterButton>
        <FilterButton 
          active={filter === 'pending'} 
          onClick={() => handleFilterChange('pending')}
        >
          Pending
        </FilterButton>
        <FilterButton 
          active={filter === 'completed'} 
          onClick={() => handleFilterChange('completed')}
        >
          Completed
        </FilterButton>
      </FilterBar>
      
      <TaskList>
        {sortedTasks.length > 0 ? (
          sortedTasks.map(task => (
            <TaskItem 
              key={task.id} 
              onClick={() => toggleTaskExpansion(task.id)}
            >
              <TaskHeader>
                <TaskDescription completed={task.status.toLowerCase() === 'completed'}>
                  {task.description}
                </TaskDescription>
                <TaskStatus status={task.status}>
                  {task.status}
                </TaskStatus>
              </TaskHeader>
              
              <TaskMeta>
                <span>Created: {formatDate(task.created)}</span>
                <span>Updated: {formatDate(task.updated)}</span>
              </TaskMeta>
              
              {expandedTasks[task.id] && task.subtasks && task.subtasks.length > 0 && (
                <SubtaskList>
                  {task.subtasks.map(subtask => (
                    <SubtaskItem 
                      key={subtask.id} 
                      completed={subtask.completed}
                    >
                      <Checkbox checked={subtask.completed} />
                      {subtask.description}
                    </SubtaskItem>
                  ))}
                </SubtaskList>
              )}
            </TaskItem>
          ))
        ) : (
          <EmptyState>
            {filter === 'all' 
              ? 'No tasks available - Execute a command in the terminal to create tasks' 
              : `No ${filter} tasks available`}
          </EmptyState>
        )}
      </TaskList>
    </Container>
  );
};

export default React.memo(ToDoList);