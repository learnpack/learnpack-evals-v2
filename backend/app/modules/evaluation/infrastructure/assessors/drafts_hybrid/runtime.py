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
    return ChatCompletionsClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        # Cached, so every caller in this process shares one client and therefore one gate.
        # That is the point: the ceiling on requests in flight has to be the process's, not
        # each caller's, or two callers would each observe their own limit and the endpoint
        # would see the sum.
        max_concurrency=settings.llm_max_concurrency,
    )
