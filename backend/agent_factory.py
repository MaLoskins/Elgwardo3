"""
Agent Factory module for the AI Agent Terminal Interface.
Provides factory methods for creating and configuring specialized agents.
"""

import os
import logging
from typing import Dict, Any, Type, Optional

from agents.coder_agent import CoderAgent
from agents.researcher_agent import ResearcherAgent
from agents.formatter_agent import FormatterAgent

logger = logging.getLogger(__name__)

class AgentFactory:
    """
    Factory class for creating and configuring specialized agents.
    
    This class handles the creation, configuration, and management of
    different agent types used in the AI Agent Terminal Interface.
    """
    
    def __init__(self, openai_api_key: str, brave_search_api_key: str = None):
        """
        Initialize the Agent Factory.
        
        Args:
            openai_api_key: API key for OpenAI
            brave_search_api_key: API key for Brave Search (optional)
        """
        self.openai_api_key = openai_api_key
        self.brave_search_api_key = brave_search_api_key
        self.agent_types = {
            "coder": CoderAgent,
            "researcher": ResearcherAgent,
            "formatter": FormatterAgent
        }
        self.agent_configs = {
            "coder": {
                "description": "Specialized in code generation and implementation",
                "capabilities": [
                    "Generate code from requirements",
                    "Fix code errors",
                    "Refine existing code",
                    "Create complex applications"
                ],
                "requires_knowledge_graph": True,
                "requires_brave_search": False
            },
            "researcher": {
                "description": "Specialized in research and information gathering",
                "capabilities": [
                    "Search for information",
                    "Analyze errors",
                    "Provide context",
                    "Verify completeness"
                ],
                "requires_knowledge_graph": True,
                "requires_brave_search": True
            },
            "formatter": {
                "description": "Specialized in code formatting and style",
                "capabilities": [
                    "Format code",
                    "Apply style guidelines",
                    "Ensure consistent formatting",
                    "Validate file structure"
                ],
                "requires_knowledge_graph": False,
                "requires_brave_search": False
            }
        }
        
        # Cache for created agents
        self.agent_instances = {}
        
        logger.info("Agent Factory initialized")
    
    def get_agent_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Get available agent types and their configurations.
        
        Returns:
            Dictionary mapping agent types to their configurations
        """
        return self.agent_configs
    
    def create_agent(
        self, 
        agent_type: str, 
        model: str = "gpt-4o", 
        knowledge_graph = None,
        **kwargs
    ) -> Any:
        """
        Create a new agent of the specified type.
        
        Args:
            agent_type: Type of agent to create
            model: Model to use for the agent
            knowledge_graph: Knowledge graph instance (if required)
            **kwargs: Additional arguments to pass to the agent constructor
            
        Returns:
            Agent instance
            
        Raises:
            ValueError: If agent_type is invalid or required dependencies are missing
        """
        if agent_type not in self.agent_types:
            raise ValueError(f"Invalid agent type: {agent_type}")
        
        # Check if we already have an instance of this agent type
        cache_key = f"{agent_type}_{model}"
        if cache_key in self.agent_instances:
            logger.info(f"Returning cached instance of {agent_type} agent")
            return self.agent_instances[cache_key]
        
        # Check required dependencies
        config = self.agent_configs[agent_type]
        if config["requires_knowledge_graph"] and knowledge_graph is None:
            raise ValueError(f"{agent_type} agent requires a knowledge graph")
        
        if config["requires_brave_search"] and self.brave_search_api_key is None:
            raise ValueError(f"{agent_type} agent requires a Brave Search API key")
        
        # Create agent based on type
        agent_class = self.agent_types[agent_type]
        
        try:
            # Create with the appropriate arguments based on agent type
            if agent_type == "coder":
                agent = agent_class(
                    openai_api_key=self.openai_api_key,
                    model=model,
                    knowledge_graph=knowledge_graph,
                    **kwargs
                )
            elif agent_type == "researcher":
                agent = agent_class(
                    openai_api_key=self.openai_api_key,
                    brave_search_api_key=self.brave_search_api_key,
                    model=model,
                    knowledge_graph=knowledge_graph,
                    **kwargs
                )
            elif agent_type == "formatter":
                agent = agent_class(
                    openai_api_key=self.openai_api_key,
                    model=model,
                    **kwargs
                )
            else:
                # Generic instantiation for custom agent types
                agent = agent_class(
                    openai_api_key=self.openai_api_key,
                    model=model,
                    **kwargs
                )
            
            # Cache the agent instance
            self.agent_instances[cache_key] = agent
            
            logger.info(f"Created {agent_type} agent with model {model}")
            return agent
            
        except Exception as e:
            logger.error(f"Error creating {agent_type} agent: {str(e)}")
            raise
    
    def create_all_agents(
        self, 
        model: str = "gpt-4o", 
        knowledge_graph = None
    ) -> Dict[str, Any]:
        """
        Create all available agent types.
        
        Args:
            model: Model to use for the agents
            knowledge_graph: Knowledge graph instance
            
        Returns:
            Dictionary mapping agent types to agent instances
        """
        agents = {}
        for agent_type in self.agent_types:
            try:
                agents[agent_type] = self.create_agent(
                    agent_type=agent_type,
                    model=model,
                    knowledge_graph=knowledge_graph
                )
            except Exception as e:
                logger.error(f"Error creating {agent_type} agent: {str(e)}")
                # Continue with other agents on error
        
        return agents
    
    def get_cached_agent(self, agent_type: str, model: str = "gpt-4o") -> Optional[Any]:
        """
        Get a cached agent instance if available.
        
        Args:
            agent_type: Type of agent
            model: Model of the agent
            
        Returns:
            Agent instance, or None if not cached
        """
        cache_key = f"{agent_type}_{model}"
        return self.agent_instances.get(cache_key)
    
    def update_all_agents_model(self, new_model: str) -> None:
        """
        Update the model for all agent instances.
        
        Args:
            new_model: New model to use
        """
        for agent_instance in self.agent_instances.values():
            if hasattr(agent_instance, "set_model"):
                agent_instance.set_model(new_model)
        
        logger.info(f"Updated all agents to use model {new_model}")
    
    def clear_cache(self) -> None:
        """Clear the agent instance cache."""
        self.agent_instances = {}
        logger.info("Cleared agent instance cache")
