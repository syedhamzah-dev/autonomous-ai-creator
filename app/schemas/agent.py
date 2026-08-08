from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated

# String type that strips whitespace and requires at least 1 character
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class Persona(BaseModel):
    """
    Schema representing the AI persona config.
    """
    name: NonEmptyString = Field(
        ..., 
        description="The name of the AI agent persona."
    )
    domain: NonEmptyString = Field(
        ..., 
        description="The domain focus of the AI agent persona."
    )

class AgentInitRequest(BaseModel):
    """
    Schema for POST /api/agent/init request payload.
    """
    persona: Persona

class AgentInitResponse(BaseModel):
    """
    Schema for POST /api/agent/init response payload.
    """
    agentId: str = Field(
        ..., 
        description="A cryptographically unique identifier generated for the agent."
    )

class PostModel(BaseModel):
    """
    Prepared schema for a published post.
    Will be fully populated in future milestones.
    """
    id: str = Field(..., description="The unique post ID.")
    createdAt: datetime = Field(..., description="The ISO datetime when the post was created.")
    text: str = Field(..., description="The text content of the post.")
    rationale: str = Field(..., description="The reasoning behind publishing this post.")
    sources: List[str] = Field(..., description="List of source URLs or topics referenced.")

    model_config = {
        "populate_by_name": True
    }

class FeedResponse(BaseModel):
    """
    Schema for GET /api/agent/feed response payload.
    """
    posts: List[PostModel] = Field(
        default_factory=list, 
        description="List of posts published by the agent."
    )
