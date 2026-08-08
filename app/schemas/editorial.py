from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class EditorialDecision(BaseModel):
    """
    Schema representing the structured decision of the Editorial Judgment Engine.
    """
    topicId: str = Field(
        ..., 
        alias="topicId",
        description="The ID of the evaluated topic candidate."
    )
    decision: Literal["ACCEPT", "REJECT"] = Field(
        ..., 
        description="The final editorial decision (ACCEPT or REJECT)."
    )
    score: float = Field(
        ..., 
        description="The calculated overall editorial score (between 0.0 and 10.0)."
    )
    reasons: List[str] = Field(
        ..., 
        description="List of concise, explainable reasons justifying the decision."
    )
    evaluatedAt: datetime = Field(
        ..., 
        alias="evaluatedAt",
        description="The UTC timestamp when the evaluation was performed."
    )

    # Explainability sub-scores (optional)
    relevanceScore: Optional[float] = Field(
        None, 
        alias="relevanceScore",
        description="Score measuring relevance to the agent's persona domain/interests."
    )
    freshnessScore: Optional[float] = Field(
        None, 
        alias="freshnessScore",
        description="Score measuring timeliness/freshness of the topic."
    )
    significanceScore: Optional[float] = Field(
        None, 
        alias="significanceScore",
        description="Score measuring significance of the tech breakthrough/development."
    )
    sourceQualityScore: Optional[float] = Field(
        None, 
        alias="sourceQualityScore",
        description="Score measuring credibility/quality of the source feed."
    )
    personaFitScore: Optional[float] = Field(
        None, 
        alias="personaFitScore",
        description="Score measuring overall alignment with persona's writing style and principles."
    )
    confidence: Optional[float] = Field(
        None, 
        description="Overall confidence in the decision."
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "topicId": "a90b4d58-9a4f-5612-bb2f-1234567890ab",
                "decision": "ACCEPT",
                "score": 8.5,
                "reasons": [
                    "Directly relevant to AI Security interest 'model vulnerabilities'.",
                    "Highly significant technical breakthrough detailing new exploit vector.",
                    "Published recently (freshness score is high)."
                ],
                "evaluatedAt": "2026-08-08T14:45:00Z",
                "relevanceScore": 9.5,
                "freshnessScore": 9.0,
                "significanceScore": 8.0,
                "sourceQualityScore": 9.0,
                "personaFitScore": 8.5,
                "confidence": 0.9
            }
        }
    }
