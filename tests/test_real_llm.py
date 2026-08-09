import pytest
import httpx
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from app.services.llm import GeminiLLMClient, MockLLMClient
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.memory import AgentMemory
from app.services.autonomous import AutonomousExecutionService
from app.repositories.agent import InMemoryAgentRepository

@pytest.fixture
def mock_persona():
    return PersonaProfile(
        name="Ada",
        domain="AI Security",
        identity="AI Security researcher focusing on model threats and defensive alignment.",
        mission="Explores and reports model vulnerabilities, zero-day exploits, and alignment strategies.",
        core_interests=["model vulnerabilities", "exploit", "zero-day", "privacy leakage", "adversarial attack"],
        editorial_principles=["prefer evidence over hype", "explain practical implications", "provide code metrics"],
        writing_style=["concise", "analytical", "technically grounded"],
        audience="AI security engineers and practitioners",
        topics_to_avoid=["politics", "celebrity gossip", "market hype"]
    )

@pytest.fixture
def mock_candidate():
    return TopicCandidate(
        id="topic-123",
        title="Zero-day token leakage exploit identified in transformer model",
        summary="A new token alignment attack allows researchers to dump model parameters.",
        source="TechCrunch",
        sourceUrl="https://techcrunch.com/ai-leakage-exploit",
        publishedAt=datetime.now(timezone.utc),
        discoveredAt=datetime.now(timezone.utc)
    )

@pytest.fixture
def mock_decision():
    return EditorialDecision(
        topicId="topic-123",
        decision="ACCEPT",
        score=8.5,
        reasons=["Aligned interest", "Vibe matched"],
        evaluatedAt=datetime.now(timezone.utc)
    )

# 1. Test Client Configuration
def test_real_client_config():
    client = GeminiLLMClient(api_key="mock-key-123", model_name="gemini-custom")
    assert client.api_key == "mock-key-123"
    assert client.model_name == "gemini-custom"

# 2. Successful Editorial structured decision parsing
@pytest.mark.anyio
async def test_successful_editorial_decision_parsing(mock_persona, mock_candidate):
    client = GeminiLLMClient(api_key="mock-key-123")
    
    mock_response_body = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": (
                        '{"decision": "ACCEPT", "score": 8.5, "reasons": ["Directly aligns with AI security interests."], '
                        '"relevanceScore": 9.0, "freshnessScore": 8.0, "significanceScore": 8.0, '
                        '"sourceQualityScore": 9.0, "personaFitScore": 9.0, "confidence": 0.95}'
                    )
                }]
            }
        }]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json=mock_response_body)
        
        decision = await client.generate_structured_decision(mock_persona, mock_candidate, "2026-08-09T06:00:00Z")
        assert decision["decision"] == "ACCEPT"
        assert decision["score"] == 8.5
        assert "Directly aligns with AI security interests." in decision["reasons"]
        assert decision["confidence"] == 0.95

# 3. Successful content generation parsing
@pytest.mark.anyio
async def test_successful_content_generation_parsing(mock_persona, mock_candidate, mock_decision):
    client = GeminiLLMClient(api_key="mock-key-123")
    
    mock_response_body = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": (
                        '{"text": "Critical zero-day leakage identified in transformer models.", '
                        '"rationale": "High AI security relevance.", '
                        '"sources": ["https://techcrunch.com/ai-leakage-exploit"]}'
                    )
                }]
            }
        }]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json=mock_response_body)

        post = await client.generate_post_content(mock_persona, mock_candidate, mock_decision, [])
        assert post["text"] == "Critical zero-day leakage identified in transformer models."
        assert post["rationale"] == "High AI security relevance."
        assert "https://techcrunch.com/ai-leakage-exploit" in post["sources"]
        assert post["generationMetadata"]["provider"] == "GeminiAPI"

# 4. Malformed LLM response error handling
@pytest.mark.anyio
async def test_malformed_llm_response_error(mock_persona, mock_candidate):
    client = GeminiLLMClient(api_key="mock-key-123")
    
    mock_response_body = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": "This is a raw text description instead of structured JSON output."
                }]
            }
        }]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json=mock_response_body)

        with pytest.raises(ValueError, match="Malformed LLM output"):
            await client.generate_structured_decision(mock_persona, mock_candidate, "2026-08-09T06:00:00Z")

