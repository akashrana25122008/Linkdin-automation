"""LinkedIn development/mock boundary. No real OAuth, API, or publishing in M0."""

from dataclasses import dataclass


@dataclass
class LinkedInStatus:
    mode: str  # "mock" | "not_configured"
    connected: bool = False
    note: str = "MOCK DATA — LinkedIn integration arrives in M9/M10."


class MockLinkedInClient:
    """Mock must never publish or claim real functionality."""

    def status(self) -> LinkedInStatus:
        return LinkedInStatus(mode="mock")

    def publish(self, *args, **kwargs) -> dict:
        raise RuntimeError("REFUSED: mock LinkedIn client never publishes.")


def get_linkedin_client(mode: str = "mock") -> MockLinkedInClient:
    if mode == "mock":
        return MockLinkedInClient()
    raise ValueError(f"LinkedIn mode '{mode}' is NOT CONFIGURED in M0")
