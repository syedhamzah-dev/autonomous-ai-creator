import pytest
import httpx
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from app.core.config import Settings
from app.services.llm import RateLimitError, GeminiLLMClient
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.services.autonomous import AutonomousExecutionService
from app.services.topic_discovery import TopicDiscoveryService
from app.services.editorial import EditorialJudgmentService
from app.services.content_generator import ContentGeneratorService
from app.services.memory import LocalFileMemoryRepository, MemoryService
from app.repositories.agent import InMemoryAgentRepository

# 1. Test settings CORS list parsing
def test_cors_settings_parsing():
    # Test comma-separated list
    s1 = Settings(CORS_ORIGINS="http://origin1.com, http://origin2.com")
    assert s1.cors_origins == ["http://origin1.com", "http://origin2.com"]

    # Test JSON list
    s2 = Settings(CORS_ORIGINS='["http://origin3.com", "http://origin4.com"]')
    assert s2.cors_origins == ["http://origin3.com", "http://origin4.com"]

    # Test empty or none defaults
    s3 = Settings(CORS_ORIGINS="")
    assert s3.cors_origins == []

# 2. Test CORS headers response
def test_cors_headers_response(client):
    # Perform preflight request
    headers = {
        "Origin": "http://localhost:8000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Requested-With"
    }
    response = client.options("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8000"
    assert response.headers.get("access-control-allow-credentials") == "true"

# 3. Test cycle safety on Gemini RateLimitError (Cycle abort and scheduler resilience)
@pytest.mark.anyio
async def test_scheduler_resilience_on_rate_limit():
    persona = PersonaProfile(
        name="Ada",
        domain="AI Security",
        identity="AI Security researcher.",
        mission="Explores vulnerabilities.",
        core_interests=["exploit"],
        editorial_principles=["evidence"],
        writing_style=["concise"],
        audience="practitioners",
        topics_to_avoid=["politics"]
    )

    candidate = TopicCandidate(
        id="topic-123",
        title="Exploit in transformer framework",
        summary="Researchers found a leakage exploit.",
        source="NVIDIA Blog",
        sourceUrl="https://developer.nvidia.com/vulnerability",
        publishedAt=datetime.now(timezone.utc),
        discoveredAt=datetime.now(timezone.utc)
    )

    class DummyDiscovery(TopicDiscoveryService):
        async def discover_topics(self):
            return [candidate]

    # Instantiate LLM Client mock to throw RateLimitError
    client = GeminiLLMClient(api_key="mock-key")

    with tempfile.TemporaryDirectory() as tmpdir:
        mem_repo = LocalFileMemoryRepository(base_dir=tmpdir)
        memory_service = MemoryService(repository=mem_repo)

        editorial = EditorialJudgmentService(engine_type="llm", llm_client=client)
        generator = ContentGeneratorService(llm_client=client, memory_service=memory_service)

        repo = InMemoryAgentRepository()
        repo.save_agent("agent-test", persona.model_dump())

        exec_service = AutonomousExecutionService(
            discovery_service=DummyDiscovery(),
            editorial_service=editorial,
            generator_service=generator,
            memory_service=memory_service,
            agent_repo=repo
        )

        # Mock the client POST to raise RateLimitError
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = httpx.Response(429, text="Resource has been exhausted")

            # Run cycle: must fail cleanly returning status FAILED instead of crash propagating out
            result = await exec_service.run_cycle("agent-test")
            assert result["status"] == "FAILED"
