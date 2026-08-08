import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.schemas.topic import TopicCandidate
from app.services.topic_discovery import (
    TopicDiscoveryService,
    RSSAtomAdapter,
    normalize_url,
    parse_datetime
)

# --- Sample XML Payloads for Testing ---

VALID_RSS_PAYLOAD = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test RSS Feed</title>
    <link>https://example.com/feed</link>
    <description>Test Description</description>
    <item>
      <title>Test Article 1</title>
      <link>https://example.com/article-1?utm_source=feed</link>
      <description>Summary of article 1</description>
      <pubDate>Fri, 07 Aug 2026 22:48:24 +0000</pubDate>
      <author>Alice</author>
      <category>AI Security</category>
    </item>
  </channel>
</rss>
"""

VALID_ATOM_PAYLOAD = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <link href="https://example.com/atom-feed"/>
  <entry>
    <title>Test Atom 1</title>
    <link rel="alternate" href="https://example.com/atom-1"/>
    <summary>Atom summary content</summary>
    <published>2026-08-04T16:00:00Z</published>
    <author>
      <name>Bob</name>
    </author>
    <category term="MLOps"/>
  </entry>
</feed>
"""

MISSING_TITLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test RSS Feed</title>
    <item>
      <link>https://example.com/article-no-title</link>
      <description>No title here</description>
      <pubDate>Fri, 07 Aug 2026 22:48:24 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

MISSING_LINK_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test RSS Feed</title>
    <item>
      <title>No Link Here</title>
      <description>Summary</description>
      <pubDate>Fri, 07 Aug 2026 22:48:24 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test RSS Feed</title>
    <item>
      <title>Truncated xml
"""

INVALID_PUBDATE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test RSS Feed</title>
    <item>
      <title>Invalid Date Article</title>
      <link>https://example.com/invalid-date</link>
      <pubDate>Not a date at all</pubDate>
    </item>
  </channel>
</rss>
"""

# --- Unit Tests: URL Normalization and Date Parsing ---

def test_url_normalization():
    """
    Test URL normalization helper.
    It should drop trailing slashes, downcase scheme/netloc, and drop utm_* query params.
    """
    assert normalize_url("HTTPS://EXAMPLE.COM/path/") == "https://example.com/path"
    assert normalize_url("https://example.com/path?utm_source=feed&ref=news") == "https://example.com/path?ref=news"
    assert normalize_url("  https://example.com/  ") == "https://example.com/"
    assert normalize_url("invalid-url") == ""
    assert normalize_url("") == ""


def test_datetime_parsing():
    """
    Test datetime parsing helper.
    It should parse RFC 822 and ISO 8601 strings and return UTC timezone-aware datetimes.
    """
    # RFC 822
    dt1 = parse_datetime("Fri, 07 Aug 2026 22:48:24 +0000")
    assert dt1.tzinfo == timezone.utc
    assert dt1.year == 2026
    assert dt1.month == 8
    assert dt1.day == 7
    assert dt1.hour == 22
    
    # RFC 822 with custom timezone offset
    dt2 = parse_datetime("Fri, 07 Aug 2026 22:48:24 -0400")
    assert dt2.tzinfo == timezone.utc
    assert dt2.hour == 2  # 22 - (-4) = 26 -> 02:00 next day
    
    # ISO 8601 with Z
    dt3 = parse_datetime("2026-08-04T16:00:00Z")
    assert dt3.tzinfo == timezone.utc
    assert dt3.day == 4
    assert dt3.hour == 16
    
    # ISO 8601 with offset
    dt4 = parse_datetime("2026-08-04T16:00:00+02:00")
    assert dt4.tzinfo == timezone.utc
    assert dt4.hour == 14  # 16 - 2 = 14
    
    # Invalid date formats
    with pytest.raises(ValueError):
        parse_datetime("invalid-date-string")


# --- Unit Tests: Source Parsing ---

