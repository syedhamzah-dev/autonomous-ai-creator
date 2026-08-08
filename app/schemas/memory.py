from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

MemoryType = Literal["PUBLISHED_POST", "PUBLISHED_TOPIC", "EDITORIAL_DECISION"]

class AgentMemory(BaseModel):
    """
    Schema representing a persistent memory entry for an autonomous agent.
    """
    memoryId: str = Field(
        ...,
        alias="memoryId",
        description="The unique UUID of this memory entry."
    )
    agentId: str = Field(
        ...,
        alias="agentId",
        description="The unique ID of the agent associated with this memory."
    )
    type: MemoryType = Field(
        ...,
        description="The category of the memory (PUBLISHED_POST, PUBLISHED_TOPIC, EDITORIAL_DECISION)."
    )
    content: str = Field(
        ...,
        description="The raw string content to remember."
    )
    createdAt: datetime = Field(
        ...,
        alias="createdAt",
        description="Timezone-aware UTC timestamp when the memory was stored."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Preserved context metadata (e.g. topicId, sourceUrl, editorialDecision)."
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "memoryId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "agentId": "a90b4d58-9a4f-5612-bb2f-1234567890ab",
                "type": "PUBLISHED_TOPIC",
                "content": "Open-source AI model security vulnerability",
                "createdAt": "2026-08-08T20:29:34Z",
                "metadata": {
                    "topicId": "f6540e97-7f92-edfo-d421-2103bd925b9e",
                    "sourceUrl": "https://example.com/article",
                    "publishedAt": "2026-08-08T10:30:00Z"
                }
            }
        }
    }
