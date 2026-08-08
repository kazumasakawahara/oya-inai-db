"""Dynamic LLM model switching based on user commands in chat.

Detects natural-language switch requests (Japanese) and returns
the target provider identifier so the caller can recreate the agent.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern -> provider mapping
# ---------------------------------------------------------------------------
# Each entry: (regex_pattern, provider_key, display_name)
# Patterns are tested in order; first match wins.

SWITCH_PATTERNS: list[tuple[str, str, str]] = [
    # Specific model names
    (r"gemma.*(?:使って|切り替え|に変更)", "ollama", "Ollama (gemma4:26b)"),
    (r"gemini.*(?:使って|切り替え|に変更)", "gemini", "Gemini 2.0 Flash"),
    (r"claude.*(?:使って|切り替え|に変更)", "claude", "Claude"),
    (r"openai.*(?:使って|切り替え|に変更)", "openai", "OpenAI"),
    (r"gpt.*(?:使って|切り替え|に変更)", "openai", "OpenAI (GPT)"),
    # Generic local / cloud
    (r"ローカル.*(?:モデル|LLM).*(?:使って|切り替え)", "ollama", "Ollama (ローカル)"),
    (r"クラウド.*(?:モデル|LLM).*(?:使って|切り替え)", "gemini", "Gemini (クラウド)"),
]


def detect_model_switch(text: str) -> tuple[str, str] | None:
    """Detect a model-switch command in user text.

    Returns:
        ``(provider, display_name)`` if a switch command is detected,
        ``None`` otherwise.
    """
    for pattern, provider, display_name in SWITCH_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger.info("Model switch detected: %s -> %s", text[:40], provider)
            return provider, display_name
    return None
