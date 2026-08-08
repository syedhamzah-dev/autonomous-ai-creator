import os
import tempfile
from datetime import datetime, timezone, timedelta
import pytest
from app.schemas.memory import AgentMemory
from app.services.memory import LocalFileMemoryRepository, MemoryService

@pytest.fixture
def temp_memory_dir():
    """Fixture that creates a temporary directory for memory storage and cleans it up after."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def repo(temp_memory_dir):
    """Fixture supplying LocalFileMemoryRepository pointing to temporary directory."""
    return LocalFileMemoryRepository(base_dir=temp_memory_dir)

@pytest.fixture
def memory_service(repo):
    """Fixture supplying MemoryService."""
    return MemoryService(repository=repo)

@pytest.mark.anyio
async def test_store_and_get(memory_service):
    agent_id = "agent-123"
    memory_id = "mem-456"
    now = datetime.now(timezone.utc)
    
    memory = AgentMemory(
        memoryId=memory_id,
        agentId=agent_id,
        type="PUBLISHED_TOPIC",
        content="Open-source AI model security vulnerability",
        createdAt=now,
        metadata={"topicId": "topic-abc"}
    )
    
    # Store memory
    await memory_service.store(agent_id, memory)
    
    # Retrieve existing
    retrieved = await memory_service.get(agent_id, memory_id)
    assert retrieved is not None
    assert retrieved.memoryId == memory_id
    assert retrieved.agentId == agent_id
    assert retrieved.type == "PUBLISHED_TOPIC"
    assert retrieved.content == "Open-source AI model security vulnerability"
    # Verify date handling (comparing timestamp floats for microsecond roundtrip compatibility)
    assert abs((retrieved.createdAt - now).total_seconds()) < 1.0
    assert retrieved.metadata == {"topicId": "topic-abc"}
    
    # Unknown memory ID
    unknown = await memory_service.get(agent_id, "unknown-id")
    assert unknown is None

@pytest.mark.anyio
async def test_agent_isolation(memory_service):
    agent_a = "agent-a"
    agent_b = "agent-b"
    memory_id = "mem-1"
    
    memory = AgentMemory(
        memoryId=memory_id,
        agentId=agent_a,
        type="PUBLISHED_POST",
        content="Topic content for agent A",
        createdAt=datetime.now(timezone.utc)
    )
    
    await memory_service.store(agent_a, memory)
    
    # Agent B should not get Agent A's memory by ID
    assert await memory_service.get(agent_b, memory_id) is None
    
    # Agent B search should return nothing
    b_results = await memory_service.search(agent_b, "Topic", limit=5)
    assert len(b_results) == 0
    
    # Agent A gets its own memory
    assert await memory_service.get(agent_a, memory_id) is not None

@pytest.mark.anyio
async def test_search(memory_service):
    agent_id = "agent-123"
    base_time = datetime.now(timezone.utc)
    
    m1 = AgentMemory(
        memoryId="m1",
        agentId=agent_id,
        type="PUBLISHED_TOPIC",
        content="AI safety and model vulnerabilities",
        createdAt=base_time - timedelta(minutes=10)
    )
    m2 = AgentMemory(
        memoryId="m2",
        agentId=agent_id,
        type="EDITORIAL_DECISION",
        content="Elections regulations in tech",
        createdAt=base_time - timedelta(minutes=5)
    )
    m3 = AgentMemory(
        memoryId="m3",
        agentId=agent_id,
        type="PUBLISHED_POST",
        content="ROS2 autonomous navigation and perception mapping",
        createdAt=base_time
    )
    
    await memory_service.store(agent_id, m1)
    await memory_service.store(agent_id, m2)
    await memory_service.store(agent_id, m3)
    
    # Search single matching keyword
    results_vulnerability = await memory_service.search(agent_id, "vulnerabilities")
    assert len(results_vulnerability) == 1
    assert results_vulnerability[0].memoryId == "m1"
    
    # Search multiple keywords case-insensitively
    results_perception = await memory_service.search(agent_id, "ROS2 PERCEPTION")
    assert len(results_perception) == 1
    assert results_perception[0].memoryId == "m3"
    
    # Search returning multiple matches sorted by match relevance/score
    results_tech = await memory_service.search(agent_id, "tech model")
    # m1 matches "model", m2 matches "tech", both should return
    assert len(results_tech) == 2
    
    # Search with empty query returns all up to limit
    results_all = await memory_service.search(agent_id, "", limit=2)
    assert len(results_all) == 2

@pytest.mark.anyio
async def test_recent(memory_service):
    agent_id = "agent-recent"
    base_time = datetime.now(timezone.utc)
    
    m_old = AgentMemory(
        memoryId="old",
        agentId=agent_id,
        type="PUBLISHED_TOPIC",
        content="Old topic",
        createdAt=base_time - timedelta(hours=2)
    )
    m_mid = AgentMemory(
        memoryId="mid",
        agentId=agent_id,
        type="PUBLISHED_TOPIC",
        content="Middle topic",
        createdAt=base_time - timedelta(hours=1)
    )
    m_new = AgentMemory(
        memoryId="new",
        agentId=agent_id,
        type="PUBLISHED_TOPIC",
        content="New topic",
        createdAt=base_time
    )
    
    await memory_service.store(agent_id, m_old)
    await memory_service.store(agent_id, m_new)
    await memory_service.store(agent_id, m_mid)
    
    # Get all with limit=5 (sorted newest first)
    recent_all = await memory_service.recent(agent_id, limit=5)
    assert len(recent_all) == 3
    assert recent_all[0].memoryId == "new"
    assert recent_all[1].memoryId == "mid"
    assert recent_all[2].memoryId == "old"
    
    # Get with limit=2
    recent_limit = await memory_service.recent(agent_id, limit=2)
    assert len(recent_limit) == 2
    assert recent_limit[0].memoryId == "new"
    assert recent_limit[1].memoryId == "mid"

@pytest.mark.anyio
async def test_persistence(temp_memory_dir):
    # Process A writes
    agent_id = "persistent-agent"
    memory_id = "p-1"
    repo_a = LocalFileMemoryRepository(base_dir=temp_memory_dir)
    
    memory = AgentMemory(
        memoryId=memory_id,
        agentId=agent_id,
        type="PUBLISHED_POST",
        content="Persistent post text content",
        createdAt=datetime.now(timezone.utc)
    )
    await repo_a.store(agent_id, memory)
    
    # Re-initialize Process B
    repo_b = LocalFileMemoryRepository(base_dir=temp_memory_dir)
    retrieved = await repo_b.get(agent_id, memory_id)
    assert retrieved is not None
    assert retrieved.content == "Persistent post text content"

@pytest.mark.anyio
async def test_repetition(memory_service):
    agent_id = "agent-repeat"
    
    m_topic = AgentMemory(
        memoryId="rep-1",
        agentId=agent_id,
        type="PUBLISHED_TOPIC",
        content="AI model vulnerabilities discovered",
        createdAt=datetime.now(timezone.utc)
    )
    await memory_service.store(agent_id, m_topic)
    
    # Exact check
    assert await memory_service.is_repetitive(agent_id, "AI model vulnerabilities discovered") is True
    
    # Case-insensitive containment check
    assert await memory_service.is_repetitive(agent_id, "model vulnerabilities") is True
    assert await memory_service.is_repetitive(agent_id, "ai model vulnerabilities discovered in frameworks") is True
    
    # Unrelated
    assert await memory_service.is_repetitive(agent_id, "ROS2 navigation systems") is False

@pytest.mark.anyio
async def test_error_handling(repo, temp_memory_dir):
    agent_id = "agent-error"
    
    # Empty persist directory (implicit: load on new agent returns empty)
    assert await repo.search(agent_id, "query") == []
    
    # Store validation: wrong agent ID mismatch
    bad_memory = AgentMemory(
        memoryId="bad-1",
        agentId="another-agent",
        type="PUBLISHED_POST",
        content="Content",
        createdAt=datetime.now(timezone.utc)
    )
    with pytest.raises(ValueError, match="scoping agent ID does not match memory agent ID"):
        await repo.store(agent_id, bad_memory)
        
    # Malformed JSON file
    file_path = os.path.join(temp_memory_dir, f"{agent_id}.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("NOT VALID JSON DATA")
        
    with pytest.raises(ValueError, match="Corrupted memory file: invalid JSON"):
        await repo.get(agent_id, "some-id")
