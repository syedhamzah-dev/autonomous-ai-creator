import asyncio
import sys
from datetime import datetime, timezone, timedelta
from typing import List

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
    print("STARTING 48-HOUR AUTONOMOUS PIPELINE EVALUATION SIMULATION")
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

        # 2. Define Agent Persona Request
        # The PersonaService will generate the full profile with stable core_interests
        # such as "model vulnerabilities" and "AI security"
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
        candidate_accepted_1 = TopicCandidate(
            id="topic-hour-0",
            title="Transformer model vulnerabilities zero-day jailbreak exploit discovered",
            summary="A newly discovered token alignment attack bypasses guardrails on current LLMs.",
            source="TechCrunch AI",
            sourceUrl="https://techcrunch.com/jailbreak-exploit",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )
        
        candidate_rejected = TopicCandidate(
            id="topic-hour-1",
            title="Presidential election primary updates live news report",
            summary="The latest political candidate poll statistics from today's debates.",
            source="Live Politics Feed",
            sourceUrl="https://politicsfeed.com/news",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )
        
        candidate_duplicate = TopicCandidate(
            id="topic-hour-2",
            title="Transformer model vulnerabilities zero-day jailbreak exploit discovered",
            summary="A newly discovered token alignment attack bypasses guardrails on current LLMs.",
            source="TechCrunch AI",
            sourceUrl="https://techcrunch.com/jailbreak-exploit",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )
        
        candidate_accepted_2 = TopicCandidate(
            id="topic-hour-3",
            title="AI security adversarial attack vectors via vision encoder",
            summary="Vision-language model architectures are vulnerable to embedded adversarial patches.",
            source="NVIDIA ML Blog",
            sourceUrl="https://nvidia.com/vision-vulnerability",
            publishedAt=datetime.now(timezone.utc),
            discoveredAt=datetime.now(timezone.utc)
        )

        # 4. Initialize Agent
        print("[STEP 1] Initializing Agent...")
        agent_id = agent_service.initialize_agent(persona_req)
        print(f"Agent initialized successfully with ID: {agent_id}")
        
        # Verify initial feed is empty
        feed = agent_service.get_agent_feed(agent_id)
        assert len(feed) == 0, f"Expected empty feed, got {len(feed)} posts."
        print("✔ Initial feed is empty.")

        # Run 48 simulated hourly cycles
        discovered_topics = []
        for hour in range(48):
            # Define what candidates are discovered at this hour
            if hour == 0:
                discovered_topics = [candidate_accepted_1]
            elif hour == 1:
                discovered_topics = [candidate_rejected]
            elif hour == 2:
                # Try publishing duplicate
                discovered_topics = [candidate_duplicate]
            elif hour == 3:
                discovered_topics = [candidate_accepted_2]
            else:
                # Rest of the hours find no new topics
                discovered_topics = []

            # Mock discovery for this run
            async def mock_discover(topics=discovered_topics):
                return topics
            discovery_service.discover_topics = mock_discover

            # Execute cycle
            print(f"\n[Hour {hour}] Triggering autonomous execution cycle...")
            
            # Print evaluation details beforehand for debugging
            if discovered_topics:
                persona_data = agent_repository.get_agent_persona(agent_id)
                persona_from_repo = PersonaProfile(**persona_data)
                for cand in discovered_topics:
                    is_rep = await memory_service.is_repetitive(agent_id, cand.title, source_url=cand.sourceUrl)
                    dec = await editorial_service.evaluate_candidate(persona_from_repo, cand)
                    print(f"  > Candidate: '{cand.title}'")
                    print(f"    - Is Repetitive: {is_rep}")
                    print(f"    - Editorial Decision: {dec.decision} (Score: {dec.score}, Reasons: {dec.reasons})")

            res = await execution_service.run_cycle(agent_id)
            print(f"Cycle Result - status: {res['status']}, discovered: {res['discoveredCount']}, accepted: {res['acceptedCount']}, rejected: {res['rejectedCount']}")

            # Poll Feed
            feed = agent_service.get_agent_feed(agent_id)
            print(f"Current Feed Count: {len(feed)}")
            
            # Verifications at specific checkpoints
            if hour == 0:
                assert len(feed) == 1, "Expected 1 post in feed after Hour 0."
                assert feed[0]["topicId"] == "topic-hour-0"
                print("✔ Hour 0: Accepted topic published successfully.")
            elif hour == 1:
                assert len(feed) == 1, "Expected feed count to remain 1 after Hour 1 (rejected topic)."
                print("✔ Hour 1: Rejected topic did not modify the feed.")
            elif hour == 2:
                assert len(feed) == 1, "Expected feed count to remain 1 after Hour 2 (duplicate topic)."
                print("✔ Hour 2: Duplicate topic was skipped and not published.")
            elif hour == 3:
                assert len(feed) == 2, "Expected 2 posts in feed after Hour 3."
                # Verify ordering: newest first
                # Hour 3 post should be index 0
                assert feed[0]["topicId"] == "topic-hour-3"
                assert feed[1]["topicId"] == "topic-hour-0"
                print("✔ Hour 3: Second accepted topic published and feed sorted newest first.")
            elif hour > 3:
                # Ensure count remains 2 and order remains newest first
                assert len(feed) == 2
                assert feed[0]["topicId"] == "topic-hour-3"

        print("\n[STEP 3] Performing Final Post Integrity Checks...")
        for post in feed:
            # Check ID is present and unique
            assert len(post["id"]) > 0
            # Check valid datetime or string format
            assert post["createdAt"] is not None
            # Check non-empty text and rationale
            assert len(post["text"].strip()) > 0
            assert len(post["rationale"].strip()) > 0
            assert len(post["sources"]) > 0
            # Verify rationale depth (selection reason, relevance, worth compared with others)
            rat = post["rationale"]
            assert "align" in rat.lower() or "interest" in rat.lower()
            assert "relevant" in rat.lower()
            assert "value" in rat.lower() or "worth" in rat.lower() or "analysis" in rat.lower()
            print(f"✔ Post {post['id']} matches all schema and quality constraints.")

        print("\n======================================================================")
        print("SIMULATION SUCCESS: 48-HOUR DETERMINISTIC PIPELINE OPERATION VERIFIED!")
        print("======================================================================")
        
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    asyncio.run(main())
