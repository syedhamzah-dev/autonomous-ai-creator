import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from app.core.config import settings
from app.repositories.agent import agent_repository
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.schemas.memory import AgentMemory
from app.schemas.post import GeneratedPost
from app.services.memory import LocalFileMemoryRepository, MemoryService
from app.services.topic_discovery import TopicDiscoveryService
from app.services.llm import MockLLMClient
from app.services.editorial import EditorialJudgmentService
from app.services.content_generator import ContentGeneratorService

logger = logging.getLogger("autonomous_creator")

class AutonomousExecutionService:
    """
    Coordinates one execution cycle for a specific agent:
    1. Topic Discovery
    2. Memory Duplication Check
    3. Editorial Judgment Filtering
    4. Post Generation & Quality Grounding (if ACCEPTED)
    5. State and Persistence memory recording
    """
    def __init__(
        self,
        discovery_service: TopicDiscoveryService,
        editorial_service: EditorialJudgmentService,
        generator_service: ContentGeneratorService,
        memory_service: MemoryService,
        agent_repo=agent_repository
    ):
        self.discovery_service = discovery_service
        self.editorial_service = editorial_service
        self.generator_service = generator_service
        self.memory_service = memory_service
        self.agent_repo = agent_repo
        self._active_runs: Set[str] = set()

    async def run_cycle(self, agent_id: str) -> Dict[str, Any]:
        """
        Executes a single workflow loop cycle for the specified agent.
        
        Args:
            agent_id: The scoping agent ID UUID.
            
        Returns:
            A results dictionary outlining discovered, rejected, and accepted counts.
        """
        # Verify agent profile initialization state
        if not self.agent_repo.agent_exists(agent_id):
            raise ValueError(f"Cannot run loop: Agent with ID '{agent_id}' does not exist.")

        # Concurrency safety lock
        if agent_id in self._active_runs:
            logger.warning(f"[CONCURRENCY_GUARD] Overlapping cycle skipped for agent {agent_id} (already active).")
            return {"status": "skipped", "reason": "concurrent_run_prevented"}

        self._active_runs.add(agent_id)
        logger.info(f"[AUTONOMOUS_CYCLE_STARTED] Initiating background cycle for agent: {agent_id}")

        cycle_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)

        result = {
            "cycleId": cycle_id,
            "agentId": agent_id,
            "startTime": start_time,
            "discoveredCount": 0,
            "rejectedCount": 0,
            "acceptedCount": 0,
            "status": "FAILED",
            "preparedPostId": None
        }

        try:
            # Load agent's persistent persona metadata
            persona_data = self.agent_repo.get_agent_persona(agent_id)
            persona = PersonaProfile(**persona_data)

            # Step 1: Discover candidate topics
            candidates = await self.discovery_service.discover_topics()
            result["discoveredCount"] = len(candidates)
            logger.info(f"[TOPICS_DISCOVERED] Discovered {len(candidates)} candidates from RSS feeds.")

            accepted_candidate: Optional[TopicCandidate] = None
            accepted_decision: Optional[EditorialDecision] = None

            # Step 2: Duplication check and Editorial Evaluation
            for candidate in candidates:
                # Deduplication: query memory repository
                is_duplicate = await self.memory_service.is_repetitive(agent_id, candidate.title)
                if is_duplicate:
                    result["rejectedCount"] += 1
                    logger.info(f"[TOPIC_REJECTED] Rejected candidate '{candidate.title}' (Reason: Repetitive / covered in memory).")
                    continue

                # Run persona filter scoring
                try:
                    decision = await self.editorial_service.evaluate_candidate(persona, candidate)
                except Exception as eval_err:
                    logger.error(f"Editorial scoring error for candidate '{candidate.title}': {eval_err}")
                    continue

                if decision.decision == "REJECT":
                    result["rejectedCount"] += 1
                    logger.info(f"[TOPIC_REJECTED] Rejected candidate '{candidate.title}' (Reasons: {decision.reasons}).")
                    
                    # Store rejection details in persistent memory (scoping context)
                    reject_memory = AgentMemory(
                        memoryId=str(uuid.uuid4()),
                        agentId=agent_id,
                        type="EDITORIAL_DECISION",
                        content=f"REJECTED: {candidate.title}",
                        createdAt=datetime.now(timezone.utc),
                        metadata={
                            "topicId": candidate.id,
                            "title": candidate.title,
                            "decision": "REJECT",
                            "reasons": decision.reasons,
                            "score": decision.score
                        }
                    )
                    await self.memory_service.store(agent_id, reject_memory)
                    continue

                if decision.decision == "ACCEPT":
                    result["acceptedCount"] += 1
                    logger.info(f"[TOPIC_ACCEPTED] Accepted candidate '{candidate.title}' (Overall score: {decision.score}).")
                    accepted_candidate = candidate
                    accepted_decision = decision
                    # Select the first accepted topic candidate and proceed to generate
                    break

            # Step 3: Content Generation (only if accepted topic exists)
            if accepted_candidate and accepted_decision:
                logger.info(f"Generating post content for accepted candidate: '{accepted_candidate.title}'")
                post = await self.generator_service.generate_post(
                    agent_id=agent_id,
                    persona=persona,
                    candidate=accepted_candidate,
                    decision=accepted_decision
                )
                logger.info(f"[CONTENT_GENERATED] Produced generated post: ID {post.id}")
                result["preparedPostId"] = post.id

                # Save generated post to internal repository state as draft/prepared post (not exposed to feed)
                self.agent_repo.save_prepared_post(agent_id, post.model_dump(by_alias=True))

                # Store post in Persistent memory to prevent future cycles from repeating this topic
                post_memory = AgentMemory(
                    memoryId=post.id,
                    agentId=agent_id,
                    type="PUBLISHED_POST",
                    content=post.text,
                    createdAt=datetime.now(timezone.utc),
                    metadata={
                        "topicId": post.topicId,
                        "sources": post.sources,
                        "rationale": post.rationale
                    }
                )
                await self.memory_service.store(agent_id, post_memory)

                # Store topic candidate reference metadata in persistent memory
                topic_memory = AgentMemory(
                    memoryId=str(uuid.uuid4()),
                    agentId=agent_id,
                    type="PUBLISHED_TOPIC",
                    content=accepted_candidate.title,
                    createdAt=datetime.now(timezone.utc),
                    metadata={
                        "topicId": accepted_candidate.id,
                        "sourceUrl": accepted_candidate.sourceUrl,
                        "publishedAt": accepted_candidate.publishedAt.isoformat()
                    }
                )
                await self.memory_service.store(agent_id, topic_memory)

                # Store the ACCEPT decision in persistent memory
                accept_dec_memory = AgentMemory(
                    memoryId=str(uuid.uuid4()),
                    agentId=agent_id,
                    type="EDITORIAL_DECISION",
                    content=f"ACCEPTED: {accepted_candidate.title}",
                    createdAt=datetime.now(timezone.utc),
                    metadata={
                        "topicId": accepted_candidate.id,
                        "title": accepted_candidate.title,
                        "decision": "ACCEPT",
                        "reasons": accepted_decision.reasons,
                        "score": accepted_decision.score
                    }
                )
                await self.memory_service.store(agent_id, accept_dec_memory)

            result["status"] = "SUCCESS"
            logger.info(f"[CYCLE_COMPLETED] Cycle completed successfully. Cycle ID: {cycle_id}")

        except Exception as cycle_err:
            result["status"] = "FAILED"
            logger.error(f"[CYCLE_FAILED] Cycle failed for agent {agent_id}: {cycle_err}", exc_info=True)
        finally:
            result["endTime"] = datetime.now(timezone.utc)
            self._active_runs.remove(agent_id)

        return result


