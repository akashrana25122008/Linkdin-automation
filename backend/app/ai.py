"""AI provider abstraction. Mock is the M0 default; real providers are later."""

import re
from typing import Protocol


class AIProvider(Protocol):
    name: str

    def generate(self, prompt: str) -> dict:
        ...


def _extract(prompt: str, marker: str) -> str:
    """Pull a `Marker: value` field out of a structured prompt.

    Values run until the next known marker (or end of text), so embedded
    periods such as "Node.js" do not truncate the capture.
    """
    stop = "(?=[ ]+(?:Topic|LinkedIn post|Author notes|Current draft|[(]variation[)]|$))"
    match = re.search(rf"{marker}:\s*(.*?){stop}", prompt, re.DOTALL)
    return match.group(1).strip() if match else ""


def _pick(key: str, options: list) -> int:
    """Deterministic index from text content (no randomness in mock)."""
    return sum(ord(ch) for ch in key) % len(options)


def _tags(topic: str, type_tag: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9]+", topic) if len(w) > 2]
    seen: list[str] = []
    for word in words:
        tag = word[:24]
        if tag.lower() not in [s.lower() for s in seen]:
            seen.append(tag)
        if len(seen) == 2:
            break
    seen.append(type_tag)
    return " ".join(f"#{tag}" for tag in seen[:3])


def _split_paragraphs(content: str) -> tuple[list[str], list[str]]:
    """Split draft into (body lines, trailing hashtag lines)."""
    lines = [line for line in content.splitlines() if line.strip()]
    tags = []
    while lines and all(part.startswith("#") for part in lines[-1].split()):
        tags.append(lines.pop())
    tags.reverse()
    return lines, tags


