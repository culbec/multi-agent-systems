"""Demo data loader for the SP1 blackboard.

Provides a small set of realistic article stubs that analysts can score
immediately, giving users instant feedback when they register a filter
during the first run or when crawlers are offline.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sp1.infra.blackboard import Blackboard

DEMO_ARTICLES: list[dict] = [
    {
        "article_id": "demo_001",
        "source_id": "techcrunch",
        "title": "OpenAI Releases GPT-5 with Multi-Modal Reasoning",
        "body": (
            "OpenAI has announced the release of GPT-5, its most advanced large language model "
            "to date. The new model features multi-modal reasoning capabilities, allowing it to "
            "process text, images, audio, and video in a single coherent pass. Early benchmarks "
            "show a 40% improvement over GPT-4.5 on coding tasks and a 25% reduction in hallucinations. "
            "The model is available via API starting today, with enterprise licensing rolling out next month."
        ),
        "summary": "OpenAI launches GPT-5 with multi-modal reasoning and improved benchmarks.",
        "url": "https://techcrunch.com/demo/gpt5",
        "published_at": (datetime.now(timezone.utc)).isoformat(),
        "fetched_at": (datetime.now(timezone.utc)).isoformat(),
        "categories": ["technology", "AI"],
        "author": "Sarah Chen",
        "embedding": [],
    },
    {
        "article_id": "demo_002",
        "source_id": "reuters",
        "title": "Global Climate Summit Reaches Landmark Emissions Agreement",
        "body": (
            "Delegates at the 2026 Global Climate Summit in Geneva reached a landmark agreement "
            "on reducing carbon emissions by 2035. The pact, signed by 187 nations, commits developed "
            "countries to a 55% reduction from 2010 levels. A new climate finance fund of $500bn "
            "will support developing nations in transitioning to renewable energy. Critics note that "
            "enforcement mechanisms remain voluntary, raising questions about compliance."
        ),
        "summary": "187 nations agree on 55% carbon cut by 2035 at Geneva climate summit.",
        "url": "https://reuters.com/demo/climate-summit",
        "published_at": (datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0).isoformat(),
        "fetched_at": (datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0).isoformat(),
        "categories": ["politics", "environment"],
        "author": "Marco Rossi",
        "embedding": [],
    },
    {
        "article_id": "demo_003",
        "source_id": "nytimes",
        "title": "New Clean Energy Breakthrough Promises Cheaper Solar Panels",
        "body": (
            "Researchers at MIT have published a paper describing a new perovskite-silicon tandem "
            "solar cell that achieves a record 33.7% efficiency in laboratory conditions. The key "
            "innovation is a novel passivation layer that prevents rapid degradation, a long-standing "
            "problem with perovskite cells. If commercialised, the technology could reduce solar panel "
            "costs by 20-30% within five years. Several startups have already licensed the patent."
        ),
        "summary": "MIT researchers develop record-breaking solar cell with commercial potential.",
        "url": "https://nytimes.com/demo/solar-breakthrough",
        "published_at": (datetime.now(timezone.utc)).replace(minute=15, second=0, microsecond=0).isoformat(),
        "fetched_at": (datetime.now(timezone.utc)).replace(minute=15, second=0, microsecond=0).isoformat(),
        "categories": ["technology", "science", "energy"],
        "author": "Jennifer Walsh",
        "embedding": [],
    },
    {
        "article_id": "demo_004",
        "source_id": "bbc",
        "title": "European Space Agency Announces Mars Sample Return Mission",
        "body": (
            "The European Space Agency has confirmed its commitment to the Mars Sample Return "
            "mission, a joint effort with NASA. The mission will retrieve rock and soil samples "
            "collected by the Perseverance rover and return them to Earth by 2033. The estimated "
            "cost has risen to €7bn, prompting some member states to call for a phased approach. "
            "ESA's director general defended the plan, calling it 'the most important planetary "
            "science endeavour of the decade'."
        ),
        "summary": "ESA confirms Mars Sample Return mission with 2033 target date.",
        "url": "https://bbc.com/demo/mars-sample-return",
        "published_at": (datetime.now(timezone.utc)).replace(minute=30, second=0, microsecond=0).isoformat(),
        "fetched_at": (datetime.now(timezone.utc)).replace(minute=30, second=0, microsecond=0).isoformat(),
        "categories": ["science", "space"],
        "author": "David Park",
        "embedding": [],
    },
    {
        "article_id": "demo_005",
        "source_id": "techcrunch",
        "title": "Startup Claims Quantum Advantage in Drug Discovery Simulation",
        "body": (
            "California-based startup AtomSim has announced that its 256-qubit quantum computer "
            "achieved a decisive advantage in a drug-discovery simulation compared to classical "
            "supercomputers. The simulation modelled the binding of a novel antibiotic to a drug-resistant "
            "bacterial protein. Independent verification by Stanford researchers confirmed the result, "
            "though they cautioned that the specific problem was carefully chosen to suit quantum hardware."
        ),
        "summary": "Quantum startup demonstrates computational advantage in drug discovery.",
        "url": "https://techcrunch.com/demo/quantum-drug-discovery",
        "published_at": (datetime.now(timezone.utc)).replace(minute=45, second=0, microsecond=0).isoformat(),
        "fetched_at": (datetime.now(timezone.utc)).replace(minute=45, second=0, microsecond=0).isoformat(),
        "categories": ["technology", "health", "science"],
        "author": "Sarah Chen",
        "embedding": [],
    },
    {
        "article_id": "demo_006",
        "source_id": "politico",
        "title": "Senate Passes Bipartisan Infrastructure Modernisation Bill",
        "body": (
            "The US Senate passed a $1.2 trillion infrastructure modernisation bill with broad "
            "bipartisan support. The legislation allocates funding for bridge repairs, broadband "
            "expansion, and electric vehicle charging networks. Key provisions include $85bn for "
            "public transit upgrades and $65bn for rural broadband. The bill now moves to the House, "
            "where progressive Democrats have signalled they may demand additional climate provisions."
        ),
        "summary": "Bipartisan $1.2tn infrastructure bill clears Senate, faces House hurdles.",
        "url": "https://politico.com/demo/infrastructure-bill",
        "published_at": (datetime.now(timezone.utc)).replace(minute=50, second=0, microsecond=0).isoformat(),
        "fetched_at": (datetime.now(timezone.utc)).replace(minute=50, second=0, microsecond=0).isoformat(),
        "categories": ["politics", "economy"],
        "author": "Robert Hayes",
        "embedding": [],
    },
]


async def load_demo_articles(blackboard: Blackboard) -> None:
    """Write demo articles into *blackboard* if the candidate pool is empty."""
    existing = await blackboard.snapshot_candidate_pool()
    if existing:
        return

    for article in DEMO_ARTICLES:
        article["article_id"] = hashlib.md5(
            f"{article['source_id']}_{article['url']}".encode(),
            usedforsecurity=False,
        ).hexdigest()
        article["fetched_at"] = datetime.now(timezone.utc).isoformat()

    await blackboard.add_articles(DEMO_ARTICLES)
