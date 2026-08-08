import pytest
from datetime import datetime, timedelta, timezone
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.services.editorial import EditorialJudgmentService
from app.services.llm import MockLLMClient

@pytest.fixture
def security_persona() -> PersonaProfile:
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
def robotics_persona() -> PersonaProfile:
    return PersonaProfile(
        name="Atlas",
        domain="Robotics Engineering",
        identity="Robotics engineer working on autonomous navigation and sensing.",
        mission="Analyzes sensor hardware, mechanical designs, and robotic path planning algorithms.",
        core_interests=["autonomous navigation", "path planning", "LiDAR sensors", "ROS2", "actuators"],
        editorial_principles=["detailed blueprints", "physical safety focus", "benchmark hardware specs"],
        writing_style=["precise", "practical", "diagram-heavy"],
        audience="Robotics engineers and developers",
        topics_to_avoid=["politics", "software-only apps", "speculative finance"]
    )

@pytest.mark.anyio
async def test_relevance_accept_and_reject(security_persona):
    service = EditorialJudgmentService(engine_type="deterministic")
    
    # Highly relevant topic candidate
    relevant_candidate = TopicCandidate(
        id="t1",
        title="Zero-day vulnerability found in popular LLM framework allows model exploit",
        summary="Security researchers discovered an adversarial attack path leading to remote code execution.",
        source="NVIDIA Developer",
        sourceUrl="https://developer.nvidia.com/blog/vulnerability-fix",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=2),
        discoveredAt=datetime.now(timezone.utc)
    )
    
    # Clearly unrelated topic candidate
    unrelated_candidate = TopicCandidate(
        id="t2",
        title="Celebrity chef announces new restaurant in downtown London",
        summary="A culinary star is opening an high-end bistro focusing on organic cuisine.",
        source="TechCrunch",
        sourceUrl="https://techcrunch.com/chef-bistro",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=5),
        discoveredAt=datetime.now(timezone.utc)
    )

    decision_rel = await service.evaluate_candidate(security_persona, relevant_candidate)
    assert decision_rel.decision == "ACCEPT"
    assert decision_rel.score >= 6.0
    assert any("vulnerabilities" in r or "exploit" in r for r in decision_rel.reasons)

    decision_unrel = await service.evaluate_candidate(security_persona, unrelated_candidate)
    assert decision_unrel.decision == "REJECT"
    assert decision_unrel.score < 6.0
    assert any("interests" in r for r in decision_unrel.reasons)

@pytest.mark.anyio
async def test_significance_breakthrough_vs_promotional(security_persona):
    service = EditorialJudgmentService(engine_type="deterministic")

    # High significance breakthrough topic candidate
    breakthrough = TopicCandidate(
        id="t3",
        title="New research paper benchmarks defensive alignment against zero-day adversarial attacks",
        summary="A comprehensive security study detailing how to shield LLMs from exploit.",
        source="AWS ML Blog",
        sourceUrl="https://aws.amazon.com/blogs/ml/research-paper",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=3),
        discoveredAt=datetime.now(timezone.utc)
    )

    # Promotional announcement/webinar candidate
    promotional = TopicCandidate(
        id="t4",
        title="Join us for a webinar with our sponsor detailing cloud sales discount",
        summary="Register today and coupon code to attend our online summit and promo sale.",
        source="TechCrunch",
        sourceUrl="https://techcrunch.com/promo-sales",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=6),
        discoveredAt=datetime.now(timezone.utc)
    )

    dec_break = await service.evaluate_candidate(security_persona, breakthrough)
    dec_promo = await service.evaluate_candidate(security_persona, promotional)

    assert dec_break.decision == "ACCEPT"
    assert dec_break.significanceScore >= 7.0

    # Promotional fluff should be rejected
    assert dec_promo.decision == "REJECT"
    assert dec_promo.significanceScore <= 4.0
    assert any("promotional" in r for r in dec_promo.reasons)

@pytest.mark.anyio
async def test_source_quality_difference(security_persona):
    service = EditorialJudgmentService(engine_type="deterministic")

    # Known high quality source candidate
    high_qual = TopicCandidate(
        id="t5",
        title="New framework release fixes exploit in privacy leakage vectors",
        summary="Details on patch release fixing model vulnerabilities.",
        source="NVIDIA Developer Blog",
        sourceUrl="https://developer.nvidia.com/nvidia-framework",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=4),
        discoveredAt=datetime.now(timezone.utc)
    )

    # Unknown source candidate
    unknown_src = TopicCandidate(
        id="t6",
        title="New framework release fixes exploit in privacy leakage vectors",
        summary="Details on patch release fixing model vulnerabilities.",
        source="Unknown Blog",
        sourceUrl="https://unknown-blog.com/framework-vulnerability",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=4),
        discoveredAt=datetime.now(timezone.utc)
    )

    dec_high = await service.evaluate_candidate(security_persona, high_qual)
    dec_unknown = await service.evaluate_candidate(security_persona, unknown_src)

    # Both accepted but high-quality source should score higher
    assert dec_high.decision == "ACCEPT"
    assert dec_unknown.decision == "ACCEPT"
    assert dec_high.sourceQualityScore == 9.0
    assert dec_unknown.sourceQualityScore == 6.0
    assert dec_high.score > dec_unknown.score