@pytest.mark.anyio
async def test_parse_valid_rss():
    """
    Test parsing a valid RSS payload.
    """
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = VALID_RSS_PAYLOAD.encode("utf-8")
    mock_client.get.return_value = mock_resp

    adapter = RSSAtomAdapter("https://example.com/rss")
    candidates = await adapter.fetch_and_parse(mock_client)
    
    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Test Article 1"
    assert c.sourceUrl == "https://example.com/article-1?utm_source=feed"
    assert c.summary == "Summary of article 1"
    assert c.publishedAt.tzinfo == timezone.utc
    assert c.sourceName == "Test RSS Feed"
    assert c.author == "Alice"
    assert c.category == "AI Security"


@pytest.mark.anyio
async def test_parse_valid_atom():
    """
    Test parsing a valid Atom payload.
    """
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = VALID_ATOM_PAYLOAD.encode("utf-8")
    mock_client.get.return_value = mock_resp

    adapter = RSSAtomAdapter("https://example.com/atom")
    candidates = await adapter.fetch_and_parse(mock_client)
    
    assert len(candidates) == 1
    c = candidates[0]
    assert c.title == "Test Atom 1"
    assert c.sourceUrl == "https://example.com/atom-1"
    assert c.summary == "Atom summary content"
    assert c.publishedAt.tzinfo == timezone.utc
    assert c.sourceName == "Test Atom Feed"
    assert c.author == "Bob"
    assert c.category == "MLOps"


@pytest.mark.anyio
async def test_missing_title_handling():
    """
    Test that items missing a title are skipped.
    """
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = MISSING_TITLE_RSS.encode("utf-8")
    mock_client.get.return_value = mock_resp

    adapter = RSSAtomAdapter("https://example.com/rss")
    candidates = await adapter.fetch_and_parse(mock_client)
    
    assert len(candidates) == 0


@pytest.mark.anyio
async def test_missing_link_handling():
    """
    Test that items missing a link are skipped.
    """
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = MISSING_LINK_RSS.encode("utf-8")
    mock_client.get.return_value = mock_resp

    adapter = RSSAtomAdapter("https://example.com/rss")
    candidates = await adapter.fetch_and_parse(mock_client)
    
    assert len(candidates) == 0


@pytest.mark.anyio
async def test_malformed_xml_handling():
    """
    Test that malformed XML causes a ValueError.
    """
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = MALFORMED_XML.encode("utf-8")
    mock_client.get.return_value = mock_resp

    adapter = RSSAtomAdapter("https://example.com/rss")
    with pytest.raises(ValueError):
        await adapter.fetch_and_parse(mock_client)


@pytest.mark.anyio
async def test_invalid_publication_timestamp():
    """
    Test that items with invalid/unparsable timestamps are skipped.
    """
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = INVALID_PUBDATE_RSS.encode("utf-8")
    mock_client.get.return_value = mock_resp

    adapter = RSSAtomAdapter("https://example.com/rss")
    candidates = await adapter.fetch_and_parse(mock_client)
    
    assert len(candidates) == 0


# --- Unit Tests: Topic Discovery Service ---

