import pytest
import asyncio
from datetime import datetime, timezone
from typing import List
from app.core.config import settings
from app.repositories.agent import InMemoryAgentRepository
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.memory import AgentMemory
from app.services.llm import MockLLMClient
from app.services.memory import LocalFileMemoryRepository, MemoryService
from app.services.topic_discovery import TopicDiscoveryService
from app.services.editorial import EditorialJudgmentService
from app.services.content_generator import ContentGeneratorService
from app.services.autonomous import AutonomousExecutionService, AgentScheduler

@pytest.fixture
def temp_memory_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def repo(temp_memory_dir):
    return LocalFileMemoryRepository(base_dir=temp_memory_dir)

@pytest.fixture
def memory_serv(repo):
    return MemoryService(repository=repo)

@pytest.fixture
def agent_repo():
    return InMemoryAgentRepository()

@pytest.fixture
def mock_llm():
    return MockLLMClient()

@pytest.fixture
def discovery_serv():
    return TopicDiscoveryService()

@pytest.fixture
def editorial_serv(mock_llm):
    return EditorialJudgmentService(llm_client=mock_llm)

@pytest.fixture
def generator_serv(mock_llm, memory_serv):
    return ContentGeneratorService(llm_client=mock_llm, memory_service=memory_serv)

@pytest.fixture
def exec_service(discovery_serv, editorial_serv, generator_serv, memory_serv, agent_repo):
    return AutonomousExecutionService(
        discovery_service=discovery_serv,
        editorial_service=editorial_serv,
        generator_service=generator_serv,
        memory_service=memory_serv,
        agent_repo=agent_repo
    )

@pytest.fixture
def scheduler(exec_service):
    return AgentScheduler(execution_service=exec_service)

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
        id="topic-accept-123",
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
        id="topic-reject-456",
        title="Breaking general politics election results live news",
        summary="Live voting counts for the primary elections occurring today.",
        source="MIT Tech Review",
        sourceUrl="https://technologyreview.com/politics-news",
        publishedAt=datetime.now(timezone.utc),
        discoveredAt=datetime.now(timezone.utc)
    )

@pytest.mark.anyio
async def test_agent_lifecycle_initialization(exec_service, agent_repo, security_persona):
    agent_id = "agent-lifecycle-uuid"
    
    # Uninitialized agent execution blocks
    with pytest.raises(ValueError, match="Cannot run loop: Agent with ID.*does not exist"):
        await exec_service.run_cycle(agent_id)

    # Initialize agent
    agent_repo.save_agent(agent_id, security_persona.model_dump())
    assert agent_repo.get_agent_status(agent_id) == "INITIALIZED"

@pytest.mark.anyio
async def test_execution_cycle_gating_and_storage(exec_service, scheduler, agent_repo, security_persona, candidate_accept, candidate_reject, monkeypatch):
    agent_id = "agent-exec-uuid"
    agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Mock Discovery Service to return our test candidates
    async def mock_discover():
        return [candidate_reject, candidate_accept]
    monkeypatch.setattr(exec_service.discovery_service, "discover_topics", mock_discover)

    # Execute one cycle
    result = await exec_service.run_cycle(agent_id)
    assert result["status"] == "SUCCESS"
    assert result["discoveredCount"] == 2
    assert result["rejectedCount"] == 1  # candidate_reject is rejected (politics topics_to_avoid)
    assert result["acceptedCount"] == 1  # candidate_accept is accepted

    # Check that the accepted candidate post was stored in prepared drafts repository
    prepared = agent_repo.get_prepared_posts(agent_id)
    assert len(prepared) == 1
    assert prepared[0]["text"] != ""
    assert prepared[0]["topicId"] == candidate_accept.id

    # Check persistent memory contains published post, published topic, and editorial decisions
    memories = await exec_service.memory_service.recent(agent_id, limit=10)
    # Types expected: PUBLISHED_POST, PUBLISHED_TOPIC, EDITORIAL_DECISION (ACCEPT), EDITORIAL_DECISION (REJECT)
    mem_types = [m.type for m in memories]
    assert "PUBLISHED_POST" in mem_types
    assert "PUBLISHED_TOPIC" in mem_types
    assert "EDITORIAL_DECISION" in mem_types

@pytest.mark.anyio
async def test_repetition_avoidance(exec_service, agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "agent-repeat-uuid"
    agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Mock Discovery
    async def mock_discover():
        return [candidate_accept]
    monkeypatch.setattr(exec_service.discovery_service, "discover_topics", mock_discover)

    # 1. Run first cycle -> generates post
    res1 = await exec_service.run_cycle(agent_id)
    assert res1["acceptedCount"] == 1
    assert res1["rejectedCount"] == 0

    # 2. Run second cycle with same candidate -> should block repetition using memory duplicate check
    res2 = await exec_service.run_cycle(agent_id)
    assert res2["acceptedCount"] == 0
    assert res2["rejectedCount"] == 1  # Marked rejected due to repetition check!

@pytest.mark.anyio
async def test_scheduler_lifecycle_and_duplicate_prevention(scheduler, agent_repo, security_persona):
    agent_id = "agent-sched-uuid"
    agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Start loop
    scheduler.start_agent_loop(agent_id, interval_seconds=10.0)
    assert scheduler.is_running(agent_id)
    assert agent_repo.get_agent_status(agent_id) == "RUNNING"
    task1 = scheduler._tasks[agent_id]

    # Start loop again -> should not duplicate tasks
    scheduler.start_agent_loop(agent_id, interval_seconds=10.0)
    assert scheduler._tasks[agent_id] == task1

    # Stop loop
    scheduler.stop_agent_loop(agent_id)
    assert not scheduler.is_running(agent_id)
    assert agent_repo.get_agent_status(agent_id) == "PAUSED"

    # Shutdown checks
    scheduler.start_agent_loop(agent_id, interval_seconds=5.0)
    scheduler.shutdown()
    assert not scheduler.is_running(agent_id)

@pytest.mark.anyio
async def test_concurrency_lock_protection(exec_service, agent_repo, security_persona, candidate_accept, monkeypatch):
    agent_id = "agent-lock-uuid"
    agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Create a slow discover mock to test overlap overlap prevention
    async def slow_discover():
        await asyncio.sleep(0.2)
        return [candidate_accept]
    monkeypatch.setattr(exec_service.discovery_service, "discover_topics", slow_discover)

    # Run cycle asynchronously
    task = asyncio.create_task(exec_service.run_cycle(agent_id))
    await asyncio.sleep(0.05)  # wait for it to capture lock

    # Try running concurrent cycle -> should return skipped
    res_overlap = await exec_service.run_cycle(agent_id)
    assert res_overlap["status"] == "skipped"
    assert res_overlap["reason"] == "concurrent_run_prevented"

    await task

@pytest.mark.anyio
async def test_failure_isolation_resilience(exec_service, agent_repo, security_persona, monkeypatch):
    agent_id = "agent-fail-uuid"
    agent_repo.save_agent(agent_id, security_persona.model_dump())

    # Mock Discovery to crash
    async def failing_discover():
        raise ConnectionError("RSS Feed timed out")
    monkeypatch.setattr(exec_service.discovery_service, "discover_topics", failing_discover)

    # Verify that the execution coordinates the crash and saves status without throwing exception
    result = await exec_service.run_cycle(agent_id)
    assert result["status"] == "FAILED"
    assert result["discoveredCount"] == 0
