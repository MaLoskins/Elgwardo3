import axios from 'axios';

// Cache configuration
const CACHE_TTL = 60000; // 1 minute in milliseconds
const EXTENDED_CACHE_TTL = 300000; // 5 minutes for fallback mode
const cache = {
  todoTasks: { data: null, timestamp: 0 },
  knowledgeGraph: { data: null, timestamp: 0 },
  status: { data: null, timestamp: 0 },
  terminalOutput: { data: null, timestamp: 0 }
};

// Service health tracking
const serviceHealth = {
  todos: { healthy: true, lastCheck: 0, failCount: 0 },
  graph: { healthy: true, lastCheck: 0, failCount: 0 },
  status: { healthy: true, lastCheck: 0, failCount: 0 },
  terminal: { healthy: true, lastCheck: 0, failCount: 0 },
  execute: { healthy: true, lastCheck: 0, failCount: 0 }
};

// Default fallback data
const fallbackData = {
  todoTasks: { 
    content: "# AI Agent Terminal Interface - ToDo List\n\n## Active Tasks\n\n* [In Progress] Set up the development environment\n  * [x] Install required dependencies\n  * [x] Configure development server\n  * [ ] Set up continuous integration\n\n## Pending Tasks\n\n* Implement user authentication\n* Create responsive UI components\n\n## Completed Tasks\n\n* [Completed] Project initialization\n  * [x] Create project structure\n  * [x] Set up version control\n", 
    timestamp: Date.now() 
  },
  knowledgeGraph: { 
    nodes: [
      { id: "1", name: "Project", type: "project" },
      { id: "2", name: "Frontend", type: "component" },
      { id: "3", name: "Backend", type: "component" }
    ], 
    links: [
      { source: "1", target: "2", value: 1 },
      { source: "1", target: "3", value: 1 }
    ] 
  },
  status: { 
    agentStatus: 'idle', 
    systemStatus: 'online', 
    lastUpdated: new Date().toISOString(), 
    version: '1.0.0' 
  },
  terminalOutput: [
    { type: 'info', content: 'Terminal initialized' },
    { type: 'command', content: 'help' },
    { type: 'output', content: 'Available commands:\n- status: Display system status\n- execute [task]: Execute a new task\n- help: Show this help message' }
  ]
};

// Base API URL - dynamically determined from current location
const getBaseUrl = () => {
  const protocol = window.location.protocol;
  const host = window.location.host;
  return `${protocol}//${host}`;
};

// Check if cache is valid
const isCacheValid = (cacheKey, extendedTtl = false) => {
  if (!cache[cacheKey].data) return false;
  const now = Date.now();
  const ttl = extendedTtl ? EXTENDED_CACHE_TTL : CACHE_TTL;
  return now - cache[cacheKey].timestamp < ttl;
};

// Update cache
const updateCache = (cacheKey, data) => {
  cache[cacheKey] = {
    data,
    timestamp: Date.now()
  };
  return data;
};

// Update service health status
const updateServiceHealth = (service, isHealthy) => {
  const now = Date.now();
  
  if (isHealthy) {
    serviceHealth[service] = {
      healthy: true,
      lastCheck: now,
      failCount: 0
    };
  } else {
    const currentHealth = serviceHealth[service];
    serviceHealth[service] = {
      healthy: false,
      lastCheck: now,
      failCount: currentHealth.failCount + 1
    };
  }
  
  return serviceHealth[service];
};

// Check if service is in fallback mode
const isServiceInFallbackMode = (service) => {
  return !serviceHealth[service].healthy && serviceHealth[service].failCount >= 3;
};

// Get all service health statuses
const getServiceHealthStatus = () => {
  return { ...serviceHealth };
};

