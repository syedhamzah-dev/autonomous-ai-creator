from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class TopicCandidate(BaseModel):
    """
    Pydantic schema representing a discovered technology topic candidate.
    This holds normalized data retrieved from RSS/Atom feeds, prepared
    for subsequent editorial evaluation.
    """
    id: str = Field(
        ...,
        description="Stable, unique identifier of the discovered topic (typically a deterministic URL hash)."
    )
    title: str = Field(
        ...,
        description="The title of the technology topic."
    )
    summary: str = Field(
        ...,
        description="A brief description or summary extracted from the source item."
    )
    source: str = Field(
        ...,
        description="The URL of the feed source from which the topic was fetched."
    )
    sourceUrl: str = Field(
        ...,
        description="The direct link/URL to the article/topic."
    )
    publishedAt: datetime = Field(
        ...,
        description="The publication timestamp as indicated by the source, normalized to UTC."
    )
    discoveredAt: datetime = Field(
        ...,
        description="The timestamp when this topic was discovered by the agent, normalized to UTC."
    )

    # Optional metadata fields (justified but not editorial)
    sourceName: Optional[str] = Field(
        None,
        description="The human-readable name of the publishing source."
    )
    category: Optional[str] = Field(
        None,
        description="An optional category tag associated with the topic."
    )
    author: Optional[str] = Field(
        None,
        description="The author of the content."
    )

    model_config = {
        "populate_by_name": True
    }
