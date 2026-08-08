from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseMemory(ABC):
    """
    Abstract persistent memory interface for the Autonomous AI Creator.
    This contract defines how the agent interacts with its memory layer.
    A concrete implementation (e.g. using Breeth) will be added in a later milestone.
    """

    @abstractmethod
    async def store_post(self, post_data: Dict[str, Any]) -> None:
        """
        Store a published post in the persistent memory.
        
        Args:
            post_data: A dictionary containing details of the post (e.g., id, title, content, timestamp).
        """
        pass

    @abstractmethod
    async def retrieve_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve previously published posts.
        
        Args:
            limit: The maximum number of posts to retrieve.
            
        Returns:
            A list of dictionary representations of the retrieved posts.
        """
        pass

    @abstractmethod
    async def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search relevant memories matching a query.
        
        Args:
            query: The semantic search query string.
            limit: The maximum number of relevant memories to return.
            
        Returns:
            A list of memories matching the query.
        """
        pass

    @abstractmethod
    async def is_repetitive(self, content: str) -> bool:
        """
        Check whether the proposed content/topic is repetitive or closely matches
        previously published posts or memories.
        
        Args:
            content: The text content or topic to inspect.
            
        Returns:
            True if the content is repetitive, False otherwise.
        """
        pass
class BreethMemoryPlaceholder(BaseMemory):
    """
    Placeholder memory class to explicitly show where Breeth integration will plug in.
    This class is not active and raises NotImplementedError for all operations as requested.
    """

    async def store_post(self, post_data: Dict[str, Any]) -> None:
        raise NotImplementedError("Breeth memory integration is planned for a later milestone.")

    async def retrieve_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        raise NotImplementedError("Breeth memory integration is planned for a later milestone.")

    async def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError("Breeth memory integration is planned for a later milestone.")

    async def is_repetitive(self, content: str) -> bool:
        raise NotImplementedError("Breeth memory integration is planned for a later milestone.")
