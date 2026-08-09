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


def validate_post_to_publish(post: GeneratedPost, agent_id: str, existing_posts: List[Dict[str, Any]]) -> bool:
    """
    Validate the generated post against multiple constraints before publishing to the feed:
    - unique ID
    - valid timestamp
    - non-empty text
    - non-empty rationale
    - valid source structure
    - correct agent association
    """
    # 1. Unique ID
    if not post.id or not isinstance(post.id, str) or not post.id.strip():
        return False
    # Check duplicate ID in existing feed posts
    existing_ids = {p.get("id") for p in existing_posts}
    if post.id in existing_ids:
        return False
        
    # 2. Valid timestamp
    if not post.createdAt or not isinstance(post.createdAt, datetime):
        return False
        
    # 3. Non-empty text
    if not post.text or not isinstance(post.text, str) or not post.text.strip():
        return False
        
    # 4. Non-empty rationale
    if not post.rationale or not isinstance(post.rationale, str) or not post.rationale.strip():
        return False
        
    # 5. Valid source structure
    if not isinstance(post.sources, list):
        return False
    for source in post.sources:
        if not isinstance(source, str) or not source.strip():
            return False
            
    # 6. Correct agent association
    if post.agentId != agent_id:
        return False
        
    return True


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
                try:
                    is_duplicate = await self.memory_service.is_repetitive(
                        agent_id, candidate.title, source_url=candidate.sourceUrl
                    )
                except Exception as mem_err:
                    # Safest duplication prevention: treat as duplicate if memory check fails
                    logger.error(f"[MEMORY_FAILURE] Repetition check failed for '{candidate.title}': {mem_err}. Treating as duplicate for safety.", exc_info=True)
                    is_duplicate = True

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

                # Enforce editorial judgment validation gate
                if not decision or decision.decision not in ("ACCEPT", "REJECT"):
                    logger.warning(f"Editorial judgment returned invalid decision format for '{candidate.title}'. Safely treating as REJECT.")
                    result["rejectedCount"] += 1
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
                    try:
                        await self.memory_service.store(agent_id, reject_memory)
                    except Exception as store_reject_err:
                        logger.warning(f"[MEMORY_FAILURE] Failed to store rejection memory for '{candidate.title}': {store_reject_err}")
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
                try:
                    logger.info(f"Generating post content for accepted candidate: '{accepted_candidate.title}'")
                    post = await self.generator_service.generate_post(
                        agent_id=agent_id,
                        persona=persona,
                        candidate=accepted_candidate,
                        decision=accepted_decision
                    )
                except Exception as gen_err:
                    logger.error(f"[GENERATION_FAILURE] Content generation failed for candidate '{accepted_candidate.title}': {gen_err}", exc_info=True)
                    raise RuntimeError(f"Content generation failed: {gen_err}") from gen_err

                logger.info(f"[CONTENT_GENERATED] Produced generated post: ID {post.id}")
                result["preparedPostId"] = post.id

                # Prepare memory structures
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

                # Store post in Persistent memory FIRST (deduplication priority check)
                try:
                    await self.memory_service.store(agent_id, post_memory)
                    await self.memory_service.store(agent_id, topic_memory)
                    await self.memory_service.store(agent_id, accept_dec_memory)
                except Exception as store_mem_err:
                    logger.error(f"[MEMORY_FAILURE] Failed to store published post metadata in memory for agent {agent_id}: {store_mem_err}", exc_info=True)
                    # Abort before publishing to feed to prevent duplicate retry anomalies
                    raise RuntimeError(f"Memory persistence failed: {store_mem_err}") from store_mem_err

                # Save generated post to internal repository state as draft/prepared post
                try:
                    self.agent_repo.save_prepared_post(agent_id, post.model_dump(by_alias=True))
                except Exception as draft_err:
                    logger.warning(f"[REPOSITORY_WARNING] Failed to save prepared draft post: {draft_err}")

                # Validate and publish the post to the evaluator-facing feed SECOND
                existing_posts = self.agent_repo.get_agent_posts(agent_id) or []
                if validate_post_to_publish(post, agent_id, existing_posts):
                    try:
                        self.agent_repo.save_published_post(agent_id, post.model_dump(by_alias=True))
                        logger.info(f"[CONTENT_PUBLISHED] Successfully validated and published post {post.id} to agent feed.")
                    except Exception as pub_err:
                        logger.error(f"[PUBLISHING_FAILURE] Feed persistence failed for post {post.id}: {pub_err}", exc_info=True)
                        raise RuntimeError(f"Feed persistence failed: {pub_err}") from pub_err
                else:
                    logger.error(f"[POST_VALIDATION_FAILED] Generated post {post.id} failed validation constraints. Post was blocked from the feed.")
                    raise ValueError(f"Post {post.id} failed validation constraints.")

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
from app.core.config import settings
from app.services.llm import MockLLMClient, GeminiLLMClient

memory_repo = LocalFileMemoryRepository(base_dir="data/memory")
memory_service = MemoryService(repository=memory_repo)
discovery_service = TopicDiscoveryService()

if settings.app_env == "test":
    llm_client = MockLLMClient()
else:
    if not settings.llm_api_key:
        raise ValueError(
            "CRITICAL CONFIGURATION ERROR: 'LLM_API_KEY' environment variable is not configured. "
            "A real LLM provider API key is required in production/development mode."
        )
    llm_client = GeminiLLMClient(api_key=settings.llm_api_key, model_name=settings.llm_model)

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
