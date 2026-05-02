"""
ResponseValidator — checks AI responses for accuracy, hallucination, and completeness.
Runs asynchronously after each response. Results are sent to the frontend via WebSocket.
"""

import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.core.config import get_settings
from app.models.model import ConfidenceLevels
from app.prompts.prompt import VALIDATOR_PROMPT

settings = get_settings()

_WEB_TRIGGERS = [
    # Time / recency
    "today", "now", "current", "latest", "recent", "recently",
    "this week", "this month", "this year", "yesterday", "just", "live", "update",

    # News / events
    "news", "breaking", "headline", "what happened", "updates", "event",

    # Weather
    "weather", "temperature", "rain", "forecast", "climate",

    # People / roles (dynamic)
    "who is", "president", "prime minister", "ceo", "leader", "minister",
    "governor", "captain", "coach",

    # Finance / market
    "price", "stock", "market", "share price", "crypto", "bitcoin",
    "ethereum", "sensex", "nifty", "trading", "rate",

    # Sports
    "score", "match", "result", "live score", "team news", "fixture",
    "points table", "standings",

    # Politics / elections
    "election", "vote", "results", "poll", "government",

    # Time-specific years
    "2023", "2024", "2025", "2026",

    # Location-based queries
    "near me", "in my area", "local", "nearby",

    # Comparisons that may change
    "top", "best", "ranking", "rank", "trending", "popular",

    # Availability / status
    "open now", "closing time", "availability",

    # General real-world queries
    "schedule", "timing", "release date", "launch", "announcement"
]

class ResponseValidator:
    """Validates AI responses for confidence and potential issues."""

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o-mini",  
            openai_api_key=settings.openai_api_key,
            temperature=0,
        )

    async def assess_response_quality(self, question: str, response: str) -> dict:
        """
        Returns:
          {
            confidence: "high"|"medium"|"low"|"unverified",
            issues: [...],
            should_search_web: bool,
            verdict: "..."
          }
        """
        stale_phrases = [
            "as of my last update", "as of my app.knowledge_base", "i don't have access",
            "i recommend checking", "i cannot browse", "my training data",
        ]
        response_lower = response.lower()
        has_stale = any(p in response_lower for p in stale_phrases)
        needs_web = any(kw in question.lower() for kw in _WEB_TRIGGERS)

        if has_stale and needs_web:
            return {
                "confidence": ConfidenceLevels.UNVERIFIED,
                "issues": ["Response uses training data for a real-time question"],
                "should_search_web": True,
                "verdict": "This answer may be outdated. Web search was not used.",
            }

        try:
            prompt = VALIDATOR_PROMPT.format(question=question, response=response)
            result = await self._llm.ainvoke([HumanMessage(content=prompt)])
            text = result.content.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception:
            return {
                "confidence": ConfidenceLevels.MEDIUM,
                "issues": [],
                "should_search_web": False,
                "verdict": "Validation unavailable.",
            }
