import React, { useState, useEffect, useCallback, useRef } from 'react';
import styled from 'styled-components';
import * as d3 from 'd3';

const GraphContainer = styled.div`
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
`;

const ControlsContainer = styled.div`
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 10;
  display: flex;
  gap: 5px;
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

const Title = styled.h3`
  margin: 0;
  padding: 10px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const EmptyState = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  height: calc(100% - 43px);
  color: #666;
  font-style: italic;
`;

const ErrorContainer = styled.div`
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background-color: rgba(255, 235, 238, 0.9);
  color: #b71c1c;
  padding: 15px;
  border-radius: 4px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  max-width: 80%;
  text-align: center;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
`;

const LoadingOverlay = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 50;
`;

const Spinner = styled.div`
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%;
  border-top: 4px solid #3498db;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
  
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const ConnectionStatus = styled.div`
  display: flex;
  align-items: center;
  margin-left: 10px;
  
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

const DebugInfo = styled.div`
  position: absolute;
  bottom: 10px;
  left: 10px;
  background-color: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 5px;
  border-radius: 4px;
  font-size: 10px;
  z-index: 100;
  max-width: 300px;
  word-break: break-all;
`;

// Sample default data to ensure visualization works
const DEFAULT_GRAPH_DATA = {
  nodes: [
    { id: "default-1", name: "Project", type: "project" },
    { id: "default-2", name: "Component A", type: "component" },
    { id: "default-3", name: "Component B", type: "component" },
    { id: "default-4", name: "Task 1", type: "task" },
    { id: "default-5", name: "Task 2", type: "task" }
  ],
  links: [
    { source: "default-1", target: "default-2", value: 1 },
    { source: "default-1", target: "default-3", value: 1 },
    { source: "default-2", target: "default-4", value: 1 },
    { source: "default-3", target: "default-5", value: 1 }
  ]
};