class AgentScheduler:
    """
    Triggers execution loops periodically and safely manages background tasklifespans.
    """
    def __init__(self, execution_service: AutonomousExecutionService):
        self.execution_service = execution_service
        self._tasks: Dict[str, asyncio.Task] = {}
        self._intervals: Dict[str, float] = {}

    def start_agent_loop(self, agent_id: str, interval_seconds: float) -> None:
        """
        Starts a background loop for the specified agent.
        """
        if agent_id in self._tasks:
            logger.info(f"Loop for agent {agent_id} is already scheduled. Ignoring request.")
            return

        async def loop():
            while True:
                try:
                    logger.info(f"Triggering scheduled autonomous cycle for agent: {agent_id}")
                    await self.execution_service.run_cycle(agent_id)
                except Exception as loop_err:
                    logger.error(f"Unhandled error in scheduled loop for agent {agent_id}: {loop_err}", exc_info=True)
                await asyncio.sleep(interval_seconds)

        self._tasks[agent_id] = asyncio.create_task(loop())
        self._intervals[agent_id] = interval_seconds
        self.execution_service.agent_repo.set_agent_status(agent_id, "RUNNING")
        logger.info(f"Autonomous background loop started for agent {agent_id} (interval={interval_seconds}s).")

    def stop_agent_loop(self, agent_id: str) -> None:
        """
        Stops the scheduled loop for the specified agent cleanly.
        """
        task = self._tasks.pop(agent_id, None)
        if task:
            task.cancel()
            self._intervals.pop(agent_id, None)
            self.execution_service.agent_repo.set_agent_status(agent_id, "PAUSED")
            logger.info(f"Autonomous background loop stopped for agent {agent_id}.")

    def is_running(self, agent_id: str) -> bool:
        """
        Verify if the agent loop is active in scheduler tasks.
        """
        return agent_id in self._tasks

    def shutdown(self) -> None:
        """
        Gracefully cleans up and cancels all running loops on server shutdown.
        """
        logger.info("Cleaning up active agent background loops...")
        for agent_id in list(self._tasks.keys()):
            self.stop_agent_loop(agent_id)


# Instantiate the singleton system instances
memory_repo = LocalFileMemoryRepository(base_dir="data/memory")
memory_service = MemoryService(repository=memory_repo)
discovery_service = TopicDiscoveryService()
llm_client = MockLLMClient()
editorial_service = EditorialJudgmentService(llm_client=llm_client)
generator_service = ContentGeneratorService(llm_client=llm_client, memory_service=memory_service)

execution_service = AutonomousExecutionService(
    discovery_service=discovery_service,
    editorial_service=editorial_service,
    generator_service=generator_service,
    memory_service=memory_service,
    agent_repo=agent_repository
)

agent_scheduler = AgentScheduler(execution_service=execution_service)
