from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate

class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients used in the Autonomous AI Creator project.
    """
    @abstractmethod
    async def generate_structured_decision(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        current_time_str: str
    ) -> Dict[str, Any]:
        """
        Request a structured editorial decision from the LLM provider.
        
        Args:
            persona: The stable PersonaProfile of the agent.
            candidate: The TopicCandidate being evaluated.
            current_time_str: Formatting helper for the evaluation timestamp.
            
        Returns:
            A dict containing structured editorial fields matching EditorialDecision requirements:
            {
                "decision": "ACCEPT" | "REJECT",
                "score": float (0.0 to 10.0),
                "reasons": list of strings,
                "relevanceScore": float (0.0 to 10.0),
                "freshnessScore": float (0.0 to 10.0),
                "significanceScore": float (0.0 to 10.0),
                "sourceQualityScore": float (0.0 to 10.0),
                "personaFitScore": float (0.0 to 10.0),
                "confidence": float (0.0 to 1.0)
            }
        """
        pass

class MockLLMClient(BaseLLMClient):
    """
    Mock LLM Client for testing the Editorial Judgment Engine deterministically.
    Allows configuring specific mock responses or error injection.
    """
    def __init__(self) -> None:
        self.mock_response: Optional[Dict[str, Any]] = None
        self.should_raise_timeout = False
        self.should_return_malformed = False

    def configure_mock_response(self, response: Dict[str, Any]) -> None:
        """
        Set up a specific mock dictionary response.
        """
        self.mock_response = response
        self.should_raise_timeout = False
        self.should_return_malformed = False

    def configure_timeout(self) -> None:
        """
        Configure client to raise a simulated connection timeout/error.
        """
        self.should_raise_timeout = True
        self.mock_response = None
        self.should_return_malformed = False

    def configure_malformed(self) -> None:
        """
        Configure client to return a response structure with missing or malformed keys.
        """
        self.should_return_malformed = True
        self.mock_response = None
        self.should_raise_timeout = False

    async def generate_structured_decision(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        current_time_str: str
    ) -> Dict[str, Any]:
        if self.should_raise_timeout:
            raise TimeoutError("Simulated LLM service connection timeout.")

        if self.should_return_malformed:
            return {
                "decision": "ACCEPT",
                # missing mandatory 'score' and 'reasons' fields
                "evaluationResult": "This looks okay but violates schema."
            }

        if self.mock_response is not None:
            # If customized mock response exists, return it
            return self.mock_response

        # Default fallback mock response based on topic keyword relevance to show basic intelligent behavior
        title_lower = candidate.title.lower()
        summary_lower = candidate.summary.lower()
        
        # Check if topic contains keywords matching interests
        matched_interest = None
        for interest in persona.core_interests:
            if interest.lower() in title_lower or interest.lower() in summary_lower:
                matched_interest = interest
                break

        # Check if topic matches topics to avoid
        avoided_matched = None
        for avoid in persona.topics_to_avoid:
            if avoid.lower() in title_lower or avoid.lower() in summary_lower:
                avoided_matched = avoid
                break

        if avoided_matched:
            return {
                "decision": "REJECT",
                "score": 2.0,
                "reasons": [f"Matches avoided topic classification: '{avoided_matched}'."],
                "relevanceScore": 1.0,
                "freshnessScore": 9.0,
                "significanceScore": 4.0,
                "sourceQualityScore": 7.0,
                "personaFitScore": 1.0,
                "confidence": 0.95
            }

        if matched_interest:
            return {
                "decision": "ACCEPT",
                "score": 8.5,
                "reasons": [
                    f"Directly fits the agent's interest in '{matched_interest}'.",
                    "Provides high quality and credible technical analysis.",
                    "Timely development matching current trends."
                ],
                "relevanceScore": 9.5,
                "freshnessScore": 9.0,
                "significanceScore": 8.0,
                "sourceQualityScore": 8.0,
                "personaFitScore": 9.0,
                "confidence": 0.9
            }

        # Otherwise generic reject
        return {
            "decision": "REJECT",
            "score": 4.0,
            "reasons": [f"Topic does not match any specified interests for '{persona.name}'."],
            "relevanceScore": 3.0,
            "freshnessScore": 8.0,
            "significanceScore": 5.0,
            "sourceQualityScore": 7.0,
            "personaFitScore": 3.0,
            "confidence": 0.8
        }
