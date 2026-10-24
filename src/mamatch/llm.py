"""Thin wrapper around Claude for structured extraction and drafting.

Every caller has an offline fallback, so the app runs (and tests pass) with no credentials.
`structured()` returns None when Claude is off, unavailable, or declines; callers then use
their heuristic path and record which one produced the result.
"""

import json
import logging

import anthropic

from . import config

log = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None
_unavailable = False  # set after an auth or connection failure so we stop retrying in this process


def enabled() -> bool:
    return config.LLM_MODE != "off" and not _unavailable


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def structured(system: str, prompt: str, schema: dict, effort: str = "medium") -> dict | None:
    """Ask Claude for JSON matching `schema`. Returns the parsed object, or None."""
    global _unavailable
    if not enabled():
        return None
    try:
        response = _get_client().beta.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            # Server-side fallback re-runs a safety-declined request on Anthropic's recommended model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.APIConnectionError) as exc:
        if config.LLM_MODE == "on":
            raise
        log.warning("Claude unavailable, using offline mode for this process: %s", exc)
        _unavailable = True
        return None
    except anthropic.RateLimitError:
        log.warning("Claude rate-limited; using offline result for this call")
        return None
    except anthropic.APIStatusError as exc:
        if config.LLM_MODE == "on":
            raise
        log.warning("Claude API error %s; using offline result for this call", exc.status_code)
        return None

    if response.stop_reason == "refusal":
        log.warning("Claude declined the request: %s", response.stop_details)
        return None
    if response.stop_reason == "max_tokens":
        log.warning("Claude output hit max_tokens; discarding partial JSON")
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("Claude returned invalid JSON; using offline result")
        return None


def label() -> str:
    return f"claude:{config.CLAUDE_MODEL}"
