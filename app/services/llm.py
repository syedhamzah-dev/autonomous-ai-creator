from abc import ABC, abstractmethod
import json
from typing import Dict, Any, List, Optional
import httpx
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.memory import AgentMemory

class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients used in the Autonomous AI Creator project.
    """
    @abstractmethod
    async def generate_post_content(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        decision: EditorialDecision,
        memories: List[AgentMemory]
    ) -> Dict[str, Any]:
        """
        Request a generated social media post and metadata from the LLM provider.
        """
        pass

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
        self.mock_post_response: Optional[Dict[str, Any]] = None
        self.should_raise_timeout = False
        self.should_return_malformed = False

    def configure_mock_response(self, response: Dict[str, Any]) -> None:
        """
        Set up a specific mock dictionary response.
        """
        self.mock_response = response
        self.should_raise_timeout = False
        self.should_return_malformed = False

    def configure_mock_post_response(self, response: Dict[str, Any]) -> None:
        """
        Set up a specific mock dictionary response for post content generation.
        """
        self.mock_post_response = response
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
                    f"Topic selected because it directly aligns with the agent's core tech interests, focusing on '{matched_interest}' to fulfill our information coverage mission.",
                    "Highly relevant now due to current trends and live public discussion surrounding these framework modifications.",
                    "Provides detailed, actionable technical analysis that offers significantly more depth and reader value than other generic high-level tech news candidates."
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

    async def generate_post_content(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        decision: EditorialDecision,
        memories: List[AgentMemory]
    ) -> Dict[str, Any]:
        if self.should_raise_timeout:
            raise TimeoutError("Simulated LLM service connection timeout during post generation.")

        if self.should_return_malformed:
            return {
                "text": "",
                "evaluationResult": "This text is empty and violates schema restrictions."
            }

        if self.mock_post_response is not None:
            return self.mock_post_response

        # Default smart generated text based on domain/persona and topic summary/title:
        title = candidate.title
        source_urls = [candidate.sourceUrl] if candidate.sourceUrl else []

        # Determine writing voice or technical depth from domain
        domain_lower = persona.domain.lower()
        if "security" in domain_lower:
            text = (
                f"[{persona.name} | AI Security] Securing transformer frameworks is paramount. "
                f"Analyzing '{title}': this recent development shows how model vulnerabilities are evolving. "
                f"Read more here: {candidate.sourceUrl}"
            )
        elif "robotics" in domain_lower:
            text = (
                f"[{persona.name} | Robotics] Robotic autonomous navigation update! "
                f"Evaluating new perception modules in '{title}'. A huge milestone for hardware accelerators. "
                f"Read more here: {candidate.sourceUrl}"
            )
        else:
            text = (
                f"[{persona.name} | {persona.domain}] In-depth coverage on '{title}'. "
                f"This topic represents a significant technical breakthrough in the domain. "
                f"Read more here: {candidate.sourceUrl}"
            )

        # Build default response
        return {
            "text": text,
            "rationale": " | ".join(decision.reasons),
            "sources": source_urls,
            "generationMetadata": {
                "model": "MockLLMClient",
                "version": "1.0",
                "matchedInterestsCount": len(persona.core_interests)
            }
        }


class GeminiLLMClient(BaseLLMClient):
    """
    Production client connecting to the Google Gemini API using httpx directly.
    Guarantees structured responses using native JSON Schema configurations.
    """
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", timeout_seconds: float = 30.0) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    async def _post_request(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper to execute the async POST request to the Gemini API.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as time_err:
            raise TimeoutError("Simulated LLM service connection timeout during API request.") from time_err
        except httpx.RequestError as req_err:
            raise RuntimeError(f"LLM API network request failed: {req_err}") from req_err

        if resp.status_code in (401, 403):
            raise PermissionError("Authentication failed: invalid LLM_API_KEY credentials.")
        elif resp.status_code == 429:
            raise RuntimeError("Rate limit exceeded on LLM provider.")
        elif resp.status_code != 200:
            raise RuntimeError(f"LLM API request failed with status code {resp.status_code}: {resp.text}")

        try:
            resp_json = resp.json()
        except Exception as parse_err:
            raise ValueError(f"Failed to parse LLM HTTP response as JSON: {parse_err}") from parse_err

        candidates = resp_json.get("candidates", [])
        if not candidates:
            raise ValueError("Empty or blocked response from LLM provider (no candidates).")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise ValueError("LLM response is missing text generation parts.")

        text_out = parts[0]["text"].strip()
        if not text_out:
            raise ValueError("LLM response returned empty text output.")

        try:
            return json.loads(text_out)
        except json.JSONDecodeError as json_err:
            raise ValueError(f"Malformed LLM output: not valid JSON schema. Detail: {json_err}") from json_err

    async def generate_structured_decision(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        current_time_str: str
    ) -> Dict[str, Any]:
        prompt = (
            f"Act as an editorially rigorous Technology Editor and QA Analyst.\n"
            f"Judge whether the discovered article candidate aligns with the persona below.\n\n"
            f"Persona Profile:\n"
            f"- Name: {persona.name}\n"
            f"- Domain: {persona.domain}\n"
            f"- Mission: {persona.mission}\n"
            f"- Core Interests: {persona.core_interests}\n"
            f"- Topics to Avoid: {persona.topics_to_avoid}\n\n"
            f"Article Candidate:\n"
            f"- Title: {candidate.title}\n"
            f"- Summary: {candidate.summary}\n"
            f"- Source URL: {candidate.sourceUrl}\n"
            f"- Discovered At: {candidate.publishedAt.isoformat() if candidate.publishedAt else 'N/A'}\n"
            f"- Current Evaluation Time: {current_time_str}\n\n"
            f"Rules:\n"
            f"1. Score overall fitness between 0.0 and 10.0.\n"
            f"2. If fit is >= 6.0 and contains no avoided topics, set decision to 'ACCEPT', otherwise 'REJECT'.\n"
            f"3. Fill in all score parameters and reasons array.\n"
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "decision": {
                    "type": "STRING",
                    "enum": ["ACCEPT", "REJECT"]
                },
                "score": {"type": "NUMBER"},
                "reasons": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                },
                "relevanceScore": {"type": "NUMBER"},
                "freshnessScore": {"type": "NUMBER"},
                "significanceScore": {"type": "NUMBER"},
                "sourceQualityScore": {"type": "NUMBER"},
                "personaFitScore": {"type": "NUMBER"},
                "confidence": {"type": "NUMBER"}
            },
            "required": [
                "decision", "score", "reasons", "relevanceScore", "freshnessScore",
                "significanceScore", "sourceQualityScore", "personaFitScore", "confidence"
            ]
        }

        parsed = await self._post_request(prompt, schema)
        
        # Verify structure keys
        for key in schema["required"]:
            if key not in parsed:
                raise ValueError(f"LLM structured response is missing required field: '{key}'")
        return parsed

    async def generate_post_content(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        decision: EditorialDecision,
        memories: List[AgentMemory]
    ) -> Dict[str, Any]:
        prompt = (
            f"Act as a professional technology content writer.\n"
            f"Generate a social media post based on the following accepted candidate.\n\n"
            f"Persona Profile:\n"
            f"- Name: {persona.name}\n"
            f"- Domain: {persona.domain}\n"
            f"- Mission: {persona.mission}\n"
            f"- Audience: Technology professionals\n"
            f"- Tone: Professional, technically precise, and concise.\n\n"
            f"Article Candidate:\n"
            f"- Title: {candidate.title}\n"
            f"- Summary: {candidate.summary}\n"
            f"- Source URL: {candidate.sourceUrl}\n\n"
            f"Editorial Reasons for Acceptance:\n"
            f"{' | '.join(decision.reasons)}\n\n"
            f"Rules:\n"
            f"1. Generate a post that is concise, clear, and grounded in candidate facts.\n"
            f"2. Write a detailed rationale explaining why this was selected.\n"
            f"3. Retain the candidate's sourceUrl in the sources list.\n"
        )

        schema = {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING"},
                "rationale": {"type": "STRING"},
                "sources": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"}
                }
            },
            "required": ["text", "rationale", "sources"]
        }

        parsed = await self._post_request(prompt, schema)
        
        # Verify structure keys
        for key in schema["required"]:
            if key not in parsed:
                raise ValueError(f"LLM structured response is missing required field: '{key}'")
                
        # Append generation metadata to resemble standard MockClient structure
        parsed["generationMetadata"] = {
            "model": self.model_name,
            "provider": "GeminiAPI"
        }
        return parsed
