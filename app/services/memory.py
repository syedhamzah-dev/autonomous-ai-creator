import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from app.schemas.memory import AgentMemory

logger = logging.getLogger(__name__)

class BaseMemory(ABC):
    """
    Abstract persistent memory interface for the Autonomous AI Creator.
    This contract defines how the agent interacts with its memory layer.
    """

    @abstractmethod
    async def store(self, agent_id: str, memory: AgentMemory) -> None:
        """
        Store a memory for a specific agent.
        """
        pass

    @abstractmethod
    async def get(self, agent_id: str, memory_id: str) -> Optional[AgentMemory]:
        """
        Retrieve a specific memory by its ID.
        """
        pass

    @abstractmethod
    async def search(self, agent_id: str, query: str, limit: int = 5) -> List[AgentMemory]:
        """
        Search memories belonging to a specific agent matching a query.
        """
        pass

    @abstractmethod
    async def recent(self, agent_id: str, limit: int = 10) -> List[AgentMemory]:
        """
        Retrieve recent memories for a specific agent in deterministic newest-first order.
        """
        pass

    @abstractmethod
    async def is_repetitive(self, agent_id: str, content: str) -> bool:
        """
        Check whether the proposed content/topic is repetitive or closely matches
        previously published posts or topics.
        """
        pass


class LocalFileMemoryRepository(BaseMemory):
    """
    Concrete implementation of BaseMemory using a local JSON file-based storage.
    Each agent's memories are stored in data/memory/<agent-id>.json.
    """

    def __init__(self, base_dir: str = "data/memory"):
        self.base_dir = Path(base_dir)

    def _get_agent_file(self, agent_id: str) -> Path:
        """
        Get the file path for the agent's memory JSON.
        """
        return self.base_dir / f"{agent_id}.json"

    def _load_memories(self, agent_id: str) -> List[AgentMemory]:
        """
        Load memories from the JSON file for the agent.
        """
        file_path = self._get_agent_file(agent_id)
        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if not data:
                    return []
                parsed_json = json.loads(data)
                if not isinstance(parsed_json, list):
                    raise ValueError("Malformed memory file: expected a list of memories.")
                
                memories = []
                for item in parsed_json:
                    # Handle date parsing
                    if "createdAt" in item and isinstance(item["createdAt"], str):
                        # datetime.fromisoformat parses ISO 8601 strings
                        # Replace Z with +00:00 for older Python compatibility if necessary
                        dt_str = item["createdAt"].replace("Z", "+00:00")
                        item["createdAt"] = datetime.fromisoformat(dt_str)
                    memories.append(AgentMemory(**item))
                return memories
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode failure reading memory for agent {agent_id}: {e}")
            raise ValueError(f"Corrupted memory file: invalid JSON for agent {agent_id}.") from e
        except Exception as e:
            logger.error(f"Error reading memory for agent {agent_id}: {e}")
            raise

    def _save_memories(self, agent_id: str, memories: List[AgentMemory]) -> None:
        """
        Save memories list to the JSON file using atomic write.
        """
        file_path = self._get_agent_file(agent_id)
        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert memories to dicts with alias fields (camelCase)
        serialized = [m.model_dump(by_alias=True, mode="json") for m in memories]
        temp_file = file_path.with_suffix(".tmp")
        
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2, ensure_ascii=False)
            # Atomic replace
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_file, file_path)
        except Exception as e:
            logger.error(f"Failed to write memory file for agent {agent_id}: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise IOError(f"Memory write failure: could not persist memories for agent {agent_id}.") from e

    async def store(self, agent_id: str, memory: AgentMemory) -> None:
        if not agent_id or agent_id != memory.agentId:
            raise ValueError("Invalid agent identity: scoping agent ID does not match memory agent ID.")
        
        memories = self._load_memories(agent_id)
        # Remove existing if same memoryId (idempotent write)
        memories = [m for m in memories if m.memoryId != memory.memoryId]
        memories.append(memory)
        self._save_memories(agent_id, memories)

    async def get(self, agent_id: str, memory_id: str) -> Optional[AgentMemory]:
        if not agent_id:
            raise ValueError("Agent ID cannot be empty.")
        memories = self._load_memories(agent_id)
        for m in memories:
            if m.memoryId == memory_id:
                return m
        return None

    async def search(self, agent_id: str, query: str, limit: int = 5) -> List[AgentMemory]:
        if not agent_id:
            raise ValueError("Agent ID cannot be empty.")
        if limit <= 0:
            return []

        memories = self._load_memories(agent_id)
        if not query:
            return memories[:limit]

        query_tokens = query.lower().split()
        matched_memories = []

        for m in memories:
            text_to_search = (m.content + " " + m.type + " " + json.dumps(m.metadata)).lower()
            # Calculate match score (number of matched query tokens)
            match_score = sum(1 for token in query_tokens if token in text_to_search)
            if match_score > 0:
                matched_memories.append((m, match_score))

        # Sort by match score descending, then by createdAt descending
        matched_memories.sort(key=lambda x: (x[1], x[0].createdAt), reverse=True)
        return [m[0] for m in matched_memories[:limit]]

    async def recent(self, agent_id: str, limit: int = 10) -> List[AgentMemory]:
        if not agent_id:
            raise ValueError("Agent ID cannot be empty.")
        if limit <= 0:
            return []

        memories = self._load_memories(agent_id)
        # Sort newest first
        memories.sort(key=lambda m: m.createdAt, reverse=True)
        return memories[:limit]

    async def is_repetitive(self, agent_id: str, content: str) -> bool:
        if not agent_id:
            raise ValueError("Agent ID cannot be empty.")
        if not content:
            return False

        memories = self._load_memories(agent_id)
        
        # Simple stop-words set to filter noise
        stop_words = {"in", "the", "and", "of", "for", "with", "on", "a", "an", "new", "discovered", "release", "patch", "is", "at", "to"}

        def get_clean_tokens(text: str) -> set:
            words = text.lower().strip().split()
            cleaned = []
            for w in words:
                cw = "".join(c for c in w if c.isalnum())
                if cw and cw not in stop_words:
                    cleaned.append(cw)
            return set(cleaned)

        check_tokens = get_clean_tokens(content)
        if not check_tokens:
            return False

        for m in memories:
            if m.type in ("PUBLISHED_POST", "PUBLISHED_TOPIC"):
                stored_tokens = get_clean_tokens(m.content)
                if not stored_tokens:
                    continue
                intersection = check_tokens.intersection(stored_tokens)
                # If a significant portion of checked content tokens exist in stored memory
                overlap_ratio = len(intersection) / len(check_tokens)
                if overlap_ratio >= 0.6:
                    return True
        return False


class MemoryService(BaseMemory):
    """
    Decoupled application service coordinating memory access.
    """

    def __init__(self, repository: BaseMemory):
        self.repository = repository

    async def store(self, agent_id: str, memory: AgentMemory) -> None:
        await self.repository.store(agent_id, memory)

    async def get(self, agent_id: str, memory_id: str) -> Optional[AgentMemory]:
        return await self.repository.get(agent_id, memory_id)

    async def search(self, agent_id: str, query: str, limit: int = 5) -> List[AgentMemory]:
        return await self.repository.search(agent_id, query, limit)

    async def recent(self, agent_id: str, limit: int = 10) -> List[AgentMemory]:
        return await self.repository.recent(agent_id, limit)

    async def is_repetitive(self, agent_id: str, content: str) -> bool:
        return await self.repository.is_repetitive(agent_id, content)
