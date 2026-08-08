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
        return agent_id

    def get_agent_feed(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the posts feed for an agent.
        
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
        if posts is None:
            return []
        return posts
