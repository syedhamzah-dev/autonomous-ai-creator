import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.post import GeneratedPost
from app.services.llm import BaseLLMClient
from app.services.memory import BaseMemory

class ContentGeneratorService:
    """
    Service responsible for converting editorially accepted topics into 
    high-quality social media posts aligned with the agent's persona.
    """
    def __init__(self, llm_client: BaseLLMClient, memory_service: BaseMemory):
        self.llm_client = llm_client
        self.memory_service = memory_service

    async def generate_post(
        self,
        agent_id: str,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        decision: EditorialDecision
    ) -> GeneratedPost:
        """
        Produce a social media post from an accepted editorial decision.
        
        Args:
            agent_id: The scoping agent UUID.
            persona: The agent's PersonaProfile config.
            candidate: The TopicCandidate containing content sources.
            decision: The EditorialDecision verifying acceptance score.
            
        Returns:
            A validated GeneratedPost schema object.
            
        Raises:
            ValueError: If inputs are invalid or the editorial decision is not ACCEPT.
        """
        # 1. Parameter Validation
        if not agent_id:
            raise ValueError("Agent ID cannot be empty.")
        if not persona:
            raise ValueError("Persona configuration is missing.")
        if not candidate:
            raise ValueError("Topic candidate is missing.")
        if not decision:
            raise ValueError("Editorial decision is missing.")

        # 2. Editorial Judgment Gate
        if decision.decision != "ACCEPT":
            raise ValueError(f"Cannot generate content for a rejected topic candidate (decision: {decision.decision}).")

        # 3. Memory Retrieval Context
        # Query recent memory context to provide historical continuity for content creation
        memories = await self.memory_service.recent(agent_id, limit=5)

        # 4. Generate post text and metadata from provider client
        raw_output = await self.llm_client.generate_post_content(
            persona=persona,
            candidate=candidate,
            decision=decision,
            memories=memories
        )

        # 5. Content Quality Constraints and Grounding
        text = raw_output.get("text")
        if not text or not text.strip():
            raise ValueError("LLM provider returned empty post text content.")

        rationale = raw_output.get("rationale")
        if not rationale or not rationale.strip():
            # Preserving the core decision rationale if output is missing
            rationale = " | ".join(decision.reasons)

        sources = raw_output.get("sources")
        if not sources:
            # Fallback to source URL if missing
            sources = [candidate.sourceUrl] if candidate.sourceUrl else []

        # Ensure unique ID and timezone-aware UTC timestamp
        post_id = f"post-{uuid.uuid4()}"
        created_at = datetime.now(timezone.utc)

        # Map topicId from candidate model or decision schema
        topic_id = candidate.id if candidate.id else decision.topicId
        if not topic_id:
            topic_id = "unknown-topic-id"

        return GeneratedPost(
            id=post_id,
            createdAt=created_at,
            text=text.strip(),
            rationale=rationale.strip(),
            sources=sources,
            agentId=agent_id,
            topicId=topic_id,
            generationMetadata=raw_output.get("generationMetadata", {})
        )
