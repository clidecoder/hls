"""Chained prompt handlers for multi-step AI processing."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .handlers import BaseHandler
from .logging_config import get_logger

logger = get_logger(__name__)


class ChainType(Enum):
    """Types of prompt chains."""
    SEQUENTIAL = "sequential"  # Each step depends on previous
    PARALLEL = "parallel"      # Steps can run independently
    CONDITIONAL = "conditional" # Next step depends on condition


@dataclass
class ChainStep:
    """Represents a single step in a prompt chain."""
    name: str
    prompt_key: str  # Key to look up the prompt template
    extract_func: Optional[str] = None  # Function name to extract data from response
    condition_func: Optional[str] = None  # Function name to check if step should run
    save_response: bool = True  # Whether to save this step's response


@dataclass 
class ChainResult:
    """Result from a chained prompt execution."""
    step_name: str
    response: str
    extracted_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ChainedPromptHandler(BaseHandler):
    """Base handler that supports chained prompt execution."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chain_results: List[ChainResult] = []
    
    @abstractmethod
    def get_chain_steps(self, payload: Dict[str, Any], action: str) -> List[ChainStep]:
        """Get the chain steps for this handler.
        
        Override this in subclasses to define the prompt chain.
        """
        pass
    
    @abstractmethod
    def get_chain_type(self) -> ChainType:
        """Get the type of chain (sequential, parallel, conditional)."""
        return ChainType.SEQUENTIAL
    
    async def execute_chain(
        self, 
        steps: List[ChainStep], 
        initial_context: Dict[str, Any],
        chain_type: ChainType = ChainType.SEQUENTIAL
    ) -> List[ChainResult]:
        """Execute a chain of prompts."""
        
        results = []
        context = initial_context.copy()
        
        if chain_type == ChainType.SEQUENTIAL:
            results = await self._execute_sequential(steps, context)
        elif chain_type == ChainType.PARALLEL:
            results = await self._execute_parallel(steps, context)
        elif chain_type == ChainType.CONDITIONAL:
            results = await self._execute_conditional(steps, context)
        
        return results
    
    async def _execute_sequential(
        self, 
        steps: List[ChainStep], 
        context: Dict[str, Any]
    ) -> List[ChainResult]:
        """Execute steps sequentially, passing context between them."""
        
        results = []
        accumulated_context = context.copy()
        
        for step in steps:
            logger.info(f"Executing chain step: {step.name}")
            
            # Check condition if specified
            if step.condition_func:
                condition_met = self._evaluate_condition(
                    step.condition_func, 
                    accumulated_context, 
                    results
                )
                if not condition_met:
                    logger.info(f"Skipping step {step.name} - condition not met")
                    continue
            
            # Load and render the prompt
            prompt = self.prompt_loader.render_prompt(
                step.prompt_key.split('.')[0],  # event_type
                step.prompt_key.split('.')[1] if '.' in step.prompt_key else 'default',  # action
                accumulated_context
            )
            
            if not prompt:
                logger.error(f"No prompt found for step: {step.name}")
                continue
            
            # Build conversation context from previous results
            conversation_history = self._build_conversation_context(results) if results else None
            
            # Get the immediate context for this step
            # The prompt has already been rendered with the context variables
            # We'll pass the rendered prompt as the context, and an empty prompt
            step_context = prompt  # The rendered prompt contains all the information
            
            # Get repository working directory from context (payload should be in accumulated_context)
            working_directory = None
            if 'payload' in accumulated_context:
                working_directory = self.get_repository_working_directory(accumulated_context['payload'])
            
            # Execute the prompt with conversation history
            response = await self.claude_client.analyze("", step_context, conversation_history, working_directory=working_directory)
            
            # Extract data if function specified
            extracted_data = None
            if step.extract_func:
                extracted_data = self._extract_data(step.extract_func, response)
                # Add extracted data to context for next steps
                accumulated_context.update(extracted_data)
            
            # Create result
            result = ChainResult(
                step_name=step.name,
                response=response,
                extracted_data=extracted_data,
                metadata={
                    "prompt_key": step.prompt_key,
                    "timestamp": context.get('timestamp')
                }
            )
            
            results.append(result)
            
            # Update accumulated context with step results
            accumulated_context[f"{step.name}_response"] = response
            if extracted_data:
                accumulated_context[f"{step.name}_data"] = extracted_data
        
        return results
    
    async def _execute_parallel(
        self, 
        steps: List[ChainStep], 
        context: Dict[str, Any]
    ) -> List[ChainResult]:
        """Execute steps in parallel (not implemented yet)."""
        # For now, fall back to sequential
        logger.warning("Parallel execution not implemented, using sequential")
        return await self._execute_sequential(steps, context)
    
    async def _execute_conditional(
        self, 
        steps: List[ChainStep], 
        context: Dict[str, Any]
    ) -> List[ChainResult]:
        """Execute steps with conditional logic."""
        # Same as sequential but with more emphasis on conditions
        return await self._execute_sequential(steps, context)
    
    def _build_conversation_context(self, previous_results: List[ChainResult]) -> str:
        """Build conversation context from previous results."""
        
        if not previous_results:
            return ""
        
        context_parts = ["# Previous Analysis Steps\n"]
        
        for i, result in enumerate(previous_results, 1):
            context_parts.append(f"## Step {i}: {result.step_name}")
            context_parts.append(result.response)
            
            if result.extracted_data:
                context_parts.append("\n### Extracted Data:")
                for key, value in result.extracted_data.items():
                    context_parts.append(f"- **{key}**: {value}")
            
            context_parts.append("\n---\n")
        
        return "\n".join(context_parts)
    
    def _evaluate_condition(
        self, 
        condition_func: str, 
        context: Dict[str, Any], 
        results: List[ChainResult]
    ) -> bool:
        """Evaluate a condition function."""
        
        # Get the condition method
        if hasattr(self, condition_func):
            method = getattr(self, condition_func)
            return method(context, results)
        
        logger.warning(f"Condition function not found: {condition_func}")
        return True  # Default to running the step
    
    def _extract_data(self, extract_func: str, response: str) -> Dict[str, Any]:
        """Extract structured data from a response."""
        
        # Get the extraction method
        if hasattr(self, extract_func):
            method = getattr(self, extract_func)
            return method(response)
        
        logger.warning(f"Extract function not found: {extract_func}")
        return {}
    
    def format_final_response(self, results: List[ChainResult]) -> str:
        """Format the final response from all chain results.
        
        Override this to customize how results are combined.
        """
        
        if not results:
            return "No analysis results available."
        
        # By default, return the last step's response
        return results[-1].response
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle the webhook event with chained prompts."""
        
        try:
            # Get chain steps
            steps = self.get_chain_steps(payload, action)
            if not steps:
                return {"status": "error", "reason": "no chain steps defined"}
            
            # Create initial context
            from .prompts import create_prompt_context
            context = create_prompt_context(self.event_type, payload)
            
            # Execute the chain
            chain_type = self.get_chain_type()
            results = await self.execute_chain(steps, context, chain_type)
            
            # Format final response
            final_response = self.format_final_response(results)
            
            # Save results
            await self.save_chain_results(payload, results, final_response)
            
            # Perform any post-processing actions
            return await self.post_process(payload, results, final_response)
            
        except Exception as e:
            logger.error(f"Error in chained handler: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    @abstractmethod
    async def save_chain_results(
        self, 
        payload: Dict[str, Any], 
        results: List[ChainResult], 
        final_response: str
    ) -> None:
        """Save the chain results."""
        pass
    
    @abstractmethod
    async def post_process(
        self, 
        payload: Dict[str, Any], 
        results: List[ChainResult], 
        final_response: str
    ) -> Dict[str, Any]:
        """Perform post-processing actions like posting comments or adding labels."""
        pass