@pytest.mark.anyio
async def test_discovery_multiple_sources():
    """
    Test discovery across multiple valid RSS/Atom sources.
    """
    # Mock responses for two feeds
    def mock_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "rss" in url:
            resp.content = VALID_RSS_PAYLOAD.encode("utf-8")
        else:
            resp.content = VALID_ATOM_PAYLOAD.encode("utf-8")
        return resp

    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(side_effect=mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        service = TopicDiscoveryService(
            feed_urls=["https://example.com/rss", "https://example.com/atom"]
        )
        candidates = await service.discover_topics()
        
        # Total candidates discovered: 1 from RSS, 1 from Atom
        assert len(candidates) == 2
        
        # Verify normalization and properties
        rss_cand = next(c for c in candidates if "article-1" in c.sourceUrl)
        atom_cand = next(c for c in candidates if "atom-1" in c.sourceUrl)
        
        # RSS candidate UTM tags stripped
        assert rss_cand.sourceUrl == "https://example.com/article-1"
        assert rss_cand.title == "Test Article 1"
        assert rss_cand.publishedAt.tzinfo == timezone.utc
        
        # Atom candidate attributes correct
        assert atom_cand.sourceUrl == "https://example.com/atom-1"
        assert atom_cand.title == "Test Atom 1"
        
        # Check generated discoveredAt
        assert rss_cand.discoveredAt.tzinfo == timezone.utc
        assert (datetime.now(timezone.utc) - rss_cand.discoveredAt).total_seconds() < 5.0


@pytest.mark.anyio
async def test_discovery_failure_isolation():
    """
    Test that one failing source (timeout, 500 error) does not crash the entire process.
    The service should successfully return candidates from other healthy sources.
    """
    def mock_get(url, *args, **kwargs):
        if "fail" in url:
            raise httpx.ConnectTimeout("Connection timed out")
        resp = MagicMock()
        resp.status_code = 200
        resp.content = VALID_RSS_PAYLOAD.encode("utf-8")
        return resp

    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(side_effect=mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        service = TopicDiscoveryService(
            feed_urls=["https://example.com/fail-feed", "https://example.com/rss"]
        )
        candidates = await service.discover_topics()
        
        # Should gracefully ignore failure-feed and return 1 candidate from rss feed
        assert len(candidates) == 1
        assert candidates[0].title == "Test Article 1"


@pytest.mark.anyio
async def test_discovery_duplicate_urls_deduplication():
    """
    Test that duplicate URLs (e.g. duplicate articles across feeds) are deduplicated
    in the same discovery run.
    """
    # Mock both feeds returning the same article
    def mock_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        # Return exact same article URL but maybe different titles/feeds
        payload = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Feed {url}</title>
            <item>
              <title>Article from {url}</title>
              <link>https://example.com/duplicate-article/</link>
              <pubDate>Fri, 07 Aug 2026 22:48:24 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        resp.content = payload.encode("utf-8")
        return resp

    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(side_effect=mock_get)

    with patch("httpx.AsyncClient", return_value=mock_client):
        service = TopicDiscoveryService(
            feed_urls=["https://example.com/feed-a", "https://example.com/feed-b"]
        )
        candidates = await service.discover_topics()
        
        # Only 1 candidate returned due to URL deduplication (normalized URL is identical)
        assert len(candidates) == 1
        assert candidates[0].sourceUrl == "https://example.com/duplicate-article"


@pytest.mark.anyio
async def test_discovery_empty_source_response():
    """
    Test discovery behavior when a source feed is completely empty (no items).
    """
    empty_feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Empty Feed</title>
        <link>https://example.com/empty</link>
      </channel>
    </rss>
    """
    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = empty_feed.encode("utf-8")
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        service = TopicDiscoveryService(feed_urls=["https://example.com/empty"])
        candidates = await service.discover_topics()
        
        assert len(candidates) == 0


@pytest.mark.anyio
async def test_topic_discovery_returns_expected_model():
    """
    Integration verification: Check that TopicDiscoveryService returns Pydantic models
    of type TopicCandidate with all required properties.
    """
    mock_client = MagicMock()
    mock_client.__aenter__.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = VALID_RSS_PAYLOAD.encode("utf-8")
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        service = TopicDiscoveryService(feed_urls=["https://example.com/rss"])
        candidates = await service.discover_topics()
        
        assert len(candidates) == 1
        candidate = candidates[0]
        
        assert isinstance(candidate, TopicCandidate)
        assert isinstance(candidate.id, str)
        assert len(candidate.id) > 0
        assert candidate.title == "Test Article 1"
        assert candidate.summary == "Summary of article 1"
        assert candidate.source == "https://example.com/rss"
        assert candidate.sourceUrl == "https://example.com/article-1"  # Normalized
        assert isinstance(candidate.publishedAt, datetime)
        assert candidate.publishedAt.tzinfo == timezone.utc
        assert isinstance(candidate.discoveredAt, datetime)
        assert candidate.discoveredAt.tzinfo == timezone.utc
