# Autonomous AI Creator

An autonomous AI and technology agent/persona designed to independently discover live tech topics, evaluate their suitability, write high-quality posts, and manage publishing schedules over a 48-hour period.

This project is built for a vibe-coding hackathon.

---

## Architecture Overview

The system is designed with a highly modular, decoupled architecture:

```text
Live Sources (News, Tech Blogs, RSS, Twitter)
     │
     ▼
Topic Discovery (Scrapes and aggregates live information)
     │
     ▼
Candidate Topics
     │
     ▼
Editorial Judge (Scores and filters topics based on value)
     │
     ▼
Persona Writer (Generates high-quality posts with consistent voice/persona)
     │
     ▼
Memory / Breeth (Checks repetition, matches context, stores published history)
     │
     ▼
Publishing Scheduler (Autonomously queues and posts over ~48h)
     │
     ▼
Feed API (Exposes GET /api/agent/feed for evaluators)
```

### Milestone Progress
* **Milestone 1**: Established the base FastAPI structure, settings validation, and base memory interface contracts.
* **Milestone 2**: Implemented the core hackathon API contract (agent initialization, in-memory repository, slim FastAPI routers).
* **Milestone 3**: Implemented the **Persona Engine** to construct stable, coherent technology/AI identities from a name and domain.
* **Milestone 4**: Implemented the **Topic Discovery Service** with unified RSS/Atom source adapters, timezone/timestamp normalization, URL deduplication, and failure isolation.
* **Milestone 5**: Implemented the **Editorial Judgment Engine** featuring deterministic heuristic scoring, automated rejection rules, and LLM mocked clients.
* **Milestone 6**: Implemented the **Persistent Agent Memory** layer with agent-scoped local JSON storage and token keyword overlap checks.

---

## Persona Engine

The **Persona Engine** is a core reusable subsystem introduced in Milestone 3. It transforms the basic configuration provided during agent initialization (`name` and `domain`) into a stable, rich, technology-focused persona profile.

### Why Persona Consistency Matters
An AI content creator needs a stable voice and defined boundary of interest. If the persona changes between API calls or regenerates randomly, the agent's identity breaks, resulting in disjointed editorial judgment and inconsistent post generation. 

By generating the profile *exactly once* during agent initialization and persisting it in the repository, the engine guarantees that subsequent reads (e.g. status requests or feed queries) interact with the exact same stable persona.

