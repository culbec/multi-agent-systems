# Application Design

This document states the high-level specification of the application design. We will look into class definitions, interaction schemas, and UX so that we make the most of our MAS for SP1.

## Class Organization

The application follows a straightforward class hierarchy rooted in SPADE’s Agent base class. Each agent type is a subclass of Agent, with its responsibilities implemented through one or more behavior classes (subclasses of the appropriate SPADE behavior type). The blackboard is implemented as a separate module independent of SPADE, exposing a thread-safe or asyncio-safe interface for its logical regions. Message classes encapsulate the structured payloads exchanged via FIPA ACL.

The main classes are:

- CrawlerAgent: one subclass instance per configured RSS source, with a PeriodicBehaviour for polling.
- RelevanceAnalystAgent, CredibilityAnalystAgent, NoveltyAnalystAgent: the Analyst types, each with a CyclicBehaviour triggered by new arrivals in the candidate pool or filter-change events.
- EditorAgent: a single instance with a CyclicBehaviour for continuous watching of the score board and a message-triggered OneShotBehaviour for responding to one-off bundle requests.
- ClerkAgent: a single instance with a CyclicBehaviour for handling user input and incoming bundles, a PeriodicBehaviour for session timeout and stale-filter suggestions, 14 and a OneShotBehaviour per feedback-solicitation decision.
- Blackboard: a module (outside the agent hierarchy) exposing accessors for each logical region: candidate pool, score board, filter registry, user profiles, session contexts, source-health flags, source-reputation table, and pending-delivery queue.
- Message classes: FilterRegisteredMessage, BundleRequestMessage, BundleDeliveryMessage, and similar, each a structured FIPA ACL payload.

## Data Schemas

The principal data schemas exchanged through the blackboard and messages are:

- Article: article id, source id, title, body, url, published at, fetched at, categories, author, optional embedding.
- Filter: filter id, user id, mode (one off or standing), keywords, keyword mode, categories, sources (include/exclude), max age hours, min credibility, delivery (max items, min interval, min items before push, breaking threshold), created at, last push at.
- Score vector: article id, filter id, user id, scores (per-dimension scores), scored at.
- User profile: user id, preferences, standing filters, saved presets, delivery history.
- Bundle: bundle id, filter id, user id, composed at, articles (list of per-article entries with summary and scores), trigger (one off request or standing push).

## Interaction Scenarios

To illustrate the runtime dynamics, two representative scenarios are described below: a synchronous one-off filter evaluation and an asynchronous standing filter push.

### One-off filter evaluation (synchronous)

1. The user submits a filter declaration via the Clerk interface.
2. The Clerk parses and validates the filter, merges it with the user’s persistent preferences, writes it to the filter registry on the blackboard, and sends a REQUEST message to the Editor.
3. The Analysts, in their continuous scoring cycles, detect the new filter and score matching articles from the candidate pool; score vectors appear on the score board.
4. The Editor, on receiving the REQUEST, reads the relevant score vectors, aggregates them using a filter-appropriate weighting policy, applies the user’s delivery preferences and quality thresholds, composes a diverse bundle, generates per-article summaries, and returns the bundle to the Clerk via an INFORM message.
5. The Clerk formats the bundle and delivers it to the user. If appropriate, the Clerk subsequently solicits feedback, and any feedback received is written to the blackboard.

### Standing filter autonomous push (asynchronous)

1. The user registers a filter with mode = standing via the Clerk.
2. The Clerk writes the filter to the user’s persistent standing-filter registry on the blackboard and sends an INFORM to the Editor announcing the new standing filter.
3. The Editor adds the filter to its watch set and initializes its readiness counter.
4. As Crawlers populate the candidate pool and Analysts continuously score new arrivals against the filter, aggregated scores accumulate on the score board.
5. The Editor, in its continuous watching cycle, tracks the readiness counter for this filter. When the readiness criteria are met (sufficient newly matched high-quality articles have accumulated and the minimum inter-push interval has elapsed, or a single article above the breaking-news threshold has arrived) the Editor autonomously composes a bundle and sends it to the Clerk via an INFORM message.
6. The Clerk delivers the bundle immediately if the user is currently in an active session, or writes it to the pending-delivery queue on the blackboard if the user is offline. In the latter case, the queued bundle is delivered on the user’s next login.

## Coordination Properties

Several architectural properties of this communication and interaction model are worth highlighting, as they justify the design choices made in the previous sections.

- Agent autonomy: Each agent owns its own decisions within its scope, rather than executing commands dispatched by a central coordinator. The Editor can autonomously decide when a bundle can be sent based on a standing-filter criteria; no other agent can make this decision, and no user action triggers it. The Clerk decides when to solicit feedback and when to suggest filter adjustments. Crawlers and Analysts exercise more limited autonomy (their behavior follows fixed polling and scoring policies) but they still operate without central orchestration, perceiving their environment and producing their outputs on their own schedules. The architecture is therefore a society of cooperating agents rather than a pipeline of centrally orchestrated services.
- Pro-activeness: The system exhibits pro-active behavior at multiple levels. Crawlers poll continuously without prompting. Analysts score continuously as new content arrives. The Editor autonomously pushes standing-filter bundles when its readiness criteria are satisfied. The Clerk pro-actively solicits feedback and suggests filter adjustments. This is goal- directed behavior, not merely stimulus-response.
- Concurrent and parallel execution: The number of Crawlers scales with the number of configured sources, and all Crawlers run concurrently. The four Analysts run concurrently with each other and with the Crawlers. The Editor and Clerk operate concurrently with all of them. Concurrency is native to the design rather than bolted on. 
- Genuine multi-agent decision-making: The final ranking of articles is not computed by any single agent: it emerges from the Editor’s aggregation of independent Analyst judgments along different dimensions. This aggregation pattern is what distinguishes the system from a distributed pipeline of sequential services and is what justifies the characterization of the architecture as a society of cooperating agents rather than as a set of orchestrated workers.

## UX - UI Framework

Lightweight **NiceGUI** or **StreamLit** interface for easy access to the application from a user stand-point. It should present the following.

- A chat window: so that the use can query the Clerk agent for new news.
- The blackboard contents, configurable at runtime: for debugging.
- The messages between agents, configurable at runtime: for debugging.
- Filter options: to ensure that we can let the user apply filters.
- User feedback interface options.
- All other UI elements needed for the application.
