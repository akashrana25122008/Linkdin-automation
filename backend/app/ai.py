"""AI provider abstraction. Mock is the M0 default; real providers are later."""

from typing import Protocol


class AIProvider(Protocol):
    name: str

    def generate(self, prompt: str) -> dict:
        ...


class MockAIProvider:
    """Clearly-labeled development provider. Works without credentials."""

    name = "mock"

    def generate(self, prompt: str) -> dict:
        return {
            "provider": "mock",
            "mock": True,
            "text": f"[MOCK AI] Draft for: {prompt[:120]}",
        }


def get_ai_provider(name: str = "mock") -> AIProvider:
    if name == "mock":
        return MockAIProvider()
    # Planned providers (groq, gemini, openai, ollama) arrive with M4.
    # Fail honestly instead of fabricating output.
    raise ValueError(f"AI provider '{name}' is NOT CONFIGURED in M0")