// API request with error handling, retries, and circuit breaker
const apiRequest = async (endpoint, method = 'GET', data = null, retries = 2, timeout = 8000) => {
  // Extract service name from endpoint
  const service = endpoint.replace('/', '').split('/')[0] || 'status';
  
  // Check if service is in circuit breaker mode (failed too many times recently)
  if (isServiceInFallbackMode(service)) {
    console.warn(`Service ${service} is in fallback mode. Using cached or default data.`);
    throw new Error(`Service ${service} is temporarily unavailable`);
  }
  
  const baseUrl = getBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  
  let retryCount = 0;
  let lastError = null;
  
  while (retryCount < retries) {
    try {
      const config = {
        method,
        url,
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: timeout // Add timeout to prevent long-hanging requests
      };
      
      if (data) {
        config.data = JSON.stringify(data);
      }
      
      const response = await axios(config);
      
      // Update service health on success
      updateServiceHealth(service, true);
      
      return response.data;
    } catch (error) {
      lastError = error;
      retryCount++;
      
      console.warn(`API request to ${endpoint} failed (attempt ${retryCount}/${retries}):`, error.message);
      
      // Exponential backoff with jitter
      const jitter = Math.random() * 300;
      const delay = Math.min(100 * (2 ** retryCount) + jitter, 3000);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  // Update service health on failure
  updateServiceHealth(service, false);
  
  throw lastError;
};

// Parse ToDo content into task objects
const parseTodoContent = (content) => {
  if (!content) return [];
  
  try {
    const tasks = [];
    let currentTaskId = 0;
    
    // Split content by lines
    const lines = content.split('\n');
    
    // Track current section
    let currentSection = '';
    let currentTask = null;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // Skip empty lines
      if (!line) continue;
      
      // Check for section headers
      if (line.startsWith('## ')) {
        currentSection = line.substring(3).trim().toLowerCase();
        continue;
      }
      
      // Check for task items
      if (line.startsWith('* ') || line.startsWith('- ')) {
        const taskText = line.substring(2).trim();
        
        // Determine status based on section and content
        let status = 'pending';
        if (currentSection.includes('completed') || 
            taskText.toLowerCase().includes('[completed]') || 
            taskText.toLowerCase().includes('✓')) {
          status = 'completed';
        } else if (currentSection.includes('active') || 
                  currentSection.includes('progress') ||
                  taskText.toLowerCase().includes('[in progress]')) {
          status = 'in progress';
        } else if (currentSection.includes('error') || 
                  currentSection.includes('issue') ||
                  taskText.toLowerCase().includes('[failed]')) {
          status = 'failed';
        }
        
        // Create new task
        currentTask = {
          id: `task_${++currentTaskId}`,
          description: taskText.replace(/\[.*?\]/g, '').trim(),
          status: status,
          created: new Date().toISOString(),
          updated: new Date().toISOString(),
          subtasks: []
        };
        
        tasks.push(currentTask);
      }
      
      // Check for subtask items (indented bullets)
      else if ((line.startsWith('  * ') || line.startsWith('  - ')) && currentTask) {
        const subtaskText = line.substring(4).trim();
        const isCompleted = subtaskText.toLowerCase().includes('[x]') || 
                           subtaskText.toLowerCase().includes('✓') ||
                           (currentTask.status === 'completed');
        
        currentTask.subtasks.push({
          id: `subtask_${currentTaskId}_${currentTask.subtasks.length + 1}`,
          description: subtaskText.replace(/\[x\]/i, '').replace('✓', '').trim(),
          completed: isCompleted
        });
      }
    }
    
    return tasks;
  } catch (error) {
    console.error('Error parsing todo content:', error);
    return [];
  }
};

// Get todo tasks with fallback behavior
const getTodoTasks = async (forceRefresh = false) => {
  // Return valid cache if available and not forced to refresh
  if (!forceRefresh && isCacheValid('todoTasks', isServiceInFallbackMode('todos'))) {
    return cache.todoTasks.data;
  }
  
  try {
    const response = await apiRequest('/todos');
    
    // If the response is already in task object format
    if (Array.isArray(response)) {
      return updateCache('todoTasks', response);
    }
    
    // If response is in markdown format with "content" field
    if (response && response.content) {
      // Parse the content into task objects
      const tasks = parseTodoContent(response.content);
      
      // Cache and return the parsed tasks
      return updateCache('todoTasks', tasks);
    }
    
    // If we got an unexpected response format
    console.error('Invalid response from /todos endpoint:', response);
    
    // Return fallback data
    const fallbackTasks = parseTodoContent(fallbackData.todoTasks.content);
    return updateCache('todoTasks', fallbackTasks);
    
  } catch (error) {
    console.error('Error fetching todo tasks:', error);
    
    // Return stale cache if available
    if (cache.todoTasks.data) {
      console.log('Using stale todo tasks data from cache');
      return cache.todoTasks.data;
    }
    
    // Use fallback data if in fallback mode
    if (isServiceInFallbackMode('todos')) {
      console.log('Using fallback todo tasks data');
      const fallbackTasks = parseTodoContent(fallbackData.todoTasks.content);
      return updateCache('todoTasks', fallbackTasks);
    }
    
    // Return fallback data as last resort
    const fallbackTasks = parseTodoContent(fallbackData.todoTasks.content);
    return updateCache('todoTasks', fallbackTasks);
  }
};

// Get knowledge graph with fallback behavior
const getKnowledgeGraph = async (forceRefresh = false) => {
  // Return valid cache if available and not forced to refresh
  if (!forceRefresh && isCacheValid('knowledgeGraph', isServiceInFallbackMode('graph'))) {
    return cache.knowledgeGraph.data;
  }
  
  try {
    const data = await apiRequest('/graph');
    
    // Validate basic structure
    if (!data || typeof data !== 'object') {
      throw new Error('Invalid response format from server');
    }
    
    // Ensure nodes and links are arrays
    const validatedData = {
      nodes: Array.isArray(data.nodes) ? data.nodes : [],
      links: Array.isArray(data.links) ? data.links : []
    };
    
    return updateCache('knowledgeGraph', validatedData);
  } catch (error) {
    console.error('Error fetching knowledge graph:', error);
    
    // Return stale cache if available
    if (cache.knowledgeGraph.data) {
      console.log('Using stale knowledge graph data from cache');
      return cache.knowledgeGraph.data;
    }
    
    // Return fallback data
    console.log('Using fallback knowledge graph data');
    return updateCache('knowledgeGraph', fallbackData.knowledgeGraph);
  }
};

// Get status with fallback behavior
const getStatus = async (forceRefresh = false) => {
  // Return valid cache if available and not forced to refresh
  if (!forceRefresh && isCacheValid('status', isServiceInFallbackMode('status'))) {
    return cache.status.data;
  }
  
  try {
    const data = await apiRequest('/status');
    
    // Validate and provide defaults
    const validatedData = {
      agentStatus: data?.agentStatus || 'idle',
      systemStatus: data?.systemStatus || 'online',
      lastUpdated: data?.lastUpdated || new Date().toISOString(),
      version: data?.version || '1.0.0',
      serviceHealth: getServiceHealthStatus()
    };
    
    return updateCache('status', validatedData);
  } catch (error) {
    console.error('Error fetching status:', error);
    
    // Return stale cache if available
    if (cache.status.data) {
      console.log('Using stale status data from cache');
      return cache.status.data;
    }
    
    // Return fallback data
    console.log('Using fallback status data');
    const fallbackStatusData = {
      ...fallbackData.status,
      serviceHealth: getServiceHealthStatus()
    };
    return updateCache('status', fallbackStatusData);
  }
};

// Execute task
const executeTask = async (taskInput) => {
  try {
    // Format task input if needed
    const formattedTaskInput = typeof taskInput === 'string' 
      ? { task: taskInput }
      : taskInput;
    
    const data = await apiRequest('/execute', 'POST', formattedTaskInput);
    return data;
  } catch (error) {
    console.error('Error executing task:', error);
    
    // Update service health for execute service
    updateServiceHealth('execute', false);
    
    // Re-throw error to be handled by UI
    throw error;
  }
};

// Reset service health
const resetServiceHealth = (service = null) => {
  if (service) {
    serviceHealth[service] = { healthy: true, lastCheck: Date.now(), failCount: 0 };
  } else {
    Object.keys(serviceHealth).forEach(key => {
      serviceHealth[key] = { healthy: true, lastCheck: Date.now(), failCount: 0 };
    });
  }
};

// Clear all caches
const clearAllCaches = () => {
  Object.keys(cache).forEach(key => {
    cache[key] = { data: null, timestamp: 0 };
  });
};

// Create a named export object
const apiServiceExport = {
  getTodoTasks,
  getKnowledgeGraph,
  getStatus,
  executeTask,
  resetServiceHealth,
  clearAllCaches,
  getServiceHealthStatus
};

export default apiServiceExport;