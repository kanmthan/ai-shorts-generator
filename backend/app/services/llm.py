"""Anthropic Claude client for transcript analysis.

Wraps the ``anthropic`` SDK behind :class:`AnthropicClient`. The public entry
point is :meth:`AnthropicClient.analyze_transcript`, which:

1. builds a system prompt from the versioned template in ``app/prompts/`` and a
   user message from the project metadata + transcript JSON,
2. calls ``claude-sonnet-5`` (``settings.ANTHROPIC_MODEL``),
3. parses the response as JSON and validates it against
   :class:`app.schemas.export.ShortsExportEnvelope`,
4. on a JSON / schema failure, makes **one** repair call that feeds the error
   text back to the model, then gives up with :class:`ExternalServiceError`.

Only token *counts* are logged - never prompt or completion content.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.config import settings
from app.exceptions import ExternalServiceError
from app.logging_config import get_logger
from app.schemas.export import ShortsExportEnvelope

logger = get_logger("services.llm")

__all__ = ["AnthropicClient", "load_prompt", "PROMPT_VERSION"]

PROMPT_VERSION = "analysis_v1"
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_MAX_OUTPUT_TOKENS = 16_000
_MAX_TRANSCRIPT_CHARS = 600_000


@lru_cache(maxsize=8)
def load_prompt(version: str = PROMPT_VERSION) -> str:
    """Load a versioned prompt template from ``app/prompts/<version>.md``."""
    path = _PROMPTS_DIR / f"{version}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - packaging error
        raise ExternalServiceError(
            f"Analysis prompt '{version}' is missing from the deployment"
        ) from exc


class AnthropicClient:
    """Thin wrapper around the Anthropic Messages API for shorts analysis."""

    def __init__(self, *, prompt_version: str = PROMPT_VERSION) -> None:
        self.prompt_version = prompt_version
        self.model = settings.ANTHROPIC_MODEL
        self._client: Any | None = None

    # ------------------------------------------------------------------ #
    # SDK plumbing                                                       #
    # ------------------------------------------------------------------ #
    def _get_client(self) -> Any:
        """Lazily construct the SDK client, guarding on a missing API key."""
        if not settings.ANTHROPIC_API_KEY:
            raise ExternalServiceError(
                "ANTHROPIC_API_KEY is not configured; cannot run shorts analysis"
            )
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:  # pragma: no cover - dep always present
                raise ExternalServiceError(
                    "The 'anthropic' package is not installed in this environment"
                ) from exc
            self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    def _create(self, messages: list[dict[str, Any]]) -> str:
        """Call the Messages API once and return the concatenated text output."""
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=_MAX_OUTPUT_TOKENS,
                system=load_prompt(self.prompt_version),
                messages=messages,
            )
        except Exception as exc:  # SDK raises many transport/error types
            logger.error("Anthropic API call failed: %s", type(exc).__name__)
            raise ExternalServiceError(
                f"Claude analysis request failed: {type(exc).__name__}"
            ) from exc

        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "Claude usage: input_tokens=%s output_tokens=%s model=%s",
                getattr(usage, "input_tokens", "?"),
                getattr(usage, "output_tokens", "?"),
                self.model,
            )
        return _extract_text(response)

    # ------------------------------------------------------------------ #
    # Public API                                                        #
    # ------------------------------------------------------------------ #
    def analyze_transcript(
        self, project: Any, transcript: list[dict[str, Any]]
    ) -> ShortsExportEnvelope:
        """Analyse ``transcript`` for ``project`` and return a validated envelope.

        Args:
            project: SQLAlchemy ``Project`` (needs ``url``, ``title``,
                ``duration_seconds``).
            transcript: Normalised ``[{start, end, text}, ...]`` segments.

        Raises:
            ExternalServiceError: On a missing API key, transport failure, or
                output that stays invalid after one repair attempt.
        """
        user_message = _build_user_message(project, transcript)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        raw = self._create(messages)
        try:
            return _parse_and_validate(raw)
        except (json.JSONDecodeError, PydanticValidationError) as first_error:
            error_detail = _error_text(first_error)
            logger.warning(
                "Claude output invalid (%s); attempting one repair call",
                type(first_error).__name__,
            )

        repair_messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "Your previous response was not valid against the required "
                    "schema. Error:\n"
                    f"{error_detail}\n\n"
                    "Return ONLY a corrected JSON object in the exact master "
                    "structure from the system prompt. No markdown, no prose."
                ),
            },
        ]
        repaired = self._create(repair_messages)
        try:
            return _parse_and_validate(repaired)
        except (json.JSONDecodeError, PydanticValidationError) as second_error:
            logger.error(
                "Claude output still invalid after repair: %s",
                type(second_error).__name__,
            )
            raise ExternalServiceError(
                "Claude returned JSON that does not conform to the shorts export "
                "schema, even after one repair attempt"
            ) from second_error


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _extract_text(response: Any) -> str:
    """Concatenate all text blocks from a Messages API response."""
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def _build_user_message(project: Any, transcript: list[dict[str, Any]]) -> str:
    """Render the user-turn payload: metadata + transcript JSON."""
    transcript_json = json.dumps(transcript, ensure_ascii=False)
    if len(transcript_json) > _MAX_TRANSCRIPT_CHARS:
        transcript_json = transcript_json[:_MAX_TRANSCRIPT_CHARS]
    meta = {
        "url": getattr(project, "url", None),
        "title": getattr(project, "title", None),
        "duration_seconds": getattr(project, "duration_seconds", None),
        "language": getattr(project, "language", None),
    }
    return (
        "VIDEO METADATA (JSON):\n"
        f"{json.dumps(meta, ensure_ascii=False)}\n\n"
        "FULL TRANSCRIPT (JSON array of {start, end, text}):\n"
        f"{transcript_json}\n\n"
        "Analyse the whole transcript and return ONLY the master JSON object."
    )


def _strip_code_fence(text: str) -> str:
    """Remove a leading/trailing ```json ... ``` fence if the model added one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
    return stripped.strip()


def _parse_and_validate(raw: str) -> ShortsExportEnvelope:
    """Parse ``raw`` as JSON and validate it against the master schema."""
    payload = json.loads(_strip_code_fence(raw))
    return ShortsExportEnvelope.model_validate(payload)


def _error_text(error: Exception) -> str:
    """Compact, content-free description of a parse/validation failure."""
    if isinstance(error, PydanticValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in error.errors()[:20]
        )
    return str(error)