const GraphViewer = ({ data, onRefresh, isLoading = false, error = null, connected = true, debug = true }) => {
  const containerRef = useRef(null);
  const svgRef = useRef(null);
  const simulationRef = useRef(null);
  const [localError, setLocalError] = useState(null);
  const [isRendering, setIsRendering] = useState(false);
  const [debugInfo, setDebugInfo] = useState({});
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  
  // Track if the graph was ever initialized
  const [initialized, setInitialized] = useState(false);
  
  // Clean up graph data for rendering - ensure we have valid objects
  const prepareGraphData = useCallback((graphData) => {
    if (!graphData) return null;
    
    // Clone to avoid modifying original
    const cleanData = {
      nodes: [],
      links: []
    };
    
    // Process nodes
    if (Array.isArray(graphData.nodes)) {
      cleanData.nodes = graphData.nodes.map(node => {
        // Create valid node objects
        return {
          id: String(node.id || `node-${Math.random().toString(36).substr(2, 9)}`),
          name: node.name || node.id || 'Unnamed',
          type: node.type || 'default',
          ...node // keep other properties
        };
      });
    }
    
    // Process links
    if (Array.isArray(graphData.links)) {
      cleanData.links = graphData.links
        .filter(link => {
          // Source and target must be valid
          return link.source && link.target;
        })
        .map(link => {
          // Create valid link objects
          return {
            source: String(link.source),
            target: String(link.target),
            value: link.value || 1,
            ...link // keep other properties
          };
        });
    }
    
    // Update debug info
    setDebugInfo(prev => ({
      ...prev,
      nodesCount: cleanData.nodes.length,
      linksCount: cleanData.links.length,
      lastCleanTime: new Date().toISOString()
    }));
    
    return cleanData;
  }, []);
  
  // Function to initialize D3 graph
  const initializeGraph = useCallback(() => {
    if (!containerRef.current) return;
    
    try {
      const container = containerRef.current;
      
      // Get container dimensions
      const boundingRect = container.getBoundingClientRect();
      const width = boundingRect.width;
      const height = boundingRect.height - 43; // Subtract header height
      
      setDimensions({ width, height });
      
      // Clear any existing SVG
      d3.select(container).selectAll("svg").remove();
      
      // Create new SVG
      const svg = d3.select(container)
        .append("svg")
        .attr("width", width)
        .attr("height", height)
        .style("background-color", "#ffffff")
        .call(d3.zoom().on("zoom", (event) => {
          g.attr("transform", event.transform);
        }));
      
      // Create container group for zoom
      const g = svg.append("g");
      
      // Create forces for simulation
      const simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(20));
      
      // Store references
      svgRef.current = svg;
      simulationRef.current = simulation;
      
      // Update debug info
      setDebugInfo(prev => ({
        ...prev,
        svgWidth: width,
        svgHeight: height,
        initTime: new Date().toISOString()
      }));
      
      setInitialized(true);
      
      return { svg, g, simulation };
    } catch (err) {
      console.error('Error initializing graph:', err);
      setLocalError(`Failed to initialize graph: ${err.message || 'Unknown error'}`);
      return null;
    }
  }, []);
  
  // Function to update graph with data
  const updateGraph = useCallback((graphData) => {
    if (!svgRef.current || !simulationRef.current || !graphData) return;
    
    try {
      setIsRendering(true);
      
      // Get references
      const svg = svgRef.current;
      const simulation = simulationRef.current;
      
      // Get SVG group
      const g = svg.select("g");
      g.selectAll("*").remove();
      
      // Update debug info
      setDebugInfo(prev => ({
        ...prev,
        updateStarted: new Date().toISOString(),
        dataNodeCount: graphData.nodes?.length || 0,
        dataLinkCount: graphData.links?.length || 0
      }));
      
      // Create link elements
      const link = g.append("g")
        .attr("class", "links")
        .selectAll("line")
        .data(graphData.links)
        .enter()
        .append("line")
        .attr("stroke", "#999")
        .attr("stroke-opacity", 0.6)
        .attr("stroke-width", d => Math.sqrt(d.value || 1));
      
      // Create node elements
      const node = g.append("g")
        .attr("class", "nodes")
        .selectAll("circle")
        .data(graphData.nodes)
        .enter()
        .append("circle")
        .attr("r", 10)
        .attr("fill", d => d.type === 'task' ? '#ff7f0e' : '#1f77b4')
        .call(d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended));
      
      // Create node labels
      const label = g.append("g")
        .attr("class", "labels")
        .selectAll("text")
        .data(graphData.nodes)
        .enter()
        .append("text")
        .text(d => d.name)
        .attr("font-size", 10)
        .attr("dx", 12)
        .attr("dy", 4);
      
      // Set up node tooltips
      node.append("title")
        .text(d => d.name);
      
      // Update simulation with new data
      simulation.nodes(graphData.nodes)
        .on("tick", ticked);
      
      simulation.force("link")
        .links(graphData.links);
      
      // Restart simulation
      simulation.alpha(1).restart();
      
      // Tick function to update positions
      function ticked() {
        link
          .attr("x1", d => d.source.x)
          .attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x)
          .attr("y2", d => d.target.y);
        
        node
          .attr("cx", d => d.x)
          .attr("cy", d => d.y);
        
        label
          .attr("x", d => d.x)
          .attr("y", d => d.y);
      }
      
      // Drag functions
      function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      }
      
      function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
      }
      
      function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      }
      
      // Clear any errors
      setLocalError(null);
      
      // Update debug info
      setDebugInfo(prev => ({
        ...prev,
        updateCompleted: new Date().toISOString(),
        renderedNodes: graphData.nodes.length,
        renderedLinks: graphData.links.length
      }));
    } catch (err) {
      console.error('Error updating graph:', err);
      setLocalError(`Failed to render graph: ${err.message || 'Unknown error'}`);
      
      setDebugInfo(prev => ({
        ...prev,
        updateError: err.message,
        errorTime: new Date().toISOString()
      }));
    } finally {
      setIsRendering(false);
    }
  }, []);
  
  // Resize handling
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && initialized) {
        const boundingRect = containerRef.current.getBoundingClientRect();
        const width = boundingRect.width;
        const height = boundingRect.height - 43;
        
        // Only update if dimensions changed
        if (width !== dimensions.width || height !== dimensions.height) {
          setDimensions({ width, height });
          
          // Update SVG dimensions
          if (svgRef.current) {
            svgRef.current
              .attr("width", width)
              .attr("height", height);
            
            // Update forces
            if (simulationRef.current) {
              simulationRef.current
                .force("center", d3.forceCenter(width / 2, height / 2))
                .alpha(0.3)
                .restart();
            }
          }
        }
      }
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [dimensions, initialized]);
  
  // Initialize on mount
  useEffect(() => {
    if (containerRef.current && !initialized) {
      initializeGraph();
    }
  }, [initializeGraph, initialized]);
  
  // Update graph when data changes
  useEffect(() => {
    if (!initialized) return;
    
    let graphData;
    
    // Check if we have valid data
    if (data && data.nodes && data.nodes.length > 0) {
      graphData = prepareGraphData(data);
      console.log("Using provided graph data:", graphData);
    } else {
      // Use default data as fallback
      graphData = prepareGraphData(DEFAULT_GRAPH_DATA);
      console.log("Using default graph data:", graphData);
    }
    
    if (graphData && graphData.nodes.length > 0) {
      updateGraph(graphData);
    }
  }, [data, initialized, prepareGraphData, updateGraph]);
  
  // Reset zoom
  const handleResetZoom = useCallback(() => {
    if (svgRef.current) {
      try {
        svgRef.current.transition().duration(750).call(
          d3.zoom().transform,
          d3.zoomIdentity
        );
      } catch (err) {
        console.error('Error resetting zoom:', err);
        setLocalError(`Failed to reset zoom: ${err.message || 'Unknown error'}`);
      }
    }
  }, []);
  
  // Refresh graph
  const handleRefresh = useCallback(() => {
    if (onRefresh) {
      try {
        onRefresh();
        setLocalError(null);
      } catch (err) {
        console.error('Error refreshing graph:', err);
        setLocalError(`Failed to refresh graph: ${err.message || 'Unknown error'}`);
      }
    }
  }, [onRefresh]);
  
  // Handle error dismissal
  const handleDismissError = useCallback(() => {
    setLocalError(null);
  }, []);
  
  // Determine if we should show an error
  const displayError = error || localError;
  
  // Determine if we should show loading
  const showLoading = isLoading || isRendering;
  
  // Force graph re-initialization
  const handleReinitialize = useCallback(() => {
    setInitialized(false);
    setTimeout(() => {
      initializeGraph();
    }, 100);
  }, [initializeGraph]);
  
  return (
    <GraphContainer ref={containerRef}>
      <Title>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          Knowledge Graph
          {connected !== undefined && (
            <ConnectionStatus>
              <div className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></div>
              <span className="status-text">{connected ? 'Connected' : 'Disconnected'}</span>
            </ConnectionStatus>
          )}
        </div>
      </Title>
      
      <ControlsContainer>
        <Button onClick={handleResetZoom} disabled={showLoading || !connected}>Reset Zoom</Button>
        <Button onClick={handleRefresh} disabled={showLoading || !connected}>
          {showLoading ? 'Loading...' : 'Refresh'}
        </Button>
        <Button onClick={handleReinitialize}>Reinitialize</Button>
      </ControlsContainer>
      
      {showLoading && (
        <LoadingOverlay>
          <Spinner />
        </LoadingOverlay>
      )}
      
      {displayError && (
        <ErrorContainer>
          <p>{displayError}</p>
          <Button onClick={handleDismissError}>Dismiss</Button>
          <Button onClick={handleRefresh} disabled={showLoading || !connected}>
            Retry
          </Button>
        </ErrorContainer>
      )}
      
      {(!initialized || (!data?.nodes?.length && !isRendering && !displayError)) && (
        <EmptyState>
          {!initialized 
            ? 'Initializing graph...' 
            : connected 
              ? 'No graph data available - will use default visualization' 
              : 'Disconnected - Cannot load graph data'}
        </EmptyState>
      )}
      
      {debug && (
        <DebugInfo>
          <div>Data Nodes: {debugInfo.dataNodeCount || 0}</div>
          <div>Data Links: {debugInfo.dataLinkCount || 0}</div>
          <div>Rendered: {debugInfo.renderedNodes || 0} nodes, {debugInfo.renderedLinks || 0} links</div>
          <div>Size: {dimensions.width}×{dimensions.height}px</div>
          <div>Initialized: {initialized ? 'Yes' : 'No'}</div>
        </DebugInfo>
      )}
    </GraphContainer>
  );
};

export default React.memo(GraphViewer);