@pytest.mark.anyio
async def test_freshness_penalization(security_persona):
    service = EditorialJudgmentService(engine_type="deterministic")

    # Fresh topic candidate
    fresh = TopicCandidate(
        id="t7",
        title="Zero-day exploit fix details for model vulnerabilities",
        summary="A recent update fixes critical adversarial attack vectors.",
        source="AWS ML Blog",
        sourceUrl="https://aws.amazon.com/blogs/ml/fresh-exploit",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=12),
        discoveredAt=datetime.now(timezone.utc)
    )

    # Stale topic candidate (e.g. 10 days old)
    stale = TopicCandidate(
        id="t8",
        title="Zero-day exploit fix details for model vulnerabilities",
        summary="A recent update fixes critical adversarial attack vectors.",
        source="AWS ML Blog",
        sourceUrl="https://aws.amazon.com/blogs/ml/stale-exploit",
        publishedAt=datetime.now(timezone.utc) - timedelta(days=10),
        discoveredAt=datetime.now(timezone.utc)
    )

    dec_fresh = await service.evaluate_candidate(security_persona, fresh)
    dec_stale = await service.evaluate_candidate(security_persona, stale)

    assert dec_fresh.decision == "ACCEPT"
    assert dec_fresh.freshnessScore == 10.0

    # Stale content should be rejected
    assert dec_stale.decision == "REJECT"
    assert dec_stale.freshnessScore <= 2.0
    assert any("stale" in r for r in dec_stale.reasons)

@pytest.mark.anyio
async def test_editorial_standards_avoided_topics_and_clickbait(security_persona):
    service = EditorialJudgmentService(engine_type="deterministic")

    # Topic containing avoided topic terms (e.g. politics)
    avoided_topic = TopicCandidate(
        id="t9",
        title="Elections and political campaigns debate tech policy",
        summary="Candidates discuss regulation and political outcomes in the tech space.",
        source="TechCrunch",
        sourceUrl="https://techcrunch.com/politics-tech",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=1),
        discoveredAt=datetime.now(timezone.utc)
    )

    # Topic containing hype/clickbait terms
    clickbait_topic = TopicCandidate(
        id="t10",
        title="This mind-blowing and revolutionary AI framework is a shocking game changer!",
        summary="Security practitioners will be amazed by this epic model release exploit.",
        source="AWS ML Blog",
        sourceUrl="https://aws.amazon.com/blogs/ml/clickbait-exploit",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=1),
        discoveredAt=datetime.now(timezone.utc)
    )

    dec_avoided = await service.evaluate_candidate(security_persona, avoided_topic)
    dec_click = await service.evaluate_candidate(security_persona, clickbait_topic)

    # Avoided topic must be rejected immediately with relevance 0.0
    assert dec_avoided.decision == "REJECT"
    assert dec_avoided.relevanceScore == 0.0
    assert any("avoided" in r for r in dec_avoided.reasons)

    # Clickbait should trigger clickbait warnings/penalties
    assert any("Hype" in r or "clickbait" in r or "exaggerated" in r for r in dec_click.reasons)

@pytest.mark.anyio
async def test_persona_differentiation(security_persona, robotics_persona):
    service = EditorialJudgmentService(engine_type="deterministic")

    # A topic candidate that is highly relevant to security but unrelated to robotics
    security_topic = TopicCandidate(
        id="t11",
        title="Zero-day vulnerability discovered in popular AI agent code allowing model exploit",
        summary="A new adversarial attack allows malicious actors to trigger remote leakage.",
        source="NVIDIA Developer",
        sourceUrl="https://developer.nvidia.com/blog/agent-exploit",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=2),
        discoveredAt=datetime.now(timezone.utc)
    )

    # A topic candidate that is highly relevant to robotics but unrelated to security
    robotics_topic = TopicCandidate(
        id="t12",
        title="ROS2 release integrates autonomous navigation algorithms for LiDAR sensors",
        summary="New kinematics path planning software benchmarks ROS2 actuators on hardware.",
        source="NVIDIA Developer",
        sourceUrl="https://developer.nvidia.com/blog/ros2-navigation",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=2),
        discoveredAt=datetime.now(timezone.utc)
    )

    dec_sec_for_sec = await service.evaluate_candidate(security_persona, security_topic)
    dec_sec_for_rob = await service.evaluate_candidate(robotics_persona, security_topic)

    dec_rob_for_sec = await service.evaluate_candidate(security_persona, robotics_topic)
    dec_rob_for_rob = await service.evaluate_candidate(robotics_persona, robotics_topic)

    # AI Security topic: accepted by Security, rejected by Robotics
    assert dec_sec_for_sec.decision == "ACCEPT"
    assert dec_sec_for_rob.decision == "REJECT"

    # Robotics topic: rejected by Security, accepted by Robotics
    assert dec_rob_for_sec.decision == "REJECT"
    assert dec_rob_for_rob.decision == "ACCEPT"

