"""
Assessment module for the AI Agent Terminal Interface.
Provides dynamic assessment of task completion and objective verification.
"""

import logging
import json
from typing import Dict, Any, List, Optional

import openai

logger = logging.getLogger(__name__)

class AssessmentSystem:
    """
    Dynamic assessment system that uses multiple LLM calls to verify task completion
    and ensure the agent continues operating until all objectives are met.
    """
    
    def __init__(self, openai_client, model: str):
        """
        Initialize the Assessment System.
        
        Args:
            openai_client: OpenAI client instance
            model: Model to use for assessments
        """
        self.openai_client = openai_client
        self.model = model
        logger.info("Assessment System initialized")
    
    async def verify_task_completion(self, task: str, code_path: str, execution_output: str, todo_content: str) -> Dict[str, Any]:
        """
        Verify if a task has been completed successfully using multiple LLM assessments.
        
        Args:
            task: Original task description
            code_path: Path to the code file
            execution_output: Terminal output from code execution
            todo_content: Current content of the ToDo.md file
            
        Returns:
            Dict containing assessment results
        """
        logger.info(f"Verifying task completion for: {task}")
        
        # Read the code file
        try:
            with open(code_path, 'r') as f:
                code_content = f.read()
        except Exception as e:
            logger.error(f"Error reading code file: {str(e)}")
            code_content = "Error reading code file"
        
        # First assessment: Code quality and correctness
        code_assessment = await self._assess_code_quality(task, code_content)
        
        # Second assessment: Execution output analysis
        execution_assessment = await self._assess_execution_output(task, execution_output)
        
        # Third assessment: Task completion verification
        completion_assessment = await self._verify_objectives_completed(task, todo_content, code_assessment, execution_assessment)
        
        # Combine all assessments
        assessment_result = {
            "code_assessment": code_assessment,
            "execution_assessment": execution_assessment,
            "completion_assessment": completion_assessment,
            "is_completed": completion_assessment.get("is_completed", False),
            "confidence": completion_assessment.get("confidence", 0),
            "recommendations": completion_assessment.get("recommendations", [])
        }
        
        logger.info(f"Task completion assessment result: {json.dumps(assessment_result, indent=2)}")
        return assessment_result
    
    async def _assess_code_quality(self, task: str, code_content: str) -> Dict[str, Any]:
        """
        Assess the quality and correctness of the generated code.
        
        Args:
            task: Original task description
            code_content: Content of the code file
            
        Returns:
            Dict containing code quality assessment
        """
        prompt = f"""
        Assess the quality and correctness of the following code for the given task:
        
        TASK: {task}
        
        CODE:
        ```
        {code_content}
        ```
        
        Please provide:
        1. An assessment of whether the code correctly implements the task requirements (true/false)
        2. A confidence score (0-100) for your assessment
        3. A list of any issues or bugs found
        4. Suggestions for improvements
        
        Format your response as a JSON object with the following keys:
        - is_correct: boolean
        - confidence: number (0-100)
        - issues: array of strings
        - suggestions: array of strings
        """
        
        try:
            response = await self._call_openai_api(prompt)
            assessment = json.loads(response)
            return assessment
        except Exception as e:
            logger.error(f"Error in code quality assessment: {str(e)}")
            return {
                "is_correct": False,
                "confidence": 0,
                "issues": [f"Error in assessment: {str(e)}"],
                "suggestions": ["Retry assessment"]
            }
    
    async def _assess_execution_output(self, task: str, execution_output: str) -> Dict[str, Any]:
        """
        Assess the execution output to determine if the code ran successfully.
        
        Args:
            task: Original task description
            execution_output: Terminal output from code execution
            
        Returns:
            Dict containing execution output assessment
        """
        prompt = f"""
        Analyze the following terminal output from executing code for the given task:
        
        TASK: {task}
        
        EXECUTION OUTPUT:
        ```
        {execution_output}
        ```
        
        Please provide:
        1. An assessment of whether the code executed successfully (true/false)
        2. A confidence score (0-100) for your assessment
        3. A list of any errors or warnings found
        4. An interpretation of the output in relation to the task requirements
        
        Format your response as a JSON object with the following keys:
        - is_successful: boolean
        - confidence: number (0-100)
        - errors: array of strings
        - interpretation: string
        """
        
        try:
            response = await self._call_openai_api(prompt)
            assessment = json.loads(response)
            return assessment
        except Exception as e:
            logger.error(f"Error in execution output assessment: {str(e)}")
            return {
                "is_successful": False,
                "confidence": 0,
                "errors": [f"Error in assessment: {str(e)}"],
                "interpretation": "Failed to assess execution output"
            }
    
    async def _verify_objectives_completed(self, task: str, todo_content: str, 
                                          code_assessment: Dict[str, Any], 
                                          execution_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify if all objectives for the task have been completed.
        
        Args:
            task: Original task description
            todo_content: Current content of the ToDo.md file
            code_assessment: Results from code quality assessment
            execution_assessment: Results from execution output assessment
            
        Returns:
            Dict containing completion verification assessment
        """
        prompt = f"""
        Verify if the following task has been completed successfully based on the provided information:
        
        TASK: {task}
        
        TODO CONTENT:
        ```
        {todo_content}
        ```
        
        CODE ASSESSMENT:
        ```
        {json.dumps(code_assessment, indent=2)}
        ```
        
        EXECUTION ASSESSMENT:
        ```
        {json.dumps(execution_assessment, indent=2)}
        ```
        
        Please provide:
        1. An assessment of whether the task is fully completed (true/false)
        2. A confidence score (0-100) for your assessment
        3. A list of any remaining objectives or requirements
        4. Recommendations for next steps if the task is not fully completed
        
        Format your response as a JSON object with the following keys:
        - is_completed: boolean
        - confidence: number (0-100)
        - remaining_objectives: array of strings
        - recommendations: array of strings
        """
        
        try:
            response = await self._call_openai_api(prompt)
            assessment = json.loads(response)
            return assessment
        except Exception as e:
            logger.error(f"Error in objectives completion verification: {str(e)}")
            return {
                "is_completed": False,
                "confidence": 0,
                "remaining_objectives": [f"Error in assessment: {str(e)}"],
                "recommendations": ["Retry assessment"]
            }
    
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
                    {"role": "user", "content": "You are an AI assistant that helps assess task completion and code quality. Provide accurate and detailed assessments in the requested JSON format.\n\n" + prompt}
                ],
                temperature=0.1,  # Lower temperature for more deterministic responses
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise
