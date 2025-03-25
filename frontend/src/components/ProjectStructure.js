import React, { useState, useEffect } from 'react';
import styled from 'styled-components';
import { FolderOpen, Folder, File, ChevronRight, ChevronDown, Code, Settings, Edit3 } from 'lucide-react';

const ProjectContainer = styled.div`
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: ${props => props.theme.cardBackground};
  border-radius: 8px;
  box-shadow: ${props => props.theme.shadow};
  transition: all 0.3s ease;
`;

const ProjectHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid ${props => props.theme.border};
`;

const ProjectTitle = styled.h2`
  margin: 0;
  font-size: 1.2rem;
  color: ${props => props.theme.text};
`;

const ViewControls = styled.div`
  display: flex;
  gap: 8px;
`;

const ViewButton = styled.button`
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: ${props => props.active ? props.theme.secondary : props.theme.cardBackground};
  color: ${props => props.active ? 'white' : props.theme.text};
  border: 1px solid ${props => props.active ? props.theme.secondary : props.theme.border};
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.8rem;
  cursor: pointer;
  gap: 4px;
  transition: all 0.2s ease;
  
  &:hover {
    background-color: ${props => props.active ? props.theme.secondaryHover : props.theme.border};
    transform: translateY(-1px);
  }
  
  &:active {
    transform: translateY(0);
  }
`;

const ProjectContent = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
  
  &::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: ${props => props.theme.background};
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.border};
    border-radius: 3px;
  }
  
  &::-webkit-scrollbar-thumb:hover {
    background: ${props => props.theme.secondary};
  }
`;

const TreeView = styled.div`
  font-family: monospace;
  font-size: 0.9rem;
  color: ${props => props.theme.text};
`;

const TreeItem = styled.div`
  padding: 4px 0;
  user-select: none;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.2s ease;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding-left: ${props => props.depth * 16}px;
  
  &:hover {
    background-color: ${props => props.theme.border}40;
  }
  
  ${props => props.selected && `
    background-color: ${props.theme.secondary}40;
    font-weight: bold;
  `}
`;

const ItemContent = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
`;

const ItemExpander = styled.div`
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${props => props.theme.text};
`;

const ItemIcon = styled.div`
  display: flex;
  align-items: center;
  color: ${props => {
    switch (props.type) {
      case 'directory':
        return props.theme.warning;
      case 'file':
        return props.theme.text;
      case 'py':
        return props.theme.success;
      case 'js':
      case 'jsx':
      case 'ts':
      case 'tsx':
        return props.theme.warning;
      case 'html':
        return props.theme.error;
      case 'css':
        return props.theme.info;
      case 'json':
        return props.theme.secondary;
      default:
        return props.theme.text;
    }
  }};
  transition: color 0.3s ease;
`;

const ItemName = styled.div`
  margin-left: 4px;
  color: ${props => props.theme.text};
`;

const DetailsPanel = styled.div`
  height: 200px;
  border-top: 1px solid ${props => props.theme.border};
  padding: 12px;
  color: ${props => props.theme.text};
  font-size: 0.9rem;
  overflow-y: auto;
  display: ${props => props.visible ? 'block' : 'none'};
  background-color: ${props => props.theme.cardBackground};
  transition: all 0.3s ease;
  
  &::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: ${props => props.theme.background};
  }
  
  &::-webkit-scrollbar-thumb {
    background: ${props => props.theme.border};
    border-radius: 3px;
  }
  
  &::-webkit-scrollbar-thumb:hover {
    background: ${props => props.theme.secondary};
  }
`;

const DetailHeader = styled.div`
  font-weight: bold;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: ${props => props.theme.text};
`;

const DetailPath = styled.div`
  font-family: monospace;
  margin-bottom: 12px;
  color: ${props => props.theme.secondary};
  word-break: break-all;
  padding: 4px 8px;
  background-color: ${props => props.theme.background};
  border-radius: 4px;
  border-left: 3px solid ${props => props.theme.secondary};
`;

const NoFilesMessage = styled.div`
  padding: 24px;
  text-align: center;
  color: ${props => props.theme.textSecondary};
  font-style: italic;
`;

const DetailItem = styled.div`
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  
  strong {
    color: ${props => props.theme.text};
  }
