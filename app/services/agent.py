import uuid
from typing import Any, Dict, List
from app.repositories.agent import BaseAgentRepository, agent_repository
from app.schemas.agent import Persona
from app.services.persona import PersonaService

class AgentService:
    """
    Coordinates agent initialization and feed retrieval business logic.
    """

    def __init__(
        self,
        repository: BaseAgentRepository = agent_repository,
        persona_service: PersonaService = None
    ) -> None:
        self.repository = repository
        self.persona_service = persona_service or PersonaService()

    def initialize_agent(self, persona: Persona) -> str:
        """
        Initializes an agent state with a cryptographically unique UUID.
        
        Args:
            persona: The persona Pydantic schema object.
            
        Returns:
            The generated agentId.
        """
        agent_id = str(uuid.uuid4())
        # Generate complete, stable technology persona profile
        profile = self.persona_service.generate_profile(persona.name, persona.domain)
        # Store serialized persona profile dict
        self.repository.save_agent(agent_id, profile.model_dump())

        # Auto-trigger scheduling loop if enabled in configurations
        from app.core.config import settings
        from app.services.autonomous import agent_scheduler
        if settings.autonomous_enabled:
            agent_scheduler.start_agent_loop(agent_id, settings.autonomous_interval_seconds)

        return agent_id

    def get_agent_feed(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the posts feed for an agent, sorted newest first.
        
        Args:
            agent_id: The unique identifier of the agent.
            
        Returns:
            A list of post dictionaries.
            
        Raises:
            KeyError: If the agentId is unknown.
        """
        if not self.repository.agent_exists(agent_id):
            raise KeyError(f"Agent with ID '{agent_id}' does not exist.")
            
        posts = self.repository.get_agent_posts(agent_id)
        if not posts:
            return []

        # Sort newest posts first (by createdAt descending)
        from datetime import datetime
        def parse_created_at(p: Dict[str, Any]) -> datetime:
            val = p.get("createdAt")
            if isinstance(val, str):
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            return val

        return sorted(posts, key=parse_created_at, reverse=True)

    def get_agent_persona(self, agent_id: str) -> Dict[str, Any]:
        """
        Retrieves the persona profile for an agent.
        """
        if not self.repository.agent_exists(agent_id):
            raise KeyError(f"Agent with ID '{agent_id}' does not exist.")
        return self.repository.get_agent_persona(agent_id)
