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
* **Milestone 3**: Implemented the **Persona Engine** to construct stable, coherent technology/AI identities from a name and domain, ensuring identity consistency.

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
│   ├── repositories/       # State tracking and repositories layer
│   │   ├── __init__.py
│   │   └── agent.py        # BaseAgentRepository & InMemoryAgentRepository
│   ├── schemas/            # Data verification schemas
│   │   ├── __init__.py
│   │   └── agent.py        # Pydantic schemas (Persona, Agent requests/responses)
│   └── services/           # Decoupled system components (Memory, Discovery, LLM)
│       ├── __init__.py
│       └── memory.py       # BaseMemory persistent memory interface
├── docs/                   # Project logs and documentation
│   └── AI_USAGE_LOG.md     # Chronological log of agent development
└── tests/                  # Automated test suite
    ├── __init__.py
    ├── conftest.py
    ├── test_agent.py       # Checks agent init, validation, and feed APIs
    └── test_health.py      # Checks base service health
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
- **Live Topic Discovery**: Scrapers and news sources have not been added.
- **LLM Persona Writing**: No LLM text generation or prompt orchestration logic.
- **Editorial Scoring**: No scoring evaluations to filter out low-value news.
- **Autonomous Scheduler**: No loops running over 48 hours yet.
- **Persistent Publishing Memory**: The system currently uses an ephemeral `InMemoryAgentRepository`. Persistent memory (Breeth) will be integrated in later milestones.

---

## Milestone Roadmaps & Future Integrations

- [x] **Milestone 1**: Project foundation, configuration management, memory abstraction interface, and health verification.
- [x] **Milestone 2**: API Contract & Agent Initialization State (In-Memory).
- [x] **Milestone 3**: Persona Engine implementation for stable AI technology identities.
- [ ] **Milestone 4**: Memory integration via the **Breeth** persistent memory layer.
- [ ] **Milestone 5**: Live topic discovery, RSS scraping, and news sources integration.
- [ ] **Milestone 6**: LLM-powered editorial scoring and persona-based article generation (Editorial Judge & Writer).
- [ ] **Milestone 7**: Scheduler for autonomous loop execution, full 48-hour loop operation.
