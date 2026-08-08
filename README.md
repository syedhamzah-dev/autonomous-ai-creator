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
* **Milestone 2**: Implemented the core hackathon API contract. This includes:
  - Agent initialization schema validations.
  - An in-memory repository layer for temporary agent state tracking.
  - Slim API handlers implementing `POST /api/agent/init` and `GET /api/agent/feed`.

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
- [ ] **Milestone 3**: Memory integration via the **Breeth** persistent memory layer.
- [ ] **Milestone 4**: LLM-powered editorial scoring and persona-based article generation.
- [ ] **Milestone 5**: Topic discovery, RSS scraping, and news sources integration.
- [ ] **Milestone 6**: Scheduler for autonomous loop execution, full 48-hour loop operation.
