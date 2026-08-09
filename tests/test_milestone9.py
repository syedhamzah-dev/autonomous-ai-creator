import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.agent import InMemoryAgentRepository, agent_repository
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.memory import AgentMemory
from app.schemas.post import GeneratedPost
from app.services.llm import MockLLMClient
from app.services.memory import LocalFileMemoryRepository, MemoryService
from app.services.topic_discovery import TopicDiscoveryService
from app.services.editorial import EditorialJudgmentService
from app.services.content_generator import ContentGeneratorService
from app.services.autonomous import AutonomousExecutionService, AgentScheduler, validate_post_to_publish
from app.services.agent import AgentService

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def temp_memory_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def local_repo(temp_memory_dir):
    return LocalFileMemoryRepository(base_dir=temp_memory_dir)

@pytest.fixture
def mem_service(local_repo):
    return MemoryService(repository=local_repo)

@pytest.fixture
def custom_agent_repo():
    return InMemoryAgentRepository()

@pytest.fixture
def mock_llm_client():
    return MockLLMClient()

@pytest.fixture
def disc_service():
    return TopicDiscoveryService()

@pytest.fixture
def edit_service(mock_llm_client):
    return EditorialJudgmentService(engine_type="llm", llm_client=mock_llm_client)

@pytest.fixture
def gen_service(mock_llm_client, mem_service):
    return ContentGeneratorService(llm_client=mock_llm_client, memory_service=mem_service)

@pytest.fixture
def execution_service(disc_service, edit_service, gen_service, mem_service, custom_agent_repo):
    return AutonomousExecutionService(
        discovery_service=disc_service,
        editorial_service=edit_service,
        generator_service=gen_service,
        memory_service=mem_service,
        agent_repo=custom_agent_repo
    )

@pytest.fixture
def security_persona():
    return PersonaProfile(
        name="Ada",
        domain="AI Security",
        identity="AI Security Specialist and Auditor",
        mission="Analyze and secure AI model architectures against adversarial exploitation",
        core_interests=["model vulnerability", "adversarial attack", "jailbreak"],
        topics_to_avoid=["general politics"],
        writing_style=["Analytical", "skeptical"],
        editorial_principles=["Always ground technical claims", "Explain exact exploit vectors"],
        audience="AI researchers and practitioners"
    )

@pytest.fixture
def candidate_accept():
    return TopicCandidate(
        id="topic-accept-999",
        title="Zero-day model vulnerability discovered in Transformer architecture",
        summary="A recent exploit vector allows remote token pollution in large language models.",
        source="TechCrunch AI",
        sourceUrl="https://techcrunch.com/ai-vulnerability-paper",
        publishedAt=datetime.now(timezone.utc),
        discoveredAt=datetime.now(timezone.utc)
    )

@pytest.fixture
def candidate_reject():
    return TopicCandidate(
        id="topic-reject-888",
        title="Breaking general politics election results live news",
        summary="Live voting counts for the primary elections occurring today.",
        source="MIT Tech Review",
        sourceUrl="https://technologyreview.com/politics-news",
        publishedAt=datetime.now(timezone.utc),
        discoveredAt=datetime.now(timezone.utc)
    )


# Test 1 — Initialization
def test_agent_initialization_m9(test_client):
    payload = {
        "persona": {
            "name": "Ada",
            "domain": "AI Security"
        }
    }
    response = test_client.post("/api/agent/init", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "agentId" in data
    assert isinstance(data["agentId"], str)
    assert len(data["agentId"]) > 0


# Test 2 — Autonomous Accepted Topic
@pytest.mark.anyio
async def test_autonomous_accepted_topic_m9(execution_service, custom_agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "test-agent-accepted-m9"
    custom_agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Mock discovery to return candidate_accept
    async def mock_discover():
        return [candidate_accept]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover)

    # Run cycle
    result = await execution_service.run_cycle(agent_id)
    assert result["status"] == "SUCCESS"
    assert result["acceptedCount"] == 1

    # Check feed posts
    posts = custom_agent_repo.get_agent_posts(agent_id)
    assert len(posts) == 1
    assert posts[0]["text"] != ""
    assert posts[0]["topicId"] == candidate_accept.id
    assert posts[0]["agentId"] == agent_id
    assert "rationale" in posts[0]
    assert "sources" in posts[0]


# Test 3 — Rejected Topic
@pytest.mark.anyio
async def test_rejected_topic_m9(execution_service, custom_agent_repo, security_persona, candidate_reject, monkeypatch):
    agent_id = "test-agent-rejected-m9"
    custom_agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Mock discovery to return candidate_reject
    async def mock_discover():
        return [candidate_reject]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover)

    # Run cycle
    result = await execution_service.run_cycle(agent_id)
    assert result["status"] == "SUCCESS"
    assert result["acceptedCount"] == 0
    assert result["rejectedCount"] == 1

    # Check feed posts remains empty
    posts = custom_agent_repo.get_agent_posts(agent_id)
    assert len(posts) == 0


