"""
Researcher Agent module for the AI Agent Terminal Interface.
Specializes in gathering information and providing context for tasks.
"""

import logging
import asyncio
import json
import os
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

import openai
import httpx

from knowledge_graph import KnowledgeGraph

logger = logging.getLogger(__name__)

class ResearcherAgent:
    """
    Specialized agent focused on gathering information and context.
    
    This agent is responsible for:
    - Searching for relevant information
    - Analyzing errors and providing solutions
    - Providing context for code generation
    - Verifying task completeness based on requirements
    """
    
    def __init__(
        self,
        openai_api_key: str,
        brave_search_api_key: str,
        model: str,
        knowledge_graph: KnowledgeGraph
    ):
        """
        Initialize the Researcher Agent.
        
        Args:
            openai_api_key: API key for OpenAI
            brave_search_api_key: API key for Brave Search
            model: OpenAI model to use
            knowledge_graph: Reference to the KnowledgeGraph instance
        """
        self.openai_api_key = openai_api_key
        self.brave_search_api_key = brave_search_api_key
        self.model = model
        self.knowledge_graph = knowledge_graph
        self.broadcast_function = None
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        
        # Initialize HTTP client for Brave Search API
        self.http_client = httpx.AsyncClient(
            headers={"X-Subscription-Token": brave_search_api_key}
        )
        
        # Cache for searches to avoid redundant requests
        self.search_cache = {}
        
        logger.info("Researcher Agent initialized")
    
    def set_broadcast_function(self, broadcast_function: Callable):
        """Set the function used to broadcast messages."""
        self.broadcast_function = broadcast_function
    
    def set_model(self, model: str):
        """Update the OpenAI model selection."""
        self.model = model
        logger.info(f"Researcher Agent model updated to {model}")
    
    async def research_task(self, task: str) -> Dict[str, Any]:
        """
        Perform comprehensive research for a task.
        
        Args:
            task: Task description
            
        Returns:
            Dictionary with research results
        """
        await self._broadcast("status_update", {
            "message": "Researching task requirements and context..."
        })
        
        # First, analyze the task to determine what needs to be researched
        analysis_prompt = f"""
        Analyze this task to determine what needs to be researched:
        
        TASK: {task}
        
        What specific information would help complete this task successfully?
        
        Return a JSON object with:
        - understanding: Brief description of the task
        - key_concepts: Array of concepts that need to be understood
        - search_queries: Array of search queries to find useful information
        - code_aspects: Array of coding aspects relevant to this task
        - technologies: Array of technologies/frameworks/libraries likely needed
        
        ONLY return the JSON object. No markdown or explanations.
        """
        
        analysis = await self._request_json_from_llm(analysis_prompt)
        
        # Perform searches for each query
        search_queries = analysis.get("search_queries", [])
        search_results = {}
        
        for query in search_queries:
            await self._broadcast("status_update", {
                "message": f"Searching for: {query}..."
            })
            
            search_results[query] = await self._search_brave(query)
        
        # Combine everything into a research report
        report_prompt = f"""
        Create a comprehensive research report for this task:
        
        TASK: {task}
        
        TASK ANALYSIS:
        {json.dumps(analysis, indent=2)}
        
        SEARCH RESULTS:
        {json.dumps(search_results, indent=2)}
        
        Synthesize this information into a research report that will help implement the task.
        
        Return a JSON object with:
        - summary: Brief summary of findings
        - key_insights: Array of key insights relevant to implementation
        - implementation_recommendations: Specific recommendations for coding
        - potential_challenges: Likely challenges and how to address them
        - resources: Useful resources (links, documentation, etc.)
        - code_examples: Snippets that might be helpful (if available)
        
        ONLY return the JSON object. No markdown or explanations.
        """
        
        report = await self._request_json_from_llm(report_prompt)
        
        # Add analysis data to the report
        report["analysis"] = analysis
        report["search_queries"] = search_queries
        
        await self._broadcast("research_completed", {
            "key_concepts": len(analysis.get("key_concepts", [])),
            "insights": len(report.get("key_insights", []))
        })
        
        return report
    
    async def search_information(self, query: str) -> str:
        """
        Search for information on a specific query.
        
        Args:
            query: Search query
            
        Returns:
            Search results as formatted string
        """
        # Check cache first
        if query in self.search_cache:
            return self.search_cache[query]
        
        # Perform search
        search_results = await self._search_brave(query)
        
        # Format results
        formatted_results = self._format_search_results(search_results)
        
        # Cache results
        self.search_cache[query] = formatted_results
        
        await self._broadcast("search_completed", {
            "query": query,
            "results_count": len(search_results.get("results", []))
        })
        
        return formatted_results
    
    def _format_search_results(self, search_results: Dict[str, Any]) -> str:
        """
        Format search results into a readable string.
        
        Args:
            search_results: Raw search results
            
        Returns:
            Formatted search results
        """
        results = search_results.get("results", [])
        if not results:
            return "No search results found."
        
        formatted = []
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "No URL")
            description = result.get("description", "No description")
            
            formatted.append(f"{i}. {title}")
            formatted.append(f"   URL: {url}")
            formatted.append(f"   Description: {description}")
            formatted.append("")
        
        return "\n".join(formatted)
    
    async def analyze_error(self, error_output: str) -> Dict[str, Any]:
        """
        Analyze error output to determine the cause and potential solutions.
        
        Args:
            error_output: Error output to analyze
            
        Returns:
            Dictionary with error analysis
        """
        prompt = f"""
        Analyze this error output to determine the cause and potential solutions:
        
        ERROR OUTPUT:
        ```
        {error_output}
        ```
        
        Return a JSON object with:
        - error_type: The type of error (e.g., SyntaxError, ImportError)
        - error_message: The specific error message
        - line_number: Line number where the error occurred (if available)
        - probable_cause: Most likely cause of the error
        - potential_solutions: Array of potential solutions
        - needs_search: Boolean indicating if external search might help
        - search_query: Suggested search query if needs_search is true
        
        ONLY return the JSON object. No markdown or explanations.
        """
        
        analysis = await self._request_json_from_llm(prompt)
        
        # If external search might help, perform it
        if analysis.get("needs_search", False) and "search_query" in analysis:
            search_results = await self._search_brave(analysis["search_query"])
            analysis["search_results"] = self._format_search_results(search_results)
        
        await self._broadcast("error_analyzed", {
            "error_type": analysis.get("error_type", "Unknown"),
            "solutions_count": len(analysis.get("potential_solutions", []))
        })
        
        return analysis
    
    async def find_solution_for_error(self, command: str, error_output: str) -> Dict[str, Any]:
        """
        Find solutions for a command that produced an error.
        
        Args:
            command: Command that produced the error
            error_output: Error output
            
        Returns:
            Dictionary with solution information
        """
        # First analyze the error
        error_analysis = await self.analyze_error(error_output)
        
        # Search for solutions if needed
        search_results = ""
        if error_analysis.get("needs_search", False) and "search_query" in error_analysis:
            search_results = await self.search_information(error_analysis["search_query"])
        
        # Create the solution prompt in parts to avoid f-string with backslash issues
        solution_prompt_base = f"""
        Find a solution for this command that produced an error:
        
        COMMAND: {command}
        
        ERROR ANALYSIS:
        {json.dumps(error_analysis, indent=2)}
        """
        
        # Add search results if available
        if search_results:
            solution_prompt_base += f"""
        
        SEARCH RESULTS:
        {search_results}
        """
            
        # Add the rest of the prompt
        solution_prompt_base += """
        
        Return a JSON object with:
        - problem: Brief description of the problem
        - solution: Explanation of the solution
        - fixed_command: Corrected command that should work
        - additional_commands: Array of any additional commands that should be run
        
        ONLY return the JSON object. No markdown or explanations.
        """
        
        solution = solution_prompt_base

        
        await self._broadcast("solution_found", {
            "command": command,
            "has_fix": "fixed_command" in solution
        })
        
        return solution
    
    async def verify_completeness(self, task: str, workspace_dir: str) -> Dict[str, Any]:
        """
        Verify that all required aspects of the task have been completed.
        
        Args:
            task: Original task description
            workspace_dir: Directory containing the implementation
            
        Returns:
            Dictionary with verification results
        """
        # Get a list of files in the workspace
        # Create a summary of the workspace
        # Fix the f-string with backslash issue by using a different approach
        files = []
        for file in files:
            rel_path = os.path.relpath(file, workspace_dir)
            files.append(f"- {rel_path}")
        workspace_summary = "\n".join(files)

        
        # Create a summary of the workspace
        workspace_summary = "\n".join([
            f"- {os.path.relpath(file, workspace_dir)}" for file in files
        ])
        
        prompt = f"""
        Verify that this implementation completely fulfills the requirements for the task:
        
        TASK: {task}
        
        IMPLEMENTATION FILES:
        {workspace_summary}
        
        Check for:
        1. Completeness - Are all required aspects implemented?
        2. Missing features - Are any features missing?
        3. Required technologies - Are all required technologies used?
        
        Return a JSON object with:
        - verified: boolean (true if implementation is complete)
        - issues: array of strings describing any missing aspects
        - recommendations: array of suggestions for improvement
        
        ONLY return the JSON object. No markdown or explanations.
        """
        
        result = await self._request_json_from_llm(prompt)
        
        await self._broadcast("completeness_verified", {
            "verified": result.get("verified", False),
            "issues_count": len(result.get("issues", []))
        })
        
        return result
    
    async def _search_brave(self, query: str) -> Dict[str, Any]:
        """
        Search the web using Brave Search API.
        
        Args:
            query: Search query
            
        Returns:
            Dictionary with search results
        """
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            params = {"q": query, "count": 5}
            
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error searching Brave: {str(e)}")
            return {"results": []}
    
    async def _call_openai_api(self, prompt: str) -> str:
        """
        Call the OpenAI API with the given prompt.
        
        Args:
            prompt: Prompt to send to the API
            
        Returns:
            API response text
        """
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert research assistant with deep knowledge across "
                            "multiple domains. You provide thorough, accurate information "
                            "and analysis to help with software development tasks."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise
    
    async def _request_json_from_llm(self, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Request JSON data from the LLM with retries for valid JSON.
        
        Args:
            prompt: Prompt to send
            max_retries: Maximum number of retries
            
        Returns:
            Parsed JSON data
        """
        system_instruction = (
            "You are an AI assistant that outputs ONLY valid JSON with no markdown, "
            "no code blocks, and no extra text. If your response is not valid JSON, "
            "you will be asked to fix it."
        )
        
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content.strip()
                
                # Try to parse JSON
                result = json.loads(content)
                return result
                
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Invalid JSON (attempt {attempt + 1}): {str(e)}")
                    # Update prompt to request valid JSON
                    prompt = f"You provided invalid JSON. The error was: {str(e)}. Please fix it and return ONLY valid JSON."
                else:
                    logger.error(f"Failed to get valid JSON after {max_retries} attempts")
                    # Return empty dict as fallback
                    return {}
            except Exception as e:
                logger.error(f"Error in request_json_from_llm: {str(e)}")
                # Return empty dict as fallback
                return {}
    
    async def _broadcast(self, update_type: str, data: Dict[str, Any]):
        """
        Broadcast an update using the broadcast function.
        
        Args:
            update_type: Type of update
            data: Update data
        """
        if self.broadcast_function:
            await self.broadcast_function(update_type, data)
