"""
Agents package for the AI Agent Terminal Interface.
Provides specialized agents for different aspects of the development process.
"""

# Import all agent classes for easier access
from agents.coder_agent import CoderAgent
from agents.researcher_agent import ResearcherAgent
from agents.formatter_agent import FormatterAgent

__all__ = ['CoderAgent', 'ResearcherAgent', 'FormatterAgent']