# Test 4 — Duplicate Topic
@pytest.mark.anyio
async def test_duplicate_topic_m9(execution_service, custom_agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "test-agent-duplicate-m9"
    custom_agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Mock discovery to return candidate_accept
    async def mock_discover():
        return [candidate_accept]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover)

    # 1. Run first cycle -> published
    res1 = await execution_service.run_cycle(agent_id)
    assert res1["acceptedCount"] == 1
    assert len(custom_agent_repo.get_agent_posts(agent_id)) == 1

    # 2. Run second cycle -> duplicate check prevents publishing
    res2 = await execution_service.run_cycle(agent_id)
    assert res2["acceptedCount"] == 0
    assert res2["rejectedCount"] == 1
    assert len(custom_agent_repo.get_agent_posts(agent_id)) == 1


# Test 5 — Multiple Posts
@pytest.mark.anyio
async def test_multiple_posts_m9(execution_service, custom_agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "test-agent-multiple-m9"
    custom_agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Create two different accepted candidates
    candidate_1 = candidate_accept
    candidate_2 = TopicCandidate(
        id="topic-accept-1010",
        title="Zero-day adversarial attack on vision-language models",
        summary="Exploit parameters in multi-modal systems.",
        source="TechCrunch AI",
        sourceUrl="https://techcrunch.com/adversarial-attack-paper",
        publishedAt=datetime.now(timezone.utc) - timedelta(minutes=5),
        discoveredAt=datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    # 1. Run cycle 1
    async def mock_discover_1():
        return [candidate_1]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover_1)
    await execution_service.run_cycle(agent_id)

    # 2. Run cycle 2
    async def mock_discover_2():
        return [candidate_2]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover_2)
    await execution_service.run_cycle(agent_id)

    # Retrieve via AgentService to check sorting
    agent_service = AgentService(repository=custom_agent_repo)
    posts = agent_service.get_agent_feed(agent_id)

    assert len(posts) == 2
    # Verify unique IDs
    assert posts[0]["id"] != posts[1]["id"]
    # Verify newest-first ordering
    time_0 = datetime.fromisoformat(posts[0]["createdAt"].replace("Z", "+00:00")) if isinstance(posts[0]["createdAt"], str) else posts[0]["createdAt"]
    time_1 = datetime.fromisoformat(posts[1]["createdAt"].replace("Z", "+00:00")) if isinstance(posts[1]["createdAt"], str) else posts[1]["createdAt"]
    assert time_0 >= time_1


# Test 6 — Rationale
@pytest.mark.anyio
async def test_rationale_m9(execution_service, custom_agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "test-agent-rationale-m9"
    custom_agent_repo.save_agent(agent_id, security_persona.model_dump())

    async def mock_discover():
        return [candidate_accept]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover)

    await execution_service.run_cycle(agent_id)
    posts = custom_agent_repo.get_agent_posts(agent_id)

    assert len(posts) == 1
    rationale = posts[0]["rationale"]
    # Verify that the rationale covers all 3 requirements
    assert "Topic selected because it directly aligns" in rationale or "interest" in rationale.lower()
    assert "Highly relevant now" in rationale or "relevant" in rationale.lower()
    assert "Provides detailed, actionable technical analysis" in rationale or "worth publishing" in rationale.lower() or "depth" in rationale.lower()