# Per-type voice: hooks to choose from, a body angle, a CTA, a tag.
# Bodies stay observational and practical: no statistics, no sources,
# no claimed personal events, no engagement bait.
_TYPE_VOICE = {
    "educational": {
        "hooks": [
            "{topic}: the fundamentals most people skip.",
            "If {topic} still feels fuzzy, start here.",
        ],
        "angle": (
            "The core idea is simpler than most explanations make it. "
            "Break it into its smallest moving parts, learn each one in "
            "isolation, then reassemble them on a real example."
        ),
        "cta": "What resource helped {topic} click for you?",
        "tag": "Learning",
    },
    "technical": {
        "hooks": [
            "A precise look at {topic}.",
            "Notes on {topic}, minus the hand-waving.",
        ],
        "angle": (
            "The details matter here: interfaces, edge cases, and failure "
            "modes. Write down the exact behavior you expect before you "
            "build, then verify each assumption one at a time."
        ),
        "cta": "How do you usually verify behavior like this?",
        "tag": "Engineering",
    },
    "project_showcase": {
        "hooks": [
            "Sharing some work on {topic}.",
            "A short walkthrough of {topic}.",
        ],
        "angle": (
            "The goal was to keep the scope small and the feedback loop "
            "short. Each iteration answered one open question, and the "
            "design improved because the questions got better, not because "
            "the plan got bigger."
        ),
        "cta": "Feedback welcome — what would you try differently?",
        "tag": "BuildInPublic",
    },
    "personal_learning": {
        "hooks": [
            "What studying {topic} is teaching me about learning itself.",
            "Learning notes on {topic}.",
        ],
        "angle": (
            "Progress comes from short, regular sessions and writing down "
            "what confused me each time. Revisiting those notes a week "
            "later shows exactly where the understanding actually improved."
        ),
        "cta": "What does your learning routine look like?",
        "tag": "Learning",
    },
    "hackathon": {
        "hooks": [
            "48 hours, one idea: {topic}.",
            "Hackathon lessons from building on {topic}.",
        ],
        "angle": (
            "Time pressure forces tradeoff thinking: cut scope early, demo "
            "something working, and treat everything else as a stretch goal. "
            "The demo matters more than the architecture diagram."
        ),
        "cta": "What is your best hackathon time-management trick?",
        "tag": "Hackathon",
    },
    "career": {
        "hooks": [
            "Career thoughts for anyone working on {topic}.",
            "What I wish I had known earlier about {topic}.",
        ],
        "angle": (
            "Depth in one area opens more doors than shallow breadth across "
            "five. Pick the skill that compounds, document your work in "
            "public, and let the portfolio do the talking."
        ),
        "cta": "What career advice shaped your path?",
        "tag": "Career",
    },
    "ai_tech_commentary": {
        "hooks": [
            "Reading past the hype on {topic}.",
            "A measured take on {topic}.",
        ],
        "angle": (
            "Every wave of tooling follows the same arc: excitement, "
            "overuse, then quiet integration into real workflows. The "
            "interesting question is always what changes in daily practice, "
            "not what the announcement claims."
        ),
        "cta": "Where do you see this settling in practice?",
        "tag": "AI",
    },
    "storytelling": {
        "hooks": [
            "A short story about {topic}.",
            "Let me tell you about {topic}.",
        ],
        "angle": (
            "It started as a small curiosity and turned into a weeks-long "
            "rabbit hole. The turning point was stopping to write down what "
            "I actually understood — that note became the foundation for "
            "everything after it."
        ),
        "cta": "Have you ever fallen down a rabbit hole like this?",
        "tag": "Storytelling",
    },
    "tutorial": {
        "hooks": [
            "A quick hands-on guide to {topic}.",
            "Learn {topic} by building, step by step.",
        ],
        "angle": (
            "Step one: set up the smallest possible working example. Step "
            "two: change one thing and observe. Step three: break it on "
            "purpose, then fix it. Repeat until the mental model holds."
        ),
        "cta": "What topic should the next walkthrough cover?",
        "tag": "Tutorial",
    },
    "opinion": {
        "hooks": [
            "An honest opinion on {topic}.",
            "Possibly unpopular: my view on {topic}.",
        ],
        "angle": (
            "Strong defaults beat endless configuration. Most debates in "
            "this space are really about taste disguised as engineering, "
            "and the pragmatic answer is usually the boring one that ships."
        ),
        "cta": "Where do you disagree?",
        "tag": "Opinion",
    },
    "achievement_update": {
        "hooks": [
            "A milestone worth sharing on {topic}.",
            "Progress update: {topic}.",
        ],
        "angle": (
            "Milestones are just consistency made visible. Showing up on a "
            "schedule, keeping the scope realistic, and reviewing what "
            "worked each week compounds faster than occasional big pushes."
        ),
        "cta": "What milestone are you working toward?",
        "tag": "Milestone",
    },
}


def _build_post(topic: str, content_type: str, notes: str, variant: int = 0) -> str:
    topic = topic.strip() or "professional growth"
    voice = _TYPE_VOICE.get(content_type, _TYPE_VOICE["educational"])
    hook = voice["hooks"][variant % len(voice["hooks"])].format(topic=topic)
    takeaway_lines = [
        f"Takeaway one: define what success with {topic} looks like before starting.",
        "Takeaway two: keep a short log of what worked and what did not.",
        "Takeaway three: share the log — teaching is the fastest review.",
    ]
    if variant >= len(voice["hooks"]):
        takeaway_lines = takeaway_lines[::-1]
    takeaways = "\n".join(takeaway_lines)
    parts = [
        hook,
        voice["angle"].format(topic=topic),
        takeaways,
        voice["cta"].format(topic=topic),
        _tags(topic, voice["tag"]),
    ]
    if notes.strip():
        parts.append(f"Notes for this draft: {notes.strip()[:140]}")
    return "\n\n".join(parts)


def _shorten(content: str, limit: int = 280) -> str:
    if len(content) <= limit:
        return content
    cut = content[:limit]
    for end in (".", "?", "!"):
        pos = cut.rfind(end)
        if pos > limit // 2:
            return cut[: pos + 1]
    return cut.rstrip() + "…"


