# Problem Definition

This document provides a specification of the application provided for SP1 and a high-level view of the multi-agent system to solve it.

## Definition

The goal of SP1 is to develop an automated Multi-Agent News Aggregation System that continuously collects, filters, unifies, ranks, summarizes, and presents news articles from multiple [public RSS source](https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/refs/heads/master/README.md) in response to user-declared interests or specific queries. The system should relieve the user from the burden of manual aggregation by providing a single, curated, and readable output tailored to their stated interests.

As each process comes with specific challenges, this system must address the following ones:

- Source heterogeneity: Multiple providers serve news with different formats and update frequencies.
- Redundancy: The same topic is typically reported by many sources, depending on the importance of that specific topic; this produces near-duplicate articles that add noise to the result set.
- Relevance: Not all collected articles are equally relevant to the user’s desires; a ranking mechanism is necessary to surface the most pertinent content.
- Credibility: Sources vary in reliability, and the same story may be corroborated or contradicted across outlets; the system must assess trustworthiness rather than treat all sources as equivalent.
- Information overload: Even after filtering and ranking the collected results, the volume of information may be too large to read in full; concise summaries are needed to allow the user to understand the point of view of each provider on the specific topic in a concise manner.
- Timeliness: Based on the user’s usage patterns (persistent subscriptions or on-demand queries), the system must support both; specifically, the system should allow background refreshes so that results remain current without requiring repeated manual requests.
- Personalization: The system should adapt to the user’s preferences during the system-user interaction by learning which sources and topics consistently produce relevant results.

A multi-agent architecture surfaces as a natural fit for this problem because the processing pipeline decomposes into well-defined, independent responsibilities that benefit from parallel and concurrent execution, modular design, and inter-agent coordination. Moreover, the ranking problem itself benefits from a society of specialized agents that each produce an independent judgment along a distinct dimension (relevance, credibility, novelty), with a separate agent aggregating these judgments into a final decision.

## High-level MAS Specification

### System Operating Modes

1. On-demand query mode: the user submits an explicit filter as a structured description of the content they wish to see, and the system returns a curated bundle composed from the current system state, prioritizing relevant keywords.
2. Periodic subscription mode: the user registers a filter as standing; the system retains it across sessions and autonomously pushes updates at a configurable interval, without requiring further user action.

### Inputs / Outputs

| Direction | Parameter           | Description                                         |
| --------- | ------------------- | --------------------------------------------------- |
| Input     | Ketwords/topics     | Free-text search terms or topic labels              |
| Input     | News providers      | Optional list of specific RSS sources               |
| Input     | Refresh interval    | Interval in minutes for periodic mode               |
| Input     | User feedback       | Optional explicit relevance signal per article      |
| Output    | Article list        | Ranked, deduplicated articles matching query        |
| Output    | Per-article summary | Short LLM-generated summary for each article        |
| Output    | Formatted output    | Human-readable output rendered as presentation      |


## Conceptual Design of MAS

### Environment

The conceptual model begins with an explicit characterization of the environment in which the agents operate. In this system, the environment is the news feed ecosystem, comprising:

- News sources: a configured set of RSS publishers, each producing a continuous stream of articles at its own cadence, with its own coverage and reputation.
- User feed configuration: the user preferences, with their declared filters, describing the content they wish to see, and the provided feedback on delivered content.

This is the external world the agents are situated in: its state evolves independently of agent action, and different agents perceive different slices of it. In addition to perceiving the environment directly, agents coordinate through a shared blackboard that holds the derived state produced by the agents as they process the environment: fetched articles, computed scores, registered filters, user preferences, and pending deliveries. The blackboard is a coordination medium rather than part of the environment itself; however, for several agents in this system (notably the Analysts and the Editor) the blackboard is the primary source of the percepts on which they act. The distinction matters for the conceptual model: the environment determines what the system is situated in, while the blackboard determines how agents coordinate over derived state.
