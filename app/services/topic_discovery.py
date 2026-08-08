import uuid
import json
import logging
import email.utils
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import xml.etree.ElementTree as ET

import httpx

from app.core.config import settings
from app.schemas.persona import PersonaProfile
from app.schemas.topic import TopicCandidate

logger = logging.getLogger(__name__)

# XML Namespaces mapped for general feed tags
NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom"
}


def normalize_url(url: str) -> str:
    """
    Normalizes a URL by:
    - Stripping surrounding spaces
    - Converting scheme and domain to lowercase
    - Dropping tracking query parameters (like utm_*)
    - Dropping trailing slash (except on the root path)
    """
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # Filter tracking parameters
        qsl = parse_qsl(parsed.query)
        clean_qsl = [(k, v) for k, v in qsl if not k.lower().startswith("utm_")]
        query = urlencode(clean_qsl)
        
        path = parsed.path
        if path.endswith("/") and len(path) > 1:
            path = path[:-1]
            
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            parsed.params,
            query,
            parsed.fragment
        ))
        return normalized
    except Exception as e:
        logger.warning(f"Failed to normalize URL '{url}': {e}")
        return ""


def parse_datetime(dt_str: str) -> datetime:
    """
    Parses datetime strings in standard RSS (RFC 822) or Atom (ISO 8601) format
    and returns a timezone-aware UTC datetime.
    """
    if not dt_str:
        raise ValueError("Date string cannot be empty")
    dt_str = dt_str.strip()
    
    # Try parsing RFC 822 format (RSS pubDate)
    try:
        dt = email.utils.parsedate_to_datetime(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
        
    # Try parsing ISO 8601 format (Atom published/updated)
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
        
    raise ValueError(f"Unsupported datetime format: '{dt_str}'")


class BaseSourceAdapter(ABC):
    """
    Abstract Interface for fetching and parsing technology feed sources.
    """
    def __init__(self, source_url: str) -> None:
        self.source_url = source_url

    @abstractmethod
    async def fetch_and_parse(self, client: httpx.AsyncClient) -> List[TopicCandidate]:
        """
        Retrieves feed items from the source and parses them into TopicCandidate models.
        """
        pass


class RSSAtomAdapter(BaseSourceAdapter):
    """
    Unified RSS and Atom source adapter.
    Uses basic ElementTree XML parsing and dynamically detects the feed schema.
    """
    async def fetch_and_parse(self, client: httpx.AsyncClient) -> List[TopicCandidate]:
        logger.info(f"Fetching feed from URL: {self.source_url}")
        try:
            resp = await client.get(self.source_url)
        except Exception as e:
            raise RuntimeError(f"HTTP request failed: {e}") from e
            
        if resp.status_code != 200:
            raise RuntimeError(f"Server returned HTTP status code {resp.status_code}")
            
        try:
            root = ET.fromstring(resp.content)
        except Exception as e:
            raise ValueError(f"Malformed XML payload: {e}") from e
            
        root_tag_lower = root.tag.lower()
        
        if "rss" in root_tag_lower:
            return self._parse_rss(root)
        elif "feed" in root_tag_lower:
            return self._parse_atom(root)
        else:
            raise ValueError(f"Unsupported feed type, root element is '{root.tag}'")

    def _parse_rss(self, root: ET.Element) -> List[TopicCandidate]:
        candidates: List[TopicCandidate] = []
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS feed missing <channel> root element")
            
        source_name = channel.findtext("title", "RSS Source").strip()
        
        for item in channel.findall("item"):
            title = item.findtext("title")
            link = item.findtext("link")
            
            if not title or not link:
                logger.warning("Skipping RSS item due to missing title or link.")
                continue
                
            summary = item.findtext("description") or ""
            if not summary:
                summary = item.findtext("content:encoded", namespaces=NAMESPACES) or ""
            summary = summary.strip()
            
            pub_date_str = item.findtext("pubDate")
            if not pub_date_str:
                logger.warning("Skipping RSS item due to missing pubDate.")
                continue
                
            try:
                published_at = parse_datetime(pub_date_str)
            except Exception as e:
                logger.warning(f"Skipping RSS item due to invalid pubDate '{pub_date_str}': {e}")
                continue
                
            # Optional attributes
            author = item.findtext("author") or item.findtext("dc:creator", namespaces=NAMESPACES) or None
            category = item.findtext("category") or None
            
            candidates.append(
                TopicCandidate(
                    id=str(uuid.uuid4()),  # Temporary ID, will be replaced with a stable hash in discovery service
                    title=title.strip(),
                    summary=summary,
                    source=self.source_url,
                    sourceUrl=link.strip(),
                    publishedAt=published_at,
                    discoveredAt=datetime.now(timezone.utc),
                    sourceName=source_name,
                    category=category.strip() if category else None,
                    author=author.strip() if author else None
                )
            )
            
        return candidates

    def _parse_atom(self, root: ET.Element) -> List[TopicCandidate]:
        candidates: List[TopicCandidate] = []
        source_name = root.findtext("atom:title", "Atom Source", namespaces=NAMESPACES).strip()
        
        for entry in root.findall("atom:entry", namespaces=NAMESPACES):
            title = entry.findtext("atom:title", namespaces=NAMESPACES)
            
            # Resolve Atom entry link (alternate)
            link = None
            for l in entry.findall("atom:link", namespaces=NAMESPACES):
                rel = l.attrib.get("rel", "alternate")
                if rel == "alternate":
                    link = l.attrib.get("href")
                    break
            if not link:
                links = entry.findall("atom:link", namespaces=NAMESPACES)
                if links:
                    link = links[0].attrib.get("href")
                    
            if not title or not link:
                logger.warning("Skipping Atom entry due to missing title or link link.")
                continue
                
            summary = entry.findtext("atom:summary", namespaces=NAMESPACES) or ""
            if not summary:
                summary = entry.findtext("atom:content", namespaces=NAMESPACES) or ""
            summary = summary.strip()
            
            pub_date_str = entry.findtext("atom:published", namespaces=NAMESPACES) or entry.findtext("atom:updated", namespaces=NAMESPACES)
            if not pub_date_str:
                logger.warning("Skipping Atom entry due to missing published/updated date.")
                continue
                
            try:
                published_at = parse_datetime(pub_date_str)
            except Exception as e:
                logger.warning(f"Skipping Atom entry due to invalid date '{pub_date_str}': {e}")
                continue
                
            # Optional attributes
            author = None
            author_el = entry.find("atom:author", namespaces=NAMESPACES)
            if author_el is not None:
                author = author_el.findtext("atom:name", namespaces=NAMESPACES)
                
            category = None
            cat_el = entry.find("atom:category", namespaces=NAMESPACES)
            if cat_el is not None:
                category = cat_el.attrib.get("term")
                
            candidates.append(
                TopicCandidate(
                    id=str(uuid.uuid4()),  # Temporary ID, will be replaced with a stable hash in discovery service
                    title=title.strip(),
                    summary=summary,
                    source=self.source_url,
                    sourceUrl=link.strip(),
                    publishedAt=published_at,
                    discoveredAt=datetime.now(timezone.utc),
                    sourceName=source_name,
                    category=category.strip() if category else None,
                    author=author.strip() if author else None
                )
            )
            
        return candidates


class TopicDiscoveryService:
    """
    Service responsible for triggering feed discovery, combining candidates,
    normalizing URLs, generating stable UUIDs, and filtering duplicate topics.
    """
    def __init__(self, feed_urls: Optional[List[str]] = None, timeout: float = 10.0) -> None:
        self.feed_urls = feed_urls if feed_urls is not None else settings.discovery_feeds
        self.timeout = timeout

    async def discover_topics(self, persona: Optional[PersonaProfile] = None) -> List[TopicCandidate]:
        """
        Coordinates discovery run across all sources.
        
        Args:
            persona: An optional PersonaProfile. Can be utilized for future lightweight
                     topic scoping, without conducting editorial judgment.
        """
        logger.info("Topic discovery service run started.")
        candidates: List[TopicCandidate] = []
        seen_urls = set()
        
        headers = {"User-Agent": "AutonomousAICreator/0.1.0"}
        
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout) as client:
            for url in self.feed_urls:
                logger.info(f"Starting discovery on source feed: {url}")
                adapter = RSSAtomAdapter(url)
                try:
                    feed_candidates = await adapter.fetch_and_parse(client)
                    logger.info(f"Successfully processed source '{url}'. Received {len(feed_candidates)} items.")
                    
                    for candidate in feed_candidates:
                        norm_url = normalize_url(candidate.sourceUrl)
                        if not norm_url:
                            logger.debug(f"Removed item with malformed/empty normalized URL: {candidate.sourceUrl}")
                            continue
                            
                        # Update URL to normalized form
                        candidate.sourceUrl = norm_url
                        
                        # Generate a stable UUID5 based on URL namespace to guarantee that
                        # duplicate items across feeds have identical IDs
                        candidate.id = str(uuid.uuid5(uuid.NAMESPACE_URL, norm_url))
                        
                        # Deduplication logic (per-run technical check)
                        if norm_url in seen_urls:
                            logger.debug(f"Deduplicated item with URL: {norm_url}")
                            continue
                            
                        seen_urls.add(norm_url)
                        candidates.append(candidate)
                except Exception as e:
                    # Failure Isolation: a failure from one source should not prevent other sources from being processed
                    logger.error(f"Error occurred during discovery on feed '{url}': {e}", exc_info=True)
                    
        logger.info(
            f"Topic discovery run completed. "
            f"Total items fetched (deduplicated): {len(seen_urls)}. "
            f"Candidates returned: {len(candidates)}."
        )
        return candidates