# 5. Empty response error handling
@pytest.mark.anyio
async def test_empty_llm_response_error(mock_persona, mock_candidate):
    client = GeminiLLMClient(api_key="mock-key-123")
    mock_response_body = {"candidates": []}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(200, json=mock_response_body)

        with pytest.raises(ValueError, match="Empty or blocked response"):
            await client.generate_structured_decision(mock_persona, mock_candidate, "2026-08-09T06:00:00Z")

# 6. Provider timeout error handling
@pytest.mark.anyio
async def test_provider_timeout_error(mock_persona, mock_candidate):
    client = GeminiLLMClient(api_key="mock-key-123")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout occurred")

        with pytest.raises(TimeoutError, match="Simulated LLM service connection timeout"):
            await client.generate_structured_decision(mock_persona, mock_candidate, "2026-08-09T06:00:00Z")

# 7. Provider authentication failure (401 / 403)
@pytest.mark.anyio
async def test_provider_auth_failure_error(mock_persona, mock_candidate):
    client = GeminiLLMClient(api_key="wrong-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(401, text="API key not valid")

        with pytest.raises(PermissionError, match="Authentication failed"):
            await client.generate_structured_decision(mock_persona, mock_candidate, "2026-08-09T06:00:00Z")

# 8. Provider rate-limit failure (429)
@pytest.mark.anyio
async def test_provider_rate_limit_error(mock_persona, mock_candidate):
    client = GeminiLLMClient(api_key="mock-key-123")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = httpx.Response(429, text="Resource has been exhausted")

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            await client.generate_structured_decision(mock_persona, mock_candidate, "2026-08-09T06:00:00Z")

# 9. LLM service failure does not crash/terminate autonomous cycle
@pytest.mark.anyio
async def test_llm_service_failure_does_not_terminate_loop(mock_persona, mock_candidate):
    import tempfile
    from app.services.autonomous import AutonomousExecutionService
    from app.services.topic_discovery import TopicDiscoveryService
    from app.services.editorial import EditorialJudgmentService
    from app.services.content_generator import ContentGeneratorService
    from app.services.memory import LocalFileMemoryRepository, MemoryService

    class DummyDiscovery(TopicDiscoveryService):
        async def discover_topics(self):
            return [mock_candidate]

    client = GeminiLLMClient(api_key="mock-key")

    with tempfile.TemporaryDirectory() as tmpdir:
        mem_repo = LocalFileMemoryRepository(base_dir=tmpdir)
        memory_service = MemoryService(repository=mem_repo)

        editorial = EditorialJudgmentService(llm_client=client)
        generator = ContentGeneratorService(llm_client=client, memory_service=memory_service)
        
        repo = InMemoryAgentRepository()
        repo.save_agent("agent-test", mock_persona.model_dump())

        exec_service = AutonomousExecutionService(
            discovery_service=DummyDiscovery(),
            editorial_service=editorial,
            generator_service=generator,
            memory_service=memory_service,
            agent_repo=repo
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")

            result = await exec_service.run_cycle("agent-test")
            assert result["status"] == "FAILED"
            assert result["agentId"] == "agent-test"

# 10. MockLLMClient continues to work correctly in test environments
@pytest.mark.anyio
async def test_mock_llm_client_works(mock_persona, mock_candidate):
    mock_client = MockLLMClient()
    
    mock_client.configure_mock_response({
        "decision": "ACCEPT",
        "score": 9.9,
        "reasons": ["Mock success Reasons"],
        "relevanceScore": 10.0,
        "freshnessScore": 10.0,
        "significanceScore": 10.0,
        "sourceQualityScore": 10.0,
        "personaFitScore": 10.0,
        "confidence": 1.0
    })

    decision = await mock_client.generate_structured_decision(mock_persona, mock_candidate, "time-string")
    assert decision["decision"] == "ACCEPT"
    assert decision["score"] == 9.9
    assert "Mock success Reasons" in decision["reasons"]
