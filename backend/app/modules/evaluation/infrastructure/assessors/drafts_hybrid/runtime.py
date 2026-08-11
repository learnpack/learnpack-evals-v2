"""Where this assessor's LLM tasks get their transport from.

The client is environment, not identity (ADR-0034): settings supply the key and the base
URL, the tasks supply the model per call. One module-level accessor so tests can swap the
whole transport for a fake by monkeypatching `get_client` — the seam is this function,
nothing else in the package touches settings or the network directly.
"""

from functools import lru_cache

from app.config import get_settings
from app.platform.llm import ChatCompletionsClient


@lru_cache
def get_client() -> ChatCompletionsClient:
    settings = get_settings()
    return ChatCompletionsClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
