# Agent Specification

This document provides a specification of each agent type involved in the MAS of SP1.

## Agent Types & Specification

### Clerk Agent

The sole user-facing agent. Receives filter declarations from the user, validates them, merges them with the user’s persistent preferences, and registers them on the blackboard (session-scoped for one-off filters, persistent for standing filters). Notifies the Editor of filter changes. Receives composed bundles from the Editor (both synchronous responses to one-off filters and asynchronous pushes for standing filters) and delivers them to the user; bundles arriving while the user is offline are written to a pending delivery queue and delivered on next login. Solicits feedback after meaningful deliveries and writes feedback events to the blackboard for use by the Analysts. Pro-actively suggests filter adjustments (broadening, narrowing, promotion to standing, cleanup of stale standing filters) based on observed outcomes.

- Input: Filter declarations and edits, feedback signals, and profile changes from the user; composed bundles from the Editor; session events (login, logout, timeout); optional source-health notices.
- Output: Filters written to the blackboard; filter-change notifications sent to the Editor; formatted bundles delivered to the user; feedback events written to the blackboard.
- Behavior: CyclicBehaviour for handling user input queries and incoming bundles; PeriodicBehaviour for session updates or timeout; OneShotBehaviour per feedback solicitation decision.

### Editor Agent

The central decision-making agent. For a one-off filter request from the Clerk, reads the relevant score vectors from the blackboard, aggregates them using a filter-appropriate weighting policy, composes a diverse bundle respecting the user’s delivery preferences, generates per-article summaries, and returns the bundle to the Clerk. For each registered standing filter, continuously watches the score board: maintains a readiness counter tracking newly matched articles and their aggregated scores, and autonomously decides when readiness criteria are met, based on accumulated item count, elapsed interval since the last push, and a breaking-news threshold, at which point the Editor composes a push bundle and sends it to the Clerk. The Editor handles conflicts between Analyst dimensions according to a defined conflict-resolution policy (e.g., high Relevance but low Credibility is demoted or flagged).

- Input: Score vectors from the Analysts (via the blackboard); active filters and delivery preferences from the blackboard; bundle requests and filter-change notifications from the Clerk; optional source-health notices from the Crawlers.
- Output: Composed bundles sent to the Clerk (both synchronous responses and asynchronous pushes); readiness-counter and push-history updates written to the blackboard.
- Behaviour: CyclicBehaviour for watching the score board and handling standing filters; message-triggered OneShotBehaviour for responding to one-off bundle requests.

### Analyst Agent

A family of specialized scoring agents running concurrently, each producing an independent judgment along its dimension. All Analysts share a common pattern: they read new articles from the candidate pool and active filters from the registry, compute a dimension-specific score for each (article, filter) pair, and write the resulting score vectors to the score board. Analysts do not communicate with one another; their independence is what gives meaning to the Editor’s subsequent aggregation.

- Input: Articles from the candidate pool; active filters from the filter registry; per-user state read from the blackboard (preference weights for Relevance, delivery history for Novelty, source-reputation table for Credibility).
- Output: Score vectors written to the score board; updates to the source-reputation table (Credibility Analyst only).
- Behaviour CyclicBehaviour triggered by new arrivals in the candidate pool or filter-change events; PeriodicBehaviour for bookkeeping such as cache maintenance of embedding representations.

#### Relevance Analyst

Scores how well an article matches the topic and source constraints of a filter, blending sparse retrieval (e.g., BM25) with per-user learned preference weights read from the blackboard.

#### Credibility Analyst

Scores article trustworthiness combining a per-source reputation table, cross-source corroboration (similarity with other recent pool articles), and light content heuristics. Updates the source-reputation table over time based on aggregated feedback.

#### Novelty Analyst
Scores how different an article is from content already delivered to the user and from other articles in the pool, penalizing redundancy and near-duplicates.

### Crawler Agent

Operates on a single assigned RSS source. Periodically polls the feed at a configured interval, extracts and normalizes new article entries, deduplicates them against its local last-seen record, and deposits them into the shared candidate pool on the blackboard. Maintains a source-health flag on the blackboard, updated on each polling cycle. Multiple Crawler instances run concurrently, one per configured source, providing the parallel perception layer of the system.