# Test 7 — Sources
@pytest.mark.anyio
async def test_sources_m9(execution_service, custom_agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "test-agent-sources-m9"
    custom_agent_repo.save_agent(agent_id, security_persona.model_dump())

    async def mock_discover():
        return [candidate_accept]
    monkeypatch.setattr(execution_service.discovery_service, "discover_topics", mock_discover)

    await execution_service.run_cycle(agent_id)
    posts = custom_agent_repo.get_agent_posts(agent_id)

    assert len(posts) == 1
    assert len(posts[0]["sources"]) == 1
    assert posts[0]["sources"][0] == candidate_accept.sourceUrl


# Test 8 — Agent Isolation
def test_agent_isolation_m9(test_client):
    # Initialize Agent A
    res_a = test_client.post("/api/agent/init", json={"persona": {"name": "AgentA", "domain": "Tech"}})
    agent_a_id = res_a.json()["agentId"]

    # Initialize Agent B
    res_b = test_client.post("/api/agent/init", json={"persona": {"name": "AgentB", "domain": "Tech"}})
    agent_b_id = res_b.json()["agentId"]

    # Retrieve Agent B's posts using Agent A's ID
    # Since agent_repository is global and shared in the test_client context,
    # let's mock one post manually for Agent B
    agent_repository.save_published_post(agent_b_id, {
        "id": "post-b-1",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "text": "Post for Agent B",
        "rationale": "Rationale B",
        "sources": ["http://src-b.com"],
        "agentId": agent_b_id
    })

    # Retrieve Agent A's feed -> should be empty
    feed_a = test_client.get(f"/api/agent/feed?agentId={agent_a_id}").json()
    assert len(feed_a["posts"]) == 0

    # Retrieve Agent B's feed -> should contain Agent B's post
    feed_b = test_client.get(f"/api/agent/feed?agentId={agent_b_id}").json()
    assert len(feed_b["posts"]) == 1
    assert feed_b["posts"][0]["id"] == "post-b-1"


# Test 9 — Empty Feed
def test_empty_feed_m9(test_client):
    res = test_client.post("/api/agent/init", json={"persona": {"name": "AgentEmpty", "domain": "Tech"}})
    agent_id = res.json()["agentId"]

    feed_res = test_client.get(f"/api/agent/feed?agentId={agent_id}")
    assert feed_res.status_code == 200
    assert feed_res.json() == {"posts": []}


# Test 10 — Unknown Agent
def test_unknown_agent_m9(test_client):
    response = test_client.get("/api/agent/feed?agentId=non-existent-agent-id")
    assert response.status_code == 404
    assert "detail" in response.json()


# Test 11 — Feed Does Not Generate
def test_feed_does_not_generate_m9(test_client):
    # Initialize agent
    res = test_client.post("/api/agent/init", json={"persona": {"name": "AgentStatic", "domain": "Tech"}})
    agent_id = res.json()["agentId"]

    # Call feed twice -> should return empty both times without starting generation
    feed1 = test_client.get(f"/api/agent/feed?agentId={agent_id}").json()
    feed2 = test_client.get(f"/api/agent/feed?agentId={agent_id}").json()

    assert feed1 == {"posts": []}
    assert feed2 == {"posts": []}


# Test 12 — Post Validation
def test_post_validation_m9():
    agent_id = "ada-validation-id"
    now = datetime.now(timezone.utc)
    
    # Valid post
    valid_post = GeneratedPost(
        id="post-valid-123",
        createdAt=now,
        text="A valid technology post text.",
        rationale="Meaningful rationale text.",
        sources=["https://sources.com/info"],
        agentId=agent_id,
        topicId="topic-1"
    )
    assert validate_post_to_publish(valid_post, agent_id, []) is True

    # Invalid post: wrong agent ID
    invalid_agent = GeneratedPost(
        id="post-invalid-1",
        createdAt=now,
        text="Text",
        rationale="Rationale",
        sources=["https://src.com"],
        agentId="wrong-agent",
        topicId="topic-1"
    )
    assert validate_post_to_publish(invalid_agent, agent_id, []) is False

    # Invalid post: empty text
    invalid_text = GeneratedPost(
        id="post-invalid-2",
        createdAt=now,
        text="    ",
        rationale="Rationale",
        sources=["https://src.com"],
        agentId=agent_id,
        topicId="topic-1"
    )
    assert validate_post_to_publish(invalid_text, agent_id, []) is False

    # Invalid post: empty rationale
    invalid_rationale = GeneratedPost(
        id="post-invalid-3",
        createdAt=now,
        text="Text",
        rationale="",
        sources=["https://src.com"],
        agentId=agent_id,
        topicId="topic-1"
    )
    assert validate_post_to_publish(invalid_rationale, agent_id, []) is False

    # Invalid post: duplicate ID
    duplicate_post = GeneratedPost(
        id="post-valid-123",
        createdAt=now,
        text="Another post text.",
        rationale="Another rationale.",
        sources=["https://src.com"],
        agentId=agent_id,
        topicId="topic-2"
    )
    existing_posts = [{"id": "post-valid-123", "text": "Old text"}]
    assert validate_post_to_publish(duplicate_post, agent_id, existing_posts) is False