### Persona Profile Structure
The profile is represented by the [PersonaProfile](file:///c:/Users/mohdh/Desktop/Projects/Autonomous%20AI%20Creator/app/schemas/persona.py) Pydantic model and includes:
* **Identity**: A short description of the AI identity (e.g., AI Security researcher, ML engineer).
* **Mission**: A concise explanation of what the persona analyzes or explains.
* **Core Interests**: A list of specific technology sub-fields (e.g., MLOps, model vulnerabilities).
* **Editorial Principles**: Stable rules governing what is worth discussing (e.g., prefer evidence over hype, explain practical implications).
* **Writing Style**: Tone and stylistic markers (e.g., concise, clear, technically grounded).
* **Audience**: Target readership.
* **Topics to Avoid**: Categories to filter out (e.g., political content unrelated to AI/tech, unsupported rumors).

### Information Flow
```text
  [POST /api/agent/init]
           │
           ▼
    [AgentService] ────(initializes)────► [PersonaService]
           │                                      │
           │                                 (generates)
           │                                      ▼
           │                             [PersonaProfile]
           │                                      │
           ▼                                      │
    [InMemoryAgentRepository] ◄──(persists dict)──┘
```

When an agent is initialized:
1. The client sends the name and domain via `POST /api/agent/init`.
2. `AgentService` validates inputs and delegates generation to `PersonaService`.
3. `PersonaService` deterministically generates a custom `PersonaProfile` (either from rich predefined technology templates or via a dynamic fallback generator for custom domains).
4. The generated profile is persisted inside the `InMemoryAgentRepository` under the agent's unique UUID.
5. All future modules (such as the future Editorial Judge and Writer) query the repository to consume the stable, structured profile rules.

---

## Topic Discovery Service

The **Topic Discovery Service** is a core reusable component introduced in Milestone 4. It enables the agent to independently aggregate and normalize tech and AI developments from live information sources.

### Discovery vs. Editorial Judgment
It is critical to distinguish between these two layers:
* **Topic Discovery**: Responsible only for answering the question *"What potentially relevant developments are available right now?"* It retrieves, parses, normalizes, and technically deduplicates topics.
* **Editorial Judgment**: (Planned for a future milestone) Evaluates the suitability of discovered topics against the stable persona rules (e.g. principles, interests, topics to avoid). 

The Topic Discovery Service does **NOT** make any publishing or scheduling decisions.

### Architecture and Data Flow
```text
  Configured RSS/Atom Feeds (TechCrunch AI, NVIDIA Developer, AWS ML, MIT Tech Review)
                                  │
                                  ▼
                   [TopicDiscoveryService.discover_topics]
                                  │
                     (Iterates through configured feeds)
                                  ▼
                       [RSSAtomAdapter (Unified)]
                     (Fetches XML, detects feed format)
                                  │
                           (Parses items)
                                  ▼
                      [Normalization & Validation]
                 - Converts publication time to UTC
                 - Strips query trackers (utm_*) from URLs
                 - Skips malformed items (missing title/URL)
                                  │
                                  ▼
                     [Technical Deduplication]
                 - Generates UUID5 based on normalized URL
                 - Removes duplicates found in the same run
                                  │
                                  ▼
                           [TopicCandidates]
```

### Configured Sources
We start with four highly reputable technology and AI blogs, configured dynamically via environment variables (`DISCOVERY_FEEDS`) with robust fallback defaults:
1. **TechCrunch AI category**: Tracks high-level technology industry news and venture activity.
2. **NVIDIA Developer Blog**: Captures technical updates, hardware accelerators, and frameworks.
3. **AWS Machine Learning Blog**: Covers cloud infrastructure and enterprise deployment patterns.
4. **MIT Technology Review (AI Feed)**: Offers strong editorial analysis, policy, and research developments.

### Error Handling & Failure Isolation
To ensure high availability, the discovery service isolates source failures. If one feed experiences a connection timeout, DNS failure, or returns a 500 error, it is logged, but the discovery process **continues** processing candidates from all other healthy feeds.

---

## Editorial Judgment Engine

The **Editorial Judgment Engine** is a core reusable subsystem introduced in Milestone 5. It evaluates candidate topics against the agent's persistent `PersonaProfile` (interests, domain, principles, avoided topics) and decides whether to accept or reject them.

### Discovery vs. Editorial Judgment
* **Topic Discovery**: Answers the question *"What is happening in the industry?"* and collects all candidates.
* **Editorial Judgment**: Answers the question *"Is this candidate worth publishing for this specific persona?"* and filters candidates.

### Scoring Criteria and Methodology
A candidate is evaluated on a `0.0` to `10.0` scale using five criteria:
1. **Relevance / Persona Fit** (`relevanceScore`): Determines if candidate matches `core_interests` (adds 2.5 per match). Set to `0.0` immediately if it matches `topics_to_avoid`. Minimum of `5.0` required for acceptance.
2. **Freshness** (`freshnessScore`): Penalizes old content. Published within 24 hours = `10.0`, <= 3 days = `8.0`, <= 7 days = `5.0`, stale (> 7 days) = `2.0`. Minimum of `5.0` required for acceptance.
3. **Significance** (`significanceScore`): Evaluates technological impact. Technical keywords (e.g. breakthrough, zero-day) increase score; promotional keywords (e.g. coupon, discount, register) reduce score.
4. **Source Credibility** (`sourceQualityScore`): Rates source reputability. Official tech dev blogs (NVIDIA/AWS) = `9.0`, major tech publications = `8.0`, others = `6.0`.
5. **Editorial Alignment** (`personaFitScore`): Overall fit for target audience and style guidelines. Penalizes generic hype terms (e.g. game changer, mind-blowing) by `-2.0` to filter out clickbait.

The overall score is computed as:
$$\text{Score} = \frac{\text{Relevance} + \text{Significance} + \text{Freshness} + \text{Source Quality} + \text{Persona Fit}}{5}$$

A topic candidate is only accepted if:
$$\text{Score} \ge \text{Threshold (6.0)} \quad \text{AND} \quad \text{Relevance} \ge 5.0 \quad \text{AND} \quad \text{Freshness} \ge 5.0$$

### Decision Explanation
Every decision contains explainable, context-specific reasons:
* **ACCEPT**: Explains which core interests matched and why the content is timely/significant.
* **REJECT**: Explains why it failed (low relevance, stale content, clickbait warning, or matches avoided topics like politics).

### Dual Engine Abstraction
* **Deterministic Engine**: Runs rule-based scoring matching interest keywords. Fast, free of external dependencies, and suitable for tests.
* **LLM Engine**: Delegates structured JSON evaluation to `BaseLLMClient`. Validates schema structure. If LLM timeouts or malformed outputs occur, it fails safely with an explicit `REJECT` decision and 0.0 score.

---

## Persistent Agent Memory

The **Persistent Agent Memory** layer is a core subsystem introduced in Milestone 6. It enables each autonomous agent to remember previously considered topics, published posts, and editorial decisions across different execution runs, preventing duplication and ensuring continuity.

### Visual Architecture & Progression

```text
Foundation ──► Agent API ──► Persona ──► Topic Discovery ──► Editorial Judgment ──► Persistent Memory (CURRENT)
```

```text
                 Agent
                   │
                   ▼
              Memory Service
                   │
                   ▼
             Memory Repository
                   │
                   ▼
          Persistent Local Storage (data/memory/<agent-id>.json)
```

### Decoupled Storage Backend
The repository follows a clean abstraction interface (`BaseMemory`) and is implemented as a local file-based repository `LocalFileMemoryRepository`. The rest of the application interacts with memories solely through the `MemoryService`, leaving the underlying storage implementation easily replaceable (e.g. migrating to an external provider like Breeth in later stages requires zero core logic rewrites).

### Memory Schema & Categories
Memory is strictly isolated per `agentId` and serialized into a structured `AgentMemory` schema mapping:
* `memoryId`: unique entry UUID.
* `agentId`: unique owner agent UUID.
* `type`: Literal value representing:
  * `PUBLISHED_POST`: Verbatim text and ID of generated posts.
  * `PUBLISHED_TOPIC`: Title, sources, and timestamps of covered topics.
  * `EDITORIAL_DECISION`: Details of previous ACCEPT/REJECT runs.
* `createdAt`: Timezone-aware UTC timestamp.
* `metadata`: Contextual keys (e.g. `topicId`, `sourceUrl`, `editorialDecision`, `publishedAt`).

### Token Overlap Duplicate Detection
To support future autonomous flows and prevent duplicate post publishing, the memory service provides `is_repetitive(agent_id, content)` capability:
1. It splits check content and stored memory content into lowercased tokens.
2. It filters out noise/stop-words (e.g. "the", "and", "in", "new", "discovered").
3. It computes the keyword overlap ratio between the check tokens and stored tokens. If the overlap is `>= 60%`, the topic is recognized as repetitive, preventing the agent from publishing identical stories with slightly different headlines.

---

## Project Structure

```text
autonomous-ai-creator/
├── .env.example            # Template for environmental configuration
├── .gitignore              # Standard ignore configurations
├── README.md               # Documentation
├── requirements.txt        # Pinned project dependencies
├── app/                    # Primary application package
│   ├── __init__.py
│   ├── main.py             # App initialization and startup
│   ├── api/                # Routing and endpoints
│   │   ├── __init__.py
│   │   ├── router.py       # Centrally maps all routing prefixes
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── agent.py    # POST /api/agent/init & GET /api/agent/feed
│   │       └── health.py   # GET /health check endpoint
│   ├── core/               # Configuration settings and security
│   │   ├── __init__.py
│   │   └── config.py
│   ├── repositories/       # In-memory storage/persistence implementations
│   │   ├── __init__.py
│   │   └── agent.py
│   ├── schemas/            # Data validation schemas (Pydantic models)
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── editorial.py    # EditorialDecision schemas
│   │   ├── memory.py       # AgentMemory schemas
│   │   ├── persona.py
│   │   └── topic.py
│   └── services/           # Business logic layer
│       ├── __init__.py
│       ├── agent.py        # Coordinates UUID creation and initialization flow
│       ├── editorial.py    # EditorialJudgmentService logic
│       ├── llm.py          # BaseLLMClient and MockLLMClient providers
│       ├── memory.py       # BaseMemory contract and LocalFileMemoryRepository
│       ├── persona.py      # Reusable Persona Generator Engine
│       └── topic_discovery.py # TopicDiscoveryService and RSS/Atom adapters
├── docs/                   # Project logs and documentation
│   └── AI_USAGE_LOG.md     # Chronological log of agent development
└── tests/                  # Automated test suite
    ├── __init__.py
    ├── conftest.py
    ├── test_agent.py       # Checks agent init, validation, and feed APIs
    ├── test_editorial.py   # Editorial Judgment unit and integration tests
    ├── test_health.py      # Checks base service health
    ├── test_memory.py      # Persistent agent memory tests
    └── test_topic_discovery.py # Topic Discovery parser and flow tests
```

---

## API Endpoints

### 1. Health Check
* **Route**: `GET /health`
* **Response**:
  ```json
  {
    "status": "healthy",
    "app_name": "Autonomous AI Creator",
    "app_env": "dev"
  }
  ```

### 2. Initialize Agent
* **Route**: `POST /api/agent/init`
* **Headers**: `Content-Type: application/json`
* **Request Body**:
  ```json
  {
    "persona": {
      "name": "Ada",
      "domain": "AI Security"
    }
  }
  ```
* **Response Body**:
  ```json
  {
    "agentId": "d20fa6c1-7bc4-4582-a108-ddad5839be57"
  }
  ```
* **Validation**:
  - `persona.name` must be a non-empty string.
  - `persona.domain` must be a non-empty string.
  - Whitespace-only values will fail validation with a `422 Unprocessable Entity` status code.

### 3. Agent Feed
* **Route**: `GET /api/agent/feed?agentId=<id>`
* **Response Body (Success)**:
  ```json
  {
    "posts": []
  }
  ```
* **Response Body (Non-Existent Agent)**:
  - If the `agentId` does not match an initialized agent, returns `404 Not Found`:
  ```json
  {
    "detail": "Agent with ID 'nonexistent-id' does not exist."
  }
  ```

---

## Setup & Local Installation

### Prerequisites
* Python 3.14.6 (or Python 3.10+)

### 1. Initialize Virtual Environment
Create and activate your Python virtual environment:

```bash
# Create
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Linux / macOS)
source .venv/bin/activate
```

### 2. Install Dependencies
Install production and testing dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the configuration template:

```bash
cp .env.example .env
```

Review `.env` settings to match your local environment requirements.

---

## Running the Application

Start the local development server:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## Running Automated Tests

Run the test suite via `pytest`:

```bash
pytest
```

---

## Current Limitations & Unimplemented Features
The following features are **NOT** implemented yet:
- **LLM Persona Writing**: No LLM text generation or prompt orchestration logic.
- **Autonomous Scheduler**: No loops running over 48 hours yet.
- **External Memory Service**: External cloud-based memory layers (like Breeth) are not integrated yet.

---

## Milestone Roadmaps & Future Integrations

- [x] **Milestone 1**: Project foundation, configuration management, memory abstraction interface, and health verification.
- [x] **Milestone 2**: API Contract & Agent Initialization State (In-Memory).
- [x] **Milestone 3**: Persona Engine implementation for stable AI technology identities.
- [x] **Milestone 4**: Live AI Topic Discovery layer with unified RSS/Atom adapters.
- [x] **Milestone 5**: Editorial Judgment Engine for persona-aware filter control.
- [x] **Milestone 6**: Persistent Agent Memory layer with local JSON file repositories and repetition checks.
- [ ] **Milestone 7**: Memory integration via external memory provider Breeth.
- [ ] **Milestone 8**: LLM-powered persona-based article generation (Writer).
- [ ] **Milestone 9**: Scheduler for autonomous loop execution, full 48-hour loop operation.
