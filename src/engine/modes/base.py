"""Base mode class and configuration.

This module defines the abstract base class for all interaction modes,
following the Template Method Pattern and Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from llama_index.core.llms import LLM
from llama_index.core.memory import BaseMemory


class ModeType(str, Enum):
    """Available interaction mode types."""
    
    CHAT = "chat"
    ASK = "ask"
    CONCLUDE = "conclude"
    EXPLAIN = "explain"


class ModeConfig(BaseModel):
    """Configuration for interaction modes.
    
    Attributes:
        mode_type: Type of the mode
        has_memory: Whether the mode maintains conversation memory
        system_prompt: Optional system prompt override
        verbose: Enable verbose output
    """
    
    mode_type: ModeType
    has_memory: bool = True
    system_prompt: Optional[str] = None
    verbose: bool = False


class BaseMode(ABC):
    """Abstract base class for all interaction modes.
    
    This class defines the common interface and template methods for
    all interaction modes. Subclasses must implement the core logic
    while reusing common functionality.
    
    Following the Template Method Pattern:
    - run() is the template method that defines the algorithm skeleton
    - _process() is the hook method that subclasses must implement
    
    Attributes:
        llm: Language model instance
        memory: Optional conversation memory
        config: Mode configuration
    """
    
    def __init__(
        self,
        llm: LLM,
        memory: Optional[BaseMemory] = None,
        config: Optional[ModeConfig] = None,
    ):
        """Initialize BaseMode.
        
        Args:
            llm: LLM instance for generating responses
            memory: Optional memory for conversation history
            config: Mode configuration
        """
        self._llm = llm
        self._memory = memory
        self._config = config or self._default_config()
        self._initialized = False
    
    @property
    def llm(self) -> LLM:
        """Get the LLM instance."""
        return self._llm
    
    @property
    def memory(self) -> Optional[BaseMemory]:
        """Get the memory instance."""
        return self._memory
    
    @property
    def config(self) -> ModeConfig:
        """Get the mode configuration."""
        return self._config
    
    @property
    def mode_type(self) -> ModeType:
        """Get the mode type."""
        return self._config.mode_type
    
    @property
    def has_memory(self) -> bool:
        """Check if this mode has conversation memory."""
        return self._config.has_memory and self._memory is not None
    
    @abstractmethod
    def _default_config(self) -> ModeConfig:
        """Return the default configuration for this mode.
        
        Subclasses must implement this to provide their default config.
        
        Returns:
            ModeConfig with default values for this mode
        """
        pass
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize mode-specific components.
        
        Subclasses must implement this to set up agents, engines, etc.
        Called once before the first run() call.
        """
        pass
    
    @abstractmethod
    async def _process(self, message: str) -> str:
        """Process a message and generate a response.
        
        This is the core method that subclasses must implement.
        
        Args:
            message: User message to process
            
        Returns:
            Generated response string
        """
        pass
    
    async def initialize(self) -> None:
        """Initialize the mode.
        
        This method ensures initialization happens only once.
        """
        if not self._initialized:
            await self._initialize()
            self._initialized = True
    
    async def run(self, message: str) -> str:
        """Process a message using this mode.
        
        This is the main entry point for interacting with a mode.
        It ensures initialization and then delegates to _process().
        
        Args:
            message: User message to process
            
        Returns:
            Generated response string
            
        Raises:
            ValueError: If message is empty
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")
        
        # Ensure initialized
        await self.initialize()
        
        # Process message
        response = await self._process(message.strip())
        
        return response
    
    def run_sync(self, message: str) -> str:
        """Synchronous wrapper for run().
        
        Args:
            message: User message to process
            
        Returns:
            Generated response string
        """
        import asyncio
        return asyncio.run(self.run(message))
    
    async def reset(self) -> None:
        """Reset conversation memory if available."""
        if self._memory is not None:
            self._memory.reset()
    
    def get_chat_history(self) -> List[Any]:
        """Get chat history if memory is available.
        
        Returns:
            List of chat messages, or empty list if no memory
        """
        if self._memory is not None:
            return self._memory.get_all()
        return []