@pytest.mark.anyio
async def test_llm_integration_pathway(security_persona):
    llm_client = MockLLMClient()
    service = EditorialJudgmentService(engine_type="llm", llm_client=llm_client)

    candidate = TopicCandidate(
        id="t13",
        title="Adversarial attack leads to privacy leakage in custom model deploy",
        summary="A review of privacy vulnerabilities and threat intelligence fixes.",
        source="AWS ML Blog",
        sourceUrl="https://aws.amazon.com/blogs/ml/privacy-leakage",
        publishedAt=datetime.now(timezone.utc) - timedelta(hours=5),
        discoveredAt=datetime.now(timezone.utc)
    )

    # 1. Success mock path
    llm_client.configure_mock_response({
        "decision": "ACCEPT",
        "score": 9.2,
        "reasons": ["Excellent LLM evaluation fit.", "Covers model threat profile."],
        "relevanceScore": 9.5,
        "freshnessScore": 9.0,
        "significanceScore": 9.0,
        "sourceQualityScore": 9.0,
        "personaFitScore": 9.5,
        "confidence": 0.98
    })

    dec_success = await service.evaluate_candidate(security_persona, candidate)
    assert dec_success.decision == "ACCEPT"
    assert dec_success.score == 9.2
    assert "Excellent LLM evaluation fit." in dec_success.reasons

    # 2. Timeout error path (must fail safely to REJECT)
    llm_client.configure_timeout()
    dec_timeout = await service.evaluate_candidate(security_persona, candidate)
    assert dec_timeout.decision == "REJECT"
    assert dec_timeout.score == 0.0
    assert any("failed" in r or "timeout" in r for r in dec_timeout.reasons)

    # 3. Malformed payload output path (must fail safely to REJECT)
    llm_client.configure_malformed()
    dec_malformed = await service.evaluate_candidate(security_persona, candidate)
    assert dec_malformed.decision == "REJECT"
    assert dec_malformed.score == 0.0
    assert any("failed" in r or "Malformed" in r for r in dec_malformed.reasons)

@pytest.mark.anyio
async def test_batch_evaluation_and_prioritizing(security_persona):
    service = EditorialJudgmentService(engine_type="deterministic")

    candidates = [
        # Candidate 1: High Relevance
        TopicCandidate(
            id="c1",
            title="Adversarial attack vulnerability patch released",
            summary="A zero-day exploit was patched in framework.",
            source="NVIDIA Developer",
            sourceUrl="https://nvidia.com/exploit-patch",
            publishedAt=datetime.now(timezone.utc) - timedelta(hours=1),
            discoveredAt=datetime.now(timezone.utc)
        ),
        # Candidate 2: Irrelevant
        TopicCandidate(
            id="c2",
            title="Football team wins league championship match",
            summary="The final match ended with a scoring record.",
            source="Unknown",
            sourceUrl="https://unknown.com/football",
            publishedAt=datetime.now(timezone.utc) - timedelta(hours=2),
            discoveredAt=datetime.now(timezone.utc)
        ),
        # Candidate 3: Medium Relevance
        TopicCandidate(
            id="c3",
            title="New exploit benchmark released to evaluate model vulnerabilities",
            summary="This research dataset tracks privacy leakage.",
            source="AWS ML Blog",
            sourceUrl="https://aws.amazon.com/blogs/ml/exploit-benchmark",
            publishedAt=datetime.now(timezone.utc) - timedelta(hours=2),
            discoveredAt=datetime.now(timezone.utc)
        )
    ]

    decisions = await service.evaluate_candidates(security_persona, candidates)
    assert len(decisions) == 3

    # Assert correct decisions mapping
    dec_c1 = next(d for d in decisions if d.topicId == "c1")
    dec_c2 = next(d for d in decisions if d.topicId == "c2")
    dec_c3 = next(d for d in decisions if d.topicId == "c3")

    assert dec_c1.decision == "ACCEPT"
    assert dec_c2.decision == "REJECT"
    assert dec_c3.decision == "ACCEPT"

    # Prioritization check (ordering sorted by score descending)
    prioritized = service.get_prioritized_candidates(decisions)
    assert len(prioritized) == 2
    assert prioritized[0].topicId == "c1"  # Matches higher interests count & newer source
    assert prioritized[1].topicId == "c3"
    assert prioritized[0].score >= prioritized[1].score
