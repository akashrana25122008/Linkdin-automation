"""Research provider abstraction. Mock data is always labeled mock."""

from typing import Protocol


class ResearchProvider(Protocol):
    name: str

    def search(self, topic: str) -> list[dict]:
        ...


class MockResearchProvider:
    """Development data only. Never present as real sources."""

    name = "mock"

    def search(self, topic: str) -> list[dict]:
        return [
            {
                "title": f"[MOCK] Starter angles for {topic}",
                "source": "mock",
                "url": "",
                "summary": "Placeholder research item for local development.",
                "topic": topic,
                "relevance_score": 0.5,
                "freshness": "mock",
                "potential_angle": "Replace with real provider in M5.",
                "mock": True,
            }
        ]


def get_research_provider(name: str = "mock") -> ResearchProvider:
    if name == "mock":
        return MockResearchProvider()
    raise ValueError(f"Research provider '{name}' is NOT CONFIGURED in M0")
