from pydantic import BaseModel, Field
from typing import List

class PersonaProfile(BaseModel):
    """
    Detailed domain model representing a stable and coherent technology persona profile.
    This structure is generated upon initialization and remains persistent.
    """
    name: str = Field(
        ...,
        description="The name of the AI agent persona."
    )
    domain: str = Field(
        ...,
        description="The technology domain focus of the AI agent persona."
    )
    identity: str = Field(
        ...,
        description="A short identity description of the persona."
    )
    mission: str = Field(
        ...,
        description="A concise description of the persona's purpose, what it analyzes, or what it contributes to."
    )
    core_interests: List[str] = Field(
        default_factory=list,
        description="A list of topics that the persona consistently cares about."
    )
    editorial_principles: List[str] = Field(
        default_factory=list,
        description="Stable rules governing what the persona considers worth discussing."
    )
    writing_style: List[str] = Field(
        default_factory=list,
        description="Key characteristics of the persona's writing style (e.g. concise, analytical, clear)."
    )
    audience: str = Field(
        ...,
        description="Description of the target audience the persona writes for."
    )
    topics_to_avoid: List[str] = Field(
        default_factory=list,
        description="Define categories that should normally not be published."
    )
