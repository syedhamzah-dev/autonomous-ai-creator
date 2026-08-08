import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from app.core.config import settings
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate
from app.schemas.editorial import EditorialDecision
from app.services.llm import BaseLLMClient

logger = logging.getLogger(__name__)

class EditorialJudgmentService:
    """
    Service responsible for evaluating topic candidates against an agent's persona.
    Supports both rule-based deterministic evaluation and LLM-driven evaluation.
    """
    def __init__(
        self,
        engine_type: Optional[str] = None,
        llm_client: Optional[BaseLLMClient] = None
    ) -> None:
        # Default to the application configuration
        self.engine_type = engine_type or settings.editorial_engine_type
        self.llm_client = llm_client
        self.threshold = settings.editorial_threshold

    async def evaluate_candidate(self, persona: PersonaProfile, candidate: TopicCandidate) -> EditorialDecision:
        """
        Evaluate a single TopicCandidate against a PersonaProfile.
        """
        evaluated_at = datetime.now(timezone.utc)
        
        # Check active engine mode
        if self.engine_type.lower() == "llm":
            if not self.llm_client:
                logger.warning("LLM client not configured. Falling back to deterministic evaluation.")
                return self._evaluate_deterministic(persona, candidate, evaluated_at)
            
            try:
                current_time_str = evaluated_at.isoformat()
                llm_res = await self.llm_client.generate_structured_decision(
                    persona, candidate, current_time_str
                )
                
                # Validate output structure
                decision = llm_res.get("decision", "REJECT")
                score = float(llm_res.get("score", 0.0))
                reasons = llm_res.get("reasons", [])
                
                # Check formatting validity
                if decision not in ("ACCEPT", "REJECT") or not isinstance(reasons, list) or not reasons:
                    raise ValueError("Malformed decision or reasons returned from LLM client.")
                
                return EditorialDecision(
                    topicId=candidate.id,
                    decision=decision,
                    score=score,
                    reasons=reasons,
                    evaluatedAt=evaluated_at,
                    relevanceScore=llm_res.get("relevanceScore"),
                    freshnessScore=llm_res.get("freshnessScore"),
                    significanceScore=llm_res.get("significanceScore"),
                    sourceQualityScore=llm_res.get("sourceQualityScore"),
                    personaFitScore=llm_res.get("personaFitScore"),
                    confidence=llm_res.get("confidence", 0.85)
                )
            except Exception as e:
                logger.error(
                    f"LLM evaluation failed for candidate {candidate.id}: {e}. Failing safely with REJECT.",
                    exc_info=True
                )
                return EditorialDecision(
                    topicId=candidate.id,
                    decision="REJECT",
                    score=0.0,
                    reasons=[f"Evaluation failed: LLM client error ({e}). Safe rejection applied."],
                    evaluatedAt=evaluated_at,
                    relevanceScore=0.0,
                    freshnessScore=5.0,
                    significanceScore=0.0,
                    sourceQualityScore=0.0,
                    personaFitScore=0.0,
                    confidence=1.0
                )
        
        # Default: Deterministic evaluation
        return self._evaluate_deterministic(persona, candidate, evaluated_at)

    async def evaluate_candidates(
        self,
        persona: PersonaProfile,
        candidates: List[TopicCandidate]
    ) -> List[EditorialDecision]:
        """
        Evaluate a batch of topic candidates in a single discovery cycle.
        Isolates individual errors so that a single failure doesn't block the batch.
        """
        decisions = []
        for candidate in candidates:
            try:
                decision = await self.evaluate_candidate(persona, candidate)
                decisions.append(decision)
            except Exception as e:
                logger.error(
                    f"Unexpected exception evaluating candidate {candidate.id}: {e}. Failing safely with REJECT.",
                    exc_info=True
                )
                decisions.append(
                    EditorialDecision(
                        topicId=candidate.id,
                        decision="REJECT",
                        score=0.0,
                        reasons=[f"Safe reject: Unexpected evaluation error ({e})."],
                        evaluatedAt=datetime.now(timezone.utc)
                    )
                )
        return decisions

    def get_prioritized_candidates(self, decisions: List[EditorialDecision]) -> List[EditorialDecision]:
        """
        Filters the evaluation results to return only accepted decisions, sorted by score descending.
        """
        accepted = [d for d in decisions if d.decision == "ACCEPT"]
        return sorted(accepted, key=lambda x: x.score, reverse=True)

    def _evaluate_deterministic(
        self,
        persona: PersonaProfile,
        candidate: TopicCandidate,
        evaluated_at: datetime
    ) -> EditorialDecision:
        """
        Heuristic-based deterministic evaluation matching topic text against persona interests.
        """
        title = candidate.title or ""
        summary = candidate.summary or ""
        text_to_analyze = f"{title} {summary}".lower()

        reasons = []

        # 1. Relevance & Avoided Topics
        # Check avoided topics first (critical filter)
        avoided_match = None
        for avoid in persona.topics_to_avoid:
            avoid_clean = avoid.lower().strip()
            if not avoid_clean:
                continue
            
            # Simple stem/alias expansions for common terms
            terms_to_check = [avoid_clean]
            if avoid_clean == "politics":
                terms_to_check.extend(["political", "politician", "elections"])
            
            for term in terms_to_check:
                if term in text_to_analyze:
                    avoided_match = avoid
                    break
            if avoided_match:
                break

        if avoided_match:
            relevance_score = 0.0
            reasons.append(f"Rejected: Topic matches avoided category list ('{avoided_match}').")
        else:
            # Base relevance is 0.0 if there is no matched interest to ensure strict relevance
            relevance_score = 0.0
            matched_interests = []
            for interest in persona.core_interests:
                if interest.lower().strip() and interest.lower().strip() in text_to_analyze:
                    matched_interests.append(interest)
                    relevance_score += 2.5
            
            if matched_interests:
                relevance_score = min(3.0 + relevance_score, 10.0)
                reasons.append(f"Accepted: Matches persona interests: {', '.join([f'\'{i}\'' for i in matched_interests])}.")
            else:
                reasons.append("Rejected: No direct match with core persona interests.")

        # 2. Significance
        # High value technical words
        significance_score = 5.0
        tech_words = [
            "breakthrough", "benchmark", "release", "research", "vulnerability",
            "exploit", "zero-day", "security breach", "framework", "architecture",
            "state of the art", "model release", "open source", "paper", "dataset"
        ]
        matched_tech = [w for w in tech_words if w in text_to_analyze]
        if matched_tech:
            significance_score += min(len(matched_tech) * 1.5, 3.0)

        # Promotional/low-information flags
        promo_words = [
            "announcing", "promo", "webinar", "register", "join us", "partnering",
            "discount", "sale", "special offer", "summit", "conference", "coupon",
            "giveaway"
        ]
        matched_promo = [w for w in promo_words if w in text_to_analyze]
        if matched_promo:
            significance_score -= min(len(matched_promo) * 2.0, 4.0)

        significance_score = max(min(significance_score, 10.0), 0.0)
        
        if matched_promo:
            reasons.append("Rejected: Contains promotional language or low-information content flags.")
        elif matched_tech:
            reasons.append(f"Significance: Technical keywords matched ({', '.join(matched_tech)}).")

        # 3. Freshness
        freshness_score = 5.0
        if candidate.publishedAt:
            diff = evaluated_at - candidate.publishedAt
            diff_hours = diff.total_seconds() / 3600.0
            
            if diff_hours < 0:
                # Future date, handle gracefully
                freshness_score = 10.0
            elif diff_hours <= 24:
                freshness_score = 10.0
                reasons.append("Freshness: Published within the last 24 hours.")
            elif diff_hours <= 72:
                freshness_score = 8.0
                reasons.append("Freshness: Published within the last 3 days.")
            elif diff_hours <= 168:
                freshness_score = 5.0
            else:
                freshness_score = 2.0
                reasons.append(f"Rejected: Topic is stale, published {diff.days} days ago.")
        else:
            reasons.append("Freshness: Publication date unavailable. Fallback score applied.")

        # 4. Source Credibility/Quality
        source_lower = (candidate.source or "").lower()
        if any(s in source_lower for s in ["nvidia", "aws", "amazon"]):
            source_quality = 9.0
        elif any(s in source_lower for s in ["techcrunch", "technologyreview", "mit"]):
            source_quality = 8.0
        else:
            source_quality = 6.0

        # 5. Persona Fit Score
        # Average of relevance and significance, penalized by generic hype clickbait words
        persona_fit = (relevance_score + significance_score) / 2.0
        hype_words = ["game changer", "revolutionary", "disruptive", "mind-blowing", "shocking", "epic"]
        matched_hype = [w for w in hype_words if w in text_to_analyze]
        if matched_hype:
            persona_fit = max(persona_fit - 2.0, 0.0)
            reasons.append("Hype check: Clickbait or exaggerated claims detected.")

        # Final Overall Score
        overall_score = (relevance_score + significance_score + freshness_score + source_quality + persona_fit) / 5.0

        # Make the decision
        # Needs to meet overall threshold AND have a positive relevance score (avoided topics reject automatically)
        # AND meet a minimum relevance threshold of 5.0 (at least one matched interest)
        # AND meet a minimum freshness threshold of 5.0 (not stale)
        decision = "REJECT"
        if overall_score >= self.threshold and relevance_score >= 5.0 and freshness_score >= 5.0:
            decision = "ACCEPT"
        else:
            # If rejected, specify key failing conditions
            if relevance_score < 5.0:
                if relevance_score == 0.0 and avoided_match:
                    pass # Handled by avoided topic message
                else:
                    reasons.append(f"Rejected: Low relevance score ({relevance_score:.2f}) - does not match core persona interests.")
            elif freshness_score < 5.0:
                reasons.append(f"Rejected: Content is stale, freshness score is low ({freshness_score:.2f}).")
            elif overall_score < self.threshold:
                reasons.append(f"Rejected: Overall score ({overall_score:.2f}) falls below threshold ({self.threshold}).")

        # Clean reasons to make them concise and unique
        clean_reasons = []
        for r in reasons:
            if r not in clean_reasons:
                clean_reasons.append(r)

        confidence = 0.95 if relevance_score >= 5.0 else 0.99

        return EditorialDecision(
            topicId=candidate.id,
            decision=decision,
            score=round(overall_score, 2),
            reasons=clean_reasons,
            evaluatedAt=evaluated_at,
            relevanceScore=relevance_score,
            freshnessScore=freshness_score,
            significanceScore=significance_score,
            sourceQualityScore=source_quality,
            personaFitScore=persona_fit,
            confidence=confidence
        )