def _rewrite(content: str, task: str, topic: str) -> str:
    """Deterministic mock transform of the current draft for one action."""
    lines, tags = _split_paragraphs(content)
    if not lines:
        return content
    tag_block = ("\n" + "\n".join(tags)) if tags else ""
    subject = topic or "this topic"

    if "hook" in task:
        lines[0] = f"{subject.capitalize()}: what actually matters (and what doesn't)."
        return "\n".join(lines) + tag_block
    if "shorten" in task:
        return _shorten("\n".join(lines)) + tag_block
    if "expand" in task:
        extra = (
            f"\n\nOne more angle on {subject} worth considering: revisit the "
            "basics whenever progress stalls. Foundations explain most "
            "confusing behavior."
        )
        return "\n".join(lines) + extra + tag_block
    if "simpl" in task:
        simple = []
        for line in lines:
            while len(line) > 120 and ", " in line:
                head, _, rest = line.partition(", ")
                simple.append(head + ".")
                line = rest.strip().capitalize() or rest.strip()
            simple.append(line)
        return "\n".join(simple) + tag_block
    if "technical" in task:
        lines[0] = f"Technical note on {subject}:"
        return "\n".join(lines) + tag_block
    if "personal" in task:
        lines[0] = f"A personal note on learning {subject}:"
        return "\n".join(lines) + tag_block
    if "professional" in task:
        lines[0] = f"A professional take on {subject}:"
        return "\n".join(lines) + tag_block
    if "call to action" in task or task.strip().endswith("cta"):
        lines.append(f"What's been your experience with {subject}?")
        return "\n".join(lines) + tag_block
    if "hashtag" in task:
        return "\n".join(lines) + "\n" + _tags(subject, "LinkedIn")
    return content


class MockAIProvider:
    """Clearly-labeled development provider. Works without credentials.

    Renders deterministic, realistic-looking LinkedIn drafts from the
    structured prompt fields (topic, type, notes, current draft) instead
    of echoing internal prompt wording. No statistics, sources, or
    personal experiences are invented.
    """

    name = "mock"

    def generate(self, prompt: str) -> dict:
        text = _mock_text(prompt or "")
        return {"provider": "mock", "mock": True, "text": text}


def _mock_text(prompt: str) -> str:
    lowered = prompt.lower()
    topic = _extract(prompt, "Topic") or _extract(prompt, "topic")
    draft = ""
    match = re.search(r"Current draft:\s*\n(.*)$", prompt, re.DOTALL)
    if match:
        draft = re.sub(r"\s*\(variation \d+\)\s*$", "", match.group(1)).strip()
    type_match = re.search(r"LinkedIn post \((\w+)\)", prompt)
    content_type = type_match.group(1) if type_match else "educational"
    notes = _extract(prompt, "Author notes")
    variant_match = re.search(r"\(variation (\d+)\)", prompt)
    variant = int(variant_match.group(1)) if variant_match else 0

    if draft and ("alternat" in lowered or "variation" in lowered):
        return _build_post(topic or draft.splitlines()[0][:60], content_type, notes, variant)
    task_line = _extract(prompt, "Task").lower()
    if "generate a new draft" in task_line:
        return _build_post(topic, content_type, notes, variant)
    if draft:
        return _rewrite(draft, task_line, topic)
    if "brief" in lowered[:200]:
        return (
            "Mock brief: steady pipeline, one draft in review. "
            "Suggested focus: turn the newest topic into a first draft."
        )
    if "angle" in lowered:
        return (
            "Mock angle: explain the core idea simply, then connect it to "
            "one practical takeaway for practitioners."
        )
    if "summary" in lowered:
        return (
            "Mock review summary: readable structure with room to sharpen "
            "the hook and tighten the closing."
        )
    if topic or "generate a new draft" in lowered:
        return _build_post(topic, content_type, notes, variant)
    return _build_post(prompt.strip().splitlines()[0][:60] if prompt.strip() else "", content_type, "", 0)


def get_ai_provider(name: str = "mock") -> AIProvider:
    if name == "mock":
        return MockAIProvider()
    # Planned providers (groq, gemini, openai, ollama) arrive with M4.
    # Fail honestly instead of fabricating output.
    raise ValueError(f"AI provider '{name}' is NOT CONFIGURED in M0")