`;

// Function to get file type icon
const getFileIcon = (filename) => {
  const extension = filename.split('.').pop().toLowerCase();
  
  switch (extension) {
    case 'py':
      return <Code size={16} />;
    case 'js':
    case 'jsx':
      return <Code size={16} />;
    case 'ts':
    case 'tsx':
      return <Code size={16} />;
    case 'html':
      return <Code size={16} />;
    case 'css':
      return <Code size={16} />;
    case 'json':
      return <Settings size={16} />;
    case 'md':
      return <Edit3 size={16} />;
    default:
      return <File size={16} />;
  }
};

// File type to readable format
const getFileType = (filename) => {
  const extension = filename.split('.').pop().toLowerCase();
  
  const typeMap = {
    'py': 'Python',
    'js': 'JavaScript',
    'jsx': 'React JSX',
    'ts': 'TypeScript',
    'tsx': 'React TSX',
    'html': 'HTML',
    'css': 'CSS',
    'json': 'JSON',
    'md': 'Markdown'
  };
  
  return typeMap[extension] || 'Plain Text';
};

const ProjectStructure = ({ projectStructure, onFileSelect }) => {
  const [expandedDirs, setExpandedDirs] = useState({});
  const [selectedItem, setSelectedItem] = useState(null);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const [viewMode, setViewMode] = useState('tree'); // 'tree' or 'flat'
  
  useEffect(() => {
    // Auto-expand root directory on mount
    setExpandedDirs(prev => ({
      ...prev,
      '/workspace': true
    }));
  }, []);
  
  const toggleDir = (path) => {
    setExpandedDirs(prev => ({
      ...prev,
      [path]: !prev[path]
    }));
  };
  
  const selectItem = (item) => {
    setSelectedItem(item);
    setDetailsVisible(true);
    
    if (onFileSelect && item.type === 'file') {
      onFileSelect(item);
    }
  };
  
  const formatData = (data) => {
    if (!data || !data.directories) return [];
    
    if (viewMode === 'flat') {
      // Flat view - just show all files
      return Object.values(data.files || {})
        .map(file => ({
          ...file,
          type: 'file'
        }))
        .sort((a, b) => a.name.localeCompare(b.name));
    }
    
    // Tree view - build hierarchical structure
    const root = {
      name: 'workspace',
      path: '/workspace',
      type: 'directory',
      children: []
    };
    
    // Add directories
    const directoryMap = {
      '/workspace': root
    };
    
    // Sort directories by path length to ensure parent dirs are processed first
    const sortedDirs = Object.values(data.directories || {})
      .sort((a, b) => a.path.length - b.path.length);
    
    // Process directories
    for (const dir of sortedDirs) {
      if (dir.path === '/workspace') continue; // Skip root
      
      const parent = directoryMap[dir.path.substring(0, dir.path.lastIndexOf('/')) || '/workspace'];
      
      if (parent) {
        const dirNode = {
          name: dir.name,
          path: dir.path,
          type: 'directory',
          children: []
        };
        
        parent.children.push(dirNode);
        directoryMap[dir.path] = dirNode;
      }
    }
    
    // Add files to directories
    Object.values(data.files || {}).forEach(file => {
      const parent = directoryMap[file.directory] || root;
      
      parent.children.push({
        name: file.name,
        path: file.path,
        type: 'file'
      });
    });
    
    // Sort directory children (directories first, then files, both alphabetically)
    Object.values(directoryMap).forEach(dir => {
      dir.children.sort((a, b) => {
        if (a.type !== b.type) {
          return a.type === 'directory' ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      });
    });
    
    return [root];
  };
  
  const renderTree = (items, depth = 0) => {
    return items.map(item => {
      const isDirectory = item.type === 'directory';
      const isExpanded = expandedDirs[item.path];
      const isSelected = selectedItem && selectedItem.path === item.path;
      const fileType = isDirectory ? 'directory' : item.name.split('.').pop();
      
      return (
        <React.Fragment key={item.path}>
          <TreeItem 
            depth={depth}
            selected={isSelected}
            onClick={() => {
              if (isDirectory) {
                toggleDir(item.path);
              }
              selectItem(item);
            }}
          >
            <ItemContent>
              <ItemExpander>
                {isDirectory && (
                  isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />
                )}
              </ItemExpander>
              
              <ItemIcon type={fileType}>
                {isDirectory ? (
                  isExpanded ? <FolderOpen size={16} /> : <Folder size={16} />
                ) : getFileIcon(item.name)}
              </ItemIcon>
              
              <ItemName>{item.name}</ItemName>
            </ItemContent>
          </TreeItem>
          
          {isDirectory && isExpanded && item.children && (
            renderTree(item.children, depth + 1)
          )}
        </React.Fragment>
      );
    });
  };
  
  const formattedData = formatData(projectStructure);
  
  return (
    <ProjectContainer>
      <ProjectHeader>
        <ProjectTitle>Project Structure</ProjectTitle>
        <ViewControls>
          <ViewButton 
            active={viewMode === 'tree'} 
            onClick={() => setViewMode('tree')}
          >
            <Folder size={16} />
            Tree
          </ViewButton>
          <ViewButton 
            active={viewMode === 'flat'} 
            onClick={() => setViewMode('flat')}
          >
            <File size={16} />
            Files
          </ViewButton>
        </ViewControls>
      </ProjectHeader>
      
      <ProjectContent>
        <TreeView>
          {formattedData.length > 0 ? (
            renderTree(formattedData)
          ) : (
            <NoFilesMessage>
              No files available yet. Files will appear here as your project grows.
            </NoFilesMessage>
          )}
        </TreeView>
      </ProjectContent>
      
      <DetailsPanel visible={detailsVisible}>
        {selectedItem && (
          <>
            <DetailHeader>
              <ItemIcon type={selectedItem.type === 'directory' ? 'directory' : selectedItem.name.split('.').pop()}>
                {selectedItem.type === 'directory' ? (
                  <Folder size={16} />
                ) : getFileIcon(selectedItem.name)}
              </ItemIcon>
              {selectedItem.name}
            </DetailHeader>
            
            <DetailPath>{selectedItem.path}</DetailPath>
            
            {selectedItem.type === 'file' && (
              <DetailItem>
                <strong>Type:</strong> {getFileType(selectedItem.name)}
              </DetailItem>
            )}
            
            {selectedItem.type === 'directory' && (
              <DetailItem>
                <strong>Items:</strong> {selectedItem.children ? selectedItem.children.length : 0}
              </DetailItem>
            )}
          </>
        )}
      </DetailsPanel>
    </ProjectContainer>
  );
};

export default ProjectStructure;