- Input: RSS feed content fetched from its assigned source; its own periodic polling trigger.
- Output: Normalized articles written to the candidate pool; source-health flag updates on the blackboard.
- Behaviour: PeriodicBehaviour for polling the assigned feed at the configured cadence; optional PeriodicBehaviour at a different cadence for dedicated source-health probes.

## Agent Communication

Agents communicate through two complementary channels given the context they naturally fit.

- Blackboard: A shared in-memory structure that holds all persistent and shared state.
  - Partitioned in logical regions:
    - The candidate pool: written by Crawlers, read by Analysts and the Editor.
    - The score board: written by Analysts, read by the Editor.
    - The filter registry: written by the Clerk, read by Analysts, and the Editor.
    - The user profiles: written by the Clerk and the Credibility Analyst, read by Analysts and the CLerk.
      - Also including preference weights, standing filters, delivery history, and bookmarks.
    - The source-reputation table: written and read by the Credibility Analyst, optionally read by the Editor.
    - The pending-delivery queue: written by the Editor and consumed by the Clerk.
  - The blackboard is the single source of truth for long-term state: agents may be restarted and rebuild their internal working state from it.
- Directed FIPA ACL messages: transported over SPADE's XMPP layer.
  - Used for targeted events that require immediate attention from a specific recipient.
  - The main message flows are:
    - Clerk INFORM Editor: on new or edited filters; Clerk REQUEST Editor: for one-off bundle composition.
    - Editor INFORM Clerk: composed bundle; Editor FAILURE Clerk: inability to compose bundle.
    - OPTIONAL Clerk INFORM Analyst: on filter edits to prompt immediate scoring.
    - OPTIONAL Crawler INFORM Editor: source-health checks.

The only "agent" that persists state specific to individual users across sessions is implicit in the blackboard itself: all information regarding user preferences or sessions is stored here rather than in any single agent. This simplifies reasoning about correctness, allows any agent to be restarted cleanly, and provides the system with a lightweight learning capability that persists across restarts.

## Agent Roles

- Clerk Agent: The counter staff. The sole user-facing agent, responsible for all user interactions: filter intake and validation, session and profile management, synchronous and asynchronous bundle delivery, feedback collection, and pro-active user guidance through filter suggestions. The Clerk is the only agent that perceives the user directly; all user-originated signals enter the system through it.
- Editor Agent: The managing editor. Owns all content-level decisions. Aggregates the independent judgments of the four Analysts, resolves conflicts between dimensions, composes diverse bundles, generates summaries, and autonomously decides when to push standing-filter updates to the Clerk. The push-timing decision is the Editor’s signature autonomous behavior and is the mechanism by which the system exhibits pro-active, content-driven delivery.
- Analyst Agents: The specialists. Concurrent scoring agents, each narrow and independent, together producing the multi-dimensional score vectors that feed the Editor’s decision process. Their independence is an architectural commitment: each Analyst sees only its own dimension and its own learning state, and the final ranking emerges from the Editor’s aggregation of their separate opinions. This composition is what distinguishes the system from a pipeline of sequential services.
- Crawler Agents: The field reporters. One instance per configured RSS source, running concurrently to provide the parallel perception layer. Each Crawler owns its assigned patch of the news ecosystem, is responsible for keeping the candidate pool fresh on that patch, and maintains a source-health flag that allows the Editor to annotate or downweight content from degraded sources.

## PAGES Agent Conceptual Modeling

- Crawler Agent.
  - Perception (P) New and updated article entries on the assigned RSS feed, including title, body, publication timestamp, categories, author, and URL; the reachability and response behavior of the assigned feed; the timing of its own polling cycle.
  - Action (A) Poll the assigned feed at the configured interval; extract and normalize new article entries; deduplicate them against its own last-seen record; deposit normalized articles into the shared candidate pool; update its source-health flag on the blackboard; report persistent unavailability of its source.
  - Goal (G): Keep the candidate pool fresh and representative for its patch of the news ecosystem; accurately reflect the current availability of its assigned source.
  - Environment (E): The news feed ecosystem, perceived through the assigned RSS feed and the Crawler’s own polling timer.
  - State (S): Last-seen article identifiers for self-deduplication, current polling cadence, current source-health flag, learned update frequency of the assigned source.
