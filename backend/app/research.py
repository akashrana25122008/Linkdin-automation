"""Research provider abstraction. Mock data is always labeled mock."""

from typing import Protocol


class ResearchProvider(Protocol):
    name: str

    def search(self, topic: str) -> list[dict]:
        ...


MOCK_ANGLES = (
    "Educational explanation: break the core idea down for practitioners.",
    "Technical insight: go one level deeper than the announcement.",
    "Developer impact: what changes in day-to-day engineering work.",
)


class MockResearchProvider:
    """Development data only. Never present as real sources: no real
    outlet names, no source URLs, no publication dates."""

    name = "mock"

    def search(self, topic: str) -> list[dict]:
        clean = topic.strip()[:120] or "general professional development"
        return [
            {
                "title": f"[MOCK] {clean} — signal {i + 1}",
                "summary": (
                    f"Development placeholder about {clean} "
                    f"(signal {i + 1} of 3). Replace with real research in "
                    "production."
                ),
                "source": "mock",
                "source_name": "mock-development",
                "url": "",
                "source_url": "",
                "published_at": None,
                "topic": clean,
                "relevance_score": round(0.85 - i * 0.1, 2),
                "freshness": "mock",
                "freshness_score": round(0.7 - i * 0.05, 2),
                "potential_angle": MOCK_ANGLES[i],
                "linkedin_angle": MOCK_ANGLES[i],
                "mock": True,
            }
            for i in range(3)
        ]


def get_research_provider(name: str = "mock") -> ResearchProvider:
    if name == "mock":
        return MockResearchProvider()
    raise ValueError(f"Research provider '{name}' is NOT CONFIGURED in M0")
