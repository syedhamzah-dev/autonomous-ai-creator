import asyncio
import sys
from datetime import datetime, timezone, timedelta

from app.repositories.agent import agent_repository
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.services.llm import MockLLMClient
from app.services.memory import LocalFileMemoryRepository, MemoryService
from app.services.topic_discovery import TopicDiscoveryService
from app.services.editorial import EditorialJudgmentService
from app.services.content_generator import ContentGeneratorService
from app.services.autonomous import AutonomousExecutionService
from app.services.agent import AgentService
from app.core.config import settings

async def main():
    print("======================================================================")
    print("STARTING AUTONOMOUS PIPELINE RELIABILITY & FAILURE RECOVERY SIMULATION")
    print("======================================================================")

    # Disable scheduler loop auto-trigger for simulation
    settings.autonomous_enabled = False

    # Setup temp memory path
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp()
    
    try:
        memory_repo = LocalFileMemoryRepository(base_dir=temp_dir)
        memory_service = MemoryService(repository=memory_repo)
        llm_client = MockLLMClient()
        
        # Configure LLM client to use "llm" engine
        editorial_service = EditorialJudgmentService(engine_type="llm", llm_client=llm_client)
        generator_service = ContentGeneratorService(llm_client=llm_client, memory_service=memory_service)
        discovery_service = TopicDiscoveryService()
        
        execution_service = AutonomousExecutionService(
            discovery_service=discovery_service,
            editorial_service=editorial_service,
            generator_service=generator_service,
            memory_service=memory_service,
            agent_repo=agent_repository
        )
        
        agent_service = AgentService(repository=agent_repository)

        # 2. Define Agent Persona
        persona_req = PersonaProfile(
            name="Ada",
            domain="AI Security",
            identity="AI Security Specialist and Auditor",
            mission="Analyze and secure AI model architectures against adversarial exploitation",
            core_interests=["model vulnerabilities", "AI security", "privacy"],
            topics_to_avoid=["general politics"],
            writing_style=["Analytical", "skeptical"],
            editorial_principles=["Always ground technical claims", "Explain exact exploit vectors"],
            audience="AI researchers and practitioners"
        )
        
        # 3. Define candidate topics at different simulated hours
        candidate_1 = TopicCandidate(
            id="topic-1",
            title="Transformer model vulnerabilities zero-day jailbreak exploit discovered",
            summary="A newly discovered token alignment attack bypasses guardrails on current LLMs.",
            source="TechCrunch AI",
            sourceUrl="https://techcrunch.com/jailbreak-exploit",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )
        
        candidate_rejected = TopicCandidate(
            id="topic-rejected",
            title="Presidential election primary updates live news report",
            summary="The latest political candidate poll statistics from today's debates.",
            source="Live Politics Feed",
            sourceUrl="https://politicsfeed.com/news",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )
        
        candidate_duplicate = TopicCandidate(
            id="topic-1-dup",
            title="Transformer model vulnerabilities zero-day jailbreak exploit discovered",
            summary="A newly discovered token alignment attack bypasses guardrails on current LLMs.",
            source="TechCrunch AI",
            sourceUrl="https://techcrunch.com/jailbreak-exploit",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )
        
        candidate_2 = TopicCandidate(
            id="topic-2",
            title="AI security adversarial attack vectors via vision encoder",
            summary="Vision-language model architectures are vulnerable to embedded adversarial patches.",
            source="NVIDIA ML Blog",
            sourceUrl="https://nvidia.com/vision-vulnerability",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )

        candidate_3 = TopicCandidate(
            id="topic-3",
            title="Privacy threat models in centralized database synchronization",
            summary="Securing cloud replication layers from adversarial side-channels.",
            source="AWS Security Blog",
            sourceUrl="https://aws.amazon.com/privacy-threats",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )

        # 4. Initialize Agent
        print("[STEP 1] Initializing Agent...")
        agent_id = agent_service.initialize_agent(persona_req)
        print(f"Agent initialized successfully with ID: {agent_id}")
        
        feed = agent_service.get_agent_feed(agent_id)
        assert len(feed) == 0, f"Expected empty feed, got {len(feed)} posts."
        print("✔ Initial feed is empty.")

        # Simulate the 7 sequential cycles
        for cycle in range(1, 8):
            print(f"\n--- [Cycle {cycle}] ---")
            
            # Setup mocks for specific cycle failures/behavior
            if cycle == 1:
                # Cycle 1: accepted -> published
                print("Behavior: Normal execution with accepted topic candidate")
                async def mock_disc():
                    return [candidate_1]
                discovery_service.discover_topics = mock_disc
            elif cycle == 2:
                # Cycle 2: rejected
                print("Behavior: Evaluation with candidate matching avoided topic (politics)")
                async def mock_disc():
                    return [candidate_rejected]
                discovery_service.discover_topics = mock_disc
            elif cycle == 3:
                # Cycle 3: discovery failure
                print("Behavior: Simulated RSS timeout / discovery exception")
                async def mock_disc():
                    raise RuntimeError("DNS lookup failed for feed server.")
                discovery_service.discover_topics = mock_disc
            elif cycle == 4:
                # Cycle 4: generation failure
                print("Behavior: Simulated content generation model failure")
                async def mock_disc():
                    return [candidate_2]
                discovery_service.discover_topics = mock_disc
                # Mock generation to throw
                async def mock_gen(*args, **kwargs):
                    raise ValueError("LLM generation API credit quota exhausted.")
                generator_service.generate_post = mock_gen
            elif cycle == 5:
                # Cycle 5: accepted -> published
                print("Behavior: Recovery and successful publication")
                async def mock_disc():
                    return [candidate_2]
                discovery_service.discover_topics = mock_disc
                # Restore generator service
                generator_service.generate_post = ContentGeneratorService(llm_client=llm_client, memory_service=memory_service).generate_post
            elif cycle == 6:
                # Cycle 6: duplicate -> rejected
                print("Behavior: Attempt to publish duplicate candidate_1")
                async def mock_disc():
                    return [candidate_duplicate]
                discovery_service.discover_topics = mock_disc
            elif cycle == 7:
                # Cycle 7: accepted -> published
                print("Behavior: Third accepted topic candidate execution")
                async def mock_disc():
                    return [candidate_3]
                discovery_service.discover_topics = mock_disc

            # Execute run_cycle
            res = await execution_service.run_cycle(agent_id)
            print(f"Cycle Result: status={res['status']}, accepted={res['acceptedCount']}, rejected={res['rejectedCount']}, discovered={res['discoveredCount']}")

            # Verification assertions at checkpoint
            feed = agent_service.get_agent_feed(agent_id)
            print(f"Current Feed Count: {len(feed)}")
            
            if cycle == 1:
                assert res["status"] == "SUCCESS"
                assert len(feed) == 1
                assert feed[0]["topicId"] == "topic-1"
                print("✔ Checkpoint Cycle 1: First post successfully published.")
            elif cycle == 2:
                assert res["status"] == "SUCCESS"
                assert len(feed) == 1
                assert res["rejectedCount"] == 1
                print("✔ Checkpoint Cycle 2: Candidate rejected correctly without modifying feed.")
            elif cycle == 3:
                assert res["status"] == "FAILED"
                assert len(feed) == 1  # Existing posts intact
                print("✔ Checkpoint Cycle 3: Discovery failure handled safely. Feed intact.")
            elif cycle == 4:
                assert res["status"] == "FAILED"
                assert len(feed) == 1  # Existing posts intact
                print("✔ Checkpoint Cycle 4: Content generation failure handled safely. Feed intact.")
            elif cycle == 5:
                assert res["status"] == "SUCCESS"
                assert len(feed) == 2
                assert feed[0]["topicId"] == "topic-2"  # Newest first
                print("✔ Checkpoint Cycle 5: Recovered successfully and published post 2.")
            elif cycle == 6:
                assert res["status"] == "SUCCESS"
                assert len(feed) == 2
                assert res["rejectedCount"] == 1  # Skipped as duplicate
                print("✔ Checkpoint Cycle 6: Duplicate candidate skipped successfully. Feed intact.")
            elif cycle == 7:
                assert res["status"] == "SUCCESS"
                assert len(feed) == 3
                assert feed[0]["topicId"] == "topic-3"  # Newest first
                print("✔ Checkpoint Cycle 7: Successfully published third post.")

        print("\n[STEP 3] Performing Final Post Integrity Checks...")
        for post in feed:
            assert len(post["id"]) > 0
            assert post["createdAt"] is not None
            assert len(post["text"].strip()) > 0
            assert len(post["rationale"].strip()) > 0
            assert len(post["sources"]) > 0
            print(f"✔ Post {post['id']} schema and rationale validated successfully.")

        # Check chronological ordering: newest first
        # feed[0] has topic-3, feed[1] has topic-2, feed[2] has topic-1
        assert feed[0]["topicId"] == "topic-3"
        assert feed[1]["topicId"] == "topic-2"
        assert feed[2]["topicId"] == "topic-1"
        print("✔ chronological ordering (newest first) verified.")

        print("\n======================================================================")
        print("SIMULATION SUCCESS: AUTONOMOUS RELIABILITY & GRACEFUL RECOVERY VERIFIED!")
        print("======================================================================")
        
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    asyncio.run(main())
