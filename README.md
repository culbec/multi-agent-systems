# multi-agent-systems

The project underlying this Git repository is designed to highlight cooperative course work on **Multi-Agent Systems**.

The "learning curve" is split in two separate components, each of them presenting usage of (intelligent) agents to solve a series of tasks.

A [Project Draft](./docs/draft/MAS_Project_Draft_Report_v2.docx) is available for indicating setup steps, core concepts, and details around the MAS components developed under this repository.

## Table Of Contents

- [Overview](#overview)
  - [SP1 - Open-Source Framework](#sp1---open-source-framework)
  - [SP2 - Scratch Framework / DAI Technique](#sp2---scratch-framework--dai-technique)
- [Setup](#setup)

## Overview

### SP1 - Open-Source Framework

This project uses [SPADE](https://spadeagents.eu) to create a virtual _newspaper kiosk_. It leverages the framework's built-in FIPA ACL communication design and XMPP communication protocol to create a **hub-and-spoke** topology used to query news from multiple public RSS feeds to serve the user's needs.

#### Starting SPADE

You can start the SPADE server by using the [start_spade.sh](./src/sp1/scripts/start_spade.sh) script. It allows specification of the database path and creation of intermediary paths if the database directory does not exist.

#### Starting the Application

You can test the Crawler agent for instance by using the following command:

```bash
cd ...repo_root...
PYTHONPATH=src uv run python -m sp1.agents.crawler.crawler
```

Every agent has a main entrypoint to be able to test them according to their capabilities. The Crawler agent will run periodically and update a `results.json` file with the scraped article results from a collection of predefined RSS/Atom feeds.

**TODO**: it should spin up [NiceGUI](https://github.com/zauberzeug/nicegui) or [StreamLit](https://streamlit.io/) interface because they are lightweight and easy to use.

### SP2 - Scratch Framework / DAI Technique

**TODO: Disaster Grid**

## Setup

Install `uv`, `ruff`, and `ty` from [astral.sh](https://astral.sh/). These are tools for Python package management, formatting, and linting + typechecking.

I recommend you to use [pyenv](https://github.com/pyenv/pyenv) to manage your Python versions. This project uses **Python 3.12.10**.

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