- Analyst Agents. The system includes four specialized Analyst agents, each sharing a common structural pattern – continuous scoring of articles in the candidate pool against active filters – but differing in the dimension along which they score.
  - Relevance Analyst.
    - P: Articles in the candidate pool; active filters (one-off and standing) on the blackboard; per-user preference weights; filter-registration and filter-edit events.
    - A: Compute relevance scores for (article, filter) pairs combining sparse text retrieval (BM25) with per-user learned weights applied as a multiplicative adjustment; write score vectors to the score board; re-score when a filter is edited or preference weights change.
    - G: Produce accurate relevance judgments for each (article, filter) pair, reflecting both the filter’s declared criteria and the user’s learned preferences.
    - E: The news feed ecosystem, perceived through the candidate pool, the filter registry, and the per-user preference weights on the blackboard.
    - S: Scoring model configuration (BM25 parameters, optional embedding model handle), last processed article marker, last-read version of each active filter.
  - Credibility Analyst.
    - P: Articles in the candidate pool (metadata, source, content); the source-reputation table on the blackboard; other recent pool articles (for cross-source corroboration detection); feedback events affecting source reputation.
    - A: Compute a credibility score for each new article combining source reputation, cross-source corroboration via semantic similarity with other recent articles, and content heuristics (length, presence of quoted sources, absence of clickbait patterns); write credibility scores to the score board; update the source-reputation table based on aggregated feedback over time.
    - G: Produce accurate credibility judgments per article; maintain calibrated source reputations that reflect observed user feedback.
    - E: The news feed ecosystem, perceived through the candidate pool and the source-reputation and feedback-history portions of the blackboard.
    - S: Scoring-model parameters, source-reputation model, corroboration cache (embeddings of recent pool articles for similarity comparison), last-processed article marker.
  - Novelty Analyst.
    - P: Articles in the candidate pool; per-user delivery histories on the blackboard; the pool-level similarity state.
    - A: Compute novelty scores as the complement of maximum semantic similarity between the article and recently delivered content for each user, and against other pool articles globally; write scores to the score board.
    - G: Produce accurate novelty judgments; prevent redundant or near-duplicate content from surfacing to the user.
    - E: The news feed ecosystem, perceived through the candidate pool and per-user delivery histories.
    - S: Similarity model, rolling embedding store for recent pool articles, last-processed article marker.
- Editor Agent.
  - P: Score vectors on the score board; active filters on the blackboard; per-user delivery prefer- ences and delivery history; the passage of time; bundle-request events from the Clerk; optional source-health notices from the Crawlers.
  - A: For one-off filter requests, aggregate the relevant score vectors using a filter-appropriate weighting policy, compose a diverse bundle respecting the user’s delivery preferences, generate per-article summaries, and return the bundle to the Clerk; for standing filters, continuously watch the score board and autonomously decide when readiness criteria are met, then compose and push a bundle; handle conflicts between Analyst dimensions according to a defined conflict-resolution policy.
  - G: Deliver the most useful bundle for each active filter at the right moment, balancing quality, diversity, and delivery timing.
  - E: The news feed ecosystem, perceived through the score board, filter registry, delivery preferences, and delivery history.
  - S: Active standing-filter watch set with per-filter readiness counters (articles accumulated since last push, last-push timestamp, aggregated-score thresholds); aggregation-policy configuration; weighting schemes per filter type; pending-bundle composition buffer.
- Clerk Agent.
  - P: User messages (filter declarations, filter edits, feedback, profile changes, bookmark actions); user engagement signals (which delivered articles the user interacted with); session events (login, logout, timeout); composed bundles arriving from the Editor (synchronous responses and asynchronous pushes); optional source-health notices for user-facing warnings.
  - A: Parse and validate filter declarations; merge active filters with persistent user preferences; register, edit, and deregister filters on the blackboard; notify the Editor of filter changes; format and deliver bundles to the user (synchronously or via inline push); queue deliveries for offline users and deliver them on reconnect; solicit feedback and write feedback events to the blackboard; pro-actively suggest filter adjustments (broadening, narrowing, promotion to standing, cleanup of stale standing filters); maintain session context and per-user delivery history.
  - G: Satisfy user intent responsively and faithfully; maintain a calibrated feedback signal; keep the user informed of matching content without overwhelming them; adapt to observed user preferences over time.
  - E: The news feed ecosystem, perceived through the user-interaction channel and the user profile, session, filter-registry, and pending-delivery portions of the blackboard.
  - S: Active session contexts (session identifier, connection handle, current-session delivery history) for each connected user; the persistent user profile is stored on the blackboard rather than kept locally.
