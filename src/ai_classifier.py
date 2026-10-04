"""Optional, cached structured LLM analysis for a small deterministic ticket sample."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from dotenv import load_dotenv

from .ai_prompts import PROMPT_VERSION, system_prompt, ticket_payload
from .config import AI_CACHE_DIR, PROJECT_ROOT, RESOLUTION_QUALITY_VALUES, UNKNOWN_CATEGORY


def load_local_environment() -> None:
    """Load project-local settings without replacing real process environment values.

    Streamlit does not load `.env` files itself. Keeping this at the LLM boundary
    means the deterministic dashboard remains dependency- and credential-free in
    normal use, while an optional provider can be configured locally.
    """
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class AIClassification:
    ticket_id: str
    issue_category: str
    sub_category: str
    confidence: float
    needs_review: bool
    resolution_quality_signal: str
    training_theme: str
    evidence: str
    source: str
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def unavailable_result(ticket_id: str, error: str = "AI unavailable") -> AIClassification:
    return AIClassification(
        ticket_id=str(ticket_id),
        issue_category=UNKNOWN_CATEGORY,
        sub_category="unclear",
        confidence=0.0,
        needs_review=False,
        resolution_quality_signal="unclear",
        training_theme="unclear",
        evidence="No AI classification available.",
        source="unavailable",
        error=error,
    )


def validate_classification(payload: dict[str, Any], ticket_id: str, categories: Sequence[str], source: str) -> AIClassification:
    """Validate/normalise model JSON before it reaches the dashboard or cache."""
    required = {
        "issue_category",
        "sub_category",
        "confidence",
        "needs_review",
        "resolution_quality_signal",
        "training_theme",
        "evidence",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"Missing AI response fields: {sorted(missing)}")
    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as error:
        raise ValueError("AI confidence must be numeric") from error
    if not 0 <= confidence <= 1:
        raise ValueError("AI confidence must be between 0 and 1")
    if not isinstance(payload["needs_review"], bool):
        raise ValueError("AI needs_review must be boolean")
    category = str(payload["issue_category"])
    if category not in set(categories):
        category = UNKNOWN_CATEGORY
    quality = str(payload["resolution_quality_signal"])
    if quality not in RESOLUTION_QUALITY_VALUES:
        quality = "unclear"
    return AIClassification(
        ticket_id=str(ticket_id),
        issue_category=category,
        sub_category=str(payload["sub_category"])[:160],
        confidence=confidence,
        needs_review=payload["needs_review"],
        resolution_quality_signal=quality,
        training_theme=str(payload["training_theme"])[:160],
        evidence=str(payload["evidence"])[:400],
        source=source,
    )


class AIClassifier:
    """A bounded OpenAI-compatible classifier; it is inert without credentials."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        cache_dir: Path = AI_CACHE_DIR,
        client: Any | None = None,
    ) -> None:
        load_local_environment()
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY", "")
        self.model = model if model is not None else os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv("LLM_BASE_URL") or None
        self.cache_dir = Path(cache_dir)
        self._client = client

    @property
    def available(self) -> bool:
        return bool(self.api_key or self._client is not None)

    @property
    def provider_label(self) -> str:
        """A non-sensitive provider label for the dashboard configuration status."""
        if self.base_url and "api.groq.com" in self.base_url.lower():
            return "Groq"
        return "OpenAI-compatible"

    def _cache_path(self, ticket_id: str, customer_message: str, agent_notes: str) -> Path:
        digest = hashlib.sha256(
            f"{PROMPT_VERSION}|{self.base_url or ''}|{self.model}|{ticket_id}|{customer_message}|{agent_notes}".encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        from openai import OpenAI  # Imported lazily so deterministic mode has no SDK requirement at import time.

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def classify_ticket(self, ticket: pd.Series, categories: Sequence[str]) -> AIClassification:
        ticket_id = str(ticket["ticket_id"])
        if bool(ticket.get("is_junk_ivr", False)):
            return unavailable_result(ticket_id, "Skipped clearly unusable IVR fragment")
        if not self.available:
            return unavailable_result(ticket_id, "AI unavailable: set LLM_API_KEY to run optional sampled analysis")

        customer_message = str(ticket.get("customer_message", ""))
        agent_notes = str(ticket.get("agent_notes", ""))
        cache_path = self._cache_path(ticket_id, customer_message, agent_notes)
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                return validate_classification(cached, ticket_id, categories, source="cache")
            except (OSError, json.JSONDecodeError, ValueError):
                # A stale/malformed cache is safely reclassified rather than trusted.
                pass

        try:
            client = self._client_or_create()
            response = client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt(categories)},
                    {"role": "user", "content": ticket_payload(customer_message, agent_notes)},
                ],
                timeout=20,
            )
            raw = response.choices[0].message.content
            parsed = json.loads(raw)
            classification = validate_classification(parsed, ticket_id, categories, source="llm")
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(classification.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            return classification
        except Exception as error:  # Dashboard must continue if network/LLM/JSON fails.
            return unavailable_result(ticket_id, f"AI unavailable: {type(error).__name__}")

    def classify_sample(self, tickets: pd.DataFrame, categories: Sequence[str], max_tickets: int) -> pd.DataFrame:
        """Classify no more than the requested representative, non-junk ticket sample."""
        eligible = tickets.loc[~tickets["is_junk_ivr"]].sort_values("ticket_id").head(max_tickets)
        return pd.DataFrame([self.classify_ticket(row, categories).as_dict() for _, row in eligible.iterrows()])


def ai_validation_summary(labels: pd.DataFrame | None) -> dict[str, Any]:
    """Calculate accuracy only from a human-labelled validation set; never invent it."""
    required = {"ticket_id", "human_issue_category", "ai_issue_category"}
    if labels is None or not required.issubset(labels.columns):
        return {"available": False, "message": "No human-labelled AI validation set has been supplied."}
    valid = labels.dropna(subset=["human_issue_category", "ai_issue_category"])
    if valid.empty:
        return {"available": False, "message": "No completed human labels are available."}
    accuracy = (valid["human_issue_category"] == valid["ai_issue_category"]).mean()
    errors = valid.loc[valid["human_issue_category"] != valid["ai_issue_category"]]
    return {
        "available": True,
        "evaluated": int(len(valid)),
        "accuracy": float(accuracy),
        "error_rate": float(1 - accuracy),
        "common_errors": errors.groupby(["human_issue_category", "ai_issue_category"]).size().sort_values(ascending=False).head(5),
    }
