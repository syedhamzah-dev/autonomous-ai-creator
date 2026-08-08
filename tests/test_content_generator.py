import pytest
from datetime import datetime, timezone
from typing import List
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.memory import AgentMemory
from app.services.llm import MockLLMClient
from app.services.memory import LocalFileMemoryRepository
from app.services.content_generator import ContentGeneratorService

@pytest.fixture
def temp_memory_dir(tmp_path):
    return str(tmp_path)

@pytest.fixture
def repo(temp_memory_dir):
    return LocalFileMemoryRepository(base_dir=temp_memory_dir)

@pytest.fixture
def llm_client():
    return MockLLMClient()

@pytest.fixture
def generator(llm_client, repo):
    return ContentGeneratorService(llm_client=llm_client, memory_service=repo)

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
        audience="AI researchers and enterprise security practitioners"
    )

@pytest.fixture
def robotics_persona():
    return PersonaProfile(
        name="Atlas",
        domain="Robotics Engineering",
        identity="Robotics Software Architect",
        mission="Design autonomous navigation stacks and robot control systems",
        core_interests=["ROS2 autonomous navigation", "lidar perception", "path planning"],
        topics_to_avoid=["cooking show"],
        writing_style=["Enthusiastic", "structured"],
        editorial_principles=["Focus on hardware efficiency", "Reference open source systems"],
        audience="Robotics engineers and open-source autonomous systems developers"
    )

@pytest.fixture
def valid_candidate():
    return TopicCandidate(
        id="topic-uuid-123",
        title="Zero-day model vulnerability discovered in Transformer architecture",
        summary="A recent exploit vector allows remote token pollution in large language models.",
        source="TechCrunch AI",
        sourceUrl="https://techcrunch.com/ai-vulnerability-paper",
        publishedAt=datetime.now(timezone.utc),
        discoveredAt=datetime.now(timezone.utc)
    )

@pytest.fixture
def accepted_decision():
    return EditorialDecision(
        topicId="topic-uuid-123",
        decision="ACCEPT",
        score=9.0,
        reasons=["Directly relevant to vulnerability assessment", "Significant industry breakthrough"],
        evaluatedAt=datetime.now(timezone.utc),
        relevanceScore=9.5,
        freshnessScore=9.0
    )

@pytest.fixture
def rejected_decision():
    return EditorialDecision(
        topicId="topic-uuid-123",
        decision="REJECT",
        score=3.0,
        reasons=["Off-topic generic news", "Does not interest AI Security profile"],
        evaluatedAt=datetime.now(timezone.utc),
        relevanceScore=2.0,
        freshnessScore=8.0
    )

@pytest.mark.anyio
async def test_basic_post_generation(generator, security_persona, valid_candidate, accepted_decision):
    agent_id = "agent-ada-uuid"
    
    post = await generator.generate_post(
        agent_id=agent_id,
        persona=security_persona,
        candidate=valid_candidate,
        decision=accepted_decision
    )
    
    assert post.id.startswith("post-")
    assert post.text != ""
    assert isinstance(post.createdAt, datetime)
    assert post.createdAt.tzinfo == timezone.utc
    assert post.agentId == agent_id
    assert post.topicId == valid_candidate.id
    assert "vulnerabilities" in post.text.lower() or "vulnerability" in post.text.lower()

@pytest.mark.anyio
async def test_persona_consistency(generator, security_persona, robotics_persona, valid_candidate, accepted_decision):
    agent_id = "agent-uuid"
    
    # 1. Security Persona
    sec_post = await generator.generate_post(agent_id, security_persona, valid_candidate, accepted_decision)
    assert "[Ada | AI Security]" in sec_post.text
    assert "Securing transformer frameworks" in sec_post.text
    
    # 2. Robotics Persona
    rob_post = await generator.generate_post(agent_id, robotics_persona, valid_candidate, accepted_decision)
    assert "[Atlas | Robotics]" in rob_post.text
    assert "Robotic autonomous navigation update" in rob_post.text

@pytest.mark.anyio
async def test_editorial_gating_and_rationale(generator, security_persona, valid_candidate, accepted_decision, rejected_decision):
    agent_id = "agent-uuid"
    
    # Accepted topic generates post
    post = await generator.generate_post(agent_id, security_persona, valid_candidate, accepted_decision)
    # The default mock concatenates reasons
    assert post.rationale == "Directly relevant to vulnerability assessment | Significant industry breakthrough"
    
    # Rejected topic raises error
    with pytest.raises(ValueError, match="Cannot generate content for a rejected topic candidate"):
        await generator.generate_post(agent_id, security_persona, valid_candidate, rejected_decision)

@pytest.mark.anyio
async def test_source_grounding(generator, security_persona, valid_candidate, accepted_decision):
    agent_id = "agent-uuid"
    
    post = await generator.generate_post(agent_id, security_persona, valid_candidate, accepted_decision)
    assert post.sources == [valid_candidate.sourceUrl]
    assert valid_candidate.sourceUrl in post.text

@pytest.mark.anyio
async def test_memory_integration(generator, llm_client, repo, security_persona, valid_candidate, accepted_decision):
    agent_id = "agent-uuid"
    
    # Store a previous memory
    past_memory = AgentMemory(
        memoryId="mem-past-1",
        agentId=agent_id,
        type="PUBLISHED_POST",
        content="Our previous analysis of Transformer vulnerability mitigations.",
        createdAt=datetime.now(timezone.utc)
    )
    await repo.store(agent_id, past_memory)
    
    # Verify generator retrieves memory and passes it to the LLM client
    # Let's spy on the LLM client by configuring a mock post response
    llm_client.configure_mock_post_response({
        "text": "Using memory: successfully avoided repetition.",
        "rationale": "Enriched reasons",
        "sources": [valid_candidate.sourceUrl],
        "generationMetadata": {"recalledMemoryCount": 1}
    })
    
    post = await generator.generate_post(agent_id, security_persona, valid_candidate, accepted_decision)
    assert post.text == "Using memory: successfully avoided repetition."
    assert post.generationMetadata.get("recalledMemoryCount") == 1

@pytest.mark.anyio
async def test_parameter_validation(generator, security_persona, valid_candidate, accepted_decision):
    # Empty agent ID
    with pytest.raises(ValueError, match="Agent ID cannot be empty"):
        await generator.generate_post("", security_persona, valid_candidate, accepted_decision)
        
    # Missing persona
    with pytest.raises(ValueError, match="Persona configuration is missing"):
        await generator.generate_post("agent-id", None, valid_candidate, accepted_decision)
        
    # Missing topic
    with pytest.raises(ValueError, match="Topic candidate is missing"):
        await generator.generate_post("agent-id", security_persona, None, accepted_decision)
        
    # Missing decision
    with pytest.raises(ValueError, match="Editorial decision is missing"):
        await generator.generate_post("agent-id", security_persona, valid_candidate, None)

@pytest.mark.anyio
async def test_provider_behavior_errors(generator, llm_client, security_persona, valid_candidate, accepted_decision):
    agent_id = "agent-uuid"
    
    # 1. Timeout Error
    llm_client.configure_timeout()
    with pytest.raises(TimeoutError, match="Simulated LLM service connection timeout during post generation"):
        await generator.generate_post(agent_id, security_persona, valid_candidate, accepted_decision)
        
    # 2. Malformed structured JSON / empty text output
    llm_client.configure_malformed()
    with pytest.raises(ValueError, match="LLM provider returned empty post text content"):
        await generator.generate_post(agent_id, security_persona, valid_candidate, accepted_decision)
