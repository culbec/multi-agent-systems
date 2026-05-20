# multi-agent-systems

The project underlying this Git repository is designed to highlight cooperative course work on **Multi-Agent Systems**.

The "learning curve" is split in two separate components, each of them presenting usage of (intelligent) agents to solve a series of tasks.

A [Project Draft](./docs/draft/MAS_Project_Draft_Report_v2.docx) is available for indicating setup steps, core concepts, and details around the MAS components developed under this repository.

## Table Of Contents

- [Overview](#overview)
  - [SP1 - Open-Source Framework](#sp1---open-source-framework)
  - [SP2 - Scratch Framework / DAI Technique](#sp2---scratch-framework--dai-technique)
- [SP1 Specification](#sp1-specification)
  - [Architecture](#architecture)
  - [Agent Roles](#agent-roles)
  - [Communication](#communication)
  - [Running SP1](#running-sp1)
    - [Prerequisites](#prerequisites)
    - [Starting the SPADE Server](#starting-the-spade-server)
    - [CLI Mode](#cli-mode)
    - [Gradio Mode](#gradio-mode)
  - [Configuration](#configuration)
  - [LLM Customisation](#llm-customisation)
- [Setup](#setup)

## Overview

### SP1 - Open-Source Framework

SP1 implements a **Multi-Agent News Aggregation System** using the [SPADE](https://spadeagents.eu) framework. It continuously collects, filters, unifies, ranks, summarises, and presents news articles from multiple public RSS feeds in response to user-declared interests or specific queries.

The system addresses key challenges inherent to news aggregation:

- **Source heterogeneity** — Multiple providers serve news with different formats and update frequencies.
- **Redundancy** — The same topic is reported by many sources, producing near-duplicate articles.
- **Relevance** — Not all collected articles are equally relevant to the user's desires.
- **Credibility** — Sources vary in reliability; the system assesses trustworthiness rather than treating all sources as equivalent.
- **Information overload** — Concise LLM-generated summaries allow the user to understand each provider's point of view.
- **Timeliness** — Supports both on-demand queries and periodic standing subscriptions with autonomous background refreshes.
- **Personalisation** — Adapts to the user's preferences during interaction by learning which sources and topics consistently produce relevant results.

The architecture follows a **hub-and-spoke** topology with a shared **blackboard** for coordination and **FIPA ACL** messages for targeted inter-agent communication.

### SP2 - Scratch Framework / DAI Technique

SP2 implements the **Intelligent Disaster Grid Response System** from scratch in Python. It simulates a distributed grid of emergency situations where autonomous **Rescue Agents** must navigate dynamically generated, obstacle-strewn terrain to respond to active distress signals, coordinated by a **Coordinator Agent** and orchestrated by an **Environment Agent**.

Key Technical Highlights:
- **Scratch-built Agent Architecture** — No heavyweight third-party agent framework; agents communicate asynchronously using direct, in-process, lock-free double-buffered message queues (`collections.deque`).
- **Distributed Learning Pathfinding (LRTA\*)** — Agents run the *Learning Real-Time A\** algorithm, performing asynchronous dynamic programming updates to build a target-indexed heuristic table (`(current_cell, target_cell) -> cost-to-go`) on the fly, guaranteeing h-monotonicity (values never decrease) and preventing local minimum traps.
- **P2P Collision Avoidance & Reservations** — Agents coordinate cellular movements using a peer-to-peer reservation protocol with deterministic tie-breaking (lower agent IDs wait).
- **Dynamic Distress & Distress Cycles** — Custom Poisson signal injection scheduled dynamically; previously resolved cells can be hit by distress signals again, automatically recycling pathfinding priorities.
- **Cooperative Base-Returning** — Idle or free rescue agents do not act as roadblocks; instead, they dynamically generate LRTA\* paths back to the base. They act as dynamic objects that can yield to active rescuers and leave trails, leaving paths open.
- **Rich Visual HUD & Diagnostics Dashboard** — A real-time Pygame GUI featuring togglable overlays for learning heatmaps (`[H]`), agent movement trails (`[T]`), yellow cellular reservations (`[R]`), message logs (`[M]`), interactive playback scrubbing, dynamic agent detail inspect cards, and complete config hot-reloading.

---

## SP1 Specification

### Architecture

SP1 is a society of cooperating agents rather than a centrally orchestrated pipeline. Each agent owns its decisions within its scope, perceives the environment through the blackboard, and acts autonomously.

```
+-----------+      +-----------+      +-----------+
|  Crawler  |      |  Crawler  |  ... |  Crawler  |
+-----+-----+      +-----+-----+      +-----+-----+
      |                  |                  |
      +------------------+------------------+
                         |
                    +----v----+  Candidate Pool
                    | Blackboard |
                    +----+----+
      +------------------+------------------+
      |                  |                  |
+-----v-----+      +-----v-----+      +-----v-----+
| Relevance |      | Credibility|      |  Novelty  |
|  Analyst  |      |  Analyst   |      |  Analyst  |
+-----+-----+      +-----+-----+      +-----+-----+
      |                  |                  |
      +------------------+------------------+
                         |
                    +----v----+  Score Board
                    | Editor  |
                    +----+----+
                         |
                    +----v----+
                    |  Clerk  |  <->  User (CLI / Gradio)
                    +---------+
```

### Agent Roles


| Agent                       | Role                   | Behaviour                                                                                                                                                                                                                                                                                                 |
| --------------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CrawlerAgent**            | Field reporter         | One instance per configured RSS source. Periodically polls the feed, extracts and normalises article entries, deduplicates them, and deposits them into the shared candidate pool. Maintains a source-health flag.                                                                                        |
| **RelevanceAnalystAgent**   | Relevance specialist   | Scores how well an article matches a filter's keywords and categories using keyword-frequency matching blended with per-user preference weights.                                                                                                                                                          |
| **CredibilityAnalystAgent** | Credibility specialist | Scores article trustworthiness combining source reputation, cross-source corroboration, and light content heuristics (length, quoted sources, clickbait penalty).                                                                                                                                         |
| **NoveltyAnalystAgent**     | Novelty specialist     | Scores how different an article is from already-delivered content and from other articles in the pool, penalising redundancy and near-duplicates.                                                                                                                                                         |
| **EditorAgent**             | Managing editor        | Aggregates the independent judgments of the three Analysts using a configurable weighting policy. Composes diverse bundles respecting delivery preferences. Generates per-article summaries via an LLM (Ollama). Autonomously decides when standing-filter readiness criteria are met and pushes bundles. |
| **ClerkAgent**              | Counter staff          | The sole user-facing agent. Receives filter declarations, validates them, registers them on the blackboard, and notifies the Editor. Receives composed bundles and delivers them to the user. Queues deliveries for offline users. Solicits feedback and proactively suggests filter adjustments.         |


### Communication

Agents coordinate through two complementary channels:

1. **Blackboard** — A shared JSON-persisted in-memory structure holding:
  - Candidate pool (articles from Crawlers)
  - Score board (dimension-specific score vectors from Analysts)
  - Filter registry (active one-off and standing filters)
  - User profiles (preferences, standing filters, delivery history)
  - Source-reputation table (updated by Credibility Analyst)
  - Pending-delivery queue (for offline users)
2. **FIPA ACL Messages** — Targeted events over SPADE's XMPP layer:
  - `Clerk INFORM Editor` — new/edited filter
  - `Clerk REQUEST Editor` — one-off bundle request
  - `Editor INFORM Clerk` — composed bundle delivery
  - `Editor FAILURE Clerk` — inability to compose bundle
  - `Crawler INFORM Editor` — source-health update

### Running SP1

#### Prerequisites

1. Install `uv`, `ruff`, and `ty` from [astral.sh](https://astral.sh/).
2. Install [pyenv](https://github.com/pyenv/pyenv) to manage Python versions. This project uses **Python 3.12.13**.
3. Install and start [Ollama](https://ollama.com) locally (or point to a remote instance via `.env`).
4. Start a local SPADE XMPP server.

```bash
# Sync dependencies
uv sync --frozen
```

#### Starting the SPADE Server

```bash
# Using the provided script
./src/sp1/scripts/start_spade.sh

# Or directly
uv run spade run --db data/spade/server.db
```

#### CLI Mode

Run the full MAS from the terminal:

```bash
# Using the convenience script
./src/sp1/scripts/run_sp1.sh

# Or directly
PYTHONPATH=src uv run python -m sp1.cli run
```

The CLI will spawn all agents (Crawlers, Analysts, Editor, Clerk), keep the blackboard persisted to `data/blackboard.json`, and shut down gracefully on `Ctrl+C`.

Show current configuration:

```bash
PYTHONPATH=src uv run python -m sp1.cli config
```

#### Gradio Mode

Run the web-based UI for interactive filter configuration, chat-based querying, blackboard inspection, and source-health monitoring:

```bash
PYTHONPATH=src uv run python -m sp1.ui.gradio_app
```

Then open your browser at `http://localhost:7860`.

The UI provides:

- **Chat window** — Interact with the Clerk agent using commands like `/filter AI, technology`, `/standing climate`, `/feedback article_id true`, `/help`.
- **News Feed** — Browse all articles in the candidate pool, even without filters.
- **Filters panel** — View and manage active filters.
- **Blackboard inspector** — View the score board with analyst dimension scores.
- **Source health dashboard** — Real-time status of all RSS sources.
- **Configuration** — View current LLM model and system status.

Unlike Streamlit, Gradio uses a persistent server that does not re-execute on every interaction, making it compatible with long-lived SPADE agents.

### Configuration

Create a `src/sp1/.env` file (see `.env.example`):

```bash
SPADE_SERVER=localhost
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_SUMMARIZATION_MODEL=mistral
OLLAMA_TEMPERATURE=0.3
OLLAMA_MAX_TOKENS=512
OLLAMA_FALLBACK_TO_EXTRACT=true
RSS_FEEDS_PATH=./src/sp1/data/rss.example.jsonc
BLACKBOARD_PATH=data/blackboard.json
```

### LLM Customisation

The Editor agent uses Ollama for per-article summarisation. You can customise the model via environment variables:


| Variable                     | Default                     | Description                                      |
| ---------------------------- | --------------------------- | ------------------------------------------------ |
| `OLLAMA_SUMMARIZATION_MODEL` | `mistral`                   | Model tag for summarisation                      |
| `OLLAMA_BASE_URL`            | `http://localhost:11434/v1` | Ollama API endpoint                              |
| `OLLAMA_TEMPERATURE`         | `0.3`                       | Sampling temperature                             |
| `OLLAMA_MAX_TOKENS`          | `512`                       | Max tokens per summary                           |
| `OLLAMA_FALLBACK_TO_EXTRACT` | `true`                      | Fallback to article `summary` field if LLM fails |


**Recommended models:**

- `mistral` (7B) — Fast, high-quality summaries (default)
- `llama3.2` (3B) — Very fast, decent quality for short summaries
- `qwen2.5:7b` — Excellent instruction following and multilingual

Change at runtime:

```bash
OLLAMA_SUMMARIZATION_MODEL=llama3.2 PYTHONPATH=src uv run python -m sp1.cli run
```

---

## Setup

Install `uv`, `ruff`, and `ty` from [astral.sh](https://astral.sh/). These are tools for Python package management, formatting, and linting + typechecking.

I recommend you to use [pyenv](https://github.com/pyenv/pyenv) to manage your Python versions. This project uses **Python 3.12.13**.

To initialize the virtual environment run the following command.

```bash
# Syncs with pyproject.toml and creates a virtual environment
# Remove '--frozen' if you want to update the packages
uv sync --frozen 
```

You can run the tutorial file located in `src/tutorial` by using the following command.
That script launches a configurable number of agents and spins up a local XMPP server for them to communicate.
They have a one-shot behavior and exit immediately after completing their task.

```bash
uv run ./src/tutorial/hello_agent.py
```

Use the following commands to access information on how to use `ruff` and `ty` for formatting and linting/typechecking.
`ruff` rules are located in [.ruff.toml](./.ruff.toml).

```bash
ruff --help
ty --help
```

---

## SP2 Specification

### Running SP2 (Intelligent Disaster Response)

SP2 is a fully self-contained multi-agent simulation framework that runs instantly out of the box with zero third-party dependencies besides standard virtual environment tools.

#### Interactive GUI Mode (Default with Hot-Reloading)
Launches the Pygame visual playback interface, metrics HUD, and side panel:

```bash
# Simply run the main entry point
PYTHONPATH=. uv run src/sp2/main.py
```

*Note: By default, this loads the config parameters inside `src/sp2/data/config.json`. If you keep the app running in one corner of your screen, open `src/sp2/data/config.json` in your IDE, change any parameter (e.g. `agent_count`, `rows` or `cols`), and hit save — the Pygame window will instantly **hot-reload and update the UI in real-time!***

To run pointing to a custom configuration file of your choice:
```bash
PYTHONPATH=. uv run src/sp2/main.py --config src/sp2/data/config.example.json
```

#### Headless CLI Mode (Command-Line)
Runs the simulation to completion immediately at maximum speed, prints an extensive analytical statistics summary of the results, and writes the frame replay to disk:

```bash
PYTHONPATH=. uv run src/sp2/main.py --headless
```

To customize parameters directly via the CLI in headless mode:
```bash
PYTHONPATH=. uv run src/sp2/main.py --headless --rows 20 --cols 20 --agents 5 --signals 8 --density 0.15 --output src/sp2/data/my_replay.json
```

#### Executing the Test Suite
We maintain a robust suite of unit and integration tests covering pathfinding, messaging, simulation states, and metrics collections:

```bash
PYTHONPATH=. uv run pytest src/sp2/tests/
```

### Core Architecture

The system coordinates the life cycle of emergency distress signals and rescuer routing through three key cooperating roles:

```
                  +-----------------------------------+
                  |        CoordinatorAgent           |
                  |  - Assigns pending signals        |
                  |  - Tracks idle rescuers           |
                  +-----------------+-----------------+
                                    |
            Assign / Free Message   |   Assign / Free Message
                        +-----------+-----------+
                        |                       |
                  +-----v-----+           +-----v-----+
                  |RescueAgent|           |RescueAgent|  ...
                  | (Rescue)  |           | (Rescue)  |
                  +-----+-----+           +-----+-----+
                        |                       |
                        +-----------+-----------+
                                    |
         Neighbor Query / Move /    |   P2P Reservation Message
         Heuristic Update Message   |   (Lower Agent ID waits)
                        +-----------+-----------+
                        |                       |
                  +-----v-----+           +-----v-----+
                  |   Grid    | <-------  |Environment|
                  | (Domain)  |           |  (State)  |
                  +-----------+           +-----------+
```

1. **Environment Agent (`EnvironmentAgent`)**: Orchestrates the physical reality of the grid, manages cell properties, maintains the shared target-indexed heuristic table, and acts as the structural state-tracker for all agents and dynamic signals.
2. **Coordinator Agent (`CoordinatorAgent`)**: Performs nearest-first optimal task distribution. It processes distress requests, manages active rescuer assignments, tracks idle agents, and gracefully fires simulation termination protocols once all situations are resolved.
3. **Rescue Agent (`RescueAgent`)**: Operates independently. It communicates with the environment to fetch neighbor costs, updates target-specific local cost-to-go matrices using the LRTA\* step, executes peer-to-peer cellular conflict negotiations, and safely navigates back to base when idle to keep traffic paths unblocked.


