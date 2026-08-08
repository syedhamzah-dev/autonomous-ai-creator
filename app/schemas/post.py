from typing import Any, Dict, Optional
from pydantic import Field
from app.schemas.agent import PostModel

class GeneratedPost(PostModel):
    """
    Schema representing an editorially generated post with internal tracking metadata.
    Extends PostModel to fulfill the feed contract while storing origin metadata.
    """
    agentId: str = Field(
        ...,
        alias="agentId",
        description="The unique ID of the agent owning this post."
    )
    topicId: str = Field(
        ...,
        alias="topicId",
        description="The unique ID of the candidate topic from which this post was generated."
    )
    generationMetadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        alias="generationMetadata",
        description="Internal metadata regarding LLM provider, prompt parameters, tokens, etc."
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "id": "post-12345678-abcd",
                "createdAt": "2026-08-08T21:12:00Z",
                "text": "Deep dive into model vulnerability mitigation strategies for enterprise LLM deployments.",
                "rationale": "Directly relevant to AI Security domain and supported by recent technical benchmarks.",
                "sources": ["https://techcrunch.com/ai-vulnerability-paper"],
                "agentId": "agent-ada-uuid",
                "topicId": "topic-uuid-111",
                "generationMetadata": {
                    "model": "MockLLMClient",
                    "temperature": 0.7
                }
            }
        }
